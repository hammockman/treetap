"""
Version 2 FTP Downloader module.
Downloads V2 summary CSV files and zip archives from remote FTP/FTPS servers with auto-reconnection and retry handling.
"""

from typing import Callable, Optional, List, Dict, Any
import os
import ftplib
import time
import logging

import re

# Regex matching TreeTap V2 zip archive pattern: YYYY-MM-DD-HH-MM-SS.zip (e.g. 2026-10-08-10-11-12.zip)
V2_ZIP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}\.zip$", re.IGNORECASE)

logger = logging.getLogger(__name__)


class FtpDownloader:
    """
    Wraps Python's standard ftplib.FTP and ftplib.FTP_TLS to download TreeTap V2 files.
    Includes auto-reconnection and retry mechanisms to handle embedded/Android server timeouts.
    """

    def __init__(
        self,
        host: str,
        port: int = 21,
        username: str = "anonymous",
        password: str = "",
        use_tls: bool = False,
        passive: bool = True,
    ):
        self.host = host
        self.port = int(port)
        self.username = username or "anonymous"
        self.password = password
        self.use_tls = use_tls
        self.passive = passive
        self.ftp: Optional[Any] = None

    def _connect(self, remote_dir: str) -> Any:
        if self.ftp:
            try:
                self.ftp.quit()
            except Exception:
                try:
                    self.ftp.close()
                except Exception:
                    pass
            self.ftp = None

        if self.use_tls:
            ftp = ftplib.FTP_TLS()
            ftp.connect(host=self.host, port=self.port, timeout=15)
            ftp.login(user=self.username, passwd=self.password)
            ftp.prot_p()  # Secure data connection
        else:
            ftp = ftplib.FTP()
            ftp.connect(host=self.host, port=self.port, timeout=15)
            ftp.login(user=self.username, passwd=self.password)

        ftp.set_pasv(self.passive)

        if remote_dir and remote_dir != "/":
            try:
                ftp.cwd(remote_dir)
            except ftplib.error_perm:
                if remote_dir.startswith("/"):
                    ftp.cwd(remote_dir.lstrip("/"))
                else:
                    raise
        self.ftp = ftp
        return ftp

    def download_v2_folder(
        self,
        remote_dir: str,
        local_target_dir: str,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[str]:
        """
        Connects to the FTP server, lists remote files matching treetap-*.csv and *.zip in remote_dir,
        and downloads them into local_target_dir with retry and auto-reconnection logic.
        """
        os.makedirs(local_target_dir, exist_ok=True)
        self._connect(remote_dir)

        # List files with retry
        remote_files: List[str] = []
        for attempt in range(3):
            try:
                remote_files = self.ftp.nlst()
                break
            except Exception as e:
                logger.warning(f"FTP nlst attempt {attempt+1} failed ({e}). Reconnecting...")
                time.sleep(0.5)
                self._connect(remote_dir)

        if not remote_files:
            try:
                lines: List[str] = []
                self.ftp.dir(lines.append)
                for line in lines:
                    parts = line.split()
                    if parts:
                        remote_files.append(parts[-1])
            except Exception:
                pass

        # Filter relevant files: summary CSVs (*.csv) and timestamped zip archives matching YYYY-MM-DD-HH-MM-SS.zip
        target_files = []
        for f in remote_files:
            flow = f.lower().strip()
            if flow.endswith(".csv"):
                target_files.append(f)
            elif flow.endswith(".zip") and V2_ZIP_PATTERN.match(f.strip()):
                target_files.append(f)
            else:
                logger.info(f"Skipping non-matching remote FTP file '{f}'")

        downloaded_paths: List[str] = []
        total_count = len(target_files)

        for idx, filename in enumerate(target_files, start=1):
            if progress_callback:
                progress_callback(idx, total_count, filename)

            local_path = os.path.join(local_target_dir, filename)
            download_success = False

            for attempt in range(3):
                try:
                    if not self.ftp:
                        self._connect(remote_dir)
                    time.sleep(0.15)
                    try:
                        self.ftp.voidcmd("NOOP")
                    except Exception:
                        pass
                    with open(local_path, "wb") as f:
                        self.ftp.retrbinary(f"RETR {filename}", f.write)
                    download_success = True
                    break
                except Exception as err:
                    logger.warning(f"FTP RETR attempt {attempt+1} failed for {filename}: {err}. Reconnecting...")
                    time.sleep(0.5)
                    try:
                        self._connect(remote_dir)
                    except Exception as conn_err:
                        logger.error(f"FTP reconnect error: {conn_err}")

            if download_success:
                downloaded_paths.append(local_path)

        if self.ftp:
            try:
                self.ftp.quit()
            except Exception:
                try:
                    self.ftp.close()
                except Exception:
                    pass

        return downloaded_paths

    def download_single_file(
        self,
        remote_dir: str,
        filename: str,
        local_destination_path: str,
    ) -> bool:
        """
        Connects to FTP server and downloads a single specified file to local_destination_path.
        """
        os.makedirs(os.path.dirname(os.path.abspath(local_destination_path)), exist_ok=True)
        self._connect(remote_dir)

        for attempt in range(3):
            try:
                if not self.ftp:
                    self._connect(remote_dir)
                time.sleep(0.05)
                with open(local_destination_path, "wb") as f:
                    self.ftp.retrbinary(f"RETR {filename}", f.write)
                return True
            except Exception as e:
                logger.warning(f"FTP single file RETR attempt {attempt+1} failed: {e}. Reconnecting...")
                time.sleep(0.5)
                try:
                    self._connect(remote_dir)
                except Exception:
                    pass

        return False
