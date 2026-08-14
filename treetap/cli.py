"""
Command Line Interface for TreeTap Python Package.
"""

import argparse
import sys
import json

from treetap.v2.ingest import ingest_v2_directory
from treetap.backend.connection import get_connection
from treetap.backend.repository import TreeTapRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="TreeTap Acoustic Data Management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # gui subcommand
    gui_parser = subparsers.add_parser("gui", help="Launch PyQt6 GUI visualizer")
    gui_parser.add_argument("--db", default="treetap.duckdb", help="DuckDB database file path")

    # v2 subcommand
    v2_parser = subparsers.add_parser("v2", help="Version 2 file & archive management")
    v2_sub = v2_parser.add_subparsers(dest="v2_command", help="v2 commands")
    
    v2_ingest = v2_sub.add_parser("ingest", help="Ingest summary CSVs and tap signal archives")
    v2_ingest.add_argument("data_dir", nargs="?", default="data/v2", help="Path to data/v2 directory")
    v2_ingest.add_argument("--db", default="treetap.duckdb", help="Target DuckDB database path")

    # info subcommand
    info_parser = subparsers.add_parser("info", help="Display summary statistics of database")
    info_parser.add_argument("--db", default="treetap.duckdb", help="DuckDB database path")

    args = parser.parse_args()

    # Default to GUI when double-clicked or called without subcommands
    if args.command == "gui" or args.command is None:
        db_path = getattr(args, "db", "treetap.duckdb") or "treetap.duckdb"
        try:
            from treetap.gui import launch_gui
            launch_gui(db_path=db_path)
        except Exception as err:
            import traceback
            tb_str = traceback.format_exc()
            with open("treetap_crash.log", "w") as f:
                f.write(tb_str)
            try:
                from PyQt6.QtWidgets import QApplication, QMessageBox
                app = QApplication.instance() or QApplication(sys.argv)
                QMessageBox.critical(None, "TreeTap Startup Error", f"Application failed to start:\n\n{err}\n\nTraceback written to treetap_crash.log")
            except Exception:
                pass
            sys.exit(1)
    elif args.command == "v2" and args.v2_command == "ingest":
        print(f"Starting v2 ingestion from '{args.data_dir}' into '{args.db}'...")
        stats = ingest_v2_directory(data_dir=args.data_dir, db_path=args.db)
        print("Ingestion completed:")
        print(json.dumps(stats, indent=2))
    elif args.command == "info":
        with get_connection(db_path=args.db, read_only=True) as conn:
            repo = TreeTapRepository(conn)
            stats = repo.get_summary_stats()
            print(f"Database Stats for '{args.db}':")
            print(json.dumps(stats, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
