from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
)


class MappingConfirmDialog(QDialog):
    def __init__(self, title: str, message: str, mappings: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(720, 480)

        label = QLabel(message)
        label.setWordWrap(True)

        mapping_box = QPlainTextEdit()
        mapping_box.setReadOnly(True)
        mapping_box.setPlainText("\n".join(mappings))
        mapping_box.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确认执行")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(label)
        layout.addWidget(mapping_box, 1)
        layout.addWidget(buttons)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

