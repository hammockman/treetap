"""
DuckDB database schema DDL definitions for TreeTap.
"""

import duckdb

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS ingest_log (
    ingest_id INTEGER PRIMARY KEY,
    ingest_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    device_version VARCHAR,
    source VARCHAR,
    data_hash VARCHAR,
    status VARCHAR,
    records_loaded INTEGER,
    details VARCHAR
);

CREATE TABLE IF NOT EXISTS measurements (
    meas_id INTEGER PRIMARY KEY,
    ingest_id INTEGER,
    local_meas_id INTEGER,
    meas_note VARCHAR,
    device_version VARCHAR DEFAULT 'v2',
    FOREIGN KEY (ingest_id) REFERENCES ingest_log(ingest_id)
);

CREATE TABLE IF NOT EXISTS taps (
    tap_id INTEGER PRIMARY KEY,
    meas_id INTEGER,
    ingest_id INTEGER,
    local_tap_id INTEGER,
    tap_time TIMESTAMP,
    separation_cm DOUBLE,
    speed_us DOUBLE,
    tof_manual DOUBLE,
    meas_note VARCHAR,
    FOREIGN KEY (meas_id) REFERENCES measurements(meas_id),
    FOREIGN KEY (ingest_id) REFERENCES ingest_log(ingest_id)
);

CREATE TABLE IF NOT EXISTS tap_metadata (
    tap_id INTEGER PRIMARY KEY,
    firmware_version VARCHAR,
    device_batch INTEGER,
    channels INTEGER DEFAULT 2,
    samples INTEGER DEFAULT 2048,
    threshold INTEGER,
    gain INTEGER,
    rate_hz DOUBLE DEFAULT 500000.0,
    offset_ch1 DOUBLE DEFAULT 0.0,
    offset_ch2 DOUBLE DEFAULT 0.0,
    std_ch1 DOUBLE DEFAULT 0.0,
    std_ch2 DOUBLE DEFAULT 0.0,
    delay_us DOUBLE DEFAULT 0.0,
    tap_note VARCHAR,
    source_file VARCHAR,
    device_version VARCHAR DEFAULT 'v2',
    FOREIGN KEY (tap_id) REFERENCES taps(tap_id)
);

CREATE TABLE IF NOT EXISTS tap_signals (
    tap_id INTEGER PRIMARY KEY,
    ch1_samples INTEGER[],
    ch2_samples INTEGER[],
    FOREIGN KEY (tap_id) REFERENCES taps(tap_id)
);

CREATE VIEW IF NOT EXISTS v_tap_signals_long AS
SELECT 
    s.tap_id,
    s.idx - 1 AS sample_index,
    ((s.idx - 1) / COALESCE(m.rate_hz, 500000.0) * 1000000.0) AS time_us,
    s.ch1,
    s.ch2
FROM (
    SELECT 
        tap_id,
        generate_subscripts(ch1_samples, 1) AS idx,
        UNNEST(ch1_samples) AS ch1,
        UNNEST(ch2_samples) AS ch2
    FROM tap_signals
) s
LEFT JOIN tap_metadata m ON s.tap_id = m.tap_id;
"""


def init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """
    Executes table and view creation SQL against the provided DuckDB connection,
    applying idempotent schema migrations.
    """
    conn.execute(CREATE_TABLES_SQL)
    migrations = [
        "ALTER TABLE ingest_log ADD COLUMN IF NOT EXISTS data_hash VARCHAR;",
        "ALTER TABLE measurements ADD COLUMN IF NOT EXISTS ingest_id INTEGER;",
        "ALTER TABLE measurements ADD COLUMN IF NOT EXISTS local_meas_id INTEGER;",
        "ALTER TABLE taps ADD COLUMN IF NOT EXISTS ingest_id INTEGER;",
        "ALTER TABLE taps ADD COLUMN IF NOT EXISTS local_tap_id INTEGER;",
        "ALTER TABLE taps ADD COLUMN IF NOT EXISTS tof_manual DOUBLE;",
    ]
    for m in migrations:
        try:
            conn.execute(m)
        except Exception:
            pass
