"""
Dialog for choosing visible columns in the TreeTap table view.
"""

from typing import List
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QCheckBox,
    QDialogButtonBox,
    QLabel,
    QScrollArea,
    QWidget,
)


class ColumnVisibilityDialog(QDialog):
    def __init__(self, headers: List[str], hidden_indices: List[int], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Visible Columns")
        self.resize(300, 400)
        self.headers = headers
        self.checkboxes: List[QCheckBox] = []

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Check columns to display:"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        c_layout = QVBoxLayout(container)

        for idx, header in enumerate(headers):
            cb = QCheckBox(header)
            cb.setChecked(idx not in hidden_indices)
            self.checkboxes.append(cb)
            c_layout.addWidget(cb)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_hidden_indices(self) -> List[int]:
        hidden = []
        for idx, cb in enumerate(self.checkboxes):
            if not cb.isChecked():
                hidden.append(idx)
        return hidden
