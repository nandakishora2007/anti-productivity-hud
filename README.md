# ANTI_PRODUCTIVE HUD 🎯

## Basic Details

### Team Name: NK

### Team Members

* Team Lead: Nandakishor A - SCTCE (2025–29 Batch)

### Project Description

DON'T ALLOW ANYONE TO WORK. A context-aware desktop application designed to sabotage overworking by monitoring physical activity and active software windows, automatically triggering audio shaming and a distraction roulette when you work too hard.

### The Problem (that doesn't exist)

People have a craving to work (if not all, some), leading to unhealthy overworking habits.

### The Solution (that nobody asked for)

Lure people away from this working problem by tracking productivity via computer vision and forcibly deploying interesting distractions (YouTube rabbit holes and The Zen Zone) combined with text-to-speech audio shaming.

## Technical Details

### Technologies/Components Used

For Software:

* Python
* PyQt6 (Light theme glassmorphism HUD interface)
* OpenCV (Webcam capture and frame rendering)
* Ultralytics YOLOv8 & MediaPipe (Object and face detection)
* PyGetWindow (Active window and browser tab monitoring)
* Pyttsx3 (Text-to-speech audio shaming engine)
* Webbrowser & Threading (Asynchronous distraction roulette triggers)

For Hardware:

* Laptop / PC
* Webcam

### Implementation

The core logic and interface are contained within `vision_hud.py`.

### Installation & Run

```powershell
python -m vvenv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.md
python vision_hud.py

```

## Project Documentation

*(Add screenshots, workflow diagrams, and demo video links here)*

---

Made with ❤️ at TinkerHub Useless Projects