# Gesture Volume Control with Hand Gestures

A real-time hand-tracking web app that controls Windows system volume using finger distance gestures.

## Features

- Live webcam feed in browser
- Start and stop gesture control from UI
- Real-time device volume display in UI
- Dynamic Gesture Type and Gesture Quality status
- Gesture guide with thresholds
- Windows-friendly camera fallback handling

## Tech Stack

- Python
- Flask
- OpenCV
- MediaPipe Hands
- PyAutoGUI
- PyCAW + comtypes

## Project Structure

- app.py: Backend server, webcam processing, gesture logic
- templates/index.html: Frontend UI
- static/style.css: UI styling
- requirements.txt: Python dependencies
- Dockerfile: Container setup

## Requirements

- Windows OS (for PyCAW system volume control)
- Python 3.9+
- Webcam access enabled

## Setup

1. Create and activate a virtual environment.

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies.

```powershell
pip install -r requirements.txt
```

3. Run the app.

```powershell
python app.py
```

4. Open the UI.

- http://127.0.0.1:5000

## Gesture Logic

- Volume Down: distance < 45
- Hold: 45 to 80
- Volume Up: distance > 80

Action is intentionally rate-limited to reduce accidental rapid volume jumps.

## API Endpoints

- GET /: Main dashboard
- POST /start: Start gesture control
- POST /pause: Stop gesture control
- GET /status: Runtime status (camera, running state, gesture type/quality, volume)
- GET /volume: Current system volume
- GET /video_feed: MJPEG webcam stream

## Troubleshooting

- Volume stays at 0.00%
  - Confirm app is running from a fresh terminal session.
  - Ensure Windows audio endpoint is available.
- Camera not opening
  - Close other apps using the webcam.
  - Check camera privacy permissions in Windows settings.
- UI shows old data
  - Hard refresh browser with Ctrl+F5.

## Notes

- This app is intended for local use on Windows desktops/laptops.
- PyCAW-based volume control is Windows-specific.
