"""
TreeTap Application Splash Screen Widget.
"""

import os
from PyQt6.QtWidgets import QSplashScreen, QApplication
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore import Qt


class TreeTapSplashScreen(QSplashScreen):
    """
    Branded splash screen displayed during GUI startup to provide immediate visual feedback.
    """

    def __init__(self):
        pixmap = QPixmap(500, 280)
        pixmap.fill(QColor("#FFFFFF"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Outer border
        painter.setPen(QColor("#E0E0E0"))
        painter.drawRect(0, 0, 499, 279)

        # Header accent bar
        painter.fillRect(0, 0, 500, 6, QColor("#1B6ACB"))

        # App Icon
        assets_dir = os.path.join(os.path.dirname(__file__), "assets")
        icon_path = os.path.join(assets_dir, "app_icon.png")
        if os.path.exists(icon_path):
            icon_pix = QPixmap(icon_path).scaled(
                110, 110, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            painter.drawPixmap(25, 75, icon_pix)

        # Title
        font_title = QFont("Sans-Serif", 19, QFont.Weight.Bold)
        painter.setFont(font_title)
        painter.setPen(QColor("#0D47A1"))
        painter.drawText(155, 110, "TreeTap Data Manager")

        # Subtitle & Version
        font_sub = QFont("Sans-Serif", 10, QFont.Weight.Normal)
        painter.setFont(font_sub)
        painter.setPen(QColor("#555555"))
        painter.drawText(155, 135, "Tree Acoustic Pulse & Propagation Analysis")

        font_ver = QFont("Sans-Serif", 9, QFont.Weight.Bold)
        painter.setFont(font_ver)
        painter.setPen(QColor("#1B6ACB"))
        painter.drawText(155, 160, "Version 0.1.0")

        # Footer message bar container
        painter.fillRect(0, 235, 500, 45, QColor("#F8F9FA"))
        painter.setPen(QColor("#E9ECEF"))
        painter.drawLine(0, 235, 500, 235)

        painter.end()
        super().__init__(pixmap)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)

    def set_status(self, message: str) -> None:
        """
        Updates the splash screen loading status message.
        """
        self.showMessage(
            f"  {message}",
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            QColor("#333333"),
        )
        QApplication.processEvents()
