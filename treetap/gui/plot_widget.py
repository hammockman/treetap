"""
PyQtGraph Plot Widget for displaying overlaid CH1 and CH2 TreeTap acoustic velocity signals on a single plot axis.
"""

from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

# Distinct color palette for overlaid tap traces
TAP_COLORS = [
    "#00E5FF",  # Cyan
    "#FF4081",  # Pink
    "#76FF03",  # Bright Green
    "#FFD600",  # Amber/Yellow
    "#D500F9",  # Purple
    "#FF6D00",  # Orange
    "#00E676",  # Emerald Green
    "#651FFF",  # Deep Purple
    "#1DE9B6",  # Teal
    "#FF1744",  # Red
    "#3D5AFE",  # Indigo
    "#F50057",  # Deep Pink
]


class TapPlotWidget(QWidget):
    """
    Plots overlaid CH1 (solid) and CH2 (dashed) signals for multiple taps on a single axis.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.plot_curves: Dict[int, Dict[str, pg.PlotDataItem]] = {}  # tap_id -> {"ch1": item, "ch2": item}
        self.tap_colors: Dict[int, QColor] = {}
        self.visible_taps: set = set()
        self.highlighted_taps: set = set()
        self.show_ch1: bool = True
        self.show_ch2: bool = True

        self.marker_lines: List[pg.InfiniteLine] = []
        self._last_cursor_str: str = "Cursor: X = --- μs, Y = ---"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Info Header Bar (shows cursor coordinates, signal legend info, and marker delta-t)
        top_bar = QHBoxLayout()
        self.info_label = QLabel(self._last_cursor_str)
        self.info_label.setStyleSheet("font-weight: bold; color: #444;")
        top_bar.addWidget(self.info_label)
        top_bar.addStretch()

        self.btn_clear_markers = QPushButton("Clear Markers")
        self.btn_clear_markers.setToolTip("Clear placed vertical measurement markers")
        self.btn_clear_markers.clicked.connect(self.clear_markers)
        top_bar.addWidget(self.btn_clear_markers)

        self.btn_reset_view = QPushButton("Reset View")
        self.btn_reset_view.setToolTip("Reset plot zoom to fit all visible traces")
        self.btn_reset_view.clicked.connect(self.reset_view)
        top_bar.addWidget(self.btn_reset_view)

        layout.addLayout(top_bar)

        # Configure pyqtgraph plot widget
        pg.setConfigOption("background", "w")  # Clean white background
        pg.setConfigOption("foreground", "k")  # Black axes/labels
        pg.setConfigOption("antialias", True)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.showGrid(x=False, y=False)
        self.plot_widget.setLabel("left", "Signal Amplitude (ADC Counts)")
        self.plot_widget.setLabel("bottom", "Time (μs)")

        # Add baseline horizontal line at Y = 2048 (representing X-axis baseline)
        baseline_pen = pg.mkPen(QColor("#777777"), width=1.0, style=Qt.PenStyle.DashLine)
        self.baseline_2048 = pg.InfiniteLine(pos=2048, angle=0, movable=False, pen=baseline_pen)
        self.plot_widget.addItem(self.baseline_2048, ignoreBounds=True)

        # Add Crosshairs (Blue dashed lines for distinct contrast against green/red signals)
        cursor_pen = pg.mkPen(QColor("#0066FF"), width=1.2, style=Qt.PenStyle.DashLine)
        self.v_line = pg.InfiniteLine(angle=90, movable=False, pen=cursor_pen)
        self.h_line = pg.InfiniteLine(angle=0, movable=False, pen=cursor_pen)
        self.plot_widget.addItem(self.v_line, ignoreBounds=True)
        self.plot_widget.addItem(self.h_line, ignoreBounds=True)

        self.plot_widget.scene().sigMouseMoved.connect(self.on_mouse_moved)
        self.plot_widget.scene().sigMouseClicked.connect(self.on_plot_clicked)

        layout.addWidget(self.plot_widget)

    def get_color_for_tap(self, idx: int) -> QColor:
        color_hex = TAP_COLORS[idx % len(TAP_COLORS)]
        return QColor(color_hex)

    def clear_plots(self) -> None:
        vb = self.plot_widget.getViewBox()
        vb.setLimits(xMin=None, xMax=None, yMin=None, yMax=None)
        self.plot_widget.clear()
        # Re-add baseline line at 2048 and crosshairs
        self.plot_widget.addItem(self.baseline_2048, ignoreBounds=True)
        self.plot_widget.addItem(self.v_line, ignoreBounds=True)
        self.plot_widget.addItem(self.h_line, ignoreBounds=True)
        # Clear vertical measurement markers when clearing/reloading plots
        self.clear_markers()
        self.plot_curves.clear()
        self.tap_colors.clear()

    def set_tap_signals(
        self,
        taps_data: List[Dict[str, Any]],
        visible_taps: Optional[set] = None,
        show_ch1: bool = True,
        show_ch2: bool = True,
    ) -> Dict[int, QColor]:
        """
        Populates plot with overlaid signals for the provided list of tap dictionaries.
        Each tap dict should have: tap_id, rate_hz, delay_us, ch1_samples, ch2_samples.
        """
        self.clear_plots()
        self.show_ch1 = show_ch1
        self.show_ch2 = show_ch2

        if visible_taps is None:
            self.visible_taps = {t["tap_id"] for t in taps_data}
        else:
            self.visible_taps = visible_taps

        CH1_COLOR = QColor("#00A000")  # Green
        CH2_COLOR = QColor("#D32F2F")  # Red

        for idx, tap_info in enumerate(taps_data):
            tap_id = tap_info["tap_id"]
            self.tap_colors[tap_id] = CH1_COLOR

            ch1_samples = np.array(tap_info.get("ch1_samples", []), dtype=float)
            ch2_samples = np.array(tap_info.get("ch2_samples", []), dtype=float)
            rate_hz = tap_info.get("rate_hz", 500000.0)
            delay_us = tap_info.get("delay_us", 0.0)

            n_samples = max(len(ch1_samples), len(ch2_samples))
            if n_samples == 0:
                continue

            time_us = (np.arange(n_samples) / rate_hz) * 1e6

            curves = {}

            # CH1 curve (Green Solid line)
            if len(ch1_samples) > 0:
                pen_ch1 = pg.mkPen(color=CH1_COLOR, width=1.5, style=Qt.PenStyle.SolidLine)
                item_ch1 = self.plot_widget.plot(
                    time_us[: len(ch1_samples)],
                    ch1_samples,
                    pen=pen_ch1,
                )
                item_ch1.setVisible(tap_id in self.visible_taps and self.show_ch1)
                curves["ch1"] = item_ch1

            # CH2 curve (Red Solid line)
            if len(ch2_samples) > 0:
                pen_ch2 = pg.mkPen(color=CH2_COLOR, width=1.5, style=Qt.PenStyle.SolidLine)
                item_ch2 = self.plot_widget.plot(
                    time_us[: len(ch2_samples)],
                    ch2_samples,
                    pen=pen_ch2,
                )
                item_ch2.setVisible(tap_id in self.visible_taps and self.show_ch2)
                curves["ch2"] = item_ch2

            self.plot_curves[tap_id] = curves

        self.reset_view()
        if self.highlighted_taps:
            self.highlight_taps(self.highlighted_taps)
        return self.tap_colors

    def highlight_taps(self, selected_tap_ids: set) -> None:
        """
        Highlights selected tap(s) with wider, fully opaque lines (width=2.5, alpha=255)
        and brings them to the front (zValue=10).
        Lowers opacity and line width (width=1.0, alpha=65) for non-selected tap traces.
        """
        self.highlighted_taps = set(selected_tap_ids)
        has_highlight = len(self.highlighted_taps) > 0

        CH1_BASE = QColor("#00A000")
        CH2_BASE = QColor("#D32F2F")

        for tap_id, curves in self.plot_curves.items():
            is_selected = tap_id in self.highlighted_taps

            if not has_highlight:
                # Default style when nothing specific is highlighted
                c1 = QColor(CH1_BASE)
                c2 = QColor(CH2_BASE)
                c1.setAlpha(220)
                c2.setAlpha(220)
                width = 1.5
                z_val = 1
            elif is_selected:
                # Highlighted tap: thick, 100% opaque, top Z-layer
                c1 = QColor(CH1_BASE)
                c2 = QColor(CH2_BASE)
                c1.setAlpha(255)
                c2.setAlpha(255)
                width = 2.5
                z_val = 10
            else:
                # De-emphasized tap: thin, ~25% opacity, bottom Z-layer
                c1 = QColor(CH1_BASE)
                c2 = QColor(CH2_BASE)
                c1.setAlpha(65)
                c2.setAlpha(65)
                width = 1.0
                z_val = 1

            if "ch1" in curves:
                curves["ch1"].setPen(pg.mkPen(color=c1, width=width, style=Qt.PenStyle.SolidLine))
                curves["ch1"].setZValue(z_val)

            if "ch2" in curves:
                curves["ch2"].setPen(pg.mkPen(color=c2, width=width, style=Qt.PenStyle.SolidLine))
                curves["ch2"].setZValue(z_val)

    def set_tap_visibility(self, tap_id: int, visible: bool) -> None:
        if tap_id in self.visible_taps and not visible:
            self.visible_taps.remove(tap_id)
        elif tap_id not in self.visible_taps and visible:
            self.visible_taps.add(tap_id)

        if tap_id in self.plot_curves:
            curves = self.plot_curves[tap_id]
            if "ch1" in curves:
                curves["ch1"].setVisible(visible and self.show_ch1)
            if "ch2" in curves:
                curves["ch2"].setVisible(visible and self.show_ch2)

    def set_channel_visibility(self, show_ch1: bool, show_ch2: bool) -> None:
        self.show_ch1 = show_ch1
        self.show_ch2 = show_ch2

        for tap_id, curves in self.plot_curves.items():
            is_tap_visible = tap_id in self.visible_taps
            if "ch1" in curves:
                curves["ch1"].setVisible(is_tap_visible and self.show_ch1)
            if "ch2" in curves:
                curves["ch2"].setVisible(is_tap_visible and self.show_ch2)

    def reset_view(self) -> None:
        vb = self.plot_widget.getViewBox()
        vb.setLimits(xMin=None, xMax=None, yMin=None, yMax=None)

        x_min, x_max = None, None
        y_min, y_max = None, None

        for item in self.plot_widget.plotItem.items:
            if isinstance(item, pg.PlotDataItem) and item.isVisible():
                x_data, y_data = item.getData()
                if x_data is not None and len(x_data) > 0:
                    xmin_i, xmax_i = float(np.min(x_data)), float(np.max(x_data))
                    x_min = xmin_i if x_min is None else min(x_min, xmin_i)
                    x_max = xmax_i if x_max is None else max(x_max, xmax_i)
                if y_data is not None and len(y_data) > 0:
                    ymin_i, ymax_i = float(np.min(y_data)), float(np.max(y_data))
                    y_min = ymin_i if y_min is None else min(y_min, ymin_i)
                    y_max = ymax_i if y_max is None else max(y_max, ymax_i)

        if x_min is None or x_max is None or y_min is None or y_max is None:
            self.plot_widget.enableAutoRange()
            return

        x_margin = (x_max - x_min) * 0.02 if x_max > x_min else 100.0
        y_margin = (y_max - y_min) * 0.05 if y_max > y_min else 100.0

        x0, x1 = x_min - x_margin, x_max + x_margin
        y0, y1 = y_min - y_margin, y_max + y_margin

        vb.setLimits(xMin=x0, xMax=x1, yMin=y0, yMax=y1)
        vb.setRange(xRange=(x0, x1), yRange=(y0, y1), padding=0)

    def clear_markers(self) -> None:
        """
        Removes all placed vertical measurement markers from the plot.
        """
        for marker in self.marker_lines:
            try:
                self.plot_widget.removeItem(marker)
            except Exception:
                pass
        self.marker_lines.clear()
        self.update_marker_display()

    def update_marker_display(self) -> None:
        """
        Updates the top info label with cursor coordinates and marker delta-t.
        """
        base_str = self._last_cursor_str
        if not self.marker_lines:
            self.info_label.setText(base_str)
            return

        if len(self.marker_lines) == 1:
            x1 = self.marker_lines[0].value()
            self.info_label.setText(f"{base_str}  |  M1 = {x1:.1f} μs")
        elif len(self.marker_lines) >= 2:
            x1 = self.marker_lines[0].value()
            x2 = self.marker_lines[1].value()
            delta_t = abs(x2 - x1)
            self.info_label.setText(
                f"{base_str}  |  M1 = {x1:.1f} μs, M2 = {x2:.1f} μs  |  Δt = {delta_t:.1f} μs"
            )

    def on_plot_clicked(self, evt: Any) -> None:
        """
        Handles mouse clicks on the plot canvas to place draggable vertical marker lines.
        Allows up to 2 markers before clearing/cycling.
        """
        if evt.button() != Qt.MouseButton.LeftButton:
            return

        pos = evt.scenePos()
        if not self.plot_widget.sceneBoundingRect().contains(pos):
            return

        mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
        click_x = float(mouse_point.x())

        # If user clicked directly on an existing marker to drag it, don't spawn a new one
        vb_range = self.plot_widget.plotItem.vb.viewRange()[0]
        x_span = vb_range[1] - vb_range[0]
        for marker in self.marker_lines:
            if abs(marker.value() - click_x) < (x_span * 0.015):
                return

        # If 2 markers already exist, clear and start fresh with Marker 1
        if len(self.marker_lines) >= 2:
            self.clear_markers()

        idx = len(self.marker_lines) + 1
        color_hex = "#FF7F0E" if idx == 1 else "#9467BD"
        hover_color_hex = "#FF9933" if idx == 1 else "#B388FF"

        pen = pg.mkPen(color=QColor(color_hex), width=2.0, style=Qt.PenStyle.SolidLine)
        hover_pen = pg.mkPen(color=QColor(hover_color_hex), width=3.0, style=Qt.PenStyle.SolidLine)

        marker = pg.InfiniteLine(
            pos=click_x,
            angle=90,
            movable=True,
            pen=pen,
            hoverPen=hover_pen,
            label=f"M{idx}: {{value:.1f}} μs",
            labelOpts={"position": 0.95, "color": color_hex, "movable": True},
        )
        marker.sigPositionChanged.connect(self.update_marker_display)
        self.plot_widget.addItem(marker, ignoreBounds=True)
        self.marker_lines.append(marker)

        self.update_marker_display()

    def on_mouse_moved(self, pos: Any) -> None:
        if isinstance(pos, tuple):
            pos = pos[0]
        if self.plot_widget.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            self.v_line.setPos(mouse_point.x())
            self.h_line.setPos(mouse_point.y())
            self._last_cursor_str = f"Cursor: X = {mouse_point.x():.1f} μs, Y = {mouse_point.y():.1f}"
            self.update_marker_display()
