from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QSlider, QPushButton, QWidget, QScrollArea, QGridLayout
)
from PyQt6.QtCore import Qt


AVAILABLE_CLASSES = [
    "person", "car", "truck", "motorcycle", "bicycle",
    "bus", "dog", "cat", "bird", "backpack", "handbag", "cell phone"
]


class SettingsDialog(QDialog):
    def __init__(self, pipeline, parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        self.setWindowTitle(f"Settings — {pipeline.name}")
        self.setFixedSize(440, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setObjectName("topbar")
        header.setFixedHeight(54)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)

        title = QLabel(f"⚙  {pipeline.name.upper()}")
        title.setObjectName("settingsTitle")
        hl.addWidget(title)
        layout.addWidget(header)

        # Body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(20, 20, 20, 20)
        bl.setSpacing(20)

        # 1 - Display
        bl.addWidget(self._section("DISPLAY"))
        self.bbox_check = QCheckBox("Show bounding boxes")
        self.bbox_check.setChecked(pipeline.settings["show_bbox"])
        self.bbox_check.stateChanged.connect(self._on_bbox)
        bl.addWidget(self.bbox_check)

        # 2 - Motion sensitivity
        bl.addWidget(self._section("MOTION SENSITIVITY"))
        self.motion_label = QLabel(f"Threshold: {pipeline.settings['motion_sensitivity']}")
        self.motion_label.setProperty("role", "value")
        self.motion_slider = QSlider(Qt.Orientation.Horizontal)
        self.motion_slider.setRange(20, 150)
        self.motion_slider.setValue(pipeline.settings["motion_sensitivity"])
        self.motion_slider.valueChanged.connect(self._on_motion)

        hint1 = QLabel("← more sensitive            less sensitive →")
        hint1.setProperty("role", "hint")

        bl.addWidget(self.motion_label)
        bl.addWidget(self.motion_slider)
        bl.addWidget(hint1)

        # 3 - Confidence
        bl.addWidget(self._section("CONFIDENCE THRESHOLD"))
        self.conf_label = QLabel(f"{int(pipeline.settings['confidence_threshold'] * 100)}%")
        self.conf_label.setProperty("role", "value")
        self.conf_slider = QSlider(Qt.Orientation.Horizontal)
        self.conf_slider.setRange(40, 95)
        self.conf_slider.setValue(int(pipeline.settings["confidence_threshold"] * 100))
        self.conf_slider.valueChanged.connect(self._on_conf)

        hint2 = QLabel("← more detections          fewer detections →")
        hint2.setProperty("role", "hint")

        bl.addWidget(self.conf_label)
        bl.addWidget(self.conf_slider)
        bl.addWidget(hint2)

        # 4 - Classes
        bl.addWidget(self._section("DETECT CLASSES"))
        classes_grid = QGridLayout()
        classes_grid.setSpacing(8)

        self.class_checks = {}
        for i, cls in enumerate(AVAILABLE_CLASSES):
            check = QCheckBox(cls)
            check.setChecked(cls in pipeline.settings["enabled_classes"])
            check.stateChanged.connect(self._on_classes)
            self.class_checks[cls] = check
            classes_grid.addWidget(check, i // 2, i % 2)

        classes_widget = QWidget()
        classes_widget.setLayout(classes_grid)
        bl.addWidget(classes_widget)

        bl.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll)

        # Footer
        footer = QWidget()
        footer.setProperty("role", "bordered-top")
        footer.setObjectName("topbar")
        footer.setFixedHeight(56)
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(20, 0, 20, 0)

        close_btn = QPushButton("Done")
        close_btn.setProperty("role", "primary")
        close_btn.setFixedSize(100, 32)
        close_btn.clicked.connect(self.accept)

        fl.addStretch()
        fl.addWidget(close_btn)
        layout.addWidget(footer)

    # ── Helpers ──

    def _section(self, text):
        lbl = QLabel(text)
        lbl.setProperty("role", "section")
        return lbl

    # ── Handlers ──

    def _on_bbox(self, state):
        self.pipeline.update_setting("show_bbox", bool(state))

    def _on_motion(self, value):
        self.motion_label.setText(f"Threshold: {value}")
        self.pipeline.update_setting("motion_sensitivity", value)

    def _on_conf(self, value):
        self.conf_label.setText(f"{value}%")
        self.pipeline.update_setting("confidence_threshold", value / 100)

    def _on_classes(self):
        enabled = {cls for cls, c in self.class_checks.items() if c.isChecked()}
        self.pipeline.update_setting("enabled_classes", enabled)