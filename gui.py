import sys
import os
import re
import numpy as np
import platform

# Verify display server connection for key simulation
HAS_KEYBOARD_SIMULATOR = False
if platform.system() == "Windows":
    HAS_KEYBOARD_SIMULATOR = True
elif platform.system() == "Linux":
    try:
        from Xlib.display import Display
        d = Display()
        d.close()
        HAS_KEYBOARD_SIMULATOR = True
    except Exception:
        HAS_KEYBOARD_SIMULATOR = False

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QComboBox, QSlider, QLabel, QCheckBox, QFrame,
    QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint, QSize, QThread
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient,
    QPainterPath, QFont, QGuiApplication, QTextCursor
)

class FileTranscriber(QThread):
    progress = pyqtSignal(int)          # Percentage (0-100)
    finished = pyqtSignal(str)          # Final concatenated text
    error_occurred = pyqtSignal(str)    # Error message

    def __init__(self, filepath, language="en-US", parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.language = language

    def run(self):
        try:
            import av
            import wave
            import io
            import speech_recognition as sr

            self.progress.emit(10)  # Start decoding
            
            container = av.open(self.filepath)
            stream = container.streams.audio[0]
            
            target_rate = 16000
            resampler = av.AudioResampler(
                format='s16',
                layout='mono',
                rate=target_rate
            )
            
            duration = 0.0
            if container.duration:
                duration = float(container.duration) / 1000000.0
            elif stream.duration and stream.time_base:
                duration = float(stream.duration * stream.time_base)
            
            if duration <= 0.0:
                duration = 30.0 # Default fallback
            
            wav_io = io.BytesIO()
            with wave.open(wav_io, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2) # 16-bit
                wav_file.setframerate(target_rate)
                
                for frame in container.decode(stream):
                    resampled_frames = resampler.resample(frame)
                    for rf in resampled_frames:
                        wav_file.writeframes(rf.to_ndarray().tobytes())
            
            wav_io.seek(0)
            
            self.progress.emit(30)  # Decoding done
            self.progress.emit(40)

            # Transcribe in chunks
            recognizer = sr.Recognizer()
            transcribed_segments = []
            
            with sr.AudioFile(wav_io) as source:
                chunk_size = 20.0
                total_chunks = max(1, int(duration / chunk_size) + (1 if duration % chunk_size > 0 else 0))
                current_chunk = 0
                
                while True:
                    try:
                        audio_chunk = recognizer.record(source, duration=chunk_size)
                    except EOFError:
                        break
                    
                    if not audio_chunk or len(audio_chunk.frame_data) == 0:
                        break
                    
                    try:
                        text = recognizer.recognize_google(audio_chunk, language=self.language)
                        if text:
                            transcribed_segments.append(text)
                    except sr.UnknownValueError:
                        pass
                    except sr.RequestError as e:
                        self.error_occurred.emit(f"API Connection Error: {str(e)}")
                        return
                    
                    current_chunk += 1
                    p = 40 + int((current_chunk / total_chunks) * 55)
                    self.progress.emit(min(95, p))
            
            self.progress.emit(100)
            final_text = " ".join(transcribed_segments)
            self.finished.emit(final_text)

        except Exception as e:
            self.error_occurred.emit(f"Transcription failed: {str(e)}")

# Supported language BCP-47 codes
LANGUAGES = [
    ("English (United States)", "en-US"),
    ("English (United Kingdom)", "en-GB"),
    ("Spanish (Spain)", "es-ES"),
    ("Spanish (United States)", "es-US"),
    ("French (France)", "fr-FR"),
    ("German (Germany)", "de-DE"),
    ("Italian (Italy)", "it-IT"),
    ("Portuguese (Brazil)", "pt-BR"),
    ("Chinese (Simplified)", "zh-CN"),
    ("Chinese (Traditional)", "zh-TW"),
    ("Japanese (Japan)", "ja-JP"),
    ("Korean (South Korea)", "ko-KR"),
    ("Russian (Russia)", "ru-RU"),
    ("Arabic (Saudi Arabia)", "ar-SA"),
]


class AudioVisualizer(QWidget):
    """
    A custom widget that paints a glowing, multi-layered fluid audio wave.
    Uses 60 FPS QTimer to animate phases and interpolate amplitudes.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.target_amplitude = 0.02
        self.current_amplitude = 0.02
        self.phase = 0.0

        # Animation timer (approx 60 FPS)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(16)

    def set_amplitude(self, rms):
        # Scale RMS value for visual impact and enforce a minimum baseline
        self.target_amplitude = max(rms * 2.0, 0.015)

    def update_animation(self):
        # Smoothly interpolate amplitude (low-pass filter)
        self.current_amplitude += (self.target_amplitude - self.current_amplitude) * 0.15
        # Advance wave phase
        self.phase += 0.08
        self.update()  # Trigger paintEvent

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        W = self.width()
        H = self.height()

        # Clear background (transparent card effect)
        painter.fillRect(self.rect(), QColor(15, 23, 42, 0))

        # We draw 3 overlapping waves with different phases, frequencies, and colors
        waves = [
            # color, phase_offset, frequency_scale, opacity
            (QColor(99, 102, 241), 0.0, 1.0, 0.7),     # Indigo primary
            (QColor(139, 92, 246), 2.0, 0.8, 0.45),    # Violet secondary
            (QColor(236, 72, 153), 4.1, 1.2, 0.25),    # Pink tertiary
        ]

        for color, phase_off, freq, opacity in waves:
            path = QPainterPath()
            path.moveTo(0, H / 2)

            for x in range(0, W + 1, 3):
                t = x / W
                # Sine envelope to pinch the ends of the wave to zero
                envelope = np.sin(t * np.pi) ** 1.8

                # Multi-frequency sine combination for a natural look
                wave1 = np.sin(t * 6.0 * freq + self.phase + phase_off) * 0.7
                wave2 = np.sin(t * 12.0 * freq - self.phase * 1.3 + phase_off) * 0.3
                combined = wave1 + wave2

                # Calculate vertical coordinate
                y = (H / 2) + combined * (self.current_amplitude * (H - 10) / 2) * envelope
                path.lineTo(x, y)

            # Style the path
            pen = QPen(color, 2)
            color.setAlphaF(opacity)
            painter.setPen(pen)
            
            # Optional: Add a light gradient fill underneath the primary wave
            if opacity > 0.6:
                grad = QLinearGradient(0, 0, 0, H)
                grad.setColorAt(0.0, QColor(99, 102, 241, 60))
                grad.setColorAt(1.0, QColor(99, 102, 241, 0))
                painter.setBrush(QBrush(grad))
                
                # Close the path for filling
                fill_path = QPainterPath(path)
                fill_path.lineTo(W, H)
                fill_path.lineTo(0, H)
                fill_path.closeSubpath()
                painter.drawPath(fill_path)
                painter.setBrush(Qt.BrushStyle.NoBrush)

            painter.drawPath(path)


class CompactOverlay(QWidget):
    """
    A frameless, focus-free, stays-on-top compact overlay bar.
    Designed to allow clicking "Record" without stealing cursor focus from background apps.
    """
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.drag_position = QPoint()

        # Frameless, Always on Top, Focus-Free window flags
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(300, 75)

        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Main container with styled rounded borders
        self.container = QFrame(self)
        self.container.setObjectName("OverlayContainer")
        self.container.setStyleSheet("""
            QFrame#OverlayContainer {
                background-color: rgba(15, 23, 42, 230);
                border: 1px solid rgba(99, 102, 241, 150);
                border-radius: 20px;
            }
        """)
        container_layout = QHBoxLayout(self.container)
        container_layout.setContentsMargins(8, 5, 8, 5)

        # Drag handle / Status label
        self.lbl_status = QLabel("🎙️ Drag", self)
        self.lbl_status.setStyleSheet("color: rgba(248, 250, 252, 180); font-size: 11px; font-weight: bold;")
        container_layout.addWidget(self.lbl_status)

        # Mini Visualizer
        self.visualizer = AudioVisualizer(self)
        self.visualizer.setMinimumHeight(40)
        self.visualizer.setFixedHeight(45)
        container_layout.addWidget(self.visualizer, 1)

        # Record button
        self.btn_record = QPushButton("⏺️", self)
        self.btn_record.setFixedSize(36, 36)
        self.btn_record.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                border: 2px solid #ef4444;
                border-radius: 18px;
                color: #ef4444;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: white;
            }
        """)
        self.btn_record.clicked.connect(self.main_app.toggle_recording)
        container_layout.addWidget(self.btn_record)

        # Full mode restore button
        self.btn_restore = QPushButton("🗖", self)
        self.btn_restore.setFixedSize(30, 30)
        self.btn_restore.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                border: 1px solid #475569;
                border-radius: 15px;
                color: #f8fafc;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #475569;
            }
        """)
        self.btn_restore.clicked.connect(self.main_app.restore_full_mode)
        container_layout.addWidget(self.btn_restore)

        layout.addWidget(self.container)

    def set_recording_state(self, is_recording):
        if is_recording:
            self.btn_record.setText("⏹️")
            self.btn_record.setStyleSheet("""
                QPushButton {
                    background-color: #ef4444;
                    border: 2px solid #ef4444;
                    border-radius: 18px;
                    color: white;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #dc2626;
                }
            """)
            self.lbl_status.setText("🎙️ Live")
        else:
            self.btn_record.setText("⏺️")
            self.btn_record.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    border: 2px solid #ef4444;
                    border-radius: 18px;
                    color: #ef4444;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #ef4444;
                    color: white;
                }
            """)
            self.lbl_status.setText("🎙️ Drag")
            self.visualizer.set_amplitude(0.0)

    # Mouse events to support dragging the frameless overlay
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()


