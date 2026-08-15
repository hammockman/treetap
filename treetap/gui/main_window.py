"""
Main Application Window for TreeTap PyQt6 GUI.
"""

from typing import List, Dict, Any, Optional
import os
import shutil
import duckdb
import pandas as pd

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTableView,
    QTreeView,
    QStackedWidget,
    QLineEdit,
    QPushButton,
    QLabel,
    QFileDialog,
    QMessageBox,
    QHeaderView,
    QStatusBar,
    QApplication,
    QMenu,
    QDialog,
)
from PyQt6.QtCore import Qt, QSortFilterProxyModel, QItemSelection, QPoint, QSettings
from PyQt6.QtGui import QAction, QIcon, QPalette, QColor, QStandardItem

from treetap.backend.connection import get_connection
from treetap.backend.repository import TreeTapRepository
from treetap.backend.schema import init_schema
from treetap.gui.table_model import TreeTapTableModel
from treetap.gui.tree_model import TreeTapTreeModel
from treetap.gui.plot_widget import TapPlotWidget
from treetap.gui.tap_selector import TapSelectorWidget
from treetap.gui.column_dialog import ColumnVisibilityDialog
from treetap.gui.source_viewer import SourceFileViewerDialog
from treetap.gui.ftp_dialog import FtpIngestDialog
from treetap.gui.v1_dialog import V1IngestDialog
from treetap.v2.ingest import ingest_v2_directory


