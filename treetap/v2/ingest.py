"""
Version 2 data ingestion workflow manager.
Parses summary CSV files and zip archives from a directory and populates DuckDB.
"""

from typing import Dict, Any, Optional
import os

from treetap.backend.connection import get_connection
from treetap.backend.repository import TreeTapRepository
from treetap.v2.summary_parser import parse_summary_directory
from treetap.v2.archive_reader import TapSignalArchiveReader


import pandas as pd


def normalize_tap_time_str(val: Any) -> Optional[str]:
    if not val:
        return None
    try:
        dt = pd.to_datetime(val, format="%d/%m/%y %H:%M:%S", errors="coerce")
        if pd.isna(dt):
            dt = pd.to_datetime(val, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def ingest_v2_directory(
    data_dir: str = "data/v2",
    db_path: str = "treetap.duckdb",
    conn: Optional[Any] = None,
    source_override: Optional[str] = None,
    target_ingest_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Ingests all Version 2 summary CSV files and individual tap signal archives
    from data_dir into the DuckDB database at db_path.
    Filters incoming taps by tap_time so existing taps are not overwritten.
    If target_ingest_id is specified, appends/updates records in that existing ingestion.
    """
    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"Target directory '{data_dir}' does not exist.")

    source_str = source_override or os.path.abspath(data_dir)

    close_conn_when_done = False
    if conn is None:
        import duckdb
        from treetap.backend.schema import init_schema
        conn = duckdb.connect(database=db_path, read_only=False)
        init_schema(conn)
        close_conn_when_done = True

    try:
        repo = TreeTapRepository(conn)

        # 1. Parse summary files
        measurements, taps = parse_summary_directory(data_dir)

        # 2. Read tap signal archives
        reader = TapSignalArchiveReader(data_dir)
        metadata_list, signals_list = reader.read_all_taps()

        # 3. Query existing tap_time values in database to prevent overwriting
        existing_tap_times = repo.get_existing_tap_times()

        skipped_tap_ids = set()
        new_taps = []
        for t in taps:
            t_norm = normalize_tap_time_str(t.tap_time)
            if t_norm and t_norm in existing_tap_times:
                skipped_tap_ids.add(t.tap_id)
            else:
                new_taps.append(t)

        new_metadata = [m for m in metadata_list if m.tap_id not in skipped_tap_ids]
        new_signals = [s for s in signals_list if s.tap_id not in skipped_tap_ids]

        status = "COMPLETED_WITH_WARNINGS" if reader.warnings else "COMPLETED"
        warn_details = "; ".join(reader.warnings) if reader.warnings else "Clean ingest."
        details_str = f"New Taps: {len(new_taps)} / {len(taps)} total. Signals: {len(new_signals)} total. Warnings: {warn_details}"

        if target_ingest_id is not None:
            ingest_id = target_ingest_id
        else:
            ingest_id = repo.log_ingestion(
                device_version="v2",
                source=source_str,
                status=status,
                records_loaded=len(new_taps),
                details=details_str,
            )

        for m in measurements:
            m.ingest_id = ingest_id
            m.local_meas_id = m.meas_id

        for t in new_taps:
            t.ingest_id = ingest_id
            t.local_tap_id = t.tap_id

        meas_res = repo.insert_measurements(measurements)
        taps_res = repo.insert_taps(new_taps)
        meta_res = repo.insert_tap_metadata(new_metadata, ingest_id=ingest_id)
        sig_res = repo.insert_tap_signals(new_signals, ingest_id=ingest_id)

        if target_ingest_id is not None:
            repo.update_ingest_log(
                ingest_id=target_ingest_id,
                added_records=taps_res.get("inserted", 0),
                status=status,
                details=details_str,
            )

        stats = repo.get_summary_stats()
        stats["status"] = status
        stats["ingest_id"] = ingest_id
        stats["inserted_measurements"] = meas_res["inserted"]
        stats["skipped_measurements"] = meas_res["skipped"]
        stats["inserted_taps"] = taps_res["inserted"]
        stats["skipped_taps"] = len(taps) - taps_res["inserted"]
        stats["inserted_metadata"] = meta_res["inserted"]
        stats["skipped_metadata"] = len(metadata_list) - meta_res["inserted"]
        stats["inserted_signals"] = sig_res["inserted"]
        stats["skipped_signals"] = len(signals_list) - sig_res["inserted"]
        stats["warnings"] = reader.warnings
    finally:
        if close_conn_when_done and conn:
            try:
                conn.close()
            except Exception:
                pass
    return stats