class VoiceTypistApp(QMainWindow):
    """
    The main application window featuring a rich dark mode editor,
    sidebar settings, and real-time audio wave visualization.
    """
    def __init__(self, recorder, transcriber):
        super().__init__()
        self.recorder = recorder
        self.transcriber = transcriber

        self.setWindowTitle("Voice Typist - Speech to Text")
        self.setMinimumSize(850, 550)

        # State Variables
        self.is_recording = False
        self.direct_dictation = False
        self.overlay_window = None

        self.init_ui()
        self.setup_style()
        self.connect_threads()

    def init_ui(self):
        # Central Widget & Main Layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # LEFT PANEL: Editor & Visualizer
        left_panel = QFrame(self)
        left_panel.setObjectName("LeftPanel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(15, 15, 15, 15)
        left_layout.setSpacing(12)

        # Header Title
        title_label = QLabel("Voice Typist", self)
        title_label.setObjectName("MainTitle")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        left_layout.addWidget(title_label)

        # Large Editor
        self.editor = QTextEdit(self)
        self.editor.setObjectName("EditorArea")
        self.editor.setPlaceholderText("Transcribed text will appear here. You can edit or type directly...")
        self.editor.setFont(QFont("Arial", 12))
        left_layout.addWidget(self.editor, 4)

        # Interim Live Transcription Preview
        self.interim_box = QLabel("Live Preview: (Speak into your microphone)", self)
        self.interim_box.setObjectName("InterimArea")
        self.interim_box.setWordWrap(True)
        self.interim_box.setFont(QFont("Arial", 11, QFont.Weight.Normal, True))
        left_layout.addWidget(self.interim_box)

        # Interactive Wave Visualizer
        self.visualizer = AudioVisualizer(self)
        left_layout.addWidget(self.visualizer, 1)

        # Action Buttons (Copy, Clear, Save)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_copy = QPushButton("📋 Copy Text", self)
        self.btn_copy.setObjectName("ActionBtn")
        self.btn_copy.clicked.connect(self.copy_text)
        btn_layout.addWidget(self.btn_copy)

        self.btn_save = QPushButton("💾 Save Transcript", self)
        self.btn_save.setObjectName("ActionBtn")
        self.btn_save.clicked.connect(self.save_text)
        btn_layout.addWidget(self.btn_save)

        self.btn_clear = QPushButton("🗑️ Clear", self)
        self.btn_clear.setObjectName("ActionBtnDanger")
        self.btn_clear.clicked.connect(self.clear_text)
        btn_layout.addWidget(self.btn_clear)

        left_layout.addLayout(btn_layout)
        main_layout.addWidget(left_panel, 3)

        # RIGHT PANEL: Settings Sidebar
        right_panel = QFrame(self)
        right_panel.setObjectName("RightPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(15, 15, 15, 15)
        right_layout.setSpacing(15)

        # Sidebar Header
        sidebar_title = QLabel("Settings", self)
        sidebar_title.setObjectName("SidebarTitle")
        sidebar_title.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        right_layout.addWidget(sidebar_title)

        # Language Selection
        lbl_lang = QLabel("Language", self)
        lbl_lang.setObjectName("SettingLabel")
        right_layout.addWidget(lbl_lang)

        self.combo_lang = QComboBox(self)
        self.combo_lang.setObjectName("SettingCombo")
        for lang_name, lang_code in LANGUAGES:
            self.combo_lang.addItem(lang_name, lang_code)
        self.combo_lang.currentIndexChanged.connect(self.change_language)
        right_layout.addWidget(self.combo_lang)

        # Silence/VAD Threshold Slider
        lbl_threshold = QLabel("Mic Sensitivity (VAD Threshold)", self)
        lbl_threshold.setObjectName("SettingLabel")
        right_layout.addWidget(lbl_threshold)

        self.slider_threshold = QSlider(Qt.Orientation.Horizontal, self)
        self.slider_threshold.setObjectName("SettingSlider")
        self.slider_threshold.setMinimum(5)
        self.slider_threshold.setMaximum(100)
        self.slider_threshold.setValue(30)  # 0.03
        self.slider_threshold.valueChanged.connect(self.change_threshold)
        right_layout.addWidget(self.slider_threshold)

        # Silence Timeout Slider
        lbl_timeout = QLabel("Auto-Commit Silence Delay", self)
        lbl_timeout.setObjectName("SettingLabel")
        right_layout.addWidget(lbl_timeout)

        self.slider_timeout = QSlider(Qt.Orientation.Horizontal, self)
        self.slider_timeout.setObjectName("SettingSlider")
        self.slider_timeout.setMinimum(5)   # 0.5 seconds
        self.slider_timeout.setMaximum(30)  # 3.0 seconds
        self.slider_timeout.setValue(10)  # 1.0 second
        self.slider_timeout.valueChanged.connect(self.change_timeout)
        right_layout.addWidget(self.slider_timeout)

        # Direct Dictation Checkbox
        self.check_dictation = QCheckBox("Direct Dictation (Paste into other apps)", self)
        self.check_dictation.setObjectName("SettingCheck")
        self.check_dictation.toggled.connect(self.change_dictation_mode)
        if HAS_KEYBOARD_SIMULATOR:
            self.check_dictation.setToolTip("Speech will be pasted automatically at your active cursor.")
        else:
            self.check_dictation.setToolTip("Copies to clipboard (Ctrl+V) and selection (Middle-click paste).\nTo enable auto-pasting, run 'xhost +local:' in your terminal.")
        right_layout.addWidget(self.check_dictation)

        # Auto Punctuation Checkbox
        self.check_auto_punctuation = QCheckBox("Auto Punctuate Sentences", self)
        self.check_auto_punctuation.setObjectName("SettingCheck")
        self.check_auto_punctuation.setChecked(True)
        self.check_auto_punctuation.setToolTip("Automatically appends periods or question marks based on phrasing if not explicitly dictated.")
        right_layout.addWidget(self.check_auto_punctuation)

        right_layout.addStretch()

        # Large Record / Stop Button
        self.btn_record = QPushButton("⏺️ Start Voice Typing", self)
        self.btn_record.setObjectName("RecordBtn")
        self.btn_record.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.btn_record.setMinimumHeight(50)
        self.btn_record.clicked.connect(self.toggle_recording)
        right_layout.addWidget(self.btn_record)

        # Compact Mode Button (Always enabled: copies to clipboard even if auto-paste is blocked)
        self.btn_overlay = QPushButton("🗗 Switch to Floating Pill", self)
        self.btn_overlay.setObjectName("OverlayBtn")
        self.btn_overlay.clicked.connect(self.switch_to_overlay)
        right_layout.addWidget(self.btn_overlay)

        # Transcribe Audio File Button
        self.btn_upload = QPushButton("🎵 Transcribe Audio File", self)
        self.btn_upload.setObjectName("UploadBtn")
        self.btn_upload.clicked.connect(self.upload_audio_file)
        right_layout.addWidget(self.btn_upload)

        # Status log label
        self.lbl_info = QLabel("Status: Ready", self)
        self.lbl_info.setObjectName("StatusInfo")
        right_layout.addWidget(self.lbl_info)

        main_layout.addWidget(right_panel, 1)

    def setup_style(self):
        self.setStyleSheet("""
            /* Base window */
            QMainWindow {
                background-color: #0b0f19;
            }

            /* Panels */
            QFrame#LeftPanel {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 12px;
            }
            QFrame#RightPanel {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 12px;
            }

            /* Labels */
            QLabel#MainTitle {
                color: #f8fafc;
            }
            QLabel#SidebarTitle {
                color: #f8fafc;
                border-bottom: 2px solid #6366f1;
                padding-bottom: 5px;
            }
            QLabel#SettingLabel {
                color: #94a3b8;
                font-size: 11px;
                font-weight: bold;
            }
            QLabel#InterimArea {
                color: #94a3b8;
                background-color: #1e293b;
                border: 1px dashed #334155;
                border-radius: 6px;
                padding: 10px;
                min-height: 40px;
            }
            QLabel#StatusInfo {
                color: #cbd5e1;
                font-size: 10px;
            }

            /* Editor Area */
            QTextEdit#EditorArea {
                background-color: #0b0f19;
                border: 1px solid #1e293b;
                border-radius: 8px;
                color: #f8fafc;
                padding: 10px;
            }
            QTextEdit#EditorArea:focus {
                border: 1px solid #6366f1;
            }

            /* Dropdowns (ComboBox) */
            QComboBox#SettingCombo {
                background-color: #0b0f19;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #f8fafc;
                padding: 5px 8px;
                min-height: 30px;
            }
            QComboBox#SettingCombo::drop-down {
                border: 0px;
            }

            /* Sliders */
            QSlider#SettingSlider::groove:horizontal {
                border: 1px solid #475569;
                height: 4px;
                background: #334155;
                border-radius: 2px;
            }
            QSlider#SettingSlider::handle:horizontal {
                background: #6366f1;
                border: 1px solid #6366f1;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }

            /* Checkbox */
            QCheckBox#SettingCheck {
                color: #cbd5e1;
                font-size: 11px;
            }
            QCheckBox#SettingCheck::indicator {
                width: 14px;
                height: 14px;
                background-color: #0b0f19;
                border: 1px solid #475569;
                border-radius: 3px;
            }
            QCheckBox#SettingCheck::indicator:checked {
                background-color: #6366f1;
                border: 1px solid #6366f1;
            }

            /* Buttons */
            QPushButton#ActionBtn {
                background-color: #334155;
                border: 1px solid #475569;
                border-radius: 8px;
                color: #f8fafc;
                font-weight: bold;
                padding: 8px 15px;
            }
            QPushButton#ActionBtn:hover {
                background-color: #475569;
            }

            QPushButton#ActionBtnDanger {
                background-color: #1e293b;
                border: 1px solid #ef4444;
                border-radius: 8px;
                color: #ef4444;
                font-weight: bold;
                padding: 8px 15px;
            }
            QPushButton#ActionBtnDanger:hover {
                background-color: #ef4444;
                color: white;
            }

            QPushButton#RecordBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ef4444, stop:1 #dc2626);
                border: none;
                border-radius: 8px;
                color: white;
                font-weight: bold;
            }
            QPushButton#RecordBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f87171, stop:1 #ef4444);
            }

            QPushButton#OverlayBtn {
                background-color: #0b0f19;
                border: 1px solid #6366f1;
                border-radius: 8px;
                color: #6366f1;
                font-weight: bold;
                padding: 6px;
            }
            QPushButton#OverlayBtn:hover {
                background-color: #6366f1;
                color: white;
            }

            QPushButton#UploadBtn {
                background-color: #0b0f19;
                border: 1px solid #10b981;
                border-radius: 8px;
                color: #10b981;
                font-weight: bold;
                padding: 6px;
            }
            QPushButton#UploadBtn:hover {
                background-color: #10b981;
                color: white;
            }
        """)

    def connect_threads(self):
        # Audio recorder live amplitude update -> visualizer
        self.recorder.amplitude_updated.connect(self.visualizer.set_amplitude)
        self.recorder.status_msg.connect(self.show_status)
        self.recorder.error_occurred.connect(self.show_error)

        # Audio recorder -> transcriber coordination
        self.recorder.speech_chunk.connect(self.transcriber.add_chunk)
        self.recorder.speech_finalized.connect(self.transcriber.request_finalize)
        self.recorder.speech_started.connect(self.transcriber.reset_buffer)

        # Transcriber text chunk -> main application
        self.transcriber.transcription_chunk.connect(self.handle_transcription)
        self.transcriber.error_occurred.connect(self.show_error)

    # Applies smart punctuation rules to finalized dictation text
    def format_smart_punctuation(self, text):
        text_stripped = text.rstrip()
        if not text_stripped:
            return ""

        # Match "period" or "full stop" (case-insensitive) at the very end of the text segment (optional dot/spaces)
        pattern_end_period = re.compile(r'\s*\b(period|full stop)\b\s*\.?$', re.IGNORECASE)
        if pattern_end_period.search(text_stripped):
            text_stripped = pattern_end_period.sub('.', text_stripped)

        # Match "period" or "full stop" in the middle of the text, but only if followed by a sentence-starting word
        # (capitalized word, pronoun, article, demonstrative, etc.)
        sentence_starters = r'(?:[A-Z][a-zA-Z]*|i|you|he|she|it|we|they|the|a|an|this|that|these|those|there|here|my|your|his|her|its|our|their|who|what|where|when|why|how|then|so|but|and|or|because|although)'
        pattern_mid_period = re.compile(
            rf'\s*\b(period|full stop)\b\s+(?={sentence_starters}\b)', 
            re.IGNORECASE
        )
        text_stripped = pattern_mid_period.sub('. ', text_stripped)

        # Match other punctuation words anywhere in the text
        replacements = [
            (re.compile(r'\s*\bcomma\b\s*', re.IGNORECASE), ', '),
            (re.compile(r'\s*\bquestion mark\b\s*', re.IGNORECASE), '? '),
            (re.compile(r'\s*\b(exclamation mark|exclamation point)\b\s*', re.IGNORECASE), '! '),
            (re.compile(r'\s*\bcolon\b\s*', re.IGNORECASE), ': '),
            (re.compile(r'\s*\bsemicolon\b\s*', re.IGNORECASE), '; '),
            (re.compile(r'\s*\b(new line|newline)\b\s*', re.IGNORECASE), '\n'),
            (re.compile(r'\s*\bnew paragraph\b\s*', re.IGNORECASE), '\n\n'),
        ]

        for pattern, replacement in replacements:
            text_stripped = pattern.sub(replacement, text_stripped)

        text_stripped = text_stripped.strip()

        # Fix any double spaces
        text_stripped = re.sub(r' +', ' ', text_stripped)

        # Capitalize the letter after '.', '?', or '!' followed by spaces
        def capitalize_match(match):
            return match.group(1) + match.group(2).upper()

        text_stripped = re.compile(r'([.?!]\s+)([a-z])').sub(capitalize_match, text_stripped)

        # Capitalize the very first character of the text segment if it is a letter
        if text_stripped:
            text_stripped = text_stripped[0].upper() + text_stripped[1:]

        return text_stripped

    # Automatically infers and appends a period or question mark based on phrasing
    def auto_punctuate(self, text):
        text_stripped = text.strip()
        if not text_stripped:
            return ""

        # If the text already ends with a punctuation mark, do nothing
        if text_stripped[-1] in ['.', '?', '!', ':', ';', ',', '\n', '\r']:
            return text_stripped

        # Split text into lowercase words for analysis
        words = text_stripped.lower().split()
        if not words:
            return text_stripped

        first_word = words[0]

        # Wh-question words
        wh_words = {"who", "what", "where", "when", "why", "how", "which", "whose", "whom"}

        # Auxiliary verbs that almost always start questions
        unambiguous_aux = {
            "is", "are", "was", "were", "does", "did", "can", "could", "will", "would", 
            "should", "shouldn't", "can't", "won't", "couldn't", "wouldn't", 
            "isn't", "aren't", "wasn't", "weren't", "doesn't", "didn't"
        }

        # Ambiguous starters (depend on the second word)
        ambiguous_aux = {"do", "have", "has", "had", "am"}
        pronouns = {"you", "he", "she", "it", "we", "they", "this", "that", "these", "those", "there"}

        is_question = False

        # Check if first word is a Wh-word
        if first_word in wh_words:
            is_question = True
        elif first_word in unambiguous_aux:
            is_question = True
        elif first_word in ambiguous_aux and len(words) > 1:
            second_word = words[1]
            if second_word in pronouns:
                is_question = True

        if is_question:
            return text_stripped + "?"
        else:
            return text_stripped + "."

    # Triggered when a speech chunk is transcribed
    def handle_transcription(self, text, is_final):
        if not text:
            return

        if self.direct_dictation:
            # If in Direct Dictation mode, paste the text into whichever app is active
            if is_final:
                formatted_text = self.format_smart_punctuation(text)
                if self.check_auto_punctuation.isChecked():
                    formatted_text = self.auto_punctuate(formatted_text)
                suffix = "" if formatted_text.endswith(('\n', '\r')) else " "
                self.paste_text_globally(formatted_text + suffix)
                preview_text = formatted_text.replace('\n', ' ')
                self.interim_box.setText("Sent: " + preview_text)
            else:
                self.interim_box.setText("Interim: " + text)
        else:
            # Standard editor text insertion
            if is_final:
                formatted_text = self.format_smart_punctuation(text)
                if self.check_auto_punctuation.isChecked():
                    formatted_text = self.auto_punctuate(formatted_text)
                # Append finalized text to main editor
                cursor = self.editor.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.editor.setTextCursor(cursor)
                suffix = "" if formatted_text.endswith(('\n', '\r')) else " "
                self.editor.insertPlainText(formatted_text + suffix)
                self.interim_box.setText("Live Preview: (Paused)")
            else:
                # Update temporary interim display
                self.interim_box.setText("Interim: " + text)

    # Clipboard Inject + Simulated Keystroke to paste text globally into active cursor focus
    def paste_text_globally(self, text):
        # Copy new phrase to standard clipboard
        QGuiApplication.clipboard().setText(text)

        # Perform paste using ctypes (Windows) or X11 fake_input / ydotool (Linux)
        sys_platform = platform.system()
        try:
            if sys_platform == "Windows":
                import ctypes
                KEYEVENTF_KEYUP = 0x0002
                VK_CONTROL = 0x11
                VK_V = 0x56
                # Press Ctrl
                ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
                # Press V
                ctypes.windll.user32.keybd_event(VK_V, 0, 0, 0)
                # Release V
                ctypes.windll.user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
                # Release Ctrl
                ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
            elif sys_platform == "Linux":
                # Copy to Linux primary selection clipboard (enables instant middle-click paste on Wayland!)
                from PyQt6.QtGui import QClipboard
                QGuiApplication.clipboard().setText(text, QClipboard.Mode.Selection)
                
                # Fallback to X11 fake_input (works on X11 and Xwayland windows)
                try:
                    from Xlib import X
                    from Xlib.display import Display
                    from Xlib.ext.xtest import fake_input
                    
                    disp = Display()
                    ctrl_keycode = disp.keysym_to_keycode(0xffe3)  # Control_L
                    v_keycode = disp.keysym_to_keycode(0x0076)     # v
                    
                    fake_input(disp, X.KeyPress, ctrl_keycode)
                    fake_input(disp, X.KeyPress, v_keycode)
                    fake_input(disp, X.KeyRelease, v_keycode)
                    fake_input(disp, X.KeyRelease, ctrl_keycode)
                    disp.sync()
                    disp.close()
                except Exception:
                    pass
        except Exception as e:
            self.show_status(f"Paste failed: {e}")

    def upload_audio_file(self):
        # Prevent starting if already recording
        if self.is_recording:
            QMessageBox.warning(self, "Recording Active", "Please stop voice typing before transcribing an audio file.")
            return
            
        file_filter = "Audio Files (*.mp3 *.wav *.m4a *.mp4 *.aac *.flac *.ogg *.caf *.3gp);;All Files (*)"
        filepath, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Audio File", 
            "", 
            file_filter
        )
        
        if not filepath:
            return
            
        # Disable buttons during transcription
        self.btn_record.setEnabled(False)
        self.btn_overlay.setEnabled(False)
        self.btn_upload.setEnabled(False)
        
        self.show_status("Transcribing: Loading audio file...")
        self.interim_box.setText("Transcribing file: " + os.path.basename(filepath))
        
        # Start background transcriber
        self.file_transcriber = FileTranscriber(filepath, language=self.transcriber.language)
        self.file_transcriber.progress.connect(self.handle_file_progress)
        self.file_transcriber.finished.connect(self.handle_file_finished)
        self.file_transcriber.error_occurred.connect(self.handle_file_error)
        self.file_transcriber.start()

    def handle_file_progress(self, val):
        self.show_status(f"Transcribing audio file... ({val}%)")

    def handle_file_finished(self, text):
        # Re-enable UI
        self.btn_record.setEnabled(True)
        self.btn_overlay.setEnabled(True)
        self.btn_upload.setEnabled(True)
        
        self.show_status("Status: Ready")
        
        if not text.strip():
            self.interim_box.setText("Transcription completed, but no speech was recognized.")
            QMessageBox.information(self, "Finished", "No speech could be recognized in the audio file.")
            return
            
        # Apply smart punctuation on the complete text
        formatted_text = self.format_smart_punctuation(text)
        
        # Display the result
        if self.direct_dictation:
            # Direct paste
            suffix = "" if formatted_text.endswith(('\n', '\r')) else " "
            self.paste_text_globally(formatted_text + suffix)
            self.interim_box.setText("Sent (File): " + formatted_text.replace('\n', ' '))
        else:
            # Insert in editor
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.editor.setTextCursor(cursor)
            suffix = "" if formatted_text.endswith(('\n', '\r')) else " "
            self.editor.insertPlainText(formatted_text + suffix)
            self.interim_box.setText("Live Preview: (Paused)")
            
        QMessageBox.information(self, "Success", "Audio file transcribed successfully!")

    def handle_file_error(self, err_msg):
        # Re-enable UI
        self.btn_record.setEnabled(True)
        self.btn_overlay.setEnabled(True)
        self.btn_upload.setEnabled(True)
        
        self.show_status("Status: Error")
        self.interim_box.setText("Error: " + err_msg)
        QMessageBox.critical(self, "Error", err_msg)

    def toggle_recording(self):
        if not self.is_recording:
            # Start recording
            self.is_recording = True
            self.btn_record.setText("⏹️ Stop Voice Typing")
            self.btn_record.setStyleSheet("""
                QPushButton#RecordBtn {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ef4444, stop:1 #ef4444);
                    border: 1px solid #f87171;
                }
            """)
            self.lbl_info.setText("Status: Listening...")
            
            # Start background threads
            self.transcriber.reset_buffer()
            self.transcriber.start()
            self.recorder.start()

            if self.overlay_window:
                self.overlay_window.set_recording_state(True)
        else:
            # Stop recording
            self.is_recording = False
            self.btn_record.setText("⏺️ Start Voice Typing")
            self.btn_record.setStyleSheet("")
            self.lbl_info.setText("Status: Stopped")

            # Stop threads
            self.recorder.stop()
            # Do NOT stop the transcriber thread here so it can complete the last sentence.
            # It will be cleanly shut down when the window closes (closeEvent).
            self.visualizer.set_amplitude(0.0)

            if self.overlay_window:
                self.overlay_window.set_recording_state(False)

    def switch_to_overlay(self):
        # Stop recording if running
        if self.is_recording:
            self.toggle_recording()

        self.hide()
        
        if not self.overlay_window:
            self.overlay_window = CompactOverlay(self)
        
        # Sync the mini visualizer with recorder signals
        self.recorder.amplitude_updated.disconnect(self.visualizer.set_amplitude)
        self.recorder.amplitude_updated.connect(self.overlay_window.visualizer.set_amplitude)

        self.overlay_window.show()
        # Automatically enable direct dictation since overlay is floating
        self.check_dictation.setChecked(True)

    def restore_full_mode(self):
        if self.is_recording:
            self.toggle_recording()

        if self.overlay_window:
            self.overlay_window.hide()

        # Connect recorder signals back to the main visualizer
        self.recorder.amplitude_updated.disconnect(self.overlay_window.visualizer.set_amplitude)
        self.recorder.amplitude_updated.connect(self.visualizer.set_amplitude)

        self.show()

    def change_language(self, index):
        lang_code = self.combo_lang.itemData(index)
        self.transcriber.language = lang_code
        self.show_status(f"Language changed to: {self.combo_lang.currentText()}")

    def change_threshold(self, value):
        # Convert slider int [5, 100] to float [0.005, 0.1]
        threshold = value / 1000.0
        self.recorder.silence_threshold = threshold
        self.show_status(f"Mic Sensitivity Threshold: {threshold:.3f}")

    def change_timeout(self, value):
        # Convert slider int [5, 30] to float [0.5, 3.0]
        timeout = value / 10.0
        self.recorder.silence_timeout = timeout
        self.show_status(f"Silence Commit Delay: {timeout:.1f}s")

    def change_dictation_mode(self, checked):
        self.direct_dictation = checked
        if checked:
            self.show_status("Direct Dictation Mode enabled. Focusing on editor is NOT required.")
        else:
            self.show_status("Direct Dictation Mode disabled. Typing into app editor.")

    def copy_text(self):
        text = self.editor.toPlainText()
        if text:
            QGuiApplication.clipboard().setText(text)
            self.show_status("Copied transcript to clipboard.")
        else:
            self.show_status("Nothing to copy.")

    def save_text(self):
        text = self.editor.toPlainText()
        if not text:
            self.show_status("Transcript is empty. Nothing to save.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Transcript", "", "Text Files (*.txt);;JSON Files (*.json)"
        )
        if file_path:
            try:
                if file_path.endswith(".json"):
                    import json
                    data = {
                        "transcript": text,
                        "language": self.transcriber.language,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                else:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(text)
                self.show_status(f"Transcript saved to {os.path.basename(file_path)}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file: {str(e)}")

    def clear_text(self):
        self.editor.clear()
        self.interim_box.setText("Live Preview: (Cleared)")
        self.show_status("Transcript cleared.")

    def show_status(self, msg):
        self.lbl_info.setText(f"Status: {msg}")

    def show_error(self, err_msg):
        self.lbl_info.setText(f"Error: {err_msg}")
        QMessageBox.warning(self, "Audio Error", err_msg)
        if self.is_recording:
            self.toggle_recording()

    def closeEvent(self, event):
        # Stop threads before window closes to prevent crash
        self.recorder.stop()
        self.transcriber.stop()
        if self.overlay_window:
            self.overlay_window.close()
        event.accept()
