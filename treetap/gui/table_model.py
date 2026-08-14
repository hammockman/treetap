"""
Custom Table Model for displaying DuckDB TreeTap data in QTableView.
"""

from typing import List, Any, Optional
import pandas as pd
import duckdb
from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex
from PyQt6.QtGui import QColor


class TreeTapTableModel(QAbstractTableModel):
    HEADERS = [
        "Ingest ID",
        "Meas ID",
        "Meas Note",
        "Tap ID",
        "Tap Time",
        "Separation (cm)",
        "ToF (us)",
        "Channels",
        "Samples",
        "Rate (Hz)",
        "Delay (μs)",
        "Device Version",
        "Source File",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._df = pd.DataFrame()
        self._data: List[List[Any]] = []

    def load_data_from_db(self, conn: duckdb.DuckDBPyConnection) -> None:
        self.beginResetModel()
        query = """
            SELECT 
                COALESCE(t.ingest_id, 1) AS ingest_id,
                COALESCE(meas.local_meas_id, t.meas_id) AS meas_id,
                COALESCE(t.meas_note, '') AS meas_note,
                COALESCE(t.local_tap_id, t.tap_id) AS tap_id,
                strftime(t.tap_time, '%Y-%m-%d %H:%M:%S') AS tap_time,
                t.separation_cm,
                t.speed_us,
                COALESCE(m.channels, 2) AS channels,
                COALESCE(m.samples, 2048) AS samples,
                COALESCE(m.rate_hz, 500000.0) AS rate_hz,
                COALESCE(m.delay_us, 0.0) AS delay_us,
                COALESCE(m.device_version, 'v2') AS device_version,
                COALESCE(m.source_file, '') AS source_file,
                t.meas_id AS global_meas_id,
                t.tap_id AS global_tap_id
            FROM taps t
            LEFT JOIN tap_metadata m ON t.tap_id = m.tap_id
            LEFT JOIN measurements meas ON t.meas_id = meas.meas_id
            ORDER BY t.tap_id ASC
        """
        self._df = conn.execute(query).df()
        # Data list for view columns 0..12
        display_df = self._df.iloc[:, :len(self.HEADERS)]
        self._data = display_df.values.tolist()
        self.endResetModel()

    def get_initial_hidden_columns(self) -> List[int]:
        hidden = []
        if self._df.empty:
            return hidden

        for idx, col in enumerate(self._df.columns):
            header_name = self.HEADERS[idx] if idx < len(self.HEADERS) else col
            # Always initially deselect "Source File"
            if header_name.lower().strip() == "source file":
                hidden.append(idx)
                continue
            # Initially deselect columns with only 1 distinct value (or empty)
            if self._df[col].nunique(dropna=False) <= 1:
                hidden.append(idx)

        return hidden

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._data)

    def columnCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._data)):
            return None

        val = self._data[index.row()][index.column()]

        if role == Qt.ItemDataRole.DisplayRole:
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return ""
            if isinstance(val, float):
                return f"{val:.2f}"
            return str(val)

        if role == Qt.ItemDataRole.ForegroundRole:
            if not self._df.empty and 0 <= index.row() < len(self._df):
                row_series = self._df.iloc[index.row()]
                off1 = abs(float(row_series.get("offset_ch1", 0.0) or 0.0))
                off2 = abs(float(row_series.get("offset_ch2", 0.0) or 0.0))
                std1 = abs(float(row_series.get("std_ch1", 0.0) or 0.0))
                std2 = abs(float(row_series.get("std_ch2", 0.0) or 0.0))
                delay = abs(float(row_series.get("delay_us", 0.0) or 0.0))
                if off1 > 20.0 or off2 > 20.0 or std1 > 10.0 or std2 > 10.0 or delay > 500.0:
                    return QColor("#D32F2F")  # Vibrant Red text for extraordinary taps

        if role == Qt.ItemDataRole.ToolTipRole:
            if not self._df.empty and 0 <= index.row() < len(self._df):
                row_series = self._df.iloc[index.row()]
                off1 = float(row_series.get("offset_ch1", 0.0) or 0.0)
                off2 = float(row_series.get("offset_ch2", 0.0) or 0.0)
                std1 = float(row_series.get("std_ch1", 0.0) or 0.0)
                std2 = float(row_series.get("std_ch2", 0.0) or 0.0)
                delay = float(row_series.get("delay_us", 0.0) or 0.0)
                if abs(off1) > 20.0 or abs(off2) > 20.0 or abs(std1) > 10.0 or abs(std2) > 10.0 or abs(delay) > 500.0:
                    return (
                        f"⚠️ Extraordinary metadata values detected:\n"
                        f"  • Offset: Ch1={off1:.2f}, Ch2={off2:.2f}\n"
                        f"  • Noise Std: Ch1={std1:.2f}, Ch2={std2:.2f}\n"
                        f"  • Delay: {delay:.2f} μs"
                    )

        if role == Qt.ItemDataRole.TextAlignmentRole:
            col = index.column()
            # Right align numeric columns
            if col in (0, 2, 4, 5, 6, 7, 8, 9):
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self.HEADERS):
                return self.HEADERS[section]
        return None

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        if self._df.empty or not (0 <= column < len(self.HEADERS)):
            return

        self.beginResetModel()
        col_name = self._df.columns[column]
        ascending = (order == Qt.SortOrder.AscendingOrder)
        self._df = self._df.sort_values(by=col_name, ascending=ascending, na_position="last")
        self._data = self._df.values.tolist()
        self.endResetModel()

    def get_row_data(self, row: int) -> Optional[dict]:
        if self._df is not None and 0 <= row < len(self._df):
            row_series = self._df.iloc[row]
            g_meas = int(row_series["global_meas_id"]) if "global_meas_id" in row_series else int(row_series["meas_id"])
            g_tap = int(row_series["global_tap_id"]) if "global_tap_id" in row_series else int(row_series["tap_id"])
            return {
                "ingest_id": int(row_series["ingest_id"]) if "ingest_id" in row_series else 1,
                "meas_id": g_meas,
                "local_meas_id": int(row_series["meas_id"]),
                "meas_note": str(row_series["meas_note"]),
                "tap_id": g_tap,
                "local_tap_id": int(row_series["tap_id"]),
                "tap_time": str(row_series["tap_time"]),
                "separation_cm": float(row_series["separation_cm"]) if pd.notnull(row_series["separation_cm"]) else 0.0,
                "speed_us": float(row_series["speed_us"]) if pd.notnull(row_series["speed_us"]) else 0.0,
                "source_file": str(row_series["source_file"]) if "source_file" in row_series else "",
            }
        return None
