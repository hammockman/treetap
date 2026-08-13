"""
Dialog for viewing raw tap source CSV files (from zip archives or disk folders).
"""

from typing import Optional, Tuple
import os
import zipfile
import logging

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QLabel,
    QMessageBox,
    QApplication,
)
from PyQt6.QtGui import QFont, QKeySequence
from PyQt6.QtCore import QSettings

from treetap.v2.ftp_downloader import FtpDownloader

logger = logging.getLogger(__name__)


class SourceFileViewerDialog(QDialog):
    def __init__(self, tap_id: int, source_file: str, db_dir: str = ".", parent=None):
        super().__init__(parent)
        self.tap_id = tap_id
        self.source_file = source_file
        self.db_dir = db_dir

        self.setWindowTitle(f"Source File Inspection - Tap {tap_id}")
        self.resize(650, 500)

        layout = QVBoxLayout(self)

        # Header Info Label
        self.info_label = QLabel()
        self.info_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #222;")
        layout.addWidget(self.info_label)

        # Text Display Area
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        # Use clean monospace font
        font = QFont("Monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(10)
        self.text_edit.setFont(font)
        layout.addWidget(self.text_edit)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_copy = QPushButton("Copy to Clipboard")
        btn_copy.clicked.connect(self.copy_to_clipboard)
        btn_layout.addWidget(btn_copy)

        btn_layout.addStretch()

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

        # Load content
        self.load_content()

    def resolve_file_location(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Resolves (kind, archive_path, inner_or_file_path).
        kind can be 'zip' or 'file'.
        """
        if not self.source_file:
            return None, None, None

        cache_dir = os.path.expanduser("~/.cache/treetap/ftp_cache")
        os.makedirs(cache_dir, exist_ok=True)

        # Case 1: Zip file format "archive.zip/000000XXXX.csv"
        if ".zip" in self.source_file:
            parts = self.source_file.split(".zip", 1)
            zip_filename = parts[0] + ".zip"
            inner_filename = parts[1].lstrip("/\\")

            # Candidate search paths for zip file
            candidates = [
                zip_filename,
                os.path.join(self.db_dir, zip_filename),
                os.path.join("data/v2", os.path.basename(zip_filename)),
                os.path.join(self.db_dir, "data/v2", os.path.basename(zip_filename)),
                os.path.join(cache_dir, os.path.basename(zip_filename)),
            ]
            for cand in candidates:
                if os.path.exists(cand):
                    return "zip", cand, inner_filename
            return "zip", os.path.join(cache_dir, os.path.basename(zip_filename)), inner_filename

        # Case 2: Standard file format
        candidates = [
            self.source_file,
            os.path.join(self.db_dir, self.source_file),
            os.path.join("data/v2", os.path.basename(os.path.dirname(self.source_file)), os.path.basename(self.source_file)),
            os.path.join(cache_dir, os.path.basename(self.source_file)),
        ]
        for cand in candidates:
            if os.path.exists(cand):
                return "file", cand, None

        return "file", os.path.join(cache_dir, os.path.basename(self.source_file)), None

    def fetch_from_ftp_if_needed(self, local_path: str) -> bool:
        """
        If local_path does not exist, uses QSettings saved FTP credentials to download it.
        """
        if os.path.exists(local_path):
            return True

        settings = QSettings("TreeTap", "TreeTapSignals")
        host = settings.value("ftp/host", "", type=str)
        if not host:
            return False

        target_file = os.path.basename(local_path)
        remote_dir = settings.value("ftp/remote_dir", "/", type=str)

        try:
            self.info_label.setText(f"Tap {self.tap_id} | Fetching '{target_file}' from FTP server ({host})...")
            QApplication.processEvents()

            downloader = FtpDownloader(
                host=host,
                port=settings.value("ftp/port", 21, type=int),
                username=settings.value("ftp/username", "anonymous", type=str),
                password=settings.value("ftp/password", "", type=str),
                use_tls=settings.value("ftp/use_tls", False, type=bool),
                passive=settings.value("ftp/passive", True, type=bool),
            )
            return downloader.download_single_file(remote_dir, target_file, local_path)
        except Exception as e:
            logger.warning(f"FTP fetch error for {target_file}: {e}")
            return False

    def load_content(self) -> None:
        kind, path1, path2 = self.resolve_file_location()
        if not kind or not path1:
            self.info_label.setText(f"Tap {self.tap_id} | Source: {self.source_file} (Not Found)")
            self.text_edit.setPlainText("Source file location not specified or missing.")
            return

        # Attempt on-demand download from FTP if file does not exist locally
        if not os.path.exists(path1):
            self.fetch_from_ftp_if_needed(path1)

        try:
            if kind == "zip":
                if not os.path.exists(path1):
                    self.info_label.setText(f"Tap {self.tap_id} | Zip Archive Not Found: {os.path.basename(path1)}")
                    self.text_edit.setPlainText(f"Could not locate zip archive '{os.path.basename(path1)}' locally or via FTP.")
                    return

                with zipfile.ZipFile(path1, "r") as zf:
                    matching = [f for f in zf.namelist() if os.path.basename(f) == os.path.basename(path2)]
                    if not matching:
                        self.text_edit.setPlainText(f"File '{path2}' not found inside zip archive '{os.path.basename(path1)}'.")
                        return
                    raw_bytes = zf.read(matching[0])
                    content = raw_bytes.decode("utf-8", errors="replace")

                self.info_label.setText(f"Tap {self.tap_id} | Archive: {os.path.basename(path1)} | Entry: {path2}")
                self.text_edit.setPlainText(content)

            else:
                if not os.path.exists(path1):
                    self.info_label.setText(f"Tap {self.tap_id} | File Not Found: {os.path.basename(path1)}")
                    self.text_edit.setPlainText(f"Could not locate file '{os.path.basename(path1)}' locally or via FTP.")
                    return

                with open(path1, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

                self.info_label.setText(f"Tap {self.tap_id} | Path: {path1}")
                self.text_edit.setPlainText(content)

        except Exception as e:
            self.info_label.setText(f"Tap {self.tap_id} | Error reading source file")
            self.text_edit.setPlainText(f"Error opening source file:\n{e}")

        except Exception as e:
            self.info_label.setText(f"Tap {self.tap_id} | Error reading source file")
            self.text_edit.setPlainText(f"Error opening source file:\n{e}")

    def copy_to_clipboard(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.text_edit.toPlainText())
