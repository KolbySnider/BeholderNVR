import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget,
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QDialog, QLineEdit, QLabel,
    QScrollArea, QGridLayout, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from dashboard.camera_widget import CameraWidget, FullscreenWindow
from dashboard.detection_log import DetectionLog
from storage.db import list_cameras


class AddCameraDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Camera")
        self.setFixedSize(420, 200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)

        self.name_input = QLineEdit(placeholderText="Camera name (e.g. Front Door)")
        self.url_input = QLineEdit(placeholderText="rtsp://user:pass@ip/stream")

        confirm = QPushButton("Add Stream")
        confirm.setProperty("role", "primary")
        confirm.clicked.connect(self.accept)

        for label_text, widget in [
            ("NAME", self.name_input),
            ("RTSP URL", self.url_input),
        ]:
            lbl = QLabel(label_text)
            lbl.setProperty("role", "form-label")
            layout.addWidget(lbl)
            layout.addWidget(widget)
        layout.addWidget(confirm)

    def get_values(self):
        return self.name_input.text().strip(), self.url_input.text().strip()


class AddCameraPlaceholder(QFrame):
    def __init__(self, on_click):
        super().__init__()
        self.on_click = on_click
        self.setObjectName("cameraPlaceholder")
        self.setFixedSize(380, 220)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        plus = QLabel("+")
        plus.setObjectName("plusIcon")
        plus.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel("Add Stream")
        label.setObjectName("plusLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(plus)
        layout.addWidget(label)

    def mousePressEvent(self, _):
        self.on_click()


class FeedsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.camera_widgets = []
        self.fullscreen_windows = []

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(12)
        self.grid_layout.setContentsMargins(16, 16, 16, 16)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll.setWidget(self.grid_container)
        main.addWidget(scroll)

        self.placeholder = AddCameraPlaceholder(self.add_camera)
        self.grid_layout.addWidget(self.placeholder, 0, 0)

        #spawn saved cameras
        for name, url in list_cameras():
            self.spawn_camera(name, url, persist=False)

    def add_camera(self):
        dialog = AddCameraDialog()
        if dialog.exec():
            name, url = dialog.get_values()
            if name and url:
                self.spawn_camera(name, url)

    def spawn_camera(self, name: str, url: str, persist: bool = True):
        widget = CameraWidget(name, url, self.open_fullscreen, self.remove_camera)
        self.camera_widgets.append(widget)
        if persist:
            from storage.db import save_camera
            save_camera(name, url)
        self.rebuild_grid()

    def remove_camera(self, widget):
        if widget not in self.camera_widgets:
            return
        from storage.db import delete_camera
        for win in list(self.fullscreen_windows):
            if getattr(win, "camera_widget", None) is widget:
                win.close()
                self.fullscreen_windows.remove(win)
        widget.stop()
        delete_camera(widget.name)
        self.camera_widgets.remove(widget)
        widget.setParent(None)
        widget.deleteLater()
        self.rebuild_grid()

    def rebuild_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        cols = 3
        for i, widget in enumerate(self.camera_widgets):
            self.grid_layout.addWidget(widget, *divmod(i, cols))
        count = len(self.camera_widgets)
        self.grid_layout.addWidget(self.placeholder, *divmod(count, cols))

    def open_fullscreen(self, camera_widget):
        win = FullscreenWindow(camera_widget)
        self.fullscreen_windows.append(win)
        win.show()

    def stop_all(self):
        for w in self.camera_widgets:
            w.stop()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BeholderNVR")
        self.setMinimumSize(1400, 900)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        topbar = QWidget()
        topbar.setObjectName("topbar")
        topbar.setFixedHeight(48)
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(16, 0, 16, 0)

        title = QLabel("BEHOLDERNVR")
        title.setObjectName("appTitle")
        topbar_layout.addWidget(title)
        topbar_layout.addStretch()
        layout.addWidget(topbar)

        self.tabs = QTabWidget()
        self.feeds_tab = FeedsTab()
        self.log_tab = DetectionLog()
        self.tabs.addTab(self.feeds_tab, "LIVE FEEDS")
        self.tabs.addTab(self.log_tab, "DETECTION LOG")
        layout.addWidget(self.tabs)

    def closeEvent(self, event):
        self.feeds_tab.stop_all()
        event.accept()


def load_stylesheet(app: QApplication):
    here = os.path.dirname(os.path.abspath(__file__))
    qss = os.path.join(here, "styles.qss")
    if os.path.exists(qss):
        with open(qss, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    load_stylesheet(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())