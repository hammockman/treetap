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

    def __init__(self, conn: duckdb.DuckDBPyConnection, auto_init_schema: bool = True):
        self.conn = conn
        if auto_init_schema:
            try:
                init_schema(self.conn)
            except Exception:
                pass

    def check_duplicate_ingest(self, data_hash: str) -> Optional[Dict[str, Any]]:
        if not data_hash:
            return None
        try:
            res = self.conn.execute(
                """
                SELECT ingest_id, strftime(ingest_time, '%Y-%m-%d %H:%M:%S'), device_version, source, status, records_loaded, details
                FROM ingest_log
                WHERE data_hash = ? AND status = 'COMPLETED'
                ORDER BY ingest_id DESC
                LIMIT 1
                """,
                [data_hash],
            ).fetchone()
            if res:
                return {
                    "ingest_id": res[0],
                    "ingest_time": res[1],
                    "device_version": res[2],
                    "source": res[3],
                    "status": res[4],
                    "records_loaded": res[5],
                    "details": res[6],
                }
        except Exception:
            pass
        return None

    def insert_measurements(self, measurements: List[Measurement]) -> Dict[str, int]:
        if not measurements:
            return {"inserted": 0, "skipped": 0, "total": 0}
        records = []
        for m in measurements:
            loc_id = m.local_meas_id if m.local_meas_id is not None else m.meas_id
            g_id = (m.ingest_id * 1000000 + loc_id) if m.ingest_id else m.meas_id
            records.append({
                "meas_id": g_id,
                "ingest_id": m.ingest_id,
                "local_meas_id": loc_id,
                "meas_note": m.meas_note,
                "device_version": m.device_version,
            })
        df = pd.DataFrame(records)
        before_cnt = self.conn.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]
        try:
            self.conn.execute("INSERT OR IGNORE INTO measurements SELECT * FROM df")
        except Exception:
            for record in records:
                try:
                    df_single = pd.DataFrame([record])
                    self.conn.execute("INSERT OR IGNORE INTO measurements SELECT * FROM df_single")
                except Exception:
                    pass
        after_cnt = self.conn.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]
        inserted = max(0, after_cnt - before_cnt)
        skipped = max(0, len(records) - inserted)
        return {"inserted": inserted, "skipped": skipped, "total": len(records)}

    def insert_taps(self, taps: List[Tap]) -> Dict[str, int]:
        if not taps:
            return {"inserted": 0, "skipped": 0, "total": 0}
        records = []
        for t in taps:
            tap_time_val = None
            if t.tap_time:
                try:
                    tap_time_val = pd.to_datetime(t.tap_time, format="%d/%m/%y %H:%M:%S", errors="coerce")
                    if pd.isna(tap_time_val):
                        tap_time_val = pd.to_datetime(t.tap_time, errors="coerce")
                except Exception:
                    tap_time_val = None
            
            loc_tap = t.local_tap_id if t.local_tap_id is not None else t.tap_id
            loc_meas = t.meas_id
            g_tap = (t.ingest_id * 1000000 + loc_tap) if t.ingest_id else t.tap_id
            g_meas = (t.ingest_id * 1000000 + loc_meas) if t.ingest_id else t.meas_id

            records.append({
                "tap_id": g_tap,
                "meas_id": g_meas,
                "ingest_id": t.ingest_id,
                "local_tap_id": loc_tap,
                "tap_time": tap_time_val,
                "separation_cm": t.separation_cm,
                "speed_us": t.speed_us,
                "tof_manual": getattr(t, "tof_manual", None),
                "meas_note": t.meas_note,
            })
        df = pd.DataFrame(records)
        before_cnt = self.conn.execute("SELECT COUNT(*) FROM taps").fetchone()[0]
        try:
            self.conn.execute("INSERT OR IGNORE INTO taps SELECT * FROM df")
        except Exception:
            for record in records:
                try:
                    df_single = pd.DataFrame([record])
                    self.conn.execute("INSERT OR IGNORE INTO taps SELECT * FROM df_single")
                except Exception:
                    pass
        after_cnt = self.conn.execute("SELECT COUNT(*) FROM taps").fetchone()[0]
        inserted = max(0, after_cnt - before_cnt)
        skipped = max(0, len(records) - inserted)
        return {"inserted": inserted, "skipped": skipped, "total": len(records)}

    def insert_tap_metadata(self, metadata_list: List[TapMetadata], ingest_id: Optional[int] = None) -> Dict[str, int]:
        if not metadata_list:
            return {"inserted": 0, "skipped": 0, "total": 0}
        records = [
            {
                "tap_id": (ingest_id * 1000000 + m.tap_id) if ingest_id else m.tap_id,
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
                "v1direction": getattr(m, "v1direction", None),
                "v1col5": getattr(m, "v1col5", None),
                "v1col6": getattr(m, "v1col6", None),
            }
            for m in metadata_list
        ]
        df = pd.DataFrame(records)
        before_cnt = self.conn.execute("SELECT COUNT(*) FROM tap_metadata").fetchone()[0]
        try:
            self.conn.execute("INSERT OR IGNORE INTO tap_metadata SELECT * FROM df")
        except Exception:
            for record in records:
                try:
                    df_single = pd.DataFrame([record])
                    self.conn.execute("INSERT OR IGNORE INTO tap_metadata SELECT * FROM df_single")
                except Exception:
                    pass
        after_cnt = self.conn.execute("SELECT COUNT(*) FROM tap_metadata").fetchone()[0]
        inserted = max(0, after_cnt - before_cnt)
        skipped = max(0, len(records) - inserted)
        return {"inserted": inserted, "skipped": skipped, "total": len(records)}

    def insert_tap_signals(self, signals: List[TapSignal], ingest_id: Optional[int] = None) -> Dict[str, int]:
        if not signals:
            return {"inserted": 0, "skipped": 0, "total": 0}
        records = [
            {
                "tap_id": (ingest_id * 1000000 + s.tap_id) if ingest_id else s.tap_id,
                "ch1_samples": s.ch1_samples,
                "ch2_samples": s.ch2_samples,
            }
            for s in signals
        ]
        df = pd.DataFrame(records)
        before_cnt = self.conn.execute("SELECT COUNT(*) FROM tap_signals").fetchone()[0]
        try:
            self.conn.execute("INSERT OR IGNORE INTO tap_signals SELECT * FROM df")
        except Exception:
            for record in records:
                try:
                    df_single = pd.DataFrame([record])
                    self.conn.execute("INSERT OR IGNORE INTO tap_signals SELECT * FROM df_single")
                except Exception:
                    pass
        after_cnt = self.conn.execute("SELECT COUNT(*) FROM tap_signals").fetchone()[0]
        inserted = max(0, after_cnt - before_cnt)
        skipped = max(0, len(records) - inserted)
        return {"inserted": inserted, "skipped": skipped, "total": len(records)}

    def log_ingestion(
        self,
        device_version: str,
        source: str,
        status: str,
        records_loaded: int,
        details: str = "",
        data_hash: Optional[str] = None,
    ) -> int:
        res = self.conn.execute("SELECT COALESCE(MAX(ingest_id), 0) + 1 FROM ingest_log").fetchone()
        next_id = res[0] if res else 1
        self.conn.execute(
            """
            INSERT INTO ingest_log (ingest_id, ingest_time, device_version, source, data_hash, status, records_loaded, details)
            VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?)
            """,
            [next_id, device_version, source, data_hash, status, records_loaded, details],
        )
        return next_id

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

    def delete_taps(self, tap_ids: List[int]) -> int:
        if not tap_ids:
            return 0
        clean_ids = [int(i) for i in tap_ids]
        placeholders = ",".join(["?"] * len(clean_ids))
        self.conn.execute(f"DELETE FROM tap_signals WHERE tap_id IN ({placeholders})", clean_ids)
        self.conn.execute(f"DELETE FROM tap_metadata WHERE tap_id IN ({placeholders})", clean_ids)
        self.conn.execute(f"DELETE FROM taps WHERE tap_id IN ({placeholders})", clean_ids)
        return len(clean_ids)

    def delete_measurements(self, meas_ids: List[int]) -> int:
        if not meas_ids:
            return 0
        clean_ids = [int(i) for i in meas_ids]
        placeholders = ",".join(["?"] * len(clean_ids))
        self.conn.execute(
            f"DELETE FROM tap_signals WHERE tap_id IN (SELECT tap_id FROM taps WHERE meas_id IN ({placeholders}))",
            clean_ids,
        )
        self.conn.execute(
            f"DELETE FROM tap_metadata WHERE tap_id IN (SELECT tap_id FROM taps WHERE meas_id IN ({placeholders}))",
            clean_ids,
        )
        self.conn.execute(
            f"DELETE FROM taps WHERE meas_id IN ({placeholders})",
            clean_ids,
        )
        self.conn.execute(
            f"DELETE FROM measurements WHERE meas_id IN ({placeholders})",
            clean_ids,
        )
        return len(clean_ids)
