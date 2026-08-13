"""
TreeTap PyQt6 GUI Package.
"""

import sys
from PyQt6.QtWidgets import QApplication
from treetap.gui.main_window import TreeTapMainWindow


def launch_gui(db_path: str = "treetap.duckdb") -> None:
    """
    Launches the TreeTap PyQt6 Graphical User Interface.
    """
    app = QApplication(sys.argv)
    window = TreeTapMainWindow(db_path=db_path)
    window.show()
    sys.exit(app.exec())


__all__ = ["launch_gui", "TreeTapMainWindow"]
