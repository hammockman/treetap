"""
Version 1 serial comms acquisition interface.
Provides serial communication receiver for TreeTap v1 hardware serial streams.
"""

from typing import Optional, Callable, Dict, Any, Tuple, List
import time
import logging
import threading

import serial
import serial.tools.list_ports

from treetap.backend.models import Measurement, Tap, TapMetadata, TapSignal

logger = logging.getLogger(__name__)


def list_available_serial_ports() -> List[str]:
    """
    Returns a list of available serial port names on the system.
    """
    ports = serial.tools.list_ports.comports()
    return [p.device for p in ports]


class V1SerialWorker(threading.Thread):
    """
    Background worker thread reading ASCII lines from a PySerial port connection.
    """

    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 57600,
        rtscts: bool = True,
        on_line_received: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(daemon=True)
        self.port = port
        self.baudrate = baudrate
        self.rtscts = rtscts
        self.on_line_received = on_line_received
        self.on_error = on_error
        self.running = False
        self.ser: Optional[serial.Serial] = None

    def run(self) -> None:
        self.running = True
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                rtscts=self.rtscts,
                timeout=1.0,
            )
            logger.info(f"Opened serial port {self.port} at {self.baudrate} baud (RTS/CTS={self.rtscts})")
        except Exception as e:
            self.running = False
            err_msg = f"Failed to open serial port '{self.port}': {e}"
            logger.error(err_msg)
            if self.on_error:
                self.on_error(err_msg)
            return

        buffer = ""
        while self.running and self.ser and self.ser.is_open:
            try:
                data = self.ser.read(1024)
                if data:
                    text = data.decode("ascii", errors="replace")
                    buffer += text
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line_clean = line.strip("\r").strip()
                        if line_clean and self.on_line_received:
                            self.on_line_received(line_clean)
            except Exception as e:
                if self.running:
                    err_msg = f"Serial read error on {self.port}: {e}"
                    logger.error(err_msg)
                    if self.on_error:
                        self.on_error(err_msg)
                break

        self.close_port()

    def stop(self) -> None:
        self.running = False
        self.close_port()

    def close_port(self) -> None:
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
