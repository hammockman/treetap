"""
PyQt6 Dialog for Version 1 TreeTap serial data acquisition and log file ingestion.
Supports live serial capture (/dev/ttyUSB0, COM ports, 57600 baud, 8N1, RTS/CTS) and file import (*.down, *.txt, *.log, *.*).
"""

from typing import Optional, List
import os
import logging

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QComboBox,
    QCheckBox,
    QDoubleSpinBox,
    QPushButton,
    QTextEdit,
    QFileDialog,
    QMessageBox,
    QApplication,
)
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings

from treetap.v1.serial_comm import V1SerialWorker, list_available_serial_ports
from treetap.v1.ingest import ingest_v1_data

logger = logging.getLogger(__name__)


class SerialWorkerThread(QThread):
    line_received = pyqtSignal(str)
    connection_error = pyqtSignal(str)

    def __init__(self, port: str, baudrate: int, rtscts: bool, parent=None):
        super().__init__(parent)
        self.port = port
        self.baudrate = baudrate
        self.rtscts = rtscts
        self.worker: Optional[V1SerialWorker] = None

    def run(self):
        self.worker = V1SerialWorker(
            port=self.port,
            baudrate=self.baudrate,
            rtscts=self.rtscts,
            on_line_received=lambda line: self.line_received.emit(line),
            on_error=lambda err: self.connection_error.emit(err),
        )
        self.worker.run()

    def stop(self):
        if self.worker:
            self.worker.stop()
        self.requestInterruption()
        self.quit()
        if not self.wait(2000):
            self.terminate()
            self.wait(500)


