import os
import psycopg2
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QDialog, QScrollArea, QGridLayout,
    QFrame, QComboBox, QPushButton, QMessageBox
)
from PyQt6.QtGui import QPixmap, QColor, QPainter, QPen, QPainterPath
from PyQt6.QtCore import Qt, QTimer, QRectF

from storage.db import delete_event


# ─────────────────────────────────────────────────────────────
#  Shared helpers
# ─────────────────────────────────────────────────────────────

_DB = dict(host="localhost", port=5432, dbname="threats", user="admin", password="secret")


def db_query(sql, params=()):
    """Run a SELECT and return rows, or [] on any error."""
    try:
        with psycopg2.connect(**_DB) as conn, conn.cursor() as cur:
            cur.execute("SET TIMEZONE TO 'America/New_York'")
            cur.execute(sql, params)
            return cur.fetchall()
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return []


def rounded_pixmap(source: QPixmap, w: int, h: int,
                   radius: int = 8, corners: str = "top") -> QPixmap:
    """Scale-and-crop source to w x h, then clip to a rounded rect."""
    scaled = source.scaled(w, h,
                           Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation)
    x, y = (scaled.width() - w) // 2, (scaled.height() - h) // 2

    out = QPixmap(w, h)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    path = QPainterPath()
    R = float(radius)
    if corners == "top":
        path.moveTo(R, 0)
        path.lineTo(w - R, 0)
        path.arcTo(w - 2 * R, 0, 2 * R, 2 * R, 90, -90)
        path.lineTo(w, h)
        path.lineTo(0, h)
        path.arcTo(0, 0, 2 * R, 2 * R, 180, -90)
        path.closeSubpath()
    else:
        path.addRoundedRect(QRectF(0, 0, w, h), R, R)

    p.setClipPath(path)
    p.drawPixmap(0, 0, scaled, x, y, w, h)
    p.end()
    return out


class CardBorder(QWidget):

    _PAGE_BG = QColor("#0d1117")

    def __init__(self, parent: QWidget, radius: int = 8):
        super().__init__(parent)
        self._r = radius
        self._color = QColor("#21262d")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setGeometry(parent.rect())
        self.raise_()

    def set_color(self, hex_color: str):
        self._color = QColor(hex_color)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h, R = self.width(), self.height(), float(self._r)

        outer = QPainterPath(); outer.addRect(QRectF(0, 0, w, h))
        inner = QPainterPath(); inner.addRoundedRect(QRectF(0, 0, w, h), R, R)
        p.fillPath(outer - inner, self._PAGE_BG)

        p.setPen(QPen(self._color, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), R, R)
        p.end()


def _conf_role(confidence: float) -> str:
    if confidence >= 0.90:
        return "conf-high"
    if confidence >= 0.75:
        return "conf-med"
    return "conf-low"


def _styled_label(text, role=None, object_name=None):
    """Helper to make a QLabel with a role/objectName tag for QSS."""
    lbl = QLabel(text)
    if role:
        lbl.setProperty("role", role)
    if object_name:
        lbl.setObjectName(object_name)
    return lbl


# ─────────────────────────────────────────────────────────────
#  Snapshot card
# ─────────────────────────────────────────────────────────────

class SnapshotCard(QFrame):
    def __init__(self, index: int, snap_path: str, captured_at, parent=None):
        super().__init__(parent)
        self.snap_path = snap_path
        self.setObjectName("snapshotCard")
        self.setFixedSize(280, 210)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        img = QLabel()
        img.setObjectName("snapshotImage")
        img.setFixedSize(280, 170)
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if snap_path and os.path.exists(snap_path):
            img.setPixmap(rounded_pixmap(QPixmap(snap_path), 280, 170))
        img.setCursor(Qt.CursorShape.PointingHandCursor)
        img.mousePressEvent = lambda e: self._open_full()

        bar = QWidget()
        bar.setObjectName("snapshotBar")
        bar.setFixedHeight(40)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(10, 0, 10, 0)

        bl.addWidget(_styled_label(f"#{index + 1}", role="seq"))
        bl.addStretch()
        bl.addWidget(_styled_label(
            str(captured_at)[11:19] if captured_at else "",
            role="muted"
        ))

        layout.addWidget(img)
        layout.addWidget(bar)
        CardBorder(self)

    def _open_full(self):
        FullSnapshotView(self.snap_path, self).exec()


