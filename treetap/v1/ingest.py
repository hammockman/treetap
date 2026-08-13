"""
Version 1 serial acquisition and file ingestion handler.
Feeds v1 serial acquisition streams and log files into the DuckDB backend repository.
"""

from typing import Dict, Any, Optional
import logging

from treetap.backend.connection import get_connection
from treetap.backend.repository import TreeTapRepository
from treetap.v1.summary_parser import parse_v1_text

logger = logging.getLogger(__name__)


import hashlib


def ingest_v1_data(
    v1_text: str,
    db_path: str = "treetap.duckdb",
    source_name: str = "v1.down",
    separation_cm: float = 0.0,
    conn: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Ingests Version 1 TreeTap ASCII text (from serial stream or file) into the DuckDB repository.
    Includes SHA-256 data fingerprinting and duplicate payload short-circuiting.
    """
    cleaned_text = v1_text.strip()
    if not cleaned_text:
        return {
            "status": "EMPTY",
            "inserted_measurements": 0,
            "skipped_measurements": 0,
            "inserted_taps": 0,
            "skipped_taps": 0,
            "inserted_signals": 0,
            "skipped_signals": 0,
            "total_taps": 0,
        }

    parsed_sessions = parse_v1_text(cleaned_text, source_name=source_name, separation_cm=separation_cm)
    if not parsed_sessions:
        return {
            "status": "NO_RECORDS",
            "inserted_measurements": 0,
            "skipped_measurements": 0,
            "inserted_taps": 0,
            "skipped_taps": 0,
            "inserted_signals": 0,
            "skipped_signals": 0,
            "total_taps": 0,
        }

    data_hash = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()

    close_conn_when_done = False
    if conn is None:
        conn = get_connection(db_path=db_path)
        close_conn_when_done = True

    try:
        repo = TreeTapRepository(conn)

        # Check for exact duplicate import payload
        dup = repo.check_duplicate_ingest(data_hash)
        if dup:
            logger.info(f"Duplicate V1 payload detected (data_hash={data_hash[:10]}). Previous ingest_id={dup['ingest_id']}")
            repo.log_ingestion(
                device_version="v1",
                source=source_name,
                status="SKIPPED_DUPLICATE",
                records_loaded=0,
                details=f"Duplicate payload matching ingest_id #{dup['ingest_id']} ({dup['source']} on {dup['ingest_time']})",
                data_hash=data_hash,
            )
            return {
                "status": "SKIPPED_DUPLICATE",
                "previous_ingest": dup,
                "inserted_measurements": 0,
                "skipped_measurements": sum(1 for _ in parsed_sessions),
                "inserted_taps": 0,
                "skipped_taps": sum(len(tuples) for _, tuples in parsed_sessions),
                "inserted_signals": 0,
                "skipped_signals": sum(len(tuples) for _, tuples in parsed_sessions),
                "total_taps": sum(len(tuples) for _, tuples in parsed_sessions),
            }

        total_records = sum(len(tuples) for _, tuples in parsed_sessions)
        ingest_id = repo.log_ingestion(
            device_version="v1",
            source=source_name,
            status="COMPLETED",
            records_loaded=total_records,
            details=f"V1 Ingest ({source_name}): {total_records} taps",
            data_hash=data_hash,
        )

        inserted_meas = 0
        skipped_meas = 0
        inserted_taps = 0
        skipped_taps = 0
        inserted_sigs = 0
        skipped_sigs = 0

        for meas, tap_tuples in parsed_sessions:
            meas.ingest_id = ingest_id
            meas.local_meas_id = meas.meas_id

            m_res = repo.insert_measurements([meas])
            inserted_meas += m_res.get("inserted", 0)
            skipped_meas += m_res.get("skipped", 0)

            taps = []
            metas = []
            sigs = []
            for t, meta, sig in tap_tuples:
                t.ingest_id = ingest_id
                t.local_tap_id = t.tap_id
                taps.append(t)
                metas.append(meta)
                sigs.append(sig)

            t_res = repo.insert_taps(taps)
            inserted_taps += t_res.get("inserted", 0)
            skipped_taps += t_res.get("skipped", 0)

            repo.insert_tap_metadata(metas, ingest_id=ingest_id)
            sig_res = repo.insert_tap_signals(sigs, ingest_id=ingest_id)
            inserted_sigs += sig_res.get("inserted", 0)
            skipped_sigs += sig_res.get("skipped", 0)

    finally:
        if close_conn_when_done and conn:
            try:
                conn.close()
            except Exception:
                pass

    stats = {
        "status": "COMPLETED",
        "ingest_id": ingest_id,
        "data_hash": data_hash,
        "inserted_measurements": inserted_meas,
        "skipped_measurements": skipped_meas,
        "inserted_taps": inserted_taps,
        "skipped_taps": skipped_taps,
        "inserted_signals": inserted_sigs,
        "skipped_signals": skipped_sigs,
        "total_taps": total_records,
    }
    logger.info(f"V1 Ingestion Finished: {stats}")
    return stats
