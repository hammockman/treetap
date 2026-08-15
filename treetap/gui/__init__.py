"""
TreeTap PyQt6 GUI Package.
"""

import sys
from typing import Optional


def launch_gui(db_path: Optional[str] = None) -> None:
    """
    Launches the TreeTap PyQt6 Graphical User Interface with a splash screen.
    Instantly displays splash window before loading heavy DuckDB / pyqtgraph modules.
    """
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    from treetap.gui.splash import TreeTapSplashScreen
    splash = TreeTapSplashScreen()
    splash.show()
    splash.set_status("Initializing TreeTap application...")
    app.processEvents()

    try:
        splash.set_status("Connecting to DuckDB database & loading views...")
        app.processEvents()

        from treetap.gui.main_window import TreeTapMainWindow
        window = TreeTapMainWindow(db_path=db_path)

        splash.set_status("Opening main window...")
        app.processEvents()

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


def __getattr__(name: str):
    if name == "TreeTapMainWindow":
        from treetap.gui.main_window import TreeTapMainWindow
        return TreeTapMainWindow
    elif name == "TreeTapSplashScreen":
        from treetap.gui.splash import TreeTapSplashScreen
        return TreeTapSplashScreen
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = ["launch_gui", "TreeTapMainWindow", "TreeTapSplashScreen"]
