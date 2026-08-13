"""
Tap Selector Sidebar widget for toggling individual tap signal traces.
"""

from typing import List, Dict, Callable
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QCheckBox,
    QPushButton,
    QLabel,
    QScrollArea,
    QFrame,
    QGroupBox,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QPixmap, QPainter


class ColorSwatchLabel(QLabel):
    def __init__(self, color: QColor, parent=None):
        super().__init__(parent)
        self.setFixedSize(18, 14)
        pix = QPixmap(18, 14)
        pix.fill(color)
        painter = QPainter(pix)
        painter.setPen(Qt.GlobalColor.black)
        painter.drawRect(0, 0, 17, 13)
        painter.end()
        self.setPixmap(pix)


class TapSelectorWidget(QWidget):
    # Signals emitted when selection changes
    tap_visibility_changed = pyqtSignal(int, bool)
    channel_visibility_changed = pyqtSignal(bool, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(200)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Title
        title = QLabel("Overlaid Tap Traces")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        main_layout.addWidget(title)

        # Channel Toggles Group
        ch_group = QGroupBox("Channels")
        ch_layout = QVBoxLayout(ch_group)
        ch_layout.setContentsMargins(5, 5, 5, 5)

        self.cb_ch1 = QCheckBox("Channel 1 (Green —)")
        self.cb_ch1.setChecked(True)
        self.cb_ch1.toggled.connect(self.on_channel_toggled)
        ch_layout.addWidget(self.cb_ch1)

        self.cb_ch2 = QCheckBox("Channel 2 (Red —)")
        self.cb_ch2.setChecked(True)
        self.cb_ch2.toggled.connect(self.on_channel_toggled)
        ch_layout.addWidget(self.cb_ch2)

        main_layout.addWidget(ch_group)

        # Selection Control Buttons
        btn_layout = QHBoxLayout()
        self.btn_select_all = QPushButton("Select All")
        self.btn_select_all.clicked.connect(self.select_all)
        btn_layout.addWidget(self.btn_select_all)

        self.btn_deselect_all = QPushButton("Deselect All")
        self.btn_deselect_all.clicked.connect(self.deselect_all)
        btn_layout.addWidget(self.btn_deselect_all)

        main_layout.addLayout(btn_layout)

        # Scrollable list for individual tap checkboxes
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.scroll_layout = QVBoxLayout(self.container)
        self.scroll_layout.setContentsMargins(2, 2, 2, 2)
        self.scroll_layout.setSpacing(4)
        self.scroll_layout.addStretch()

        self.scroll.setWidget(self.container)
        main_layout.addWidget(self.scroll)

        self.checkboxes: Dict[int, QCheckBox] = {}

    def populate_taps(self, taps: List[dict], colors: Dict[int, QColor]) -> None:
        # Clear previous widgets
        for i in reversed(range(self.scroll_layout.count() - 1)):
            w = self.scroll_layout.itemAt(i).widget()
            if w:
                w.deleteLater()

        self.checkboxes.clear()

        green_color = QColor("#00A000")
        red_color = QColor("#D32F2F")

        for t in taps:
            tap_id = t["tap_id"]

            row_frame = QFrame()
            row_layout = QHBoxLayout(row_frame)
            row_layout.setContentsMargins(4, 2, 4, 2)

            swatch_ch1 = ColorSwatchLabel(green_color)
            swatch_ch2 = ColorSwatchLabel(red_color)
            row_layout.addWidget(swatch_ch1)
            row_layout.addWidget(swatch_ch2)

            has_signal = len(t.get("ch1_samples", [])) > 0 or len(t.get("ch2_samples", [])) > 0
            sig_text = " (No Signal)" if not has_signal else ""

            cb = QCheckBox(f"Tap {tap_id}{sig_text}")
            cb.setChecked(True)

            # Lambda binding with tap_id
            cb.toggled.connect(lambda checked, tid=tap_id: self.on_tap_toggled(tid, checked))
            row_layout.addWidget(cb)
            row_layout.addStretch()

            self.checkboxes[tap_id] = cb
            self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, row_frame)

    def on_tap_toggled(self, tap_id: int, checked: bool) -> None:
        self.tap_visibility_changed.emit(tap_id, checked)

    def on_channel_toggled(self) -> None:
        self.channel_visibility_changed.emit(self.cb_ch1.isChecked(), self.cb_ch2.isChecked())

    def select_all(self) -> None:
        for cb in self.checkboxes.values():
            cb.setChecked(True)

    def deselect_all(self) -> None:
        for cb in self.checkboxes.values():
            cb.setChecked(False)
