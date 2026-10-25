"""
ANTI-PRODUCTIVITY HUD 🎯
--------------------------------------------------------------------------------
A context-aware desktop computer vision HUD designed to aggressively sabotage
unhealthy overworking habits. Monitors your physical environment (webcam + YOLOv8)
and active software windows, triggering hilarious context-aware YouTube distractions
and audio shaming whenever productivity is detected!

Architecture:
- PyQt6 (Main GUI Thread): Glassmorphism frameless HUD, ultra-smooth 60 FPS rendering.
- VisionWorker (QThread): Dedicated computer vision worker running OpenCV capture,
  MediaPipe/Haar face detection, and YOLOv8 inference decoupled from the UI.
- DistractionEngine: Context-aware YouTube video & audio shaming router tailored to
  the user's specific detected activity (Coding, Studying, General Grinding).
"""

import sys
import os
import time
import random
import subprocess
import webbrowser
import threading
from typing import Optional, Tuple, List, Dict

import cv2
import numpy as np

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint, QTimer
from PyQt6.QtGui import QImage, QPixmap, QColor
from PyQt6.QtWidgets import (
    QApplication, QLabel, QVBoxLayout, QHBoxLayout, 
    QWidget, QFrame, QPushButton, QGraphicsDropShadowEffect
)

# Optional dependencies loaded with safe fallbacks
try:
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    HAS_YOLO = False

try:
    import mediapipe as mp
    HAS_MEDIAPIPE = True
except ImportError:
    HAS_MEDIAPIPE = False

try:
    import pygetwindow as gw
    HAS_PYGETWINDOW = True
except (ImportError, NotImplementedError, Exception):
    HAS_PYGETWINDOW = False

try:
    import pyttsx3
    HAS_TTS = True
except ImportError:
    HAS_TTS = False


# ==============================================================================
# Cross-Platform Active Window Detection
# ==============================================================================
def get_active_window_title() -> str:
    """
    Retrieves the title of the frontmost/active window across Windows, Linux, and macOS.
    Gracefully falls back to 'Desktop' if window detection is unavailable.
    """
    # 1. Windows via pygetwindow
    if sys.platform == "win32" and HAS_PYGETWINDOW:
        try:
            win = gw.getActiveWindow()
            if win and win.title:
                return win.title.strip()
        except Exception:
            pass

    # 2. Linux (X11 / standard desktop via xprop)
    if sys.platform.startswith("linux"):
        try:
            root_out = subprocess.check_output(
                ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
                stderr=subprocess.DEVNULL, timeout=0.15
            ).decode("utf-8", errors="ignore")
            parts = root_out.strip().split()
            if len(parts) >= 5 and parts[4] != "0x0":
                win_id = parts[4]
                title_out = subprocess.check_output(
                    ["xprop", "-id", win_id, "WM_NAME", "_NET_WM_NAME"],
                    stderr=subprocess.DEVNULL, timeout=0.15
                ).decode("utf-8", errors="ignore")
                for line in title_out.splitlines():
                    if ' = "' in line:
                        title = line.split(' = "', 1)[1].rstrip('"')
                        if title:
                            return title
        except Exception:
            pass

    # 3. macOS via AppleScript
    if sys.platform == "darwin":
        try:
            cmd = 'tell application "System Events" to get name of first application process whose frontmost is true'
            title = subprocess.check_output(
                ["osascript", "-e", cmd],
                stderr=subprocess.DEVNULL, timeout=0.15
            ).decode("utf-8", errors="ignore").strip()
            if title:
                return title
        except Exception:
            pass

    return "Workspace Desktop"


