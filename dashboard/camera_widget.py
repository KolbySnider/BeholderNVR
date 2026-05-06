import cv2
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QMainWindow, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
from camera.pipeline import CameraPipeline
from dashboard.settings_dialog import SettingsDialog


def _restyle(widget, role: str):
    """Update a QSS property and force re-polish so the new style applies."""
    widget.setProperty("role", role)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class CameraWidget(QWidget):
    def __init__(self, name: str, url: str, on_fullscreen_cb, on_remove_cb=None):
        super().__init__()
        self.name = name
        self.on_fullscreen_cb = on_fullscreen_cb
        self.on_remove_cb = on_remove_cb
        self.pipeline = CameraPipeline(name, url)

        self.setObjectName("cameraCard")
        self.setFixedSize(380, 220)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Video
        self.video_label = QLabel()
        self.video_label.setObjectName("cameraVideo")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setFixedSize(380, 180)
        self.video_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.video_label.mousePressEvent = lambda e: self.on_fullscreen_cb(self)
        layout.addWidget(self.video_label)

        # Bottom bar
        bottom = QWidget()
        bottom.setObjectName("cameraBottomBar")
        bottom.setFixedHeight(40)
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(8, 0, 8, 0)
        bl.setSpacing(6)

        # Status group: dot + name share one background
        status_group = QWidget()
        status_group.setObjectName("cameraStatusGroup")
        sg = QHBoxLayout(status_group)
        sg.setContentsMargins(8, 4, 10, 4)
        sg.setSpacing(6)

        self.status_dot = QLabel("•")
        self.status_dot.setObjectName("cameraDot")
        self.status_dot.setProperty("active", "false")

        self.name_label = QLabel(name)
        self.name_label.setObjectName("cameraName")

        sg.addWidget(self.status_dot)
        sg.addWidget(self.name_label)

        self.detect_btn = QPushButton("DETECT")
        self.detect_btn.setProperty("role", "ghost")
        self.detect_btn.setFixedSize(70, 24)
        self.detect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.detect_btn.clicked.connect(self.toggle_detection)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setProperty("role", "cog")
        self.settings_btn.setFixedSize(28, 24)
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.clicked.connect(self.open_settings)

        self.remove_btn = QPushButton("x")
        self.remove_btn.setProperty("role", "remove")
        self.remove_btn.setFixedSize(28, 24)
        self.remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_btn.setToolTip("Remove camera")
        self.remove_btn.clicked.connect(self._handle_remove)

        bl.addWidget(status_group)
        bl.addStretch()
        bl.addWidget(self.detect_btn)
        bl.addWidget(self.settings_btn)
        bl.addWidget(self.remove_btn)
        layout.addWidget(bottom)

        # Timers
        self.preview_timer = QTimer(timeout=self.update_display, interval=2000)
        self.preview_timer.start()
        self.active_timer = QTimer(timeout=self.update_display, interval=30)

    # ── Actions ──

    def open_settings(self):
        SettingsDialog(self.pipeline, self).exec()

    def _handle_remove(self):
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Remove Camera",
            f"Remove '{self.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes and self.on_remove_cb:
            self.on_remove_cb(self)

    def toggle_detection(self):
        if not self.pipeline.detection_active:
            self.pipeline.start_detection()
            self.detect_btn.setText("STOP")
            _restyle(self.detect_btn, "danger")
            self.status_dot.setProperty("active", "true")
            self.status_dot.style().unpolish(self.status_dot)
            self.status_dot.style().polish(self.status_dot)
            self.preview_timer.stop()
            self.active_timer.start()
        else:
            self.pipeline.stop_detection()
            self.detect_btn.setText("DETECT")
            _restyle(self.detect_btn, "ghost")
            self.status_dot.setProperty("active", "false")
            self.status_dot.style().unpolish(self.status_dot)
            self.status_dot.style().polish(self.status_dot)
            self.active_timer.stop()
            self.preview_timer.start()

    # ── Display ──

    def update_display(self):
        frame = self.pipeline.get_frame()
        if frame is None:
            return

        frame = frame.copy()

        if self.pipeline.detection_active and self.pipeline.settings.get("show_bbox", True):
            for track in self.pipeline.get_tracks():
                x1, y1, x2, y2 = track["bbox"]
                label = f'{track["class"]} {track["confidence"]:.0%}'
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 1, cv2.LINE_AA)
                cv2.putText(frame, label, (x1, y1 - 3),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1, cv2.LINE_AA)

        frame = cv2.resize(frame, (380, 180), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self.video_label.setPixmap(QPixmap.fromImage(img))

    def get_current_frame(self):
        return self.pipeline.get_frame()

    def get_current_tracks(self):
        return self.pipeline.get_tracks()

    def stop(self):
        self.pipeline.stop()
        self.preview_timer.stop()
        self.active_timer.stop()


class FullscreenWindow(QMainWindow):
    def __init__(self, camera_widget: CameraWidget):
        super().__init__()
        self.camera_widget = camera_widget
        self.setWindowTitle(f"BeholderNVR — {camera_widget.name}")
        self.setMinimumSize(1280, 720)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top bar
        topbar = QWidget()
        topbar.setObjectName("topbar")
        topbar.setFixedHeight(44)
        tl = QHBoxLayout(topbar)
        tl.setContentsMargins(16, 0, 16, 0)

        cam_label = QLabel(f"⬡  {camera_widget.name.upper()}")
        cam_label.setObjectName("fullscreenTitle")

        self.settings_btn = QPushButton("⚙ SETTINGS")
        self.settings_btn.setProperty("role", "ghost")
        self.settings_btn.setFixedSize(120, 28)
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.clicked.connect(self.open_settings)

        active = camera_widget.pipeline.detection_active
        self.detect_btn = QPushButton("STOP DETECTION" if active else "START DETECTION")
        self.detect_btn.setProperty("role", "danger" if active else "primary")
        self.detect_btn.setFixedSize(160, 28)
        self.detect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.detect_btn.clicked.connect(self.toggle_detection)

        tl.addWidget(cam_label)
        tl.addStretch()
        tl.addWidget(self.settings_btn)
        tl.addWidget(self.detect_btn)
        layout.addWidget(topbar)

        # Video
        self.video_label = QLabel()
        self.video_label.setObjectName("fullscreenVideo")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.video_label)

        self.timer = QTimer(timeout=self.update_display, interval=30)
        self.timer.start()

    def open_settings(self):
        SettingsDialog(self.camera_widget.pipeline, self).exec()

    def toggle_detection(self):
        # Toggle on the inner widget so its UI also updates
        self.camera_widget.toggle_detection()
        active = self.camera_widget.pipeline.detection_active
        self.detect_btn.setText("STOP DETECTION" if active else "START DETECTION")
        _restyle(self.detect_btn, "danger" if active else "primary")

    def update_display(self):
        frame = self.camera_widget.get_current_frame()
        if frame is None:
            return

        frame = frame.copy()
        pipeline = self.camera_widget.pipeline

        if pipeline.detection_active and pipeline.settings.get("show_bbox", True):
            for track in self.camera_widget.get_current_tracks():
                x1, y1, x2, y2 = track["bbox"]
                label = f'{track["class"]} {track["confidence"]:.0%}'
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 1, cv2.LINE_AA)
                cv2.putText(frame, label,
                            (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1, cv2.LINE_AA)

        h, w = self.video_label.height(), self.video_label.width()
        if h > 0 and w > 0:
            frame = cv2.resize(frame, (w, h))

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        fh, fw, ch = rgb.shape
        img = QImage(rgb.data, fw, fh, ch * fw, QImage.Format.Format_RGB888)
        self.video_label.setPixmap(QPixmap.fromImage(img))

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()