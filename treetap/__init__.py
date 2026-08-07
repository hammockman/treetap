"""
TreeTap Python Package.
"""

from treetap.v2 import ingest_v2_directory
from treetap.backend import get_connection, TreeTapRepository

__version__ = "0.1.0"

__all__ = [
    "ingest_v2_directory",
    "get_connection",
    "TreeTapRepository",
]