# ─────────────────────────────────────────────────────────────
#  Snapshot gallery dialog
# ─────────────────────────────────────────────────────────────

class SnapshotGallery(QDialog):
    def __init__(self, event_id: int, cls: str, camera: str,
                 dwell: float, confidence: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{cls} — {camera}")
        self.setMinimumSize(1000, 680)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setObjectName("topbar")
        header.setFixedHeight(60)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)

        title = _styled_label(cls.upper(), object_name="galleryTitle")
        hl.addWidget(title)
        hl.addStretch()

        for text, role in [
            (camera.upper(), "muted"),
            (f"{dwell:.1f}s" if dwell else "active", "active"),
            (f"{confidence:.0%}", "accent"),
        ]:
            hl.addWidget(_styled_label(text, role=f"meta-{role}"))
        layout.addWidget(header)

        # Photo grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(12)
        grid.setContentsMargins(20, 20, 20, 20)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        rows = db_query("""
            SELECT snapshot, captured_at FROM snapshots
            WHERE event_id = %s ORDER BY captured_at ASC
        """, (event_id,))

        if not rows:
            empty = _styled_label("No snapshots found for this event", role="muted")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(empty, 0, 0)
        else:
            for i, (snap_path, captured_at) in enumerate(rows):
                grid.addWidget(SnapshotCard(i, snap_path, captured_at), *divmod(i, 3))

        scroll.setWidget(container)
        layout.addWidget(scroll)


# ─────────────────────────────────────────────────────────────
#  Event card
# ─────────────────────────────────────────────────────────────

