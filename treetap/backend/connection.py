"""
DuckDB database connection manager for TreeTap.
"""

from contextlib import contextmanager
import duckdb
from typing import Generator


@contextmanager
def get_connection(db_path: str = "treetap.duckdb", read_only: bool = False) -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """
    Context manager that yields a DuckDB connection and closes it cleanly upon exit.
    """
    conn = duckdb.connect(database=db_path, read_only=read_only)
    try:
        yield conn
    finally:
        conn.close()
