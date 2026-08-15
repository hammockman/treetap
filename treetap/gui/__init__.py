"""
TreeTap PyQt6 GUI Package.
"""

import sys
from typing import Optional
from PyQt6.QtWidgets import QApplication
from treetap.gui.main_window import TreeTapMainWindow
from treetap.gui.splash import TreeTapSplashScreen


def launch_gui(db_path: Optional[str] = None) -> None:
    """
    Launches the TreeTap PyQt6 Graphical User Interface with a splash screen.
    """
    app = QApplication.instance() or QApplication(sys.argv)

    splash = TreeTapSplashScreen()
    splash.show()
    splash.set_status("Initializing TreeTap application...")

    try:
        splash.set_status("Connecting to DuckDB database & loading views...")
        window = TreeTapMainWindow(db_path=db_path)

        splash.set_status("Opening main window...")
        window.show()
        window.raise_()
        window.activateWindow()
        splash.finish(window)
        splash.close()
    except Exception as err:
        if "splash" in locals():
            try:
                splash.close()
            except Exception:
                pass
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(None, "Startup Error", f"An error occurred while launching TreeTap:\n{err}")
        sys.exit(1)

    sys.exit(app.exec())


__all__ = ["launch_gui", "TreeTapMainWindow", "TreeTapSplashScreen"]
