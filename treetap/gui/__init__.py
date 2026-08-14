"""
TreeTap PyQt6 GUI Package.
"""

from typing import Optional
from PyQt6.QtWidgets import QApplication
from treetap.gui.main_window import TreeTapMainWindow


def launch_gui(db_path: Optional[str] = None) -> None:
    """
    Launches the TreeTap PyQt6 Graphical User Interface.
    """
    app = QApplication(sys.argv)
    window = TreeTapMainWindow(db_path=db_path)
    window.show()
    sys.exit(app.exec())


__all__ = ["launch_gui", "TreeTapMainWindow"]
