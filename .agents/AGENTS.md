# TreeTap Agent Rules

## Pre-Commit Verification Requirement

Before making any git commit or claiming a GUI change is ready, **ALWAYS** run an `xvfb-run` virtual X11 display test to verify that the application launches, initializes all models and dialogs, and exits cleanly without syntax, import, or PyQt6 runtime exceptions:

```bash
xvfb-run -a python3 -c "
import sys
from PyQt6.QtWidgets import QApplication
from treetap.gui import TreeTapSplashScreen, TreeTapMainWindow, launch_gui
from treetap.gui.ftp_dialog import FtpIngestDialog

app = QApplication(sys.argv)
splash = TreeTapSplashScreen()
splash.show()
splash.set_status('Xvfb pre-commit verification check...')

win = TreeTapMainWindow('treetap.duckdb')
win.show()
win.raise_()
win.activateWindow()

splash.finish(win)
splash.close()

dlg = FtpIngestDialog(win, conn=win.conn)
print('✅ Xvfb App Startup Verification Check: PASSED CLEANLY')
"
```
