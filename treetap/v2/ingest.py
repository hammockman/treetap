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


import hashlib


def compute_v2_directory_hash(data_dir: str) -> str:
    hasher = hashlib.sha256()
    for root, _, files in sorted(os.walk(data_dir)):
        for f in sorted(files):
            p = os.path.join(root, f)
            try:
                with open(p, "rb") as fp:
                    while chunk := fp.read(65536):
                        hasher.update(chunk)
            except Exception:
                pass
    return hasher.hexdigest()


def ingest_v2_directory(
    data_dir: str = "data/v2",
    db_path: str = "treetap.duckdb",
    conn: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Ingests all Version 2 summary CSV files and individual tap signal archives
    from data_dir into the DuckDB database at db_path.
    Includes SHA-256 data fingerprinting and duplicate payload short-circuiting.
    """
    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"Target directory '{data_dir}' does not exist.")

    data_hash = compute_v2_directory_hash(data_dir)

    close_conn_when_done = False
    if conn is None:
        import duckdb
        from treetap.backend.schema import init_schema
        conn = duckdb.connect(database=db_path, read_only=False)
        init_schema(conn)
        close_conn_when_done = True

    try:
        repo = TreeTapRepository(conn)

        # Check for exact duplicate import payload
        dup = repo.check_duplicate_ingest(data_hash)
        if dup:
            repo.log_ingestion(
                device_version="v2",
                source=os.path.abspath(data_dir),
                status="SKIPPED_DUPLICATE",
                records_loaded=0,
                details=f"Duplicate payload matching ingest_id #{dup['ingest_id']} ({dup['source']} on {dup['ingest_time']})",
                data_hash=data_hash,
            )
            return {
                "status": "SKIPPED_DUPLICATE",
                "previous_ingest": dup,
                "inserted_measurements": 0,
                "skipped_measurements": 0,
                "inserted_taps": 0,
                "skipped_taps": 0,
                "inserted_metadata": 0,
                "skipped_metadata": 0,
                "inserted_signals": 0,
                "skipped_signals": 0,
                "warnings": [],
            }

        # 1. Parse summary files
        measurements, taps = parse_summary_directory(data_dir)

        # 2. Read tap signal archives
        reader = TapSignalArchiveReader(data_dir)
        metadata_list, signals_list = reader.read_all_taps()

        status = "COMPLETED_WITH_WARNINGS" if reader.warnings else "COMPLETED"
        warn_details = "; ".join(reader.warnings) if reader.warnings else "Clean ingest."
        details_str = f"Taps: {len(taps)} total. Signals: {len(signals_list)} total. Warnings: {warn_details}"

        ingest_id = repo.log_ingestion(
            device_version="v2",
            source=os.path.abspath(data_dir),
            status=status,
            records_loaded=len(taps),
            details=details_str,
            data_hash=data_hash,
        )

        for m in measurements:
            m.ingest_id = ingest_id
            m.local_meas_id = m.meas_id

        for t in taps:
            t.ingest_id = ingest_id
            t.local_tap_id = t.tap_id

        meas_res = repo.insert_measurements(measurements)
        taps_res = repo.insert_taps(taps)
        meta_res = repo.insert_tap_metadata(metadata_list, ingest_id=ingest_id)
        sig_res = repo.insert_tap_signals(signals_list, ingest_id=ingest_id)

        stats = repo.get_summary_stats()
        stats["status"] = status
        stats["ingest_id"] = ingest_id
        stats["data_hash"] = data_hash
        stats["inserted_measurements"] = meas_res["inserted"]
        stats["skipped_measurements"] = meas_res["skipped"]
        stats["inserted_taps"] = taps_res["inserted"]
        stats["skipped_taps"] = taps_res["skipped"]
        stats["inserted_metadata"] = meta_res["inserted"]
        stats["skipped_metadata"] = meta_res["skipped"]
        stats["inserted_signals"] = sig_res["inserted"]
        stats["skipped_signals"] = sig_res["skipped"]
        stats["warnings"] = reader.warnings
    finally:
        if close_conn_when_done and conn:
            try:
                conn.close()
            except Exception:
                pass
    return stats
