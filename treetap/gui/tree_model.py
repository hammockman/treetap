"""
Hierarchical Tree Model for TreeTap GUI.
Organizes Measurement Sessions as parent rows and individual Taps as child rows.
"""

from typing import Dict, List, Optional, Any
import pandas as pd

from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt


class TreeTapTreeModel(QStandardItemModel):
    """
    QStandardItemModel subclass representing hierarchical Measurement -> Tap relationships.
    """

    HEADERS = [
        "Meas / Tap",
        "Meas Note",
        "Tap ID",
        "Tap Time",
        "Separation (cm)",
        "Speed (us)",
        "Source File",
    ]

    ITEM_TYPE_ROLE = Qt.ItemDataRole.UserRole + 1
    MEAS_ID_ROLE = Qt.ItemDataRole.UserRole + 2
    TAP_ID_ROLE = Qt.ItemDataRole.UserRole + 3
    SOURCE_FILE_ROLE = Qt.ItemDataRole.UserRole + 4
    INGEST_ID_ROLE = Qt.ItemDataRole.UserRole + 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHorizontalHeaderLabels(self.HEADERS)
        self._raw_df: pd.DataFrame = pd.DataFrame()

    def load_data_from_df(self, df: pd.DataFrame) -> None:
        """
        Populates tree items from flat join DataFrame.
        Organizes hierarchy: Ingestion Session -> Measurement Session -> Tap.
        """
        self.clear()
        self.setHorizontalHeaderLabels(self.HEADERS)
        self._raw_df = df

        if df.empty:
            return

        import os

        # 1. Group by ingest_id (Level 1: Ingestion Nodes)
        ingest_grouped = df.groupby("ingest_id", sort=False) if "ingest_id" in df.columns else [(1, df)]

        for ingest_id, ingest_group in ingest_grouped:
            ingest_id = int(ingest_id)
            src_files = [s for s in ingest_group["source_file"].dropna().unique() if s]
            main_src = os.path.basename(src_files[0]) if src_files else ""
            src_info = f" ({main_src})" if main_src else ""

            n_meas = int(ingest_group["global_meas_id"].nunique()) if "global_meas_id" in ingest_group.columns else int(ingest_group["meas_id"].nunique())
            n_taps = len(ingest_group)

            # Top-Level Ingestion Node
            item_ingest = QStandardItem(f"Ingest #{ingest_id}{src_info}")
            item_ingest.setData("ingest", self.ITEM_TYPE_ROLE)
            item_ingest.setData(ingest_id, self.INGEST_ID_ROLE)
            item_ingest.setData(ingest_id, Qt.ItemDataRole.UserRole)

            ingest_note = QStandardItem(f"Ingest Set #{ingest_id}")
            ingest_note.setData("ingest", self.ITEM_TYPE_ROLE)
            ingest_note.setData(ingest_id, self.INGEST_ID_ROLE)

            ingest_count = QStandardItem(f"{n_meas} session(s), {n_taps} tap(s)")
            ingest_count.setData("ingest", self.ITEM_TYPE_ROLE)
            ingest_count.setData(ingest_id, self.INGEST_ID_ROLE)

            ingest_row = [
                item_ingest,
                ingest_note,
                ingest_count,
                QStandardItem(""),
                QStandardItem(""),
                QStandardItem(""),
                QStandardItem(main_src),
            ]

            # 2. Group by local_meas_id (Level 2: Measurement Nodes under Ingest Node)
            meas_grouped = ingest_group.groupby("meas_id", sort=False)

            for local_meas_id, meas_group in meas_grouped:
                local_meas_id = int(local_meas_id)
                meas_note = str(meas_group["meas_note"].iloc[0]) if "meas_note" in meas_group.columns else ""
                source_file = str(meas_group["source_file"].iloc[0]) if "source_file" in meas_group.columns else ""
                n_meas_taps = len(meas_group)
                g_meas_id = int(meas_group["global_meas_id"].iloc[0]) if "global_meas_id" in meas_group.columns else local_meas_id

                valid_speeds = meas_group["speed_us"].dropna() if "speed_us" in meas_group.columns else pd.Series(dtype=float)
                median_speed = float(valid_speeds.median()) if not valid_speeds.empty else None

                # Simplified Measurement Node (just number!)
                item_meas = QStandardItem(f"Meas {local_meas_id}")
                item_meas.setData("meas", self.ITEM_TYPE_ROLE)
                item_meas.setData(g_meas_id, self.MEAS_ID_ROLE)
                item_meas.setData(ingest_id, self.INGEST_ID_ROLE)
                item_meas.setData(g_meas_id, Qt.ItemDataRole.UserRole)

                item_note = QStandardItem(meas_note)
                item_note.setData("meas", self.ITEM_TYPE_ROLE)
                item_note.setData(g_meas_id, self.MEAS_ID_ROLE)
                item_note.setData(ingest_id, self.INGEST_ID_ROLE)

                item_count = QStandardItem(f"{n_meas_taps} tap(s)")
                item_count.setData("meas", self.ITEM_TYPE_ROLE)
                item_count.setData(g_meas_id, self.MEAS_ID_ROLE)
                item_count.setData(ingest_id, self.INGEST_ID_ROLE)

                speed_str = f"{median_speed:.2f}" if median_speed is not None else ""
                item_speed = QStandardItem(speed_str)
                item_speed.setData(median_speed if median_speed is not None else -1.0, Qt.ItemDataRole.UserRole)
                item_speed.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

                item_src = QStandardItem(source_file)

                meas_row = [
                    item_meas,
                    item_note,
                    item_count,
                    QStandardItem(""),
                    QStandardItem(""),
                    item_speed,
                    item_src,
                ]

                # 3. Child rows (Level 3: Taps under Measurement Node)
                for _, row in meas_group.iterrows():
                    local_tap_id = int(row["tap_id"])
                    g_tap_id = int(row["global_tap_id"]) if "global_tap_id" in row else local_tap_id
                    tap_time = str(row["tap_time"]) if "tap_time" in row else ""
                    sep_val = float(row["separation_cm"]) if "separation_cm" in row and pd.notnull(row["separation_cm"]) else 0.0
                    sep_cm = f"{sep_val:.2f}" if sep_val > 0 else ""

                    speed_val = float(row["speed_us"]) if "speed_us" in row and pd.notnull(row["speed_us"]) else -1.0
                    speed_us = f"{speed_val:.2f}" if speed_val >= 0 else ""
                    source_file = str(row["source_file"]) if "source_file" in row and pd.notnull(row["source_file"]) else ""

                    c_name = QStandardItem(f"  Tap {local_tap_id}")
                    c_name.setData("tap", self.ITEM_TYPE_ROLE)
                    c_name.setData(g_meas_id, self.MEAS_ID_ROLE)
                    c_name.setData(g_tap_id, self.TAP_ID_ROLE)
                    c_name.setData(ingest_id, self.INGEST_ID_ROLE)
                    c_name.setData(source_file, self.SOURCE_FILE_ROLE)

                    c_note = QStandardItem("")

                    c_tid = QStandardItem(str(local_tap_id))
                    c_tid.setData("tap", self.ITEM_TYPE_ROLE)
                    c_tid.setData(g_meas_id, self.MEAS_ID_ROLE)
                    c_tid.setData(g_tap_id, self.TAP_ID_ROLE)
                    c_tid.setData(ingest_id, self.INGEST_ID_ROLE)

                    c_time = QStandardItem(tap_time)
                    c_sep = QStandardItem(sep_cm)
                    c_speed = QStandardItem(speed_us)
                    c_src = QStandardItem(source_file)

                    for c in (c_tid, c_sep, c_speed):
                        c.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

                    child_row = [c_name, c_note, c_tid, c_time, c_sep, c_speed, c_src]
                    item_meas.appendRow(child_row)

                item_ingest.appendRow(meas_row)

            self.appendRow(ingest_row)
