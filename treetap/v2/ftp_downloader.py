"""
Version 2 FTP Downloader module.
Downloads V2 summary CSV files and zip archives from remote FTP/FTPS servers.
"""

from typing import Callable, Optional, List, Dict, Any
import os
import ftplib
import logging

logger = logging.getLogger(__name__)


class FtpDownloader:
    """
    Wraps Python's standard ftplib.FTP and ftplib.FTP_TLS to download TreeTap V2 files.
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

    def download_v2_folder(
        self,
        remote_dir: str,
        local_target_dir: str,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[str]:
        """
        Connects to the FTP server, lists remote files matching treetap-*.csv and *.zip in remote_dir,
        and downloads them into local_target_dir.

        Returns list of downloaded local file paths.
        """
        os.makedirs(local_target_dir, exist_ok=True)

        if self.use_tls:
            ftp = ftplib.FTP_TLS()
            ftp.connect(host=self.host, port=self.port, timeout=30)
            ftp.login(user=self.username, passwd=self.password)
            ftp.prot_p()  # Secure data connection
        else:
            ftp = ftplib.FTP()
            ftp.connect(host=self.host, port=self.port, timeout=30)
            ftp.login(user=self.username, passwd=self.password)

        ftp.set_pasv(self.passive)

        if remote_dir and remote_dir != "/":
            ftp.cwd(remote_dir)

        # List files in current remote directory
        remote_files = []
        try:
            remote_files = ftp.nlst()
        except ftplib.error_perm:
            # Fallback if nlst is restricted
            lines = []
            ftp.dir(lines.append)
            for line in lines:
                parts = line.split()
                if parts:
                    remote_files.append(parts[-1])

        # Filter relevant files: summary CSVs (treetap-*.csv) and zip archives (*.zip)
        target_files = [
            f for f in remote_files
            if f.lower().endswith(".zip") or (f.lower().endswith(".csv") and "treetap" in f.lower())
        ]

        if not target_files:
            # If no specific treetap files found, list all .csv and .zip files
            target_files = [f for f in remote_files if f.lower().endswith(".zip") or f.lower().endswith(".csv")]

        downloaded_paths = []
        total_count = len(target_files)

        for idx, filename in enumerate(target_files, start=1):
            if progress_callback:
                progress_callback(idx, total_count, filename)

            local_path = os.path.join(local_target_dir, filename)
            with open(local_path, "wb") as f:
                ftp.retrbinary(f"RETR {filename}", f.write)

            downloaded_paths.append(local_path)

        try:
            ftp.quit()
        except Exception:
            ftp.close()

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

        if self.use_tls:
            ftp = ftplib.FTP_TLS()
            ftp.connect(host=self.host, port=self.port, timeout=15)
            ftp.login(user=self.username, passwd=self.password)
            ftp.prot_p()
        else:
            ftp = ftplib.FTP()
            ftp.connect(host=self.host, port=self.port, timeout=15)
            ftp.login(user=self.username, passwd=self.password)

        ftp.set_pasv(self.passive)

        if remote_dir and remote_dir != "/":
            ftp.cwd(remote_dir)

        with open(local_destination_path, "wb") as f:
            ftp.retrbinary(f"RETR {filename}", f.write)

        try:
            ftp.quit()
        except Exception:
            ftp.close()

        return os.path.exists(local_destination_path)
