# Requirements

Install the dependencies using `pip`:

```bash
pip install -r requirements.txt
```

### Core Packages
- `PyQt6` (>=6.4.0): Modern GUI framework with glassmorphism styling and multi-threaded event loop.
- `opencv-python` (>=4.8.0): High-speed webcam capture, real-time video manipulation, and computer vision utilities.
- `ultralytics` (>=8.0.0): YOLOv8 nano model for high-efficiency, real-time object detection (laptops, keyboards, books, people).
- `numpy` (>=1.24.0): Fast array operations and image buffer conversion.
- `pyttsx3` (>=2.90): Cross-platform, thread-safe text-to-speech engine for audio shaming.
- `pygetwindow` (>=0.0.9): Active desktop window detection (Windows). On Linux, built-in X11/`xprop` is used automatically.

### Optional Packages
- `mediapipe` (<=0.10.14): Optional facial landmark detection (automatically falls back to OpenCV's built-in Haar Cascade if not installed).
