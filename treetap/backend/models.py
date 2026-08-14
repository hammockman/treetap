"""
Domain models for TreeTap data objects.
Independent of input ingestion source (v1 serial comms vs v2 file/zip archives).
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class Measurement:
    meas_id: int
    ingest_id: Optional[int] = None
    local_meas_id: Optional[int] = None
    meas_note: Optional[str] = ""
    device_version: str = "v2"


@dataclass
class Tap:
    tap_id: int
    meas_id: int
    ingest_id: Optional[int] = None
    local_tap_id: Optional[int] = None
    tap_time: Optional[str] = None
    separation_cm: Optional[float] = 0.0
    speed_us: Optional[float] = 0.0
    meas_note: Optional[str] = ""


@dataclass
class TapMetadata:
    tap_id: int
    firmware_version: Optional[str] = None
    device_batch: Optional[int] = None
    channels: int = 2
    samples: int = 2048
    threshold: Optional[int] = None
    gain: Optional[int] = None
    rate_hz: float = 500000.0
    offset_ch1: float = 0.0
    offset_ch2: float = 0.0
    std_ch1: float = 0.0
    std_ch2: float = 0.0
    delay_us: float = 0.0
    tap_note: Optional[str] = ""
    source_file: Optional[str] = ""
    device_version: str = "v2"
    v1direction: Optional[str] = None
    v1col5: Optional[int] = None
    v1col6: Optional[int] = None


@dataclass
class TapSignal:
    tap_id: int
    ch1_samples: List[int] = field(default_factory=list)
    ch2_samples: List[int] = field(default_factory=list)
