"""
Version 2 data ingestion workflow manager.
Parses summary CSV files and zip archives from a directory and populates DuckDB.
"""

from typing import Dict, Any
import os

from treetap.backend.connection import get_connection
from treetap.backend.repository import TreeTapRepository
from treetap.v2.summary_parser import parse_summary_directory
from treetap.v2.archive_reader import TapSignalArchiveReader


def ingest_v2_directory(data_dir: str = "data/v2", db_path: str = "treetap.duckdb") -> Dict[str, Any]:
    """
    Ingests all Version 2 summary CSV files and individual tap signal archives
    from data_dir into the DuckDB database at db_path.
    """
    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"Target directory '{data_dir}' does not exist.")

    with get_connection(db_path=db_path) as conn:
        repo = TreeTapRepository(conn)

        # 1. Parse summary files
        measurements, taps = parse_summary_directory(data_dir)
        n_meas = repo.insert_measurements(measurements)
        n_taps = repo.insert_taps(taps)

        # 2. Read tap signal archives
        reader = TapSignalArchiveReader(data_dir)
        metadata_list, signals_list = reader.read_all_taps()

        n_meta = repo.insert_tap_metadata(metadata_list)
        n_sig = repo.insert_tap_signals(signals_list)

        # 3. Log ingestion details
        warn_details = "; ".join(reader.warnings) if reader.warnings else "Clean ingest."
        details_str = f"Summary taps: {len(taps)}, Signals read: {len(signals_list)}. Warnings: {warn_details}"
        
        status = "COMPLETED_WITH_WARNINGS" if reader.warnings else "COMPLETED"
        repo.log_ingestion(
            device_version="v2",
            source=os.path.abspath(data_dir),
            status=status,
            records_loaded=n_taps,
            details=details_str,
        )

        stats = repo.get_summary_stats()
        stats["warnings"] = reader.warnings
        stats["status"] = status
        return stats
