import cv2
import mediapipe as mp
import math
import threading
import time
import numpy as np
import pyautogui
from flask import Flask, Response, jsonify, render_template
from pycaw.pycaw import AudioUtilities

try:
    from comtypes import CoInitialize, CoUninitialize
except Exception:
    CoInitialize = None
    CoUninitialize = None

gesture_thread = None
gesture_lock = threading.Lock()
stop_event = threading.Event()
latest_frame_jpeg = None
frame_lock = threading.Lock()
status_lock = threading.Lock()
runtime_status = {
    "running": False,
    "camera": "inactive",
    "message": "Click START to begin",
    "volume_percent": 0.0,
    "volume_text": "0.00%",
    "gesture_type": "None",
    "gesture_quality": "Good"
}


def get_current_volume_percent():
    com_initialized = False
    try:
        # Flask serves requests in worker threads; COM must be initialized per thread.
        if CoInitialize is not None:
            CoInitialize()
            com_initialized = True

        endpoint_volume = AudioUtilities.GetSpeakers().EndpointVolume
        return float(endpoint_volume.GetMasterVolumeLevelScalar() * 100.0)
    except Exception:
        return None
    finally:
        if com_initialized and CoUninitialize is not None:
            try:
                CoUninitialize()
            except Exception:
                pass


def build_status_frame(title, subtitle):
    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    frame[:] = (7, 9, 13)
    cv2.putText(frame, title, (240, 270), cv2.FONT_HERSHEY_SIMPLEX, 1.45, (255, 255, 255), 3, cv2.LINE_AA)
    cv2.putText(frame, subtitle, (285, 325), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (185, 194, 207), 2, cv2.LINE_AA)
    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        return b""
    return encoded.tobytes()


def set_runtime_status(running, camera, message):
    with status_lock:
        runtime_status["running"] = running
        runtime_status["camera"] = camera
        runtime_status["message"] = message


def set_gesture_details(gesture_type, gesture_quality):
    with status_lock:
        runtime_status["gesture_type"] = gesture_type
        runtime_status["gesture_quality"] = gesture_quality


def open_camera_with_fallback():
    # Try Windows-friendly backends first, then generic fallback.
    candidates = [
        (0, cv2.CAP_DSHOW),
        (0, cv2.CAP_MSMF),
        (0, None),
        (1, cv2.CAP_DSHOW),
        (1, cv2.CAP_MSMF),
        (1, None)
    ]

    for index, backend in candidates:
        cap = cv2.VideoCapture(index, backend) if backend is not None else cv2.VideoCapture(index)
        if cap.isOpened():
            return cap
        cap.release()
    return None


def build_volume_payload(volume_percent):
    return {
        "volume_percent": round(volume_percent, 2),
        "volume_text": f"{volume_percent:.2f}%"
    }


def create_web_app():
    app = Flask(__name__)

    @app.after_request
    def add_no_cache_headers(response):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/start", methods=["POST"])
    def start_gesture_control():
        global gesture_thread

        with gesture_lock:
            if gesture_thread is not None and gesture_thread.is_alive():
                return jsonify({"status": "already_running", "message": "Gesture control is already running."}), 200

            stop_event.clear()
            with frame_lock:
                # Show immediate visual feedback while camera initializes.
                global latest_frame_jpeg
                latest_frame_jpeg = build_status_frame("Starting Camera", "Please wait...")
            set_runtime_status(True, "starting", "Initializing camera")
            gesture_thread = threading.Thread(target=run_gesture_control, daemon=True)
            gesture_thread.start()

        return jsonify({"status": "started", "message": "Gesture control started."}), 200

    @app.route("/pause", methods=["POST"])
    def pause_gesture_control():
        global gesture_thread

        with gesture_lock:
            if gesture_thread is None or not gesture_thread.is_alive():
                stop_event.set()
                set_runtime_status(False, "inactive", "Click START to begin")
                return jsonify({"status": "not_running", "message": "Gesture control is not running."}), 200

            stop_event.set()

        gesture_thread.join(timeout=2.0)
        with gesture_lock:
            gesture_thread = None
        set_runtime_status(False, "inactive", "Click START to begin")

        return jsonify({"status": "paused", "message": "Gesture control stopped."}), 200

    @app.route("/status")
    def get_status():
        with status_lock:
            status_payload = dict(runtime_status)

        volume_percent = get_current_volume_percent()
        if volume_percent is not None:
            status_payload.update(build_volume_payload(volume_percent))

        return jsonify(status_payload), 200

    @app.route("/volume")
    def get_volume():
        volume_percent = get_current_volume_percent()
        if volume_percent is None:
            with status_lock:
                fallback_percent = float(runtime_status.get("volume_percent", 0.0))
            return jsonify(build_volume_payload(fallback_percent)), 200

        return jsonify(build_volume_payload(volume_percent)), 200

    @app.route("/video_feed")
    def video_feed():
        def generate_frames():
            while True:
                with frame_lock:
                    frame_bytes = latest_frame_jpeg

                if frame_bytes is None:
                    if gesture_thread is not None and gesture_thread.is_alive():
                        frame_bytes = build_status_frame("Starting Camera", "Please wait...")
                    else:
                        frame_bytes = build_status_frame("Camera Inactive", "Click START to begin")

                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
                time.sleep(0.03)

        return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

    return app


