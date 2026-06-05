from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QByteArray, QMimeData, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor

from app.naming import NamingOptions, build_new_name, validate_target_path
from app.rename_service import RenamePlan


STATUS_READY = "就绪"
STATUS_NO_CHANGE = "无需修改"
STATUS_EXCLUDED = "已屏蔽"


@dataclass
class FileItem:
    path: Path
    included: bool = True
    preview_name: str = ""
    status: str = STATUS_READY


class FileTableModel(QAbstractTableModel):
    order_changed = Signal()
    preview_changed = Signal()

    HEADERS = ["参与", "顺序", "排序标签", "当前名称", "重命名预览", "类型", "状态"]

    def __init__(self) -> None:
        super().__init__()
        self._items: list[FileItem] = []
        self._initial_state: list[tuple[Path, bool]] = []
        self._options = NamingOptions()
        self._dirty = False
        self._search_rows: set[int] = set()
        self._current_search_row: int | None = None

    @property
    def dirty(self) -> bool:
        return self._dirty

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._items)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        item = self._items[index.row()]
        column = index.column()

        if role == Qt.ItemDataRole.CheckStateRole and column == 0:
            return Qt.CheckState.Checked if item.included else Qt.CheckState.Unchecked

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if column == 0:
                return ""
            if column == 1:
                return self._sequence_text(index.row())
            if column == 2:
                return self._sequence_text(index.row())
            if column == 3:
                return item.path.name
            if column == 4:
                return item.preview_name if item.included else "不参与重命名"
            if column == 5:
                return self._type_text(item.path)
            if column == 6:
                return item.status

        if role == Qt.ItemDataRole.ToolTipRole:
            if column == 0:
                return "点击切换是否参与重命名"
            if column == 2:
                return "输入目标顺序号后，该条目会移动到对应位置"
            if column in (3, 4, 6):
                return self.data(index, Qt.ItemDataRole.DisplayRole)

        if role == Qt.ItemDataRole.BackgroundRole:
            row = index.row()
            if row == self._current_search_row:
                return QColor("#fde68a")
            if row in self._search_rows:
                return QColor("#fef3c7")
            if not item.included:
                return QColor("#f1f3f5")
            if item.status not in (STATUS_READY, STATUS_NO_CHANGE):
                return QColor("#fff1f0")

        if role == Qt.ItemDataRole.ForegroundRole:
            if not item.included:
                return QColor("#8a95a3")
            if item.status == STATUS_READY:
                return QColor("#276749")
            if item.status == STATUS_NO_CHANGE:
                return QColor("#4a5568")
            if column == 6:
                return QColor("#b42318")

        if role == Qt.ItemDataRole.TextAlignmentRole and column in (0, 1, 2):
            return Qt.AlignmentFlag.AlignCenter

        return None

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid():
            return False

        if index.column() == 0 and role == Qt.ItemDataRole.CheckStateRole:
            return self.set_row_included(index.row(), value == Qt.CheckState.Checked)

        if index.column() == 2 and role == Qt.ItemDataRole.EditRole:
            try:
                target_position = int(str(value).strip())
            except ValueError:
                return False
            return self.move_row_to_sequence(index.row(), target_position)

        return False

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        base = super().flags(index)
        if index.isValid():
            flags = base | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled
            if index.column() == 0:
                flags |= Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
            if index.column() == 2 and self._items[index.row()].included:
                flags |= Qt.ItemFlag.ItemIsEditable
            return flags
        return base | Qt.ItemFlag.ItemIsDropEnabled

    def supportedDropActions(self) -> Qt.DropAction:
        return Qt.DropAction.MoveAction

    def supportedDragActions(self) -> Qt.DropAction:
        return Qt.DropAction.MoveAction

    def mimeTypes(self) -> list[str]:
        return ["application/x-file-row"]

    def mimeData(self, indexes: list[QModelIndex]) -> QMimeData:
        rows = sorted({index.row() for index in indexes})
        data = QMimeData()
        if rows:
            data.setData("application/x-file-row", QByteArray(str(rows[0]).encode("utf-8")))
        return data

    def canDropMimeData(
        self,
        data: QMimeData,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex,
    ) -> bool:
        return action == Qt.DropAction.MoveAction and data.hasFormat("application/x-file-row")

    def dropMimeData(
        self,
        data: QMimeData,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex,
    ) -> bool:
        if not self.canDropMimeData(data, action, row, column, parent):
            return False
        source_row = int(bytes(data.data("application/x-file-row")).decode("utf-8"))
        destination = row if row != -1 else parent.row()
        if destination < 0:
            destination = len(self._items)
        return self.moveRows(QModelIndex(), source_row, 1, QModelIndex(), destination)

    def moveRows(
        self,
        sourceParent: QModelIndex,
        sourceRow: int,
        count: int,
        destinationParent: QModelIndex,
        destinationChild: int,
    ) -> bool:
        if sourceParent.isValid() or destinationParent.isValid() or count != 1:
            return False
        if sourceRow < 0 or sourceRow >= len(self._items):
            return False
        if destinationChild < 0 or destinationChild > len(self._items):
            return False
        if destinationChild in (sourceRow, sourceRow + 1):
            return False

        self.beginMoveRows(sourceParent, sourceRow, sourceRow, destinationParent, destinationChild)
        item = self._items.pop(sourceRow)
        if destinationChild > sourceRow:
            destinationChild -= 1
        self._items.insert(destinationChild, item)
        self.endMoveRows()
        self._after_order_mutation()
        return True

    def load_folder(self, folder: Path) -> None:
        entries = sorted(
            (path for path in folder.iterdir() if path.is_file() or path.is_dir()),
            key=lambda p: (0 if p.is_dir() else 1, p.name.casefold()),
        )
        self.beginResetModel()
        self._items = [FileItem(path=path) for path in entries]
        self._initial_state = [(item.path, item.included) for item in self._items]
        self._dirty = False
        self._search_rows = set()
        self._current_search_row = None
        self.endResetModel()
        self.update_previews()

    def set_options(self, options: NamingOptions) -> None:
        self._options = options
        self.update_previews()

    def restore_initial_order(self) -> None:
        order = {path: index for index, (path, _included) in enumerate(self._initial_state)}
        included = {path: is_included for path, is_included in self._initial_state}
        self.beginResetModel()
        self._items.sort(key=lambda item: order.get(item.path, len(order)))
        for item in self._items:
            item.included = included.get(item.path, item.included)
        self._dirty = False
        self.endResetModel()
        self.update_previews()
        self.order_changed.emit()

    def set_row_included(self, row: int, included: bool) -> bool:
        if row < 0 or row >= len(self._items):
            return False
        self._items[row].included = included
        self._after_order_mutation()
        return True

    def toggle_row_included(self, row: int) -> bool:
        if row < 0 or row >= len(self._items):
            return False
        return self.set_row_included(row, not self._items[row].included)

    def move_row_to_sequence(self, row: int, target_position: int) -> bool:
        if row < 0 or row >= len(self._items):
            return False
        item = self._items[row]
        if not item.included:
            return False

        active_count = self.active_count_value()
        target_position = max(1, min(target_position, active_count))
        current_position = int(self._sequence_text(row))
        if target_position == current_position:
            return True

        self.beginResetModel()
        item = self._items.pop(row)
        insert_at = self._row_for_active_insert(target_position)
        self._items.insert(insert_at, item)
        self.endResetModel()
        self._after_order_mutation()
        return True

    def matching_rows(self, query: str) -> list[int]:
        normalized = query.strip().casefold()
        if not normalized:
            return []
        return [
            row
            for row, item in enumerate(self._items)
            if normalized in item.path.name.casefold()
            or (item.preview_name and normalized in item.preview_name.casefold())
        ]

    def set_search_highlight(self, rows: list[int], current_row: int | None) -> None:
        self._search_rows = set(rows)
        self._current_search_row = current_row
        if self._items:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self._items) - 1, len(self.HEADERS) - 1))

    def update_previews(self) -> None:
        source_paths = {item.path.resolve() for item in self._items if item.included and item.path.exists()}
        target_counts: dict[str, int] = {}
        active_index = 0

        for item in self._items:
            if not item.included:
                item.preview_name = ""
                continue
            item.preview_name = build_new_name(item.path, active_index, self._options)
            target_key = item.preview_name.casefold()
            target_counts[target_key] = target_counts.get(target_key, 0) + 1
            active_index += 1

        for item in self._items:
            if not item.included:
                item.status = STATUS_EXCLUDED
                continue

            target_path = item.path.with_name(item.preview_name)
            errors = validate_target_path(target_path)
            target_key = item.preview_name.casefold()

            if not item.path.exists():
                item.status = "对象不存在"
            elif not item.path.is_file() and not item.path.is_dir():
                item.status = "不是文件或文件夹"
            elif target_counts[target_key] > 1:
                item.status = "目标重复"
            elif target_path.exists() and target_path.resolve() not in source_paths:
                item.status = "目标已存在"
            elif errors:
                item.status = "；".join(errors)
            elif target_path == item.path:
                item.status = STATUS_NO_CHANGE
            else:
                item.status = STATUS_READY

        if self._items:
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self._items) - 1, len(self.HEADERS) - 1)
            self.dataChanged.emit(top_left, bottom_right)
        self.preview_changed.emit()

    def current_paths(self) -> list[Path]:
        return [item.path for item in self._items]

    def target_names(self) -> list[str]:
        return [item.preview_name for item in self._items if item.included]

    def plans(self) -> list[RenamePlan]:
        return [
            RenamePlan(source=item.path, target=item.path.with_name(item.preview_name))
            for item in self._items
            if item.included
        ]

    def has_errors(self) -> bool:
        return any(
            item.included and item.status not in (STATUS_READY, STATUS_NO_CHANGE)
            for item in self._items
        )

    def row_count_value(self) -> int:
        return len(self._items)

    def active_count_value(self) -> int:
        return sum(1 for item in self._items if item.included)

    def _sequence_text(self, row: int) -> str:
        item = self._items[row]
        if not item.included:
            return "-"
        return str(sum(1 for previous in self._items[: row + 1] if previous.included))

    def _type_text(self, path: Path) -> str:
        if path.is_dir():
            return "文件夹"
        return path.suffix.lower() or "(无扩展名)"

    def _row_for_active_insert(self, target_position: int) -> int:
        active_seen = 0
        for row, item in enumerate(self._items):
            if not item.included:
                continue
            active_seen += 1
            if active_seen >= target_position:
                return row
        return len(self._items)

    def _after_order_mutation(self) -> None:
        self._refresh_dirty()
        self.update_previews()
        self.order_changed.emit()

    def _refresh_dirty(self) -> None:
        self._dirty = [(item.path, item.included) for item in self._items] != self._initial_state