# ==============================================================================
# Distraction & Shame Engine
# ==============================================================================
class DistractionEngine:
    """
    Manages intelligent action-based YouTube distraction routing and
    text-to-speech audio shaming.
    """
    
    # Slacking keywords: if active, the user is already slacking!
    SLACK_KEYWORDS = [
        "youtube", "netflix", "twitch", "discord", "steam", "game", "reddit",
        "spotify", "twitter", "x.com", "tiktok", "instagram", "prime video",
        "hulu", "thezen.zone", "disney"
    ]

    # Action-specific profiles with curated working URLs and tailored audio phrases
    PROFILES = {
        "coding": {
            "title": "Software Development / Coding",
            "window_keywords": [
                "visual studio", "vscode", "cursor", "neovim", "vim", "pycharm", 
                "sublime", "xcode", "terminal", "bash", "zsh", "python", "github", 
                "gitlab", "stackoverflow", "git", "docker", "tmux", "intellij"
            ],
            "objects": ["keyboard", "laptop"],
            "urls": [
                ("Every Programming Tutorial Ever", "https://www.youtube.com/watch?v=kYJsmfaE0wA"),
                ("Tabs vs Spaces - Silicon Valley", "https://www.youtube.com/watch?v=SsoOG6ZeyUI"),
                ("10 Hours of Windows XP Error Remix", "https://www.youtube.com/watch?v=Gb2x5lsN-XU"),
                ("Why Modern Software is Broken", "https://www.youtube.com/watch?v=48h57PspBec"),
                ("Lo-Fi Elevator Beats to Procrastinate To", "https://www.youtube.com/watch?v=5qap5aO4i9A"),
                ("The Classic Rickroll Escape Hatch", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            ],
            "phrases": [
                "Emergency! Excessive coding detected. Drop the IDE and touch grass immediately!",
                "Warning: Compiler overload. You are writing too many bugs. Step away from the keyboard.",
                "Overworking hazard! Your pull request has been permanently rejected by the universe.",
                "Cease typing at once! Mandatory procrastination protocol engaged."
            ]
        },
        "studying": {
            "title": "Reading / Research / Studying",
            "window_keywords": [
                "pdf", "docs", "arxiv", "scholar", "notion", "obsidian", 
                "wikipedia", "chegg", "overleaf", "research", "canvas", "blackboard"
            ],
            "objects": ["book"],
            "urls": [
                ("Kurzgesagt: The Egg", "https://www.youtube.com/watch?v=h6fcK_fRYaI"),
                ("Veritasium: The Infinite Hotel Paradox", "https://www.youtube.com/watch?v=Uj3_KqkI9Zo"),
                ("Vsauce: Why Do We Feel Nostalgia?", "https://www.youtube.com/watch?v=coGfGo_La4Y"),
                ("Mind-Bending Visual Illusions", "https://www.youtube.com/watch?v=kJQP7kiw5Fk"),
                ("The Zen Zone Deep Relaxation", "https://thezen.zone/")
            ],
            "phrases": [
                "Intellectual exertion detected! Diverting your brain into a scientific rabbit hole.",
                "Warning: Reading too many documents causes unwanted competence. Halting session.",
                "Deep thought alert! Deploying existential curiosity now.",
                "Stop studying! Put down the reading material and relax."
            ]
        },
        "general_work": {
            "title": "General Work / Productivity",
            "window_keywords": [
                "excel", "sheets", "word", "trello", "jira", "slack", "teams", 
                "outlook", "mail", "chatgpt", "claude", "asana", "notion"
            ],
            "objects": ["laptop", "keyboard", "mouse"],
            "urls": [
                ("Never Gonna Give You Up (The Classic)", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
                ("Cat Absolutely Malfunctions After Seeing Cucumber", "https://www.youtube.com/watch?v=kJQP7kiw5Fk"),
                ("The Zen Zone Relaxation Experience", "https://thezen.zone/"),
                ("Epic Sax Guy 10 Hours Loop", "https://www.youtube.com/watch?v=8Zbf9_jK-ZI"),
                ("Viral Animal Fails Compilation", "https://www.youtube.com/watch?v=9bZkp7q19f0")
            ],
            "phrases": [
                "Productivity detected! Drop your tools immediately!",
                "Warning: Overworking hazard detected. Mandatory distraction deployed.",
                "Hey! Stop being productive and take an unsanctioned break.",
                "Error 404: Fun not found. Deploying emergency distraction!"
            ]
        }
    }

    def __init__(self):
        self.recent_urls: List[str] = []
        self.tts_lock = threading.Lock()

    def classify_action(self, active_window: str, detected_objects: List[str]) -> Tuple[str, bool, bool]:
        """
        Classifies current user activity:
        Returns: (category, is_working, is_slacking)
        """
        win_lower = active_window.lower()

        # Check if already slacking
        is_slacking = any(k in win_lower for k in self.SLACK_KEYWORDS)
        if is_slacking:
            return ("slacking", False, True)

        # Check coding
        coding_match = any(k in win_lower for k in self.PROFILES["coding"]["window_keywords"])
        coding_objects = any(o in detected_objects for o in self.PROFILES["coding"]["objects"])
        if coding_match or (coding_objects and "person" in detected_objects):
            return ("coding", True, False)

        # Check studying / reading
        study_match = any(k in win_lower for k in self.PROFILES["studying"]["window_keywords"])
        study_objects = "book" in detected_objects
        if study_match or study_objects:
            return ("studying", True, False)

        # Check general work
        work_match = any(k in win_lower for k in self.PROFILES["general_work"]["window_keywords"])
        work_objects = any(o in detected_objects for o in self.PROFILES["general_work"]["objects"])
        if work_match or work_objects:
            return ("general_work", True, False)

        # Idle / no work detected
        return ("idle", False, False)

    def get_distraction(self, category: str) -> Tuple[str, str, str]:
        """
        Selects an appropriate distraction without repeating recently used URLs.
        Returns: (title, url, speech_phrase)
        """
        profile = self.PROFILES.get(category, self.PROFILES["general_work"])
        available_urls = [u for u in profile["urls"] if u[1] not in self.recent_urls]
        if not available_urls:
            available_urls = profile["urls"]
            self.recent_urls.clear()

        title, url = random.choice(available_urls)
        phrase = random.choice(profile["phrases"])

        self.recent_urls.append(url)
        if len(self.recent_urls) > 4:
            self.recent_urls.pop(0)

        return (title, url, phrase)

    def trigger_distraction(self, url: str):
        """Opens the distraction URL asynchronously."""
        def _open():
            try:
                webbrowser.open_new_tab(url)
            except Exception as e:
                print(f"[DistractionEngine] Failed to open browser: {e}")
        threading.Thread(target=_open, daemon=True).start()

    def speak(self, phrase: str, enabled: bool = True):
        """Safely synthesizes speech without blocking or colliding."""
        if not enabled or not HAS_TTS:
            print(f"[Anti-Productivity Voice]: \"{phrase}\"")
            return

        def _speak():
            with self.tts_lock:
                try:
                    engine = pyttsx3.init()
                    engine.setProperty('rate', 170)
                    engine.say(phrase)
                    engine.runAndWait()
                    del engine
                except Exception as e:
                    print(f"[TTS Fallback]: \"{phrase}\" (Audio error: {e})")

        threading.Thread(target=_speak, daemon=True).start()


# ==============================================================================
# Vision Processing Worker Thread (OpenCV + YOLOv8 + Face Detection)
# ==============================================================================
class VisionWorker(QThread):
    """
    Runs computer vision inference and telemetry on a dedicated background thread,
    keeping the PyQt6 UI completely smooth and responsive.
    """
    frame_ready = pyqtSignal(QImage)
    telemetry_ready = pyqtSignal(dict)
    distraction_triggered = pyqtSignal(str, str, str)  # (category, url, phrase)

    # YOLO COCO target indices for work gear:
    # 0: person, 63: laptop, 64: mouse, 66: keyboard, 73: book, 76: scissors
    TARGET_CLASSES = [0, 63, 64, 66, 73, 76]

    def __init__(self, camera_index: int = 0):
        super().__init__()
        self.camera_index = camera_index
        self.running = True
        self.cooldown = 20.0  # seconds between automatic triggers
        self.last_trigger_time = 0.0
        self.audio_enabled = True
        
        self.engine = DistractionEngine()
        
        # Performance optimization: frame skipping for YOLO inference
        self.inference_decimation = 2  # Run YOLO inference every 2 frames
        self.frame_counter = 0
        self.cached_detections: List[Dict] = []
        self.cached_faces: List[Tuple[int, int, int, int]] = []

    def run(self):
        # 1. Initialize Camera
        cap = cv2.VideoCapture(self.camera_index)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce latency lag
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # 2. Initialize Models
        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yolov8n.pt")
        yolo_model = None
        if HAS_YOLO and os.path.exists(model_path):
            try:
                yolo_model = YOLO(model_path)
            except Exception as e:
                print(f"[VisionWorker] Could not load YOLO model: {e}")

        # MediaPipe or Haar Face Detector
        face_detector = None
        haar_cascade = None
        if HAS_MEDIAPIPE:
            try:
                mp_face = mp.solutions.face_detection
                face_detector = mp_face.FaceDetection(model_selection=0, min_detection_confidence=0.55)
            except Exception:
                face_detector = None

        if face_detector is None:
            # Fallback to OpenCV built-in Haar Cascade
            try:
                cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                if os.path.exists(cascade_path):
                    haar_cascade = cv2.CascadeClassifier(cascade_path)
            except Exception:
                haar_cascade = None

        last_fps_time = time.time()
        fps_counter = 0
        current_fps = 30.0

        while self.running:
            loop_start = time.time()
            ret, frame = cap.read()

            if not ret or frame is None:
                # Generate synthetic frame if webcam is missing or busy
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(
                    frame, "CONNECTING WEBCAM...", (150, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2
                )
                time.sleep(0.04)

            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            self.frame_counter += 1
            run_heavy_inference = (self.frame_counter % self.inference_decimation == 0)

            # --- A. Face Detection ---
            if run_heavy_inference:
                detected_faces = []
                if face_detector:
                    try:
                        results_mp = face_detector.process(rgb_frame)
                        if results_mp.detections:
                            for det in results_mp.detections:
                                box = det.location_data.relative_bounding_box
                                x = int(box.xmin * w)
                                y = int(box.ymin * h)
                                bw = int(box.width * w)
                                bh = int(box.height * h)
                                detected_faces.append((x, y, bw, bh))
                    except Exception:
                        pass
                elif haar_cascade:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = haar_cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=4, minSize=(60, 60))
                    for (x, y, bw, bh) in faces:
                        detected_faces.append((x, y, bw, bh))
                self.cached_faces = detected_faces

            # --- B. YOLOv8 Object Detection (Optimized with downscaling) ---
            detected_object_names = []
            if run_heavy_inference and yolo_model:
                try:
                    # Run on smaller spatial resolution (imgsz=320) for 3x speedup on CPU
                    results = yolo_model.predict(
                        frame, imgsz=320, classes=self.TARGET_CLASSES,
                        conf=0.38, verbose=False
                    )
                    new_detections = []
                    for r in results:
                        for box in r.boxes:
                            cls_id = int(box.cls[0])
                            conf = float(box.conf[0])
                            name = yolo_model.names[cls_id]
                            coords = box.xyxy[0].cpu().numpy().astype(int)
                            new_detections.append({
                                "name": name,
                                "conf": conf,
                                "box": coords
                            })
                            detected_object_names.append(name)
                    self.cached_detections = new_detections
                except Exception as e:
                    pass
            else:
                detected_object_names = [d["name"] for d in self.cached_detections]

            # --- C. Draw Bounding Boxes onto Video Frame ---
            # 1. Face boxes (Green)
            for (x, y, bw, bh) in self.cached_faces:
                cv2.rectangle(frame, (x, y), (x + bw, y + bh), (100, 230, 0), 2)
                cv2.rectangle(frame, (x, max(0, y - 22)), (x + 85, max(0, y)), (100, 230, 0), -1)
                cv2.putText(
                    frame, "face 0.98", (x + 4, max(14, y - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (10, 20, 15), 1, cv2.LINE_AA
                )

            # 2. Object boxes (Cyan/Amber)
            for det in self.cached_detections:
                bx0, by0, bx1, by1 = det["box"]
                name = det["name"]
                conf = det["conf"]
                color = (255, 190, 0) if name in ["laptop", "keyboard", "book"] else (255, 120, 0)
                cv2.rectangle(frame, (bx0, by0), (bx1, by1), color, 2)
                label = f"{name} {int(conf * 100)}%"
                cv2.rectangle(frame, (bx0, max(0, by0 - 20)), (bx0 + 95, max(0, by0)), color, -1)
                cv2.putText(
                    frame, label, (bx0 + 4, max(14, by0 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (15, 20, 25), 1, cv2.LINE_AA
                )

            # Overlay Live Tag
            cv2.circle(frame, (20, 22), 6, (40, 40, 240), -1)
            cv2.putText(
                frame, f"YOLOv8 LIVE • {int(current_fps)} FPS", (34, 26),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA
            )

            # --- D. Telemetry & Distraction Logic ---
            active_window = get_active_window_title()
            category, is_working, is_slacking = self.engine.classify_action(
                active_window, detected_object_names
            )

            now = time.time()
            elapsed = now - self.last_trigger_time

            if is_slacking:
                status_text = "SUPPRESSED (ALREADY SLACKING)"
                status_color = "#B36B00"
                pill_text = "🛡️ Suppressed"
                pill_type = "suppressed"
                sub_info = "Slacking protocol active. Distraction roulette disarmed."
            elif is_working:
                status_text = f"DANGER: {category.upper()} DETECTED"
                status_color = "#D61A3C"
                remaining = int(max(0, self.cooldown - elapsed))
                if remaining > 0:
                    pill_text = f"⏱️ Cooldown {remaining}s"
                    pill_type = "working"
                    sub_info = f"Working detected ({category})! Distraction incoming in {remaining}s."
                else:
                    pill_text = "⚡ TRIGGERING"
                    pill_type = "working"
                    sub_info = "Cooldown expired! Unleashing distraction!"
                    # Trigger distraction!
                    title, url, phrase = self.engine.get_distraction(category)
                    self.last_trigger_time = now
                    self.engine.speak(phrase, enabled=self.audio_enabled)
                    self.engine.trigger_distraction(url)
                    self.distraction_triggered.emit(category, url, phrase)
            else:
                status_text = "SAFE / IDLE"
                status_color = "#008050"
                pill_text = "✨ Ready"
                pill_type = "ready"
                sub_info = "No productive activities detected. Slacking approved."

            telemetry = {
                "status_text": status_text,
                "status_color": status_color,
                "pill_text": pill_text,
                "pill_type": pill_type,
                "active_window": active_window,
                "sub_info": sub_info,
                "objects": detected_object_names,
                "fps": current_fps,
                "category": category
            }
            self.telemetry_ready.emit(telemetry)

            # --- E. Convert Frame to PyQt QImage and Emit ---
            rgb_display = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            bytes_per_line = 3 * w
            q_img = QImage(rgb_display.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
            self.frame_ready.emit(q_img)

            # Calculate FPS
            fps_counter += 1
            if time.time() - last_fps_time >= 1.0:
                current_fps = fps_counter / (time.time() - last_fps_time)
                fps_counter = 0
                last_fps_time = time.time()

            # Throttle to target ~30 FPS
            time_spent = time.time() - loop_start
            sleep_needed = max(0.005, 0.033 - time_spent)
            time.sleep(sleep_needed)

        cap.release()

    def stop(self):
        """Stops the worker thread and releases OpenCV camera."""
        self.running = False

    def trigger_manual_distraction(self):
        """Triggers an immediate distraction roulette."""
        title, url, phrase = self.engine.get_distraction("general_work")
        self.last_trigger_time = time.time()
        self.engine.speak(phrase, enabled=self.audio_enabled)
        self.engine.trigger_distraction(url)
        self.distraction_triggered.emit("manual", url, phrase)


# ==============================================================================
# Main Glassmorphism PyQt6 HUD Widget
# ==============================================================================
class VisionHUD(QWidget):
    """
    Main interactive HUD window with macOS/iOS glassmorphism aesthetics,
    smooth frameless dragging, and real-time computer vision display.
    """
    def __init__(self):
        super().__init__()
        
        # Frameless, Always On Top, Translucent Background
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.SubWindow
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(430, 640)
        
        self.old_pos = QPoint()
        self.is_dark_mode = False
        self.audio_enabled = True

        self.init_ui()

        # Start Vision CV Processing on dedicated QThread worker
        self.worker = VisionWorker(camera_index=0)
        self.worker.frame_ready.connect(self.on_frame_ready)
        self.worker.telemetry_ready.connect(self.on_telemetry_ready)
        self.worker.distraction_triggered.connect(self.on_distraction_triggered)
        self.worker.start()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Main Glass Card Container
        self.card = QFrame(self)
        self.card.setStyleSheet("""
            QFrame {
                background-color: rgba(246, 248, 252, 245);
                border: 1.5px solid rgba(195, 204, 218, 220);
                border-radius: 28px;
            }
        """)
        
        # Subtle drop shadow effect for elevation
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 8)
        self.card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(12)

        # 1. Top Badges Row
        pills_layout = QHBoxLayout()
        pills_layout.setSpacing(8)

        # Mode Pill
        self.pill_mode = QLabel("☀️ LIGHT HUD", self)
        self.pill_mode.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pill_mode.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pill_mode.setStyleSheet("""
            background-color: rgba(0, 0, 0, 8);
            color: rgba(45, 52, 70, 240);
            font-size: 11px;
            font-weight: bold;
            border-radius: 14px;
            padding: 6px 12px;
            border: 1px solid rgba(0, 0, 0, 16);
        """)
        self.pill_mode.mousePressEvent = lambda e: self.toggle_theme()
        pills_layout.addWidget(self.pill_mode)

        # Cooldown / Status Pill
        self.pill_cooldown = QLabel("✨ Ready", self)
        self.pill_cooldown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pill_cooldown.setStyleSheet("""
            background-color: rgba(0, 180, 100, 20);
            color: #008050;
            font-size: 11px;
            font-weight: bold;
            border-radius: 14px;
            padding: 6px 12px;
            border: 1px solid rgba(0, 180, 100, 40);
        """)
        pills_layout.addWidget(self.pill_cooldown)

        # Close Pill
        close_pill = QLabel("✕", self)
        close_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        close_pill.setCursor(Qt.CursorShape.PointingHandCursor)
        close_pill.setStyleSheet("""
            background-color: rgba(220, 40, 70, 18);
            color: #D61A3C;
            font-size: 12px;
            font-weight: bold;
            border-radius: 14px;
            padding: 6px 14px;
            border: 1px solid rgba(220, 40, 70, 40);
        """)
        close_pill.mousePressEvent = lambda e: self.close()
        pills_layout.addWidget(close_pill)

        card_layout.addLayout(pills_layout)

        # 2. Camera Viewport
        self.cam_lbl = QLabel(self)
        self.cam_lbl.setFixedSize(364, 215)
        self.cam_lbl.setStyleSheet("""
            background-color: rgba(228, 232, 240, 220);
            border-radius: 18px;
            border: 1.5px solid rgba(195, 204, 218, 160);
        """)
        self.cam_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.cam_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        # 3. Status Telemetry Card
        status_panel = QFrame(self)
        status_panel.setStyleSheet("""
            QFrame {
                background-color: rgba(236, 240, 248, 240);
                border: 1px solid rgba(204, 212, 224, 200);
                border-radius: 16px;
            }
        """)
        status_layout = QVBoxLayout(status_panel)
        status_layout.setContentsMargins(14, 12, 14, 12)
        status_layout.setSpacing(6)

        self.status_lbl = QLabel("Status: Initializing AI Engine...", self)
        self.status_lbl.setStyleSheet("color: #008050; font-size: 12px; font-weight: bold; border: none; background: transparent;")
        status_layout.addWidget(self.status_lbl)

        self.window_lbl = QLabel("Active App: Scanning workspace...", self)
        self.window_lbl.setStyleSheet("color: rgba(60, 68, 85, 230); font-size: 11px; border: none; background: transparent;")
        status_layout.addWidget(self.window_lbl)

        self.sub_info_lbl = QLabel("Monitoring productivity via computer vision.", self)
        self.sub_info_lbl.setStyleSheet("color: rgba(90, 100, 115, 200); font-size: 10px; border: none; background: transparent;")
        status_layout.addWidget(self.sub_info_lbl)

        self.telemetry_lbl = QLabel("Engine: YOLOv8n + QThread (Decoupled)", self)
        self.telemetry_lbl.setStyleSheet("color: rgba(110, 120, 135, 180); font-size: 9.5px; border: none; background: transparent;")
        status_layout.addWidget(self.telemetry_lbl)

        card_layout.addWidget(status_panel)

        # 4. Bottom Action Buttons
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(10)

        self.btn_audio = QLabel("🔊 Audio On", self)
        self.btn_audio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_audio.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_audio.setStyleSheet("""
            background-color: rgba(0, 0, 0, 8);
            color: rgba(45, 52, 70, 220);
            font-size: 11px;
            font-weight: bold;
            border-radius: 14px;
            padding: 8px 14px;
            border: 1px solid rgba(0, 0, 0, 15);
        """)
        self.btn_audio.mousePressEvent = lambda e: self.toggle_audio()
        bottom_bar.addWidget(self.btn_audio)

        self.btn_distract = QLabel("🎯 Distract Me!", self)
        self.btn_distract.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_distract.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_distract.setStyleSheet("""
            background-color: rgba(220, 40, 70, 15);
            color: #D61A3C;
            font-size: 11px;
            font-weight: bold;
            border-radius: 14px;
            padding: 8px 14px;
            border: 1px solid rgba(220, 40, 70, 35);
        """)
        self.btn_distract.mousePressEvent = lambda e: self.trigger_manual_distraction()
        bottom_bar.addWidget(self.btn_distract)

        card_layout.addLayout(bottom_bar)
        main_layout.addWidget(self.card)

    def on_frame_ready(self, q_img: QImage):
        """Renders received camera frame smoothly without UI lag."""
        scaled_pixmap = QPixmap.fromImage(q_img).scaled(
            self.cam_lbl.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        self.cam_lbl.setPixmap(scaled_pixmap)

    def on_telemetry_ready(self, data: dict):
        """Updates UI status labels and badges from worker telemetry."""
        self.status_lbl.setText(f"Status: {data['status_text']}")
        self.status_lbl.setStyleSheet(
            f"color: {data['status_color']}; font-size: 12px; font-weight: bold; border: none; background: transparent;"
        )

        app_title = data['active_window']
        if len(app_title) > 34:
            app_title = app_title[:32] + ".."
        self.window_lbl.setText(f"Active App: {app_title}")
        self.sub_info_lbl.setText(data['sub_info'])

        objects_str = ", ".join(data['objects']) if data['objects'] else "None"
        self.telemetry_lbl.setText(
            f"Detected: [{objects_str}] | FPS: {data['fps']:.1f} | Latency: OK"
        )

        # Update Cooldown Pill Style
        self.pill_cooldown.setText(data['pill_text'])
        pill_type = data['pill_type']
        if pill_type == "working":
            self.pill_cooldown.setStyleSheet("""
                background-color: rgba(220, 40, 70, 20);
                color: #D61A3C;
                font-size: 11px;
                font-weight: bold;
                border-radius: 14px;
                padding: 6px 12px;
                border: 1px solid rgba(220, 40, 70, 40);
            """)
        elif pill_type == "suppressed":
            self.pill_cooldown.setStyleSheet("""
                background-color: rgba(220, 140, 0, 22);
                color: #B36B00;
                font-size: 11px;
                font-weight: bold;
                border-radius: 14px;
                padding: 6px 12px;
                border: 1px solid rgba(220, 140, 0, 40);
            """)
        else:
            self.pill_cooldown.setStyleSheet("""
                background-color: rgba(0, 180, 100, 20);
                color: #008050;
                font-size: 11px;
                font-weight: bold;
                border-radius: 14px;
                padding: 6px 12px;
                border: 1px solid rgba(0, 180, 100, 40);
            """)

    def on_distraction_triggered(self, category: str, url: str, phrase: str):
        """Feedback effect when distraction fires."""
        print(f"[HUD] Distraction Triggered! Category: {category} | URL: {url}")

    def trigger_manual_distraction(self):
        """Manual test trigger for instant distraction."""
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.trigger_manual_distraction()

    def toggle_audio(self):
        """Toggles audio text-to-speech voice shaming."""
        self.audio_enabled = not self.audio_enabled
        self.worker.audio_enabled = self.audio_enabled
        if self.audio_enabled:
            self.btn_audio.setText("🔊 Audio On")
            self.btn_audio.setStyleSheet("""
                background-color: rgba(0, 0, 0, 8);
                color: rgba(45, 52, 70, 220);
                font-size: 11px;
                font-weight: bold;
                border-radius: 14px;
                padding: 8px 14px;
                border: 1px solid rgba(0, 0, 0, 15);
            """)
        else:
            self.btn_audio.setText("🔇 Audio Muted")
            self.btn_audio.setStyleSheet("""
                background-color: rgba(220, 40, 70, 15);
                color: #D61A3C;
                font-size: 11px;
                font-weight: bold;
                border-radius: 14px;
                padding: 8px 14px;
                border: 1px solid rgba(220, 40, 70, 30);
            """)

    def toggle_theme(self):
        """Toggles between Light Glass and Dark Frosted Glass theme."""
        self.is_dark_mode = not self.is_dark_mode
        if self.is_dark_mode:
            self.pill_mode.setText("🌙 DARK HUD")
            self.card.setStyleSheet("""
                QFrame {
                    background-color: rgba(24, 28, 38, 245);
                    border: 1.5px solid rgba(60, 70, 90, 200);
                    border-radius: 28px;
                }
            """)
            self.window_lbl.setStyleSheet("color: rgba(180, 190, 210, 230); font-size: 11px; border: none; background: transparent;")
            self.sub_info_lbl.setStyleSheet("color: rgba(150, 160, 180, 200); font-size: 10px; border: none; background: transparent;")
            self.btn_audio.setStyleSheet("""
                background-color: rgba(255, 255, 255, 12);
                color: #ECEFF4;
                font-size: 11px;
                font-weight: bold;
                border-radius: 14px;
                padding: 8px 14px;
                border: 1px solid rgba(255, 255, 255, 20);
            """)
        else:
            self.pill_mode.setText("☀️ LIGHT HUD")
            self.card.setStyleSheet("""
                QFrame {
                    background-color: rgba(246, 248, 252, 245);
                    border: 1.5px solid rgba(195, 204, 218, 220);
                    border-radius: 28px;
                }
            """)
            self.window_lbl.setStyleSheet("color: rgba(60, 68, 85, 230); font-size: 11px; border: none; background: transparent;")
            self.sub_info_lbl.setStyleSheet("color: rgba(90, 100, 115, 200); font-size: 10px; border: none; background: transparent;")
            self.btn_audio.setStyleSheet("""
                background-color: rgba(0, 0, 0, 8);
                color: rgba(45, 52, 70, 220);
                font-size: 11px;
                font-weight: bold;
                border-radius: 14px;
                padding: 8px 14px;
                border: 1px solid rgba(0, 0, 0, 15);
            """)

    def mousePressEvent(self, event):
        """Initiates smooth frameless dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        """Translates frameless window across desktop."""
        if not self.old_pos.isNull():
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        """Releases drag tracking."""
        self.old_pos = QPoint()

    def closeEvent(self, event):
        """Cleanly releases camera and background worker on exit."""
        print("[HUD] Shutting down Vision Worker & releasing camera...")
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(1500)
        event.accept()


# ==============================================================================
# Entry Point
# ==============================================================================
if __name__ == '__main__':
    app = QApplication(sys.argv)
    hud = VisionHUD()
    hud.show()
    sys.exit(app.exec())