def run_frontend_server():
    app = create_web_app()
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)


def run_gesture_control():
    global latest_frame_jpeg

    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        model_complexity=0,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7
    )

    cap = open_camera_with_fallback()
    if cap is None:
        with frame_lock:
            latest_frame_jpeg = build_status_frame("Camera Not Found", "Check webcam access")
        set_runtime_status(False, "error", "Camera not found")
        set_gesture_details("No Camera", "Unavailable")
        hands.close()
        return

    cap.set(3, 640)
    cap.set(4, 480)

    frame_count = 0
    action_every_n_frames = 6
    set_runtime_status(True, "active", "Running")
    set_gesture_details("No Hand", "Searching")

    endpoint_volume = None
    try:
        endpoint_volume = AudioUtilities.GetSpeakers().EndpointVolume
    except Exception:
        endpoint_volume = None

    try:
        while not stop_event.is_set():
            ok, frame = cap.read()
            if not ok:
                set_runtime_status(False, "error", "Unable to read camera frame")
                set_gesture_details("Camera Error", "Unavailable")
                with frame_lock:
                    latest_frame_jpeg = build_status_frame("Camera Read Failed", "Check webcam usage in other apps")
                break

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = hands.process(rgb)
            if result.multi_hand_landmarks:
                for hand_landmarks in result.multi_hand_landmarks:
                    mp_draw.draw_landmarks(
                        frame,
                        hand_landmarks,
                        mp_hands.HAND_CONNECTIONS
                    )
                    h, w, _ = frame.shape
                    thumb = hand_landmarks.landmark[4]
                    index = hand_landmarks.landmark[8]

                    x1, y1 = int(thumb.x * w), int(thumb.y * h)
                    x2, y2 = int(index.x * w), int(index.y * h)
                    distance = math.hypot(x2 - x1, y2 - y1)
                    frame_count += 1

                    if distance < 45:
                        gesture = "VOLUME DOWN"
                        quality = "Excellent" if distance > 25 else "Good"
                        if frame_count % action_every_n_frames == 0:
                            pyautogui.press("volumedown")
                    elif distance > 80:
                        gesture = "VOLUME UP"
                        quality = "Excellent" if distance < 130 else "Good"
                        if frame_count % action_every_n_frames == 0:
                            pyautogui.press("volumeup")
                    else:
                        gesture = "HOLD"
                        quality = "Excellent"

                    set_gesture_details(gesture, quality)

                    cv2.circle(frame, (x1, y1), 8, (0, 255, 0), -1)
                    cv2.circle(frame, (x2, y2), 8, (0, 255, 0), -1)
                    cv2.line(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)

                    bar_top = 150
                    bar_bottom = 400
                    bar_left = 560
                    bar_right = 600
                    bar_height = bar_bottom - bar_top
                    if endpoint_volume is not None:
                        volume_percent = int(endpoint_volume.GetMasterVolumeLevelScalar() * 100)
                    else:
                        volume_percent = 0
                    fill_top = bar_bottom - int(bar_height * volume_percent / 100)

                    cv2.rectangle(frame, (bar_left, bar_top), (bar_right, bar_bottom), (255, 255, 255), 2)
                    cv2.rectangle(frame, (bar_left, fill_top), (bar_right, bar_bottom), (0, 255, 0), -1)
                    cv2.putText(frame, f"{volume_percent}%", (545, 430), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                    cv2.putText(frame, f"Distance: {int(distance)}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

            else:
                set_gesture_details("No Hand", "Searching")

            ok, encoded = cv2.imencode(".jpg", frame)
            if ok:
                with frame_lock:
                    latest_frame_jpeg = encoded.tobytes()
    except Exception:
        with frame_lock:
            latest_frame_jpeg = build_status_frame("Runtime Error", "Restart and check terminal logs")
        set_runtime_status(False, "error", "Runtime error while processing video")
        set_gesture_details("Runtime Error", "Unavailable")

    cap.release()
    hands.close()
    if stop_event.is_set():
        with frame_lock:
            latest_frame_jpeg = build_status_frame("Camera Inactive", "Click START to begin")
        set_runtime_status(False, "inactive", "Click START to begin")
        set_gesture_details("None", "Good")


if __name__ == "__main__":
    run_frontend_server()

