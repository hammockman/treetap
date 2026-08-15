"""
FTP Connection & Ingestion Dialog for TreeTap GUI.
Allows user to configure FTP connection details, save preferences via QSettings,
and download V2 data files with real-time progress.
"""

from typing import Optional, List, Any
import os
import tempfile
import shutil

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QCheckBox,
    QPushButton,
    QLabel,
    QProgressBar,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QSettings, QThread, pyqtSignal

from treetap.v2.ftp_downloader import FtpDownloader


class FtpDownloadWorker(QThread):
    """
    Background worker thread for non-blocking FTP downloads.
    """
    progress_updated = pyqtSignal(int, int, str)  # current, total, filename
    download_finished = pyqtSignal(str, list)      # temp_dir, downloaded_paths
    download_failed = pyqtSignal(str)              # error_message

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        remote_dir: str,
        use_tls: bool,
        passive: bool,
        parent=None,
    ):
        super().__init__(parent)
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.remote_dir = remote_dir
        self.use_tls = use_tls
        self.passive = passive
        self.temp_dir: Optional[str] = None

    def run(self) -> None:
        try:
            self.temp_dir = tempfile.mkdtemp(prefix="treetap_ftp_")
            downloader = FtpDownloader(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                use_tls=self.use_tls,
                passive=self.passive,
            )

            def on_progress(idx: int, total: int, fname: str) -> None:
                self.progress_updated.emit(idx, total, fname)

            downloaded = downloader.download_v2_folder(
                remote_dir=self.remote_dir,
                local_target_dir=self.temp_dir,
                progress_callback=on_progress,
            )
            self.download_finished.emit(self.temp_dir, downloaded)
        except Exception as e:
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.download_failed.emit(str(e))


class FtpIngestDialog(QDialog):
    """
    Dialog for configuring FTP settings and launching FTP data ingestion.
    Remembers settings across sessions via QSettings.
    """

    def __init__(self, parent=None, conn: Optional[Any] = None):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("Ingest V2 Data via FTP")
        self.setMinimumWidth(440)
        self.settings = QSettings("TreeTap", "TreeTapSignals")

        self.temp_dir: Optional[str] = None
        self.downloaded_files: List[str] = []
        self.worker: Optional[FtpDownloadWorker] = None

        self.init_ui()
        self.load_settings()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header info label
        info_label = QLabel(
            "<b>FTP Server Connection</b><br>"
            "Enter details to download and ingest summary CSVs and zip archives."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Form layout for settings
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.edit_host = QLineEdit()
        self.edit_host.setPlaceholderText("e.g. ftp.example.com or 192.168.1.100")
        form_layout.addRow("Host / Server:", self.edit_host)

        self.spin_port = QSpinBox()
        self.spin_port.setRange(1, 65535)
        self.spin_port.setValue(21)
        form_layout.addRow("Port:", self.spin_port)

        self.edit_remote_dir = QLineEdit()
        self.edit_remote_dir.setPlaceholderText("e.g. /data/v2 or /")
        form_layout.addRow("Remote Directory:", self.edit_remote_dir)

        self.edit_username = QLineEdit()
        self.edit_username.setPlaceholderText("anonymous")
        form_layout.addRow("Username:", self.edit_username)

        self.edit_password = QLineEdit()
        self.edit_password.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow("Password:", self.edit_password)

        self.chk_passive = QCheckBox("Use Passive Mode (PASV)")
        self.chk_passive.setChecked(True)
        form_layout.addRow("", self.chk_passive)

        self.chk_tls = QCheckBox("Use FTPS (FTP over TLS)")
        self.chk_tls.setChecked(False)
        form_layout.addRow("", self.chk_tls)

        layout.addLayout(form_layout)

        # Progress controls (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #0066CC;")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        # Button box
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_connect = QPushButton("Connect & Ingest")
        self.btn_connect.setDefault(True)
        self.btn_connect.clicked.connect(self.on_start_download)
        btn_layout.addWidget(self.btn_connect)

        layout.addLayout(btn_layout)

    def load_settings(self) -> None:
        self.edit_host.setText(self.settings.value("ftp/host", "", type=str))
        self.spin_port.setValue(self.settings.value("ftp/port", 21, type=int))
        self.edit_remote_dir.setText(self.settings.value("ftp/remote_dir", "/", type=str))
        self.edit_username.setText(self.settings.value("ftp/username", "anonymous", type=str))
        self.edit_password.setText(self.settings.value("ftp/password", "", type=str))
        self.chk_passive.setChecked(self.settings.value("ftp/passive", True, type=bool))
        self.chk_tls.setChecked(self.settings.value("ftp/use_tls", False, type=bool))

    def save_settings(self) -> None:
        self.settings.setValue("ftp/host", self.edit_host.text().strip())
        self.settings.setValue("ftp/port", self.spin_port.value())
        self.settings.setValue("ftp/remote_dir", self.edit_remote_dir.text().strip() or "/")
        self.settings.setValue("ftp/username", self.edit_username.text().strip() or "anonymous")
        self.settings.setValue("ftp/password", self.edit_password.text())
        self.settings.setValue("ftp/passive", self.chk_passive.isChecked())
        self.settings.setValue("ftp/use_tls", self.chk_tls.isChecked())

    def on_start_download(self) -> None:
        host = self.edit_host.text().strip()
        if not host:
            QMessageBox.warning(self, "Input Error", "Please enter a valid FTP host/server address.")
            return

        self.save_settings()

        self.btn_connect.setEnabled(False)
        self.edit_host.setEnabled(False)
        self.spin_port.setEnabled(False)
        self.edit_remote_dir.setEnabled(False)
        self.edit_username.setEnabled(False)
        self.edit_password.setEnabled(False)

        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)
        self.status_label.setText("Connecting to FTP server...")

        self.worker = FtpDownloadWorker(
            host=host,
            port=self.spin_port.value(),
            username=self.edit_username.text().strip() or "anonymous",
            password=self.edit_password.text(),
            remote_dir=self.edit_remote_dir.text().strip() or "/",
            use_tls=self.chk_tls.isChecked(),
            passive=self.chk_passive.isChecked(),
            parent=self,
        )
        self.worker.progress_updated.connect(self.on_progress)
        self.worker.download_finished.connect(self.on_finished)
        self.worker.download_failed.connect(self.on_failed)
        self.worker.start()

    def on_progress(self, current: int, total: int, filename: str) -> None:
        if total > 0:
            pct = int((current / total) * 100)
            self.progress_bar.setValue(pct)
            self.status_label.setText(f"Downloading file {current} of {total}: {filename}")

    def on_finished(self, temp_dir: str, downloaded_files: list) -> None:
        self.temp_dir = temp_dir
        self.downloaded_files = downloaded_files
        self.accept()

    def on_failed(self, error_msg: str) -> None:
        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)

        self.btn_connect.setEnabled(True)
        self.edit_host.setEnabled(True)
        self.spin_port.setEnabled(True)
        self.edit_remote_dir.setEnabled(True)
        self.edit_username.setEnabled(True)
        self.edit_password.setEnabled(True)

        QMessageBox.critical(self, "FTP Download Error", f"Failed to download files from FTP server:\n\n{error_msg}")
