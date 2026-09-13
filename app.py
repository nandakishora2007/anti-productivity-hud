import sys
import time
import random
import webbrowser
import threading
import cv2
import numpy as np
import mediapipe as mp
from ultralytics import YOLO
import pygetwindow as gw
import pyttsx3

from PyQt6.QtCore import QTimer, Qt, QPoint
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QFrame

class VisionHUD(QWidget):
    def __init__(self):
        super().__init__()
        
        # Window Flags: Frameless, Always on Top, Translucent Background
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.SubWindow
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(430, 640)
        
        self.old_pos = QPoint()

        # AI Models & Audio Initialization
        print("Loading AI Engine & Audio Synthesizer...")
        self.model = YOLO('yolov8n.pt')
        self.mp_face = mp.solutions.face_detection
        self.face_detection = self.mp_face.FaceDetection(model_selection=0, min_detection_confidence=0.6)
        
        # Initialize Text-to-Speech Engine
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty('rate', 170)

        self.cap = cv2.VideoCapture(0)

        # Logic States & Feature Lists
        self.cooldown = 25
        self.last_trigger = 0
        self.is_distracted = False
        
        # Distraction Roulette Links (YouTube + The Zen Zone)
        self.distractions = [
            "https://thezen.zone/",                       # The Zen Zone website
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # The Classic
            "https://www.youtube.com/watch?v=V-_O7nl0Ii0",  # Fascinating science breakdown
            "https://www.youtube.com/watch?v=8Zbf9_jK-ZI",  # Mind-bending visualization
            "https://www.youtube.com/watch?v=kJQP7kiw5Fk",  # High-energy distraction
            "https://www.youtube.com/watch?v=9bZkp7q19f0"   # Viral phenomenon
        ]
        
        # Audio Shame Messages
        self.shame_phrases = [
            "Productivity detected! Drop your tools immediately!",
            "Warning. Overworking hazard detected. Cease coding at once.",
            "Hey! Stop being productive and take a break.",
            "Error 404: Fun not found. Deploying distraction!"
        ]

        self.work_objects = ['laptop', 'keyboard', 'book', 'mouse', 'scissors']
        self.slack_kw = ['youtube', 'netflix', 'twitch', 'discord', 'steam', 'game', 'reddit', 'spotify']
        self.work_kw = ['visual studio', 'vscode', 'github', 'stackoverflow', 'chatgpt', 'docs', 'python', 'terminal']

        self.init_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

    def speak_warning(self):
        def run_speech():
            try:
                phrase = random.choice(self.shame_phrases)
                self.tts_engine.say(phrase)
                self.tts_engine.runAndWait()
            except Exception:
                pass
        threading.Thread(target=run_speech, daemon=True).start()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Main Light Glass Container Card
        self.card = QFrame(self)
        self.card.setStyleSheet("""
            QFrame {
                background-color: rgba(245, 247, 250, 235);
                border: 1.5px solid rgba(200, 205, 215, 150);
                border-radius: 28px;
            }
        """)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(10)

        # 1. Top Glass Pill Badges Row (Light Theme)
        pills_layout = QHBoxLayout()
        pills_layout.setSpacing(8)

        self.pill_mode = QLabel("☀️ LIGHT HUD", self)
        self.pill_mode.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pill_mode.setStyleSheet("""
            background-color: rgba(0, 0, 0, 6);
            color: rgba(40, 45, 60, 220);
            font-size: 11px;
            font-weight: bold;
            border-radius: 14px;
            padding: 6px 10px;
            border: 1px solid rgba(0, 0, 0, 12);
        """)
        pills_layout.addWidget(self.pill_mode)

        self.pill_cooldown = QLabel("⏳ Ready", self)
        self.pill_cooldown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pill_cooldown.setStyleSheet("""
            background-color: rgba(0, 180, 100, 12);
            color: #008050;
            font-size: 11px;
            font-weight: bold;
            border-radius: 14px;
            padding: 6px 10px;
            border: 1px solid rgba(0, 180, 100, 30);
        """)
        pills_layout.addWidget(self.pill_cooldown)

        # Close Pill Button
        close_pill = QLabel("✕", self)
        close_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        close_pill.setStyleSheet("""
            background-color: rgba(220, 40, 70, 12);
            color: #D61A3C;
            font-size: 12px;
            font-weight: bold;
            border-radius: 14px;
            padding: 6px 12px;
            border: 1px solid rgba(220, 40, 70, 30);
        """)
        close_pill.mousePressEvent = lambda e: self.close()
        pills_layout.addWidget(close_pill)

        card_layout.addLayout(pills_layout)

        # 2. Camera Display Screen Card (Light Rounded Inner Panel)
        self.cam_lbl = QLabel(self)
        self.cam_lbl.setFixedSize(364, 210)
        self.cam_lbl.setStyleSheet("""
            background-color: rgba(230, 233, 240, 200);
            border-radius: 18px;
            border: 1px solid rgba(200, 205, 215, 100);
        """)
        self.cam_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.cam_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        # 3. Status Telemetry Container Card (Bottom Light Panel)
        status_panel = QFrame(self)
        status_panel.setStyleSheet("""
            QFrame {
                background-color: rgba(235, 238, 245, 200);
                border: 1px solid rgba(200, 205, 215, 120);
                border-radius: 16px;
            }
        """)
        status_layout = QVBoxLayout(status_panel)
        status_layout.setContentsMargins(12, 10, 12, 10)
        status_layout.setSpacing(6)

        self.status_lbl = QLabel("Status: Initializing...", self)
        self.status_lbl.setStyleSheet("color: #008050; font-size: 12px; font-weight: bold; border: none; background: transparent;")
        status_layout.addWidget(self.status_lbl)

        self.window_lbl = QLabel("Active App: Scanning...", self)
        self.window_lbl.setStyleSheet("color: rgba(80, 85, 100, 180); font-size: 11px; border: none; background: transparent;")
        status_layout.addWidget(self.window_lbl)

        card_layout.addWidget(status_panel)

        # 4. Bottom Action Pill Buttons (Light iOS Style Bar)
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(10)

        self.btn_settings = QLabel("⚙️ Settings", self)
        self.btn_settings.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_settings.setStyleSheet("""
            background-color: rgba(0, 0, 0, 5);
            color: rgba(50, 55, 70, 200);
            font-size: 11px;
            font-weight: bold;
            border-radius: 14px;
            padding: 8px 14px;
            border: 1px solid rgba(0, 0, 0, 10);
        """)
        bottom_bar.addWidget(self.btn_settings)

        self.btn_message = QLabel("💬 Anti-Productive HUD", self)
        self.btn_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_message.setStyleSheet("""
            background-color: rgba(0, 0, 0, 5);
            color: rgba(50, 55, 70, 200);
            font-size: 11px;
            font-weight: bold;
            border-radius: 14px;
            padding: 8px 14px;
            border: 1px solid rgba(0, 0, 0, 10);
        """)
        bottom_bar.addWidget(self.btn_message)

        card_layout.addLayout(bottom_bar)
        main_layout.addWidget(self.card)

    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret: return

        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        working = False
        face_found = False
        active_title = "Desktop"

        # 1. Active Window Check
        try:
            win = gw.getActiveWindow()
            if win and win.title:
                active_title = win.title.lower()
        except:
            pass

        slack_mode = any(k in active_title for k in self.slack_kw)
        important_work = any(k in active_title for k in self.work_kw)

        # 2. Face Detection
        fd = self.face_detection.process(rgb)
        if fd.detections:
            face_found = True
            for d in fd.detections:
                box = d.location_data.relative_bounding_box
                x, y, bw, bh = int(box.xmin*w), int(box.ymin*h), int(box.width*w), int(box.height*h)
                cv2.rectangle(frame, (x, y), (x+bw, y+bh), (0, 150, 80), 2)

        # 3. YOLO Detection
        results = self.model(frame, stream=True, verbose=False)
        for r in results:
            for b in r.boxes:
                obj_name = self.model.names[int(b.cls[0])]
                if float(b.conf[0]) > 0.4 and obj_name in self.work_objects:
                    working = True

        if face_found and important_work:
            working = True

        # 4. Trigger & Cooldown Logic with Audio & Roulette
        now = time.time()
        elapsed = now - self.last_trigger

        if slack_mode:
            working = False
            status_text = "SUPPRESSED (ALREADY SLACKING)"
            status_color = "#B36B00"
            self.pill_cooldown.setText("🛡️ Suppressed")
            self.pill_cooldown.setStyleSheet("""
                background-color: rgba(220, 140, 0, 15);
                color: #B36B00;
                font-size: 11px;
                font-weight: bold;
                border-radius: 14px;
                padding: 6px 10px;
                border: 1px solid rgba(220, 140, 0, 30);
            """)
        elif working:
            status_text = "DANGER: WORKING DETECTED"
            status_color = "#D61A3C"
            remaining = int(max(0, self.cooldown - elapsed))
            if remaining > 0:
                self.pill_cooldown.setText(f"⏱️ Cooldown {remaining}s")
            else:
                self.pill_cooldown.setText("⚡ TRIGGERING")
            
            self.pill_cooldown.setStyleSheet("""
                background-color: rgba(220, 40, 70, 15);
                color: #D61A3C;
                font-size: 11px;
                font-weight: bold;
                border-radius: 14px;
                padding: 6px 10px;
                border: 1px solid rgba(220, 40, 70, 30);
            """)

            if not self.is_distracted and elapsed > self.cooldown:
                # Trigger Audio Shame & Random Link (Zen Zone or YouTube)
                self.speak_warning()
                target_url = random.choice(self.distractions)
                webbrowser.open(target_url)
                self.is_distracted = True
                self.last_trigger = now
        else:
            status_text = "SAFE / IDLE"
            status_color = "#008050"
            self.is_distracted = False
            self.pill_cooldown.setText("✨ Ready")
            self.pill_cooldown.setStyleSheet("""
                background-color: rgba(0, 180, 100, 12);
                color: #008050;
                font-size: 11px;
                font-weight: bold;
                border-radius: 14px;
                padding: 6px 10px;
                border: 1px solid rgba(0, 180, 100, 30);
            """)

        # Update UI Text Labels
        self.status_lbl.setText(status_text)
        self.status_lbl.setStyleSheet(f"color: {status_color}; font-size: 12px; font-weight: bold; border: none; background: transparent;")
        self.window_lbl.setText(f"App: {active_title[:32]}..")

        # Render Camera Frame to PyQt Label
        qt_img = QImage(frame.data, w, h, 3 * w, QImage.Format.Format_BGR888)
        self.cam_lbl.setPixmap(QPixmap.fromImage(qt_img).scaled(364, 210, Qt.AspectRatioMode.KeepAspectRatio))

    def mousePressEvent(self, event):
        self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        delta = event.globalPosition().toPoint() - self.old_pos
        self.move(self.pos() + delta)
        self.old_pos = event.globalPosition().toPoint()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    hud = VisionHUD()
    hud.show()
    sys.exit(app.exec())