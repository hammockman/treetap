"""
Repository layer for TreeTap DuckDB database operations.
Provides standardized batch upsert and query methods.
"""

from typing import List, Dict, Any, Optional
import pandas as pd
import duckdb
from datetime import datetime

from treetap.backend.models import Measurement, Tap, TapMetadata, TapSignal
from treetap.backend.schema import init_schema


class TreeTapRepository:
    """
    Data repository wrapping a DuckDB connection for TreeTap entities.
    """

    def __init__(self, conn: duckdb.DuckDBPyConnection):
        self.conn = conn
        init_schema(self.conn)

    def insert_measurements(self, measurements: List[Measurement]) -> int:
        if not measurements:
            return 0
        records = [
            {
                "meas_id": m.meas_id,
                "meas_note": m.meas_note,
                "device_version": m.device_version,
            }
            for m in measurements
        ]
        df = pd.DataFrame(records)
        self.conn.execute("INSERT OR REPLACE INTO measurements SELECT * FROM df")
        return len(records)

    def insert_taps(self, taps: List[Tap]) -> int:
        if not taps:
            return 0
        records = []
        for t in taps:
            tap_time_val = None
            if t.tap_time:
                try:
                    # Convert string timestamp DD/MM/YY HH:MM:SS or standard ISO to Timestamp
                    tap_time_val = pd.to_datetime(t.tap_time, format="%d/%m/%y %H:%M:%S", errors="coerce")
                    if pd.isna(tap_time_val):
                        tap_time_val = pd.to_datetime(t.tap_time, errors="coerce")
                except Exception:
                    tap_time_val = None
            
            records.append({
                "tap_id": t.tap_id,
                "meas_id": t.meas_id,
                "tap_time": tap_time_val,
                "separation_cm": t.separation_cm,
                "speed_us": t.speed_us,
                "meas_note": t.meas_note,
            })
        df = pd.DataFrame(records)
        self.conn.execute("INSERT OR REPLACE INTO taps SELECT * FROM df")
        return len(records)

    def insert_tap_metadata(self, metadata_list: List[TapMetadata]) -> int:
        if not metadata_list:
            return 0
        records = [
            {
                "tap_id": m.tap_id,
                "firmware_version": m.firmware_version,
                "device_batch": m.device_batch,
                "channels": m.channels,
                "samples": m.samples,
                "threshold": m.threshold,
                "gain": m.gain,
                "rate_hz": m.rate_hz,
                "offset_ch1": m.offset_ch1,
                "offset_ch2": m.offset_ch2,
                "std_ch1": m.std_ch1,
                "std_ch2": m.std_ch2,
                "delay_us": m.delay_us,
                "tap_note": m.tap_note,
                "source_file": m.source_file,
                "device_version": m.device_version,
            }
            for m in metadata_list
        ]
        df = pd.DataFrame(records)
        self.conn.execute("INSERT OR REPLACE INTO tap_metadata SELECT * FROM df")
        return len(records)

    def insert_tap_signals(self, signals: List[TapSignal]) -> int:
        if not signals:
            return 0
        records = [
            {
                "tap_id": s.tap_id,
                "ch1_samples": s.ch1_samples,
                "ch2_samples": s.ch2_samples,
            }
            for s in signals
        ]
        df = pd.DataFrame(records)
        self.conn.execute("INSERT OR REPLACE INTO tap_signals SELECT * FROM df")
        return len(records)

    def log_ingestion(
        self,
        device_version: str,
        source: str,
        status: str,
        records_loaded: int,
        details: str = "",
    ) -> None:
        res = self.conn.execute("SELECT COALESCE(MAX(ingest_id), 0) + 1 FROM ingest_log").fetchone()
        next_id = res[0] if res else 1
        self.conn.execute(
            """
            INSERT INTO ingest_log (ingest_id, ingest_time, device_version, source, status, records_loaded, details)
            VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?)
            """,
            [next_id, device_version, source, status, records_loaded, details],
        )

    def get_summary_stats(self) -> Dict[str, Any]:
        meas_count = self.conn.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]
        taps_count = self.conn.execute("SELECT COUNT(*) FROM taps").fetchone()[0]
        meta_count = self.conn.execute("SELECT COUNT(*) FROM tap_metadata").fetchone()[0]
        sig_count = self.conn.execute("SELECT COUNT(*) FROM tap_signals").fetchone()[0]
        
        return {
            "measurements_count": meas_count,
            "taps_count": taps_count,
            "tap_metadata_count": meta_count,
            "tap_signals_count": sig_count,
        }