class V1IngestDialog(QDialog):
    def __init__(self, parent=None, initial_port: Optional[str] = None, target_ingest_id: Optional[int] = None):
        super().__init__(parent)
        self.setWindowTitle("Ingest Version 1 TreeTap Data (Serial / File)")
        self.resize(680, 560)

        self.target_ingest_id = target_ingest_id
        self.worker_thread: Optional[SerialWorkerThread] = None
        self.loaded_file_name: Optional[str] = None

        layout = QVBoxLayout(self)

        # 1. Serial Port Connection Group
        conn_group = QGroupBox("Serial Port Configuration")
        conn_layout = QVBoxLayout(conn_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Serial Port:"))
        
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)  # Freeform entry for any custom port (/dev/ttyUSB0, COM3, etc.)
        self.populate_serial_ports()
        if initial_port:
            idx = self.port_combo.findText(initial_port)
            if idx >= 0:
                self.port_combo.setCurrentIndex(idx)
            else:
                self.port_combo.setCurrentText(initial_port)
        row1.addWidget(self.port_combo, stretch=1)

        btn_refresh_ports = QPushButton("Refresh Ports")
        btn_refresh_ports.clicked.connect(self.populate_serial_ports)
        row1.addWidget(btn_refresh_ports)

        row1.addSpacing(15)
        row1.addWidget(QLabel("Baud Rate:"))
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["57600", "115200", "38400", "19200", "9600"])
        row1.addWidget(self.baud_combo)

        conn_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.chk_rtscts = QCheckBox("Hardware Flow Control (RTS/CTS)")
        self.chk_rtscts.setChecked(True)
        row2.addWidget(self.chk_rtscts)

        row2.addSpacing(15)
        row2.addWidget(QLabel("Probe Separation:"))
        self.spin_separation = QDoubleSpinBox()
        self.spin_separation.setRange(0.0, 10000.0)
        self.spin_separation.setDecimals(1)
        self.spin_separation.setSuffix(" cm")
        self.spin_separation.setValue(100.0)
        row2.addWidget(self.spin_separation)

        row2.addStretch()

        self.btn_connect = QPushButton("Connect & Listen")
        self.btn_connect.setStyleSheet("font-weight: bold; background-color: #2E7D32; color: white;")
        self.btn_connect.clicked.connect(self.start_listening)
        row2.addWidget(self.btn_connect)

        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.setEnabled(False)
        self.btn_disconnect.clicked.connect(self.stop_listening)
        row2.addWidget(self.btn_disconnect)

        conn_layout.addLayout(row2)

        self.status_label = QLabel("Status: Disconnected")
        self.status_label.setStyleSheet("font-style: italic; color: #666;")
        conn_layout.addWidget(self.status_label)

        layout.addWidget(conn_group)

        # 2. Live Terminal & Buffer Display
        terminal_group = QGroupBox("ASCII Data Terminal / Buffer")
        terminal_layout = QVBoxLayout(terminal_group)

        self.terminal_edit = QTextEdit()
        font = QFont("Monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(9)
        self.terminal_edit.setFont(font)
        self.terminal_edit.setPlaceholderText(
            "Captured serial transmission or loaded file lines will appear here..."
        )
        terminal_layout.addWidget(self.terminal_edit)

        term_btn_layout = QHBoxLayout()
        btn_clear_term = QPushButton("Clear Buffer")
        btn_clear_term.clicked.connect(self.clear_buffer)
        term_btn_layout.addWidget(btn_clear_term)

        term_btn_layout.addStretch()

        btn_load_file = QPushButton("Load V1 File (.down / .txt)...")
        btn_load_file.clicked.connect(self.on_load_file)
        term_btn_layout.addWidget(btn_load_file)

        terminal_layout.addLayout(term_btn_layout)
        layout.addWidget(terminal_group)

        # 3. Action Buttons
        action_layout = QHBoxLayout()

        self.btn_ingest = QPushButton("Import Captured Taps into Database")
        self.btn_ingest.setStyleSheet("font-weight: bold; font-size: 13px; padding: 6px 12px;")
        self.btn_ingest.clicked.connect(self.on_ingest_clicked)
        action_layout.addWidget(self.btn_ingest)

        action_layout.addStretch()

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.reject)
        action_layout.addWidget(btn_close)

        layout.addLayout(action_layout)

        # Restore saved settings
        self.load_settings()

    def populate_serial_ports(self) -> None:
        current_text = self.port_combo.currentText()
        self.port_combo.clear()

        detected = list_available_serial_ports()
        if not detected:

            detected = ["/dev/ttyUSB0", "/dev/ttyS0", "COM1", "COM3"]

        self.port_combo.addItems(detected)
        if current_text:
            self.port_combo.setEditText(current_text)
        elif detected:
            self.port_combo.setCurrentIndex(0)

    def load_settings(self) -> None:
        settings = QSettings("TreeTap", "TreeTapSignals")
        saved_port = settings.value("v1/port", "/dev/ttyUSB0", type=str)
        saved_baud = settings.value("v1/baudrate", "57600", type=str)
        saved_rtscts = settings.value("v1/flow_control", True, type=bool)
        saved_sep = settings.value("v1/probe_separation_cm", 100.0, type=float)

        if saved_port:
            self.port_combo.setEditText(saved_port)

        idx = self.baud_combo.findText(saved_baud)
        if idx >= 0:
            self.baud_combo.setCurrentIndex(idx)

        self.chk_rtscts.setChecked(saved_rtscts)
        self.spin_separation.setValue(saved_sep)

    def save_settings(self) -> None:
        settings = QSettings("TreeTap", "TreeTapSignals")
        settings.setValue("v1/port", self.port_combo.currentText().strip())
        settings.setValue("v1/baudrate", self.baud_combo.currentText())
        settings.setValue("v1/flow_control", self.chk_rtscts.isChecked())
        settings.setValue("v1/probe_separation_cm", self.spin_separation.value())

    def start_listening(self) -> None:
        port = self.port_combo.currentText().strip()
        if not port:
            QMessageBox.warning(self, "Invalid Port", "Please select or type a valid serial port name.")
            return

        baudrate = int(self.baud_combo.currentText())
        rtscts = self.chk_rtscts.isChecked()

        self.save_settings()

        self.worker_thread = SerialWorkerThread(port=port, baudrate=baudrate, rtscts=rtscts, parent=self)
        self.worker_thread.line_received.connect(self.on_line_received)
        self.worker_thread.connection_error.connect(self.on_connection_error)
        self.worker_thread.start()

        self.btn_connect.setEnabled(False)
        self.btn_disconnect.setEnabled(True)
        self.status_label.setText(f"Status: Listening on '{port}' ({baudrate} baud)... Press buttons on V1 device.")
        self.status_label.setStyleSheet("font-style: italic; font-weight: bold; color: #2E7D32;")

    def stop_listening(self) -> None:
        if self.worker_thread:
            self.worker_thread.stop()
            self.worker_thread = None

        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)
        self.status_label.setText("Status: Disconnected")
        self.status_label.setStyleSheet("font-style: italic; color: #666;")

    def on_line_received(self, line: str) -> None:
        self.terminal_edit.append(line)

    def on_connection_error(self, err_msg: str) -> None:
        self.stop_listening()
        port = self.port_combo.currentText().strip()

        if "permission" in err_msg.lower() or "denied" in err_msg.lower() or "errno 13" in err_msg.lower():
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("Serial Port Permission Denied")
            msg_box.setText(f"Permission denied accessing serial port '{port}'.")
            msg_box.setInformativeText(
                f"On Linux, serial devices require group permission.\n\n"
                f"• Permanent Fix (Recommended):\n"
                f"  Run the following command in terminal, then re-login:\n"
                f"  sudo usermod -aG uucp,dialout $USER\n\n"
                f"• Quick Workaround:\n"
                f"  Click 'Fix Permissions Now' to grant access for this session."
            )
            btn_fix = msg_box.addButton("Fix Permissions Now (chmod 666)", QMessageBox.ButtonRole.ActionRole)
            btn_close = msg_box.addButton(QMessageBox.StandardButton.Close)

            msg_box.exec()

            if msg_box.clickedButton() == btn_fix:
                self.fix_port_permissions(port)
        else:
            QMessageBox.critical(self, "Serial Connection Error", err_msg)

    def fix_port_permissions(self, port: str) -> None:
        import subprocess
        try:
            res = subprocess.run(["pkexec", "chmod", "666", port], capture_output=True, text=True)
            if res.returncode == 0:
                QMessageBox.information(
                    self,
                    "Permissions Fixed",
                    f"Successfully granted permissions for '{port}'. Click 'Connect & Listen' to start acquisition.",
                )
            else:
                QMessageBox.warning(
                    self,
                    "Permission Fix Failed",
                    f"Could not update permissions for '{port}':\n{res.stderr.strip() or 'Action was cancelled or denied.'}",
                )
        except Exception as e:
            QMessageBox.critical(self, "Permission Fix Error", f"Failed to execute permission fix:\n{e}")

    def clear_buffer(self) -> None:
        self.terminal_edit.clear()
        self.loaded_file_name = None

    def on_load_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select V1 TreeTap Log File",
            "",
            "V1 Log Files (*.down *.txt *.log *.csv);;All Files (*)",
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

                self.terminal_edit.setText(content)
                self.loaded_file_name = os.path.basename(file_path)
                QMessageBox.information(
                    self,
                    "File Loaded",
                    f"Successfully loaded file '{os.path.basename(file_path)}' ({len(content.splitlines())} lines).",
                )
            except Exception as e:
                QMessageBox.critical(self, "File Read Error", f"Could not read file '{file_path}':\n{e}")

    def on_ingest_clicked(self) -> None:
        text = self.terminal_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Empty Buffer", "No serial data or file content present in terminal buffer to ingest.")
            return

        db_path = getattr(self.parent(), "db_path", "treetap.duckdb")
        conn = getattr(self.parent(), "conn", None)
        source_name = self.loaded_file_name or f"serial_{self.port_combo.currentText().strip()}"
        separation_cm = self.spin_separation.value()
        self.save_settings()

        try:
            stats = ingest_v1_data(
                text,
                db_path=db_path,
                source_name=source_name,
                separation_cm=separation_cm,
                conn=conn,
                target_ingest_id=self.target_ingest_id,
            )
            if stats.get("status") == "SKIPPED_DUPLICATE":
                prev = stats.get("previous_ingest", {})
                msg = (
                    "Duplicate Data Payload Detected!\n\n"
                    f"This exact dataset (SHA-256 fingerprint) was previously imported:\n"
                    f"• Previous Ingest ID: #{prev.get('ingest_id')}\n"
                    f"• Original Source: {prev.get('source')}\n"
                    f"• Import Timestamp: {prev.get('ingest_time')}\n\n"
                    "No duplicate records were added to the database."
                )
                QMessageBox.warning(self, "Duplicate Import Skipped", msg)
            else:
                ins_meas = stats.get("inserted_measurements", 0)
                skip_meas = stats.get("skipped_measurements", 0)
                ins_taps = stats.get("inserted_taps", 0)
                skip_taps = stats.get("skipped_taps", 0)

                msg = (
                    "V1 Ingestion Finished!\n\n"
                    f"• Ingest ID: #{stats.get('ingest_id')}\n"
                    f"• Measurements: {ins_meas} inserted, {skip_meas} skipped\n"
                    f"• Taps: {ins_taps} inserted, {skip_taps} skipped"
                )
                QMessageBox.information(self, "V1 Ingestion Complete", msg)

            self.stop_listening()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Ingestion Error", f"Failed to ingest V1 data into database:\n{e}")

    def reject(self) -> None:
        self.stop_listening()
        super().reject()

    def closeEvent(self, event) -> None:
        self.stop_listening()
        event.accept()
