
import cv2
import mediapipe as mp
import math
import pyautogui
from pycaw.pycaw import AudioUtilities

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles  

hands = mp_hands.Hands(
    static_image_mode=False,          
    max_num_hands=1,                 
    model_complexity=1,               
    min_detection_confidence=0.7,     
    min_tracking_confidence=0.7       
)

cap=cv2.VideoCapture(0)
cap.set(3,640)
cap.set(4,480)

frame_count = 0
action_every_n_frames = 6
last_action = "NONE"
endpoint_volume = AudioUtilities.GetSpeakers().EndpointVolume

while True:
    ok,frame=cap.read()
    if not ok:break
    rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
    result=hands.process(rgb)
    if result.multi_hand_landmarks:
        for hand_landmarks in result.multi_hand_landmarks:
            mp_draw.draw_landmarks(
                frame,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS
            )
            h,w,_=frame.shape
            thumb=hand_landmarks.landmark[4]
            index=hand_landmarks.landmark[8]

            x1,y1=int(thumb.x*w),int(thumb.y*h)
            x2,y2=int(index.x*w),int(index.y*h)
            distance=math.hypot(x2-x1,y2-y1)
            frame_count += 1

            if distance < 45:
                gesture="VOLUME DOWN"
                if frame_count % action_every_n_frames == 0:
                    pyautogui.press("volumedown")
                    last_action = "DOWN"
            elif distance > 80:
                gesture="VOLUME UP"
                if frame_count % action_every_n_frames == 0:
                    pyautogui.press("volumeup")
                    last_action = "UP"
            else:
                gesture="HOLD"


            cv2.circle(frame,(x1,y1),8,(0,255,0),-1)
            cv2.circle(frame,(x2,y2),8,(0,255,0),-1)
            cv2.line(frame,(x1,y1),(x2,y2),(255,0,0),2)

            bar_top = 150
            bar_bottom = 400
            bar_left = 560
            bar_right = 600
            bar_height = bar_bottom - bar_top
            volume_percent = int(endpoint_volume.GetMasterVolumeLevelScalar() * 100)
            fill_top = bar_bottom - int(bar_height * volume_percent / 100)

            cv2.rectangle(frame,(bar_left,bar_top),(bar_right,bar_bottom),(255,255,255),2)
            cv2.rectangle(frame,(bar_left,fill_top),(bar_right,bar_bottom),(0,255,0),-1)
            cv2.putText(frame,f"{volume_percent}%",(545,430),cv2.FONT_HERSHEY_SIMPLEX,0.6,(255,255,255),2)

            cv2.putText(frame,f"Distance: {int(distance)}",(20,40),cv2.FONT_HERSHEY_SIMPLEX,0.8,(0,255,255),2)
            cv2.putText(frame,f"Gesture: {gesture}",(20,80),cv2.FONT_HERSHEY_SIMPLEX,0.8,(0,255,255),2)
            cv2.putText(frame,f"Last Action: {last_action}",(20,120),cv2.FONT_HERSHEY_SIMPLEX,0.8,(0,255,255),2)
    cv2.imshow("Gesture Detection",frame)
    key=cv2.waitKey(1) & 0xFF
    if key == ord('q') or key == 27:
        break
cap.release()
cv2.destroyAllWindows()