class TreeTapMainWindow(QMainWindow):
    def __init__(self, db_path: Optional[str] = None):
        super().__init__()

        settings = QSettings("TreeTap", "TreeTapSignals")
        saved_db = settings.value("last_db_path", None)

        if not db_path or db_path == "treetap.duckdb":
            if saved_db and os.path.exists(str(saved_db)):
                db_path = str(saved_db)
            else:
                db_path = "treetap.duckdb"

        self.db_path = db_path
        self.conn: Optional[duckdb.DuckDBPyConnection] = None
        self.hidden_columns: List[int] = []
        self.current_meas_id: Optional[int] = None
        self.is_read_only = False

        self.update_window_title()
        self.resize(1200, 800)

        icon_path = os.path.join(os.path.dirname(__file__), "assets", "app_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Main Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(4, 4, 4, 4)

        # 1. Top Control Bar (Search & Quick Action)
        control_bar = QHBoxLayout()

        self.db_label = QLabel(f"<b>Database:</b> {os.path.basename(self.db_path)}")
        control_bar.addWidget(self.db_label)

        control_bar.addSpacing(20)
        control_bar.addWidget(QLabel("Filter:"))

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search notes, IDs, time...")
        self.search_edit.textChanged.connect(self.on_filter_changed)
        control_bar.addWidget(self.search_edit)

        control_bar.addSpacing(15)
        control_bar.addWidget(QLabel("View:"))
        self.btn_view_flat = QPushButton("Flat Table")
        self.btn_view_flat.setCheckable(True)
        self.btn_view_flat.setChecked(False)
        self.btn_view_flat.clicked.connect(lambda: self.switch_view_mode(0))
        control_bar.addWidget(self.btn_view_flat)

        self.btn_view_tree = QPushButton("Hierarchical Tree")
        self.btn_view_tree.setCheckable(True)
        self.btn_view_tree.setChecked(True)
        self.btn_view_tree.clicked.connect(lambda: self.switch_view_mode(1))
        control_bar.addWidget(self.btn_view_tree)

        self.btn_columns = QPushButton("Select Columns...")
        self.btn_columns.clicked.connect(self.on_open_column_dialog)
        control_bar.addWidget(self.btn_columns)

        main_layout.addLayout(control_bar)

        # 2. Main Splitter (Upper Pane / Lower Signal Plot Pane)
        self.splitter = QSplitter(Qt.Orientation.Vertical)

        # --- UPPER PANE: Stacked Widget (Flat Table vs Hierarchical Tree) ---
        self.stacked_upper = QStackedWidget(self)

        # View 0: Flat Table (QTableView)
        self.table_model = TreeTapTableModel(self)
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.table_model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy_model.setFilterKeyColumn(-1)

        VIEW_STYLESHEET = """
            QAbstractItemView::item:selected {
                background-color: #E0E0E0;
                color: #000000;
            }
            QAbstractItemView::item:selected:active {
                background-color: #E0E0E0;
                color: #000000;
            }
            QAbstractItemView::item:selected:hover {
                background-color: #D5D5D5;
                color: #000000;
            }
            QAbstractItemView::item:hover {
                background-color: #F5F5F5;
                color: #000000;
            }
        """

        self.table_view = QTableView()
        self.table_view.setStyleSheet(VIEW_STYLESHEET)
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.table_view.setSortingEnabled(True)

        header_table = self.table_view.horizontalHeader()
        header_table.setSectionsMovable(True)
        header_table.setStretchLastSection(False)
        header_table.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.on_table_context_menu)
        self.table_view.selectionModel().selectionChanged.connect(self.on_table_selection_changed)
        self.stacked_upper.addWidget(self.table_view)

        # View 1: Hierarchical Tree (QTreeView)
        self.tree_model = TreeTapTreeModel(self)
        self.tree_proxy = QSortFilterProxyModel(self)
        self.tree_proxy.setSourceModel(self.tree_model)
        self.tree_proxy.setSortRole(Qt.ItemDataRole.UserRole)
        self.tree_proxy.setRecursiveFilteringEnabled(True)
        self.tree_proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.tree_proxy.setFilterKeyColumn(-1)

        self.tree_view = QTreeView()
        self.tree_view.setStyleSheet(VIEW_STYLESHEET)
        self.tree_view.setModel(self.tree_proxy)
        self.tree_view.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        self.tree_view.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.tree_view.setSortingEnabled(True)
        self.tree_view.setAlternatingRowColors(True)

        header_tree = self.tree_view.header()
        header_tree.setSectionsMovable(True)
        header_tree.setStretchLastSection(False)
        header_tree.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.on_tree_context_menu)
        self.tree_view.selectionModel().selectionChanged.connect(self.on_tree_selection_changed)
        self.stacked_upper.addWidget(self.tree_view)
        self.stacked_upper.setCurrentIndex(1)

        self.splitter.addWidget(self.stacked_upper)

        # --- LOWER PANE: Plot & Tap Selector ---
        lower_container = QWidget()
        lower_layout = QHBoxLayout(lower_container)
        lower_layout.setContentsMargins(0, 0, 0, 0)

        self.plot_widget = TapPlotWidget(self)
        self.plot_widget.sig_manual_tof_changed.connect(self.on_manual_tof_changed)
        lower_layout.addWidget(self.plot_widget, stretch=3)

        self.tap_selector = TapSelectorWidget(self)
        self.tap_selector.tap_visibility_changed.connect(self.plot_widget.set_tap_visibility)
        self.tap_selector.channel_visibility_changed.connect(self.plot_widget.set_channel_visibility)
        lower_layout.addWidget(self.tap_selector, stretch=1)

        self.splitter.addWidget(lower_container)
        self.splitter.setSizes([350, 450])  # Initial height ratio

        main_layout.addWidget(self.splitter)

        # 4. Menu Bar & Status Bar
        self._create_menu_bar()
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Initialize Database connection & load table
        self.connect_db(self.db_path)

    def update_window_title(self) -> None:
        title = f"Treetap Signals - {os.path.basename(self.db_path)}"
        if getattr(self, "is_read_only", False):
            title += " [Read-Only]"
        self.setWindowTitle(title)

    def _create_menu_bar(self) -> None:
        menu = self.menuBar()

        # File Menu
        file_menu = menu.addMenu("&File")

        new_action = QAction("&New Database...", self)
        new_action.triggered.connect(self.on_create_new_database)
        file_menu.addAction(new_action)

        open_action = QAction("&Open Database...", self)
        open_action.triggered.connect(self.on_open_database)
        file_menu.addAction(open_action)

        ingest_v1_action = QAction("Ingest &V1 Data (Serial / File)...", self)
        ingest_v1_action.triggered.connect(self.on_ingest_v1)
        file_menu.addAction(ingest_v1_action)

        ingest_action = QAction("&Ingest V2 Data Directory...", self)
        ingest_action.triggered.connect(self.on_ingest_v2)
        file_menu.addAction(ingest_action)

        ingest_ftp_action = QAction("Ingest V2 Data via &FTP...", self)
        ingest_ftp_action.triggered.connect(self.on_ingest_v2_ftp)
        file_menu.addAction(ingest_ftp_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View Menu
        view_menu = menu.addMenu("&View")

        cols_action = QAction("&Columns Visibility...", self)
        cols_action.triggered.connect(self.on_open_column_dialog)
        view_menu.addAction(cols_action)

        reset_plot_action = QAction("&Reset Plot Zoom", self)
        reset_plot_action.triggered.connect(self.plot_widget.reset_view)
        view_menu.addAction(reset_plot_action)

        # Help Menu
        help_menu = menu.addMenu("&Help")
        about_action = QAction("&About TreeTap", self)
        about_action.triggered.connect(self.on_about)
        help_menu.addAction(about_action)

    def connect_db(self, db_path: str) -> None:
        try:
            if self.conn:
                try:
                    self.conn.close()
                except Exception:
                    pass
            self.db_path = db_path
            self.current_meas_id = None
            self.is_read_only = False

            try:
                self.conn = duckdb.connect(database=db_path, read_only=False)
            except Exception:
                # Fall back to read-only mode if locked by another process or on Windows
                try:
                    self.conn = duckdb.connect(database=db_path, read_only=True)
                    self.is_read_only = True
                except Exception as err:
                    QMessageBox.critical(self, "Database Error", f"Failed to open DuckDB database '{db_path}':\n{err}")
                    return

            # Ensure schema (tables & views) is initialized
            try:
                init_schema(self.conn)
            except Exception:
                pass

            # Save successfully connected database path to QSettings
            try:
                if os.path.exists(db_path):
                    settings = QSettings("TreeTap", "TreeTapSignals")
                    settings.setValue("last_db_path", os.path.abspath(db_path))
            except Exception:
                pass

            self.update_window_title()
            self.table_model.load_data_from_db(self.conn)
            self.tree_model.load_data_from_df(self.table_model._df)

            self.hidden_columns = self.table_model.get_initial_hidden_columns()
            for col_idx in range(len(TreeTapTableModel.HEADERS)):
                self.table_view.setColumnHidden(col_idx, col_idx in self.hidden_columns)

            header_table = self.table_view.horizontalHeader()
            header_table.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            self.table_view.resizeColumnsToContents()

            header_tree = self.tree_view.header()
            header_tree.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            for col_i in range(len(TreeTapTreeModel.HEADERS)):
                self.tree_view.resizeColumnToContents(col_i)
            self.tree_view.expandToDepth(0)

            mode_str = " (Read-Only Mode)" if self.is_read_only else ""
            self.db_label.setText(f"<b>Database:</b> {os.path.basename(self.db_path)}{mode_str}")
            self.status_bar.showMessage(
                f"Loaded {self.table_model.rowCount()} taps from {os.path.basename(db_path)}{mode_str}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to open database '{db_path}':\n{e}")

    def switch_view_mode(self, idx: int) -> None:
        self.stacked_upper.setCurrentIndex(idx)
        self.btn_view_flat.setChecked(idx == 0)
        self.btn_view_tree.setChecked(idx == 1)

    def on_filter_changed(self, text: str) -> None:
        self.proxy_model.setFilterFixedString(text)
        self.tree_proxy.setFilterFixedString(text)

    def ensure_write_connection(self) -> bool:
        if not self.is_read_only:
            return True
        try:
            if self.conn:
                self.conn.close()
            self.conn = duckdb.connect(database=self.db_path, read_only=False)
            self.is_read_only = False
            self.db_label.setText(f"<b>Database:</b> {os.path.basename(self.db_path)}")
            return True
        except duckdb.Error:
            self.conn = duckdb.connect(database=self.db_path, read_only=True)
            self.is_read_only = True
            QMessageBox.warning(
                self,
                "Database Locked",
                f"Cannot perform edit/delete operation:\n"
                f"Database file '{os.path.basename(self.db_path)}' is currently locked by another process.\n\n"
                f"Please close other Python or CLI sessions accessing the database to enable write operations."
            )
            return False

    def on_filter_changed(self, text: str) -> None:
        self.proxy_model.setFilterFixedString(text)

    def on_open_column_dialog(self) -> None:
        dialog = ColumnVisibilityDialog(
            headers=TreeTapTableModel.HEADERS,
            hidden_indices=self.hidden_columns,
            parent=self,
        )
        if dialog.exec():
            self.hidden_columns = dialog.get_hidden_indices()
            for col_idx in range(len(TreeTapTableModel.HEADERS)):
                self.table_view.setColumnHidden(col_idx, col_idx in self.hidden_columns)

    def on_table_selection_changed(self, selected: QItemSelection, deselected: QItemSelection) -> None:
        selected_indexes = self.table_view.selectionModel().selectedRows()
        if not selected_indexes or not self.conn:
            self.current_meas_id = None
            self.plot_widget.clear_markers()
            self.plot_widget.clear_plots()
            self.tap_selector.populate_taps([], {})
            return

        selected_tap_ids = set()
        selected_meas_ids = set()

        for proxy_idx in selected_indexes:
            source_idx = self.proxy_model.mapToSource(proxy_idx)
            row_data = self.table_model.get_row_data(source_idx.row())
            if row_data:
                selected_tap_ids.add(int(row_data["tap_id"]))
                if row_data.get("meas_id") is not None:
                    selected_meas_ids.add(int(row_data["meas_id"]))

        if selected_meas_ids:
            placeholders = ", ".join(["?"] * len(selected_meas_ids))
            query = f"""
                SELECT 
                    t.tap_id,
                    COALESCE(m.rate_hz, 500000.0) AS rate_hz,
                    COALESCE(m.delay_us, 0.0) AS delay_us,
                    s.ch1_samples,
                    s.ch2_samples,
                    COALESCE(t.separation_cm, 100.0) AS separation_cm
                FROM taps t
                LEFT JOIN tap_metadata m ON t.tap_id = m.tap_id
                LEFT JOIN tap_signals s ON t.tap_id = s.tap_id
                WHERE t.meas_id IN ({placeholders})
                ORDER BY t.tap_id ASC
            """
            meas_id_list = [int(m) for m in sorted(selected_meas_ids)]
            rows = self.conn.execute(query, meas_id_list).fetchall()
            taps_data = []
            for r in rows:
                taps_data.append({
                    "tap_id": r[0],
                    "rate_hz": r[1],
                    "delay_us": r[2],
                    "ch1_samples": r[3] if r[3] else [],
                    "ch2_samples": r[4] if r[4] else [],
                    "separation_cm": r[5] if len(r) > 5 and r[5] is not None else 100.0,
                })

            colors = self.plot_widget.set_tap_signals(taps_data)
            self.tap_selector.populate_taps(taps_data, colors)

            meas_str = ", ".join(str(m) for m in meas_id_list[:3])
            if len(meas_id_list) > 3:
                meas_str += f" (+{len(meas_id_list) - 3} more)"
            self.status_bar.showMessage(
                f"Measurement Session(s) {meas_str} selected — Overlaid {len(taps_data)} tap signals"
            )

        # Highlight selected tap trace(s) with wider, opaque line styling
        self.plot_widget.highlight_taps(selected_tap_ids)

    def on_tree_selection_changed(self, selected: QItemSelection, deselected: QItemSelection) -> None:
        selected_indexes = self.tree_view.selectionModel().selectedRows()
        if not selected_indexes:
            selected_indexes = self.tree_view.selectionModel().selectedIndexes()

        if not selected_indexes or not self.conn:
            self.current_meas_id = None
            self.plot_widget.clear_markers()
            self.plot_widget.clear_plots()
            self.tap_selector.populate_taps([], {})
            return

        selected_tap_ids = set()
        selected_meas_ids = set()
        selected_ingest_ids = set()

        def _collect_tree_node(item: QStandardItem) -> None:
            if not item:
                return

            # Normalize to column 0 item so rowCount() finds all child nodes
            if item.column() != 0:
                parent = item.parent()
                if parent:
                    item = parent.child(item.row(), 0)
                else:
                    item = self.tree_model.item(item.row(), 0)
            if not item:
                return

            item_type = item.data(TreeTapTreeModel.ITEM_TYPE_ROLE)
            if item_type == "ingest":
                ingest_id = item.data(TreeTapTreeModel.INGEST_ID_ROLE)
                if ingest_id is not None:
                    selected_ingest_ids.add(int(ingest_id))
                # Do not recurse into children of an Ingestion node to plot all signals
                return

            meas_id = item.data(TreeTapTreeModel.MEAS_ID_ROLE)
            if meas_id is not None:
                selected_meas_ids.add(int(meas_id))

            tid = item.data(TreeTapTreeModel.TAP_ID_ROLE)
            if tid is not None:
                selected_tap_ids.add(int(tid))

            for row_i in range(item.rowCount()):
                child_item = item.child(row_i, 0)
                if child_item:
                    _collect_tree_node(child_item)

        for proxy_idx in selected_indexes:
            source_idx = self.tree_proxy.mapToSource(proxy_idx)
            item = self.tree_model.itemFromIndex(source_idx)
            if item:
                _collect_tree_node(item)

        if not selected_meas_ids:
            self.current_meas_id = None
            self.plot_widget.clear_markers()
            self.plot_widget.clear_plots()
            self.tap_selector.populate_taps([], {})
            if selected_ingest_ids:
                ingest_str = ", ".join(str(i) for i in sorted(selected_ingest_ids))
                self.status_bar.showMessage(f"Ingestion Session #{ingest_str} selected — Expand tree to select a Measurement or Tap.")
            return

        placeholders = ", ".join(["?"] * len(selected_meas_ids))
        query = f"""
            SELECT 
                t.tap_id,
                COALESCE(m.rate_hz, 500000.0) AS rate_hz,
                COALESCE(m.delay_us, 0.0) AS delay_us,
                s.ch1_samples,
                s.ch2_samples,
                COALESCE(t.separation_cm, 100.0) AS separation_cm
            FROM taps t
            LEFT JOIN tap_metadata m ON t.tap_id = m.tap_id
            LEFT JOIN tap_signals s ON t.tap_id = s.tap_id
            WHERE t.meas_id IN ({placeholders})
            ORDER BY t.tap_id ASC
        """
        meas_id_list = [int(m) for m in sorted(selected_meas_ids)]
        rows = self.conn.execute(query, meas_id_list).fetchall()
        taps_data = []
        for r in rows:
            taps_data.append({
                "tap_id": r[0],
                "rate_hz": r[1],
                "delay_us": r[2],
                "ch1_samples": r[3] if r[3] else [],
                "ch2_samples": r[4] if r[4] else [],
                "separation_cm": r[5] if len(r) > 5 and r[5] is not None else 100.0,
            })

        n_plotted = sum(1 for t in taps_data if len(t.get("ch1_samples", [])) > 0 or len(t.get("ch2_samples", [])) > 0)
        colors = self.plot_widget.set_tap_signals(taps_data)
        self.tap_selector.populate_taps(taps_data, colors)

        meas_str = ", ".join(str(m) for m in meas_id_list[:3])
        if len(meas_id_list) > 3:
            meas_str += f" (+{len(meas_id_list) - 3} more)"

        if n_plotted > 0:
            self.status_bar.showMessage(
                f"Measurement Session(s) {meas_str} selected — Overlaid {n_plotted} tap signals"
            )
        else:
            self.status_bar.showMessage(
                f"Measurement Session(s) {meas_str} selected — (V1 summary session; no raw waveform arrays stored)"
            )

        self.plot_widget.highlight_taps(selected_tap_ids)

    def on_manual_tof_changed(self, delta_t: Optional[float]) -> None:
        """
        Records manual time-of-flight delta (in μs) to DuckDB in tof_manual column of taps table.
        """
        if not self.conn:
            return

        if self.is_read_only:
            self.status_bar.showMessage("Database is open read-only. Cannot record manual ToF.")
            return

        # Only record if exactly 1 single tap is currently selected
        if len(self.plot_widget.highlighted_taps) != 1:
            return

        target_tap_id = next(iter(self.plot_widget.highlighted_taps))

        try:
            if delta_t is not None:
                self.conn.execute("UPDATE taps SET tof_manual = ? WHERE tap_id = ?", [float(delta_t), target_tap_id])
                self.status_bar.showMessage(f"Recorded Manual ToF = {delta_t:.2f} μs for Tap #{target_tap_id}")
            else:
                self.conn.execute("UPDATE taps SET tof_manual = NULL WHERE tap_id = ?", [target_tap_id])
                self.status_bar.showMessage(f"Cleared Manual ToF for Tap #{target_tap_id}")

            self.table_model.update_tof_manual(target_tap_id, delta_t)
            self.tree_model.update_tof_manual(target_tap_id, delta_t)
        except Exception as err:
            self.status_bar.showMessage(f"Failed to record manual ToF: {err}")

    def on_tree_context_menu(self, pos: QPoint) -> None:
        selected_indexes = self.tree_view.selectionModel().selectedRows()
        if not selected_indexes:
            return

        tap_ids = []
        meas_ids = set()
        ingest_ids = set()
        source_files: List[Tuple[int, str]] = []

        def _collect_context_node(item: QStandardItem) -> None:
            ing_id = item.data(TreeTapTreeModel.INGEST_ID_ROLE)
            if ing_id is not None:
                ingest_ids.add(int(ing_id))

            meas_id = item.data(TreeTapTreeModel.MEAS_ID_ROLE)
            if meas_id is not None:
                meas_ids.add(int(meas_id))

            tid = item.data(TreeTapTreeModel.TAP_ID_ROLE)
            sf = item.data(TreeTapTreeModel.SOURCE_FILE_ROLE)
            if tid is not None:
                tap_ids.append(int(tid))
                if sf:
                    source_files.append((int(tid), sf))

            for row_i in range(item.rowCount()):
                child_item = item.child(row_i, 0)
                if child_item:
                    _collect_context_node(child_item)

        for proxy_idx in selected_indexes:
            source_idx = self.tree_proxy.mapToSource(proxy_idx)
            item = self.tree_model.itemFromIndex(source_idx)
            if item:
                _collect_context_node(item)

        meas_ids_list = sorted(list(meas_ids))
        tap_ids_list = sorted(list(set(tap_ids)))

        menu = QMenu(self.tree_view)

        if ingest_ids and self.conn:
            target_ingest_id = sorted(list(ingest_ids))[0]
            try:
                row = self.conn.execute(
                    "SELECT ingest_id, source, device_version FROM ingest_log WHERE ingest_id = ?",
                    [target_ingest_id],
                ).fetchone()
                if row:
                    ing_id, src_str, dev_ver = row[0], row[1] or "", row[2] or "v2"
                    disp_src = src_str if len(src_str) <= 30 else (src_str[:27] + "...")
                    repeat_action = QAction(f"🔄 Repeat Ingestion (Ingest #{ing_id} - {disp_src})...", self)
                    repeat_action.triggered.connect(
                        lambda _, iid=ing_id, src=src_str, dver=dev_ver: self.on_repeat_ingestion(iid, src, dver)
                    )
                    menu.addAction(repeat_action)
                    menu.addSeparator()
            except Exception:
                pass

        if source_files:
            for tap_id, src_file in source_files[:3]:
                view_src_action = QAction(f"Open Original Source File (Tap {tap_id})...", self)
                view_src_action.triggered.connect(lambda _, tid=tap_id, sf=src_file: self.on_view_source_file(tid, sf))
                menu.addAction(view_src_action)
            menu.addSeparator()

        tap_str = ", ".join(map(str, tap_ids_list[:5])) + ("..." if len(tap_ids_list) > 5 else "")
        delete_taps_action = QAction(f"Delete Selected Tap(s) [{tap_str}]", self)
        delete_taps_action.triggered.connect(lambda: self.on_delete_taps(tap_ids_list))
        menu.addAction(delete_taps_action)

        meas_str = ", ".join(map(str, meas_ids_list[:5])) + ("..." if len(meas_ids_list) > 5 else "")
        delete_meas_action = QAction(f"Delete Measurement Session(s) [Meas ID: {meas_str}]", self)
        delete_meas_action.triggered.connect(lambda: self.on_delete_measurements(meas_ids_list))
        menu.addAction(delete_meas_action)

        menu.addSeparator()
        expand_action = QAction("Expand All", self)
        expand_action.triggered.connect(self.tree_view.expandAll)
        menu.addAction(expand_action)

        collapse_action = QAction("Collapse All", self)
        collapse_action.triggered.connect(self.tree_view.collapseAll)
        menu.addAction(collapse_action)

        menu.exec(self.tree_view.viewport().mapToGlobal(pos))

    def on_repeat_ingestion(self, ingest_id: int, source: str, device_version: str) -> None:
        """
        Triggers a re-ingestion workflow for the specified ingestion session.
        - For V1 Serial: Pre-fills V1 Ingestion Dialog with target port.
        - For V1 Log File: Ingests file or launches V1 Dialog.
        - For V2 / FTP: Opens FtpIngestDialog or directory ingestion.
        """
        if not self.conn:
            return

        if source.startswith("serial_"):
            port_name = source[7:]
            dlg = V1IngestDialog(self, initial_port=port_name)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.refresh_views()
        elif device_version == "v1":
            if os.path.exists(source):
                from treetap.v1.ingest import ingest_v1_data
                try:
                    res = ingest_v1_data(source, conn=self.conn)
                    QMessageBox.information(
                        self,
                        "Repeat Ingestion Successful",
                        f"Re-ingested V1 log file '{os.path.basename(source)}'.\n\nLoaded {res.get('records_loaded', 0)} taps.",
                    )
                    self.refresh_views()
                except Exception as e:
                    QMessageBox.critical(self, "Ingestion Failed", f"Failed to re-ingest file:\n{str(e)}")
            else:
                dlg = V1IngestDialog(self)
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    self.refresh_views()
        elif os.path.exists(source) and os.path.isdir(source):
            try:
                res = ingest_v2_directory(data_dir=source, conn=self.conn)
                if res.get("status") == "SKIPPED_DUPLICATE":
                    prev_id = res.get("previous_ingest", {}).get("ingest_id")
                    QMessageBox.information(
                        self,
                        "Duplicate Ingestion Skipped",
                        f"Directory '{source}' has already been ingested with identical contents (Ingest #{prev_id}).",
                    )
                else:
                    QMessageBox.information(
                        self,
                        "Repeat Ingestion Successful",
                        f"Re-ingested V2 directory '{source}'.\n\nLoaded {res.get('total_taps', 0)} taps.",
                    )
                    self.refresh_views()
            except Exception as e:
                QMessageBox.critical(self, "Ingestion Failed", f"Failed to re-ingest V2 directory:\n{str(e)}")
        else:
            dlg = FtpIngestDialog(self, conn=self.conn)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.refresh_views()

    def on_create_new_database(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Create New TreeTap DuckDB Database",
            "treetap_new.duckdb",
            "DuckDB Files (*.duckdb *.db);;All Files (*)",
        )
        if path:
            if not path.endswith(".duckdb") and not path.endswith(".db"):
                path += ".duckdb"
            try:
                if os.path.exists(path):
                    reply = QMessageBox.question(
                        self,
                        "Overwrite Existing File?",
                        f"File '{os.path.basename(path)}' already exists.\n\nDo you want to overwrite it with a new empty database?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        if self.conn and self.db_path == path:
                            self.conn.close()
                            self.conn = None
                        os.remove(path)
                    else:
                        return

                self.connect_db(path)
                self.plot_widget.clear_plots()
                self.tap_selector.populate_taps([], {})
                self.status_bar.showMessage(f"Created and connected to new empty database '{os.path.basename(path)}'")
                QMessageBox.information(
                    self,
                    "New Database Created",
                    f"Successfully created and connected to new empty database:\n{path}",
                )
            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Failed to create new database '{path}':\n{e}")

    def on_open_database(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open TreeTap DuckDB Database", "", "DuckDB Files (*.duckdb *.db);;All Files (*)"
        )
        if path:
            self.connect_db(path)

    def on_ingest_v1(self) -> None:
        dialog = V1IngestDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh_views()

    def on_ingest_v2(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(self, "Select Version 2 Data Directory")
        if dir_path:
            try:
                stats = ingest_v2_directory(data_dir=dir_path, db_path=self.db_path, conn=self.conn)
                if stats.get("status") == "SKIPPED_DUPLICATE":
                    prev = stats.get("previous_ingest", {})
                    msg = (
                        "Duplicate Data Payload Detected!\n\n"
                        f"This exact dataset (SHA-256 fingerprint) was previously imported:\n"
                        f"• Previous Ingest ID: #{prev.get('ingest_id')}\n"
                        f"• Original Source: {prev.get('source')}\n"
                        f"• Import Timestamp: {prev.get('ingest_time')}\n\n"
                        "No duplicate records were added to the database."
                    )
                    QMessageBox.warning(self, "Duplicate Import Skipped", msg)
                else:
                    ins_meas = stats.get("inserted_measurements", 0)
                    skip_meas = stats.get("skipped_measurements", 0)
                    ins_taps = stats.get("inserted_taps", 0)
                    skip_taps = stats.get("skipped_taps", 0)
                    ins_sig = stats.get("inserted_signals", 0)
                    skip_sig = stats.get("skipped_signals", 0)

                    msg = (
                        "Ingestion Finished!\n\n"
                        f"• Ingest ID: #{stats.get('ingest_id')}\n"
                        f"• Measurements: {ins_meas} inserted, {skip_meas} skipped\n"
                        f"• Taps: {ins_taps} inserted, {skip_taps} skipped\n"
                        f"• Signals: {ins_sig} inserted, {skip_sig} skipped"
                    )
                    if stats.get("warnings"):
                        msg += f"\n\nWarnings: {len(stats['warnings'])}"

                    QMessageBox.information(self, "Ingestion Complete", msg)
                    self.refresh_views()
            except Exception as e:
                QMessageBox.critical(self, "Ingestion Error", f"Failed to ingest directory:\n{e}")

    def on_ingest_v2_ftp(self) -> None:
        dialog = FtpIngestDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.temp_dir:
            try:
                stats = ingest_v2_directory(data_dir=dialog.temp_dir, db_path=self.db_path, conn=self.conn)
                if stats.get("status") == "SKIPPED_DUPLICATE":
                    prev = stats.get("previous_ingest", {})
                    msg = (
                        "Duplicate FTP Data Payload Detected!\n\n"
                        f"This exact dataset (SHA-256 fingerprint) was previously imported:\n"
                        f"• Previous Ingest ID: #{prev.get('ingest_id')}\n"
                        f"• Original Source: {prev.get('source')}\n"
                        f"• Import Timestamp: {prev.get('ingest_time')}\n\n"
                        "No duplicate records were added to the database."
                    )
                    QMessageBox.warning(self, "Duplicate Import Skipped", msg)
                else:
                    ins_meas = stats.get("inserted_measurements", 0)
                    skip_meas = stats.get("skipped_measurements", 0)
                    ins_taps = stats.get("inserted_taps", 0)
                    skip_taps = stats.get("skipped_taps", 0)
                    ins_sig = stats.get("inserted_signals", 0)
                    skip_sig = stats.get("skipped_signals", 0)

                    msg = (
                        "FTP Ingestion Finished!\n\n"
                        f"• Ingest ID: #{stats.get('ingest_id')}\n"
                        f"• Measurements: {ins_meas} inserted, {skip_meas} skipped\n"
                        f"• Taps: {ins_taps} inserted, {skip_taps} skipped\n"
                        f"• Signals: {ins_sig} inserted, {skip_sig} skipped"
                    )
                    if stats.get("warnings"):
                        msg += f"\n\nWarnings: {len(stats['warnings'])}"

                    QMessageBox.information(self, "FTP Ingestion Complete", msg)
                    self.refresh_views()
            except Exception as e:
                QMessageBox.critical(self, "FTP Ingestion Error", f"Failed to ingest downloaded FTP data:\n{e}")
            finally:
                if dialog.temp_dir and os.path.exists(dialog.temp_dir):
                    shutil.rmtree(dialog.temp_dir, ignore_errors=True)

    def on_about(self) -> None:
        QMessageBox.about(
            self,
            "About Treetap Signals",
            "<h3>Treetap Signals</h3>"
            "<p>A PyQt6 + pyqtgraph + DuckDB desktop application for analyzing acoustic tree signals.</p>",
        )

    def on_table_context_menu(self, pos: QPoint) -> None:
        selected_indexes = self.table_view.selectionModel().selectedRows()
        if not selected_indexes:
            return

        tap_ids = []
        meas_ids = set()
        source_files: List[Tuple[int, str]] = []

        for proxy_idx in selected_indexes:
            source_idx = self.proxy_model.mapToSource(proxy_idx)
            row_data = self.table_model.get_row_data(source_idx.row())
            if row_data:
                tap_id = row_data["tap_id"]
                local_tap = row_data.get("local_tap_id", tap_id)
                tap_ids.append(tap_id)
                meas_ids.add(row_data["meas_id"])
                if row_data.get("source_file"):
                    source_files.append((tap_id, local_tap, row_data["source_file"]))

        meas_ids_list = sorted(list(meas_ids))
        tap_ids_list = sorted(list(set(tap_ids)))

        menu = QMenu(self.table_view)

        # 1. Source file viewer action(s)
        if source_files:
            for tap_id, local_tap, src_file in source_files[:3]:
                view_src_action = QAction(f"Open Original Source File (Tap {local_tap})...", self)
                view_src_action.triggered.connect(lambda _, tid=tap_id, sf=src_file: self.on_view_source_file(tid, sf))
                menu.addAction(view_src_action)
            menu.addSeparator()

        # 2. Delete Tap action
        tap_str = ", ".join(map(str, tap_ids_list[:5])) + ("..." if len(tap_ids_list) > 5 else "")
        delete_taps_action = QAction(f"Delete Selected Tap(s) [{tap_str}]", self)
        delete_taps_action.triggered.connect(lambda: self.on_delete_taps(tap_ids_list))
        menu.addAction(delete_taps_action)

        # 3. Delete Measurement action
        meas_str = ", ".join(map(str, meas_ids_list[:5])) + ("..." if len(meas_ids_list) > 5 else "")
        delete_meas_action = QAction(f"Delete Measurement Session(s) [Meas ID: {meas_str}]", self)
        delete_meas_action.triggered.connect(lambda: self.on_delete_measurements(meas_ids_list))
        menu.addAction(delete_meas_action)

        menu.exec(self.table_view.viewport().mapToGlobal(pos))

    def on_view_source_file(self, tap_id: int, source_file: str) -> None:
        db_dir = os.path.dirname(os.path.abspath(self.db_path)) if self.db_path else "."
        dialog = SourceFileViewerDialog(
            tap_id=tap_id,
            source_file=source_file,
            db_dir=db_dir,
            parent=self,
        )
        dialog.exec()

    def refresh_views(
        self,
        preserve_tree_state: bool = True,
        target_ingest_id: Optional[int] = None,
    ) -> None:
        """
        Reloads database records into table_model and updates tree_model,
        preserving tree expansion state and moving selection to the parent Ingest node.
        """
        if not self.conn:
            return

        expanded_ingest_ids = set()
        if preserve_tree_state:
            for r in range(self.tree_proxy.rowCount()):
                proxy_idx = self.tree_proxy.index(r, 0)
                if self.tree_view.isExpanded(proxy_idx):
                    source_idx = self.tree_proxy.mapToSource(proxy_idx)
                    item = self.tree_model.itemFromIndex(source_idx)
                    if item:
                        ing_id = item.data(TreeTapTreeModel.INGEST_ID_ROLE)
                        if ing_id is not None:
                            expanded_ingest_ids.add(int(ing_id))

        self.table_model.load_data_from_db(self.conn)
        self.tree_model.load_data_from_df(self.table_model._df)

        # Re-expand tree to depth 0 plus any previously expanded ingest nodes
        self.tree_view.expandToDepth(0)
        if expanded_ingest_ids:
            for r in range(self.tree_proxy.rowCount()):
                proxy_idx = self.tree_proxy.index(r, 0)
                source_idx = self.tree_proxy.mapToSource(proxy_idx)
                item = self.tree_model.itemFromIndex(source_idx)
                if item:
                    ing_id = item.data(TreeTapTreeModel.INGEST_ID_ROLE)
                    if ing_id is not None and int(ing_id) in expanded_ingest_ids:
                        self.tree_view.setExpanded(proxy_idx, True)

        self.plot_widget.clear_plots()
        self.tap_selector.populate_taps([], {})
        self.current_meas_id = None

        if target_ingest_id is not None:
            self.select_ingest_node(target_ingest_id)

    def select_ingest_node(self, target_ingest_id: int) -> None:
        """
        Selects the top-level Ingest node matching target_ingest_id in the tree view.
        """
        for r in range(self.tree_proxy.rowCount()):
            proxy_idx = self.tree_proxy.index(r, 0)
            source_idx = self.tree_proxy.mapToSource(proxy_idx)
            item = self.tree_model.itemFromIndex(source_idx)
            if item and item.data(TreeTapTreeModel.ITEM_TYPE_ROLE) == "ingest":
                ing_id = item.data(TreeTapTreeModel.INGEST_ID_ROLE)
                if ing_id is not None and int(ing_id) == target_ingest_id:
                    self.tree_view.selectionModel().clearSelection()
                    self.tree_view.selectionModel().select(
                        proxy_idx,
                        QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
                    )
                    self.tree_view.scrollTo(proxy_idx)
                    return

    def on_delete_taps(self, tap_ids: List[int]) -> None:
        if not tap_ids or not self.conn:
            return
        if not self.ensure_write_connection():
            return

        target_ingest_id = None
        try:
            placeholders = ", ".join(["?"] * len(tap_ids))
            row = self.conn.execute(
                f"SELECT ingest_id FROM taps WHERE tap_id IN ({placeholders}) LIMIT 1",
                tap_ids,
            ).fetchone()
            if row and row[0] is not None:
                target_ingest_id = int(row[0])
        except Exception:
            pass

        tap_str = ", ".join(map(str, tap_ids))
        reply = QMessageBox.question(
            self,
            "Confirm Delete Tap(s)",
            f"Are you sure you want to delete {len(tap_ids)} tap(s) ({tap_str}) from the database?\n\nThis will remove the tap metadata and signal samples.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                repo = TreeTapRepository(self.conn)
                count = repo.delete_taps(tap_ids)
                self.refresh_views(preserve_tree_state=True, target_ingest_id=target_ingest_id)
                self.status_bar.showMessage(f"Successfully deleted {count} tap(s)")
                QMessageBox.information(self, "Deleted", f"Successfully deleted {count} tap(s).")
            except Exception as e:
                QMessageBox.critical(self, "Delete Error", f"Failed to delete tap(s):\n{e}")

    def on_delete_measurements(self, meas_ids: List[int]) -> None:
        if not meas_ids or not self.conn:
            return
        if not self.ensure_write_connection():
            return

        target_ingest_id = None
        try:
            placeholders = ", ".join(["?"] * len(meas_ids))
            row = self.conn.execute(
                f"SELECT ingest_id FROM measurements WHERE meas_id IN ({placeholders}) LIMIT 1",
                meas_ids,
            ).fetchone()
            if row and row[0] is not None:
                target_ingest_id = int(row[0])
        except Exception:
            pass

        meas_str = ", ".join(map(str, meas_ids))
        reply = QMessageBox.question(
            self,
            "Confirm Delete Measurement Session(s)",
            f"Are you sure you want to delete {len(meas_ids)} measurement session(s) (ID: {meas_str})?\n\nThis will delete the measurement sessions and ALL associated taps, metadata, and signals.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                repo = TreeTapRepository(self.conn)
                count = repo.delete_measurements(meas_ids)
                self.refresh_views(preserve_tree_state=True, target_ingest_id=target_ingest_id)
                self.status_bar.showMessage(f"Successfully deleted {count} measurement session(s)")
                QMessageBox.information(self, "Deleted", f"Successfully deleted {count} measurement session(s).")
            except Exception as e:
                QMessageBox.critical(self, "Delete Error", f"Failed to delete measurement session(s):\n{e}")

    def closeEvent(self, event) -> None:
        if self.conn:
            self.conn.close()
        event.accept()