class EventCard(QFrame):
    def __init__(self, event_data: tuple, on_click, on_delete):
        super().__init__()
        event_id, first_seen, camera, cls, confidence, dwell, latest_snap, snap_count = event_data
        self.event_data = event_data
        self.event_id = event_id
        self.cls = cls
        self.on_click = on_click
        self.on_delete = on_delete

        self.setObjectName("eventCard")
        self.setFixedSize(300, 230)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        img = QLabel()
        img.setObjectName("eventImage")
        img.setFixedSize(300, 168)
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if latest_snap and os.path.exists(latest_snap):
            img.setPixmap(rounded_pixmap(QPixmap(latest_snap), 300, 168))
        else:
            img.setText("No snapshot")
            img.setProperty("role", "muted")

        # Delete button overlay (top-right of image)
        self.delete_btn = QPushButton("✕", img)
        self.delete_btn.setObjectName("eventDelete")
        self.delete_btn.setFixedSize(24, 24)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.move(300 - 24 - 6, 6)
        self.delete_btn.clicked.connect(self._handle_delete)
        self.delete_btn.raise_()

        cc_role = _conf_role(confidence)
        info = QWidget()
        info.setObjectName("eventInfo")
        info.setFixedHeight(62)
        il = QVBoxLayout(info)
        il.setContentsMargins(10, 6, 10, 6)
        il.setSpacing(2)

        # Row 1 - class + confidence
        row1 = QHBoxLayout()
        row1.addWidget(_styled_label((cls or "").upper(), role=f"{cc_role}-bold"))
        row1.addStretch()
        row1.addWidget(_styled_label(f"{confidence:.0%}", role=cc_role))

        # Row 2 - camera + time + snap count
        row2 = QHBoxLayout()
        row2.addWidget(_styled_label(camera or "", role="muted-sm"))
        row2.addStretch()
        row2.addWidget(_styled_label(
            first_seen.astimezone().strftime("%H:%M:%S") if first_seen else "",
            role="muted-sm"
        ))
        row2.addWidget(_styled_label(f"  {snap_count}", role="accent-sm"))

        il.addLayout(row1)
        il.addLayout(row2)

        layout.addWidget(img)
        layout.addWidget(info)
        self.border = CardBorder(self)

    def _handle_delete(self):
        reply = QMessageBox.question(
            self,
            "Delete Event",
            f"Delete this {self.cls} event?\nThis will also delete its snapshots.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.on_delete(self.event_id)

    def enterEvent(self, _):
        self.border.set_color("#388bfd")

    def leaveEvent(self, _):
        self.border.set_color("#21262d")

    def mousePressEvent(self, _):
        self.on_click(self.event_data)


# ─────────────────────────────────────────────────────────────
#  Detection log
# ─────────────────────────────────────────────────────────────

_SORT_KEYS = [lambda e: e[1], lambda e: e[1], lambda e: e[4], lambda e: e[5]]
_SORT_REV  = [True,           False,          True,            True]


class DetectionLog(QWidget):
    def __init__(self):
        super().__init__()
        self.all_events = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Filter bar
        bar = QWidget()
        bar.setObjectName("topbar")
        bar.setFixedHeight(52)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 0, 16, 0)
        bl.setSpacing(12)

        self.filter_input = QLineEdit(placeholderText="Search by class or camera...")
        self.filter_input.textChanged.connect(self.apply_filter)
        self.filter_input.setFixedWidth(260)

        self.sort_box = QComboBox()
        self.sort_box.addItems(["Newest First", "Oldest First", "Highest Confidence", "Longest Dwell"])
        self.sort_box.currentIndexChanged.connect(self.apply_filter)
        self.sort_box.setFixedWidth(180)

        self.count_label = _styled_label("0 events", role="muted")

        bl.addWidget(self.filter_input)
        bl.addWidget(self.sort_box)
        bl.addStretch()
        bl.addWidget(self.count_label)
        layout.addWidget(bar)

        # Card grid
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.grid_container = QWidget()
        self.grid = QGridLayout(self.grid_container)
        self.grid.setSpacing(14)
        self.grid.setContentsMargins(16, 16, 16, 16)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidget(self.grid_container)
        layout.addWidget(self.scroll)

        self.timer = QTimer(timeout=self.refresh, interval=3000)
        self.timer.start()
        self.refresh()

    def refresh(self):
        self.all_events = db_query("""
            SELECT
                e.id, e.first_seen, e.camera, e.class,
                e.confidence, e.dwell_time,
                (SELECT s.snapshot FROM snapshots s
                 WHERE s.event_id = e.id
                 ORDER BY s.captured_at DESC LIMIT 1) AS latest_snapshot,
                (SELECT COUNT(*) FROM snapshots s WHERE s.event_id = e.id) AS snap_count
            FROM events e ORDER BY e.first_seen DESC LIMIT 200
        """)
        self.apply_filter()

    def apply_filter(self):
        q = self.filter_input.text().lower()
        idx = self.sort_box.currentIndex()

        filtered = [
            e for e in self.all_events
            if not q or q in (e[3] or "").lower() or q in (e[2] or "").lower()
        ]
        filtered.sort(key=lambda e: _SORT_KEYS[idx](e) or 0, reverse=_SORT_REV[idx])

        while self.grid.count():
            if w := self.grid.takeAt(0).widget():
                w.deleteLater()

        for i, event in enumerate(filtered):
            self.grid.addWidget(
                EventCard(event, self._open_gallery, self._delete_event),
                *divmod(i, 4)
            )

        self.count_label.setText(f"{len(filtered)} events")

    def _open_gallery(self, event_data):
        eid, _, camera, cls, conf, dwell, *_ = event_data
        SnapshotGallery(eid, cls, camera, dwell or 0, conf, self).exec()

    def _delete_event(self, event_id: int):
        paths = delete_event(event_id)
        for path in paths:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                print(f"[DELETE] Could not remove {path}: {e}")
        QTimer.singleShot(0, self.refresh)


# ─────────────────────────────────────────────────────────────
#  Full-size snapshot viewer
# ─────────────────────────────────────────────────────────────

class FullSnapshotView(QDialog):
    def __init__(self, snapshot_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Snapshot")

        screen = self.screen().availableGeometry()
        self.setMinimumSize(min(1400, screen.width() - 100),
                            min(900, screen.height() - 100))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        img_label = QLabel()
        img_label.setObjectName("fullscreenVideo")
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if snapshot_path and os.path.exists(snapshot_path):
            pixmap = QPixmap(snapshot_path)
            scaled = pixmap.scaled(
                self.width(), self.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            img_label.setPixmap(scaled)

        img_label.setCursor(Qt.CursorShape.PointingHandCursor)
        img_label.mousePressEvent = lambda e: self.accept()

        layout.addWidget(img_label)