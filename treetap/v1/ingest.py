"""
Version 1 serial acquisition ingestion handler.
Feeds live or recorded v1 serial acquisition events into the DuckDB backend repository.
"""

from typing import Dict, Any, Optional

from treetap.backend.connection import get_connection
from treetap.backend.repository import TreeTapRepository
from treetap.backend.models import Measurement, Tap, TapMetadata, TapSignal


def ingest_v1_tap(
    measurement: Measurement,
    tap: Tap,
    metadata: TapMetadata,
    signal: TapSignal,
    db_path: str = "treetap.duckdb",
) -> bool:
    """
    Ingests a single v1 tap acquisition event into the DuckDB repository.
    """
    # Enforce device_version='v1'
    measurement.device_version = "v1"
    metadata.device_version = "v1"

    with get_connection(db_path=db_path) as conn:
        repo = TreeTapRepository(conn)
        repo.insert_measurements([measurement])
        repo.insert_taps([tap])
        repo.insert_tap_metadata([metadata])
        repo.insert_tap_signals([signal])
        
        repo.log_ingestion(
            device_version="v1",
            source="serial_comms",
            status="COMPLETED",
            records_loaded=1,
            details=f"Single v1 tap ingested: tap_id={tap.tap_id}",
        )
    return True
