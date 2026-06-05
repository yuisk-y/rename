from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.dialogs import MappingConfirmDialog
from app.file_model import FileTableModel
from app.history import HistoryStore
from app.naming import NamingOptions
from app.rename_service import RenameExecutionError, RenamePlan, RenameService, RenameValidationError


class FileTableView(QTableView):
    def mouseReleaseEvent(self, event) -> None:
        index = self.indexAt(event.position().toPoint())
        if (
            index.isValid()
            and index.column() == 0
            and event.button() == Qt.MouseButton.LeftButton
            and hasattr(self.model(), "toggle_row_included")
        ):
            self.model().toggle_row_included(index.row())
            self.selectRow(index.row())
            event.accept()
            return
        super().mouseReleaseEvent(event)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("教学资料排序重命名工具")
        self.resize(1180, 760)

        self.settings = QSettings()
        self.current_folder: Path | None = None
        self.model = FileTableModel()
        self.rename_service = RenameService(HistoryStore())
        self.search_matches: list[int] = []
        self.search_position = -1

        self._build_ui()
        self._connect_signals()
        self._apply_style()
        self._sync_options()
        self._update_actions()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        top_box = QGroupBox("文件夹")
        top_layout = QHBoxLayout(top_box)
        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)
        self.folder_edit.setPlaceholderText("尚未选择文件夹")
        self.choose_button = QPushButton("选择文件夹")
        self.refresh_button = QPushButton("刷新列表")
        top_layout.addWidget(QLabel("当前文件夹："))
        top_layout.addWidget(self.folder_edit, 1)
        top_layout.addWidget(self.choose_button)
        top_layout.addWidget(self.refresh_button)

        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索文件或文件夹名称，按 Enter 跳到下一个")
        self.prev_match_button = QPushButton("上一个")
        self.next_match_button = QPushButton("下一个")
        self.search_count_label = QLabel("0/0")
        search_layout.addWidget(QLabel("搜索："))
        search_layout.addWidget(self.search_edit, 1)
        search_layout.addWidget(self.prev_match_button)
        search_layout.addWidget(self.next_match_button)
        search_layout.addWidget(self.search_count_label)

        self.table = FileTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        self.table.setDragEnabled(True)
        self.table.setAcceptDrops(True)
        self.table.setDropIndicatorShown(True)
        self.table.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.table.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.table.setDragDropOverwriteMode(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)

        settings_box = QGroupBox("重命名设置")
        settings_layout = QGridLayout(settings_box)
        self.start_spin = QSpinBox()
        self.start_spin.setRange(1, 9999)
        self.start_spin.setValue(1)
        self.digits_spin = QSpinBox()
        self.digits_spin.setRange(1, 6)
        self.digits_spin.setValue(2)
        self.separator_edit = QLineEdit(". ")
        self.remove_old_check = QCheckBox("删除原有序号")
        self.remove_old_check.setChecked(True)
        self.confirm_check = QCheckBox("重命名前要求确认")
        self.confirm_check.setChecked(True)
        self.confirm_check.setEnabled(False)

        settings_layout.addWidget(QLabel("起始序号"), 0, 0)
        settings_layout.addWidget(self.start_spin, 0, 1)
        settings_layout.addWidget(QLabel("序号位数"), 0, 2)
        settings_layout.addWidget(self.digits_spin, 0, 3)
        settings_layout.addWidget(QLabel("分隔格式"), 0, 4)
        settings_layout.addWidget(self.separator_edit, 0, 5)
        settings_layout.addWidget(self.remove_old_check, 1, 0, 1, 2)
        settings_layout.addWidget(self.confirm_check, 1, 2, 1, 2)
        settings_layout.setColumnStretch(6, 1)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)

        button_layout = QHBoxLayout()
        self.rename_button = QPushButton("一键重命名")
        self.rename_button.setObjectName("PrimaryButton")
        self.exclude_button = QPushButton("屏蔽选中项")
        self.include_button = QPushButton("取消屏蔽")
        self.undo_button = QPushButton("撤销上次重命名")
        self.restore_button = QPushButton("恢复初始顺序")
        self.exit_button = QPushButton("退出")
        button_layout.addWidget(self.rename_button)
        button_layout.addWidget(self.exclude_button)
        button_layout.addWidget(self.include_button)
        button_layout.addWidget(self.undo_button)
        button_layout.addWidget(self.restore_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.exit_button)

        root.addWidget(top_box)
        root.addLayout(search_layout)
        root.addWidget(self.table, 1)
        root.addWidget(settings_box)
        root.addWidget(divider)
        root.addLayout(button_layout)
        self.setCentralWidget(central)

        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        self.addAction(exit_action)

    def _connect_signals(self) -> None:
        self.choose_button.clicked.connect(self.choose_folder)
        self.refresh_button.clicked.connect(self.refresh_folder)
        self.rename_button.clicked.connect(self.rename_items)
        self.exclude_button.clicked.connect(lambda: self.set_selected_included(False))
        self.include_button.clicked.connect(lambda: self.set_selected_included(True))
        self.undo_button.clicked.connect(self.undo_last)
        self.restore_button.clicked.connect(self.restore_initial_order)
        self.exit_button.clicked.connect(self.close)
        self.prev_match_button.clicked.connect(lambda: self.goto_search_match(-1))
        self.next_match_button.clicked.connect(lambda: self.goto_search_match(1))
        self.search_edit.textChanged.connect(self.update_search)
        self.search_edit.returnPressed.connect(lambda: self.goto_search_match(1))

        self.start_spin.valueChanged.connect(self._sync_options)
        self.digits_spin.valueChanged.connect(self._sync_options)
        self.separator_edit.textChanged.connect(self._sync_options)
        self.remove_old_check.stateChanged.connect(self._sync_options)
        self.model.preview_changed.connect(self._update_actions)
        self.model.order_changed.connect(self._after_model_order_changed)
        self.table.selectionModel().selectionChanged.connect(self._update_actions)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
                font-size: 10pt;
                color: #1f2933;
            }
            QGroupBox {
                border: 1px solid #d8dee6;
                border-radius: 6px;
                margin-top: 10px;
                padding: 10px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QLineEdit, QSpinBox {
                border: 1px solid #c8d1dc;
                border-radius: 4px;
                padding: 5px 7px;
                background: #ffffff;
            }
            QTableView {
                border: 1px solid #d8dee6;
                gridline-color: #edf1f5;
                selection-background-color: #dbeafe;
                selection-color: #102a43;
                alternate-background-color: #f8fafc;
            }
            QHeaderView::section {
                background: #eef2f7;
                border: none;
                border-right: 1px solid #d8dee6;
                border-bottom: 1px solid #d8dee6;
                padding: 7px;
                font-weight: 600;
            }
            QPushButton {
                border: 1px solid #b8c2cc;
                border-radius: 5px;
                padding: 7px 13px;
                background: #ffffff;
            }
            QPushButton:hover {
                background: #f3f6f9;
            }
            QPushButton:disabled {
                color: #97a3b1;
                background: #f1f3f5;
            }
            QPushButton#PrimaryButton {
                background: #1f6feb;
                border-color: #1f6feb;
                color: white;
                font-weight: 700;
            }
            QPushButton#PrimaryButton:hover {
                background: #185abc;
            }
            """
        )

    def _sync_options(self) -> None:
        options = NamingOptions(
            start_number=self.start_spin.value(),
            digits=self.digits_spin.value(),
            separator=self.separator_edit.text(),
            remove_old_number=self.remove_old_check.isChecked(),
        )
        self.model.set_options(options)

    def _update_actions(self) -> None:
        has_folder = self.current_folder is not None
        has_rows = self.model.row_count_value() > 0
        has_active = self.model.active_count_value() > 0
        has_selection = self.table.selectionModel().hasSelection()
        has_errors = self.model.has_errors()
        has_search = bool(self.search_matches)

        self.refresh_button.setEnabled(has_folder)
        self.exclude_button.setEnabled(has_rows and has_selection)
        self.include_button.setEnabled(has_rows and has_selection)
        self.restore_button.setEnabled(has_rows and self.model.dirty)
        self.rename_button.setEnabled(has_folder and has_active and not has_errors)
        self.prev_match_button.setEnabled(has_search)
        self.next_match_button.setEnabled(has_search)

        if has_errors:
            self.rename_button.setToolTip("请先处理状态列中标识的问题")
        elif not has_active:
            self.rename_button.setToolTip("至少保留一个未屏蔽对象")
        else:
            self.rename_button.setToolTip("按当前顺序批量重命名未屏蔽对象")

    @Slot()
    def choose_folder(self) -> None:
        initial = self.settings.value("last_folder", "", str)
        folder = QFileDialog.getExistingDirectory(self, "选择教学资料文件夹", initial)
        if not folder:
            return
        self._load_folder(Path(folder))
        self.settings.setValue("last_folder", folder)

    @Slot()
    def refresh_folder(self) -> None:
        if self.current_folder is None:
            return
        if self.model.dirty:
            reply = QMessageBox.question(
                self,
                "确认刷新",
                "当前排序或屏蔽状态已被调整。刷新会重新读取列表并丢失当前调整，是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._load_folder(self.current_folder)

    def _load_folder(self, folder: Path) -> None:
        try:
            self.model.load_folder(folder)
        except OSError as exc:
            QMessageBox.critical(self, "读取失败", f"无法读取文件夹：\n{exc}")
            return
        self.current_folder = folder
        self.folder_edit.setText(str(folder))
        self.statusBar().showMessage(f"已读取 {self.model.row_count_value()} 个对象", 5000)
        self.update_search()
        self._update_actions()

    @Slot()
    def set_selected_included(self, included: bool) -> None:
        row = self._selected_row()
        if row is None:
            return
        self.model.set_row_included(row, included)

    @Slot()
    def update_search(self) -> None:
        query = self.search_edit.text()
        self.search_matches = self.model.matching_rows(query)
        self.search_position = 0 if self.search_matches else -1
        self._apply_search_position(scroll=bool(query.strip()))

    @Slot()
    def goto_search_match(self, step: int) -> None:
        if not self.search_matches:
            return
        self.search_position = (self.search_position + step) % len(self.search_matches)
        self._apply_search_position(scroll=True)

    def _apply_search_position(self, scroll: bool) -> None:
        current_row = None
        if self.search_matches and 0 <= self.search_position < len(self.search_matches):
            current_row = self.search_matches[self.search_position]
            self.search_count_label.setText(f"{self.search_position + 1}/{len(self.search_matches)}")
        elif self.search_edit.text().strip():
            self.search_count_label.setText("0/0")
        else:
            self.search_count_label.setText("0/0")

        self.model.set_search_highlight(self.search_matches, current_row)
        if current_row is not None and scroll:
            index = self.model.index(current_row, 3)
            self.table.selectRow(current_row)
            self.table.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtCenter)
        self._update_actions()

    def _after_model_order_changed(self) -> None:
        self.update_search()
        self._update_actions()

    @Slot()
    def rename_items(self) -> None:
        plans = self.model.plans()
        try:
            self.rename_service.validate_or_raise(plans)
        except RenameValidationError as exc:
            QMessageBox.warning(self, "无法重命名", "\n".join(exc.messages))
            self.model.update_previews()
            return

        mappings = [f"{plan.source.name}  →  {plan.target.name}" for plan in plans if plan.source != plan.target]
        if not mappings:
            QMessageBox.information(self, "无需重命名", "当前预览与原名称一致，没有需要修改的对象。")
            return

        dialog = MappingConfirmDialog(
            "确认批量重命名",
            f"即将重命名 {len(mappings)} 个对象。请确认以下完整映射，执行过程中不会覆盖已有对象。",
            mappings,
            self,
        )
        if dialog.exec() != MappingConfirmDialog.DialogCode.Accepted:
            return

        try:
            result = self.rename_service.rename(plans)
        except RenameValidationError as exc:
            QMessageBox.warning(self, "无法重命名", "\n".join(exc.messages))
            self.model.update_previews()
            return
        except RenameExecutionError as exc:
            QMessageBox.critical(self, "重命名失败", str(exc))
            self.model.update_previews()
            return

        QMessageBox.information(self, "重命名完成", f"成功修改 {result.success_count} 个对象。")
        if self.current_folder is not None:
            self._load_folder(self.current_folder)

    @Slot()
    def undo_last(self) -> None:
        history = self.rename_service.history_store.load()
        if history is None:
            QMessageBox.information(self, "无法撤销", "没有可撤销的重命名记录。")
            return

        plans = [
            RenamePlan(source=Path(pair.renamed), target=Path(pair.original))
            for pair in history.pairs
        ]
        try:
            self.rename_service.validate_or_raise(plans)
        except RenameValidationError as exc:
            QMessageBox.warning(self, "无法撤销", "\n".join(exc.messages))
            return

        mappings = [
            f"{Path(pair.renamed).name}  →  {Path(pair.original).name}"
            for pair in history.pairs
        ]
        dialog = MappingConfirmDialog(
            "确认撤销",
            f"即将撤销 {len(mappings)} 个对象的上次重命名操作。请确认以下完整映射。",
            mappings,
            self,
        )
        if dialog.exec() != MappingConfirmDialog.DialogCode.Accepted:
            return

        try:
            result = self.rename_service.undo_last()
        except RenameValidationError as exc:
            QMessageBox.warning(self, "无法撤销", "\n".join(exc.messages))
            return
        except RenameExecutionError as exc:
            QMessageBox.critical(self, "撤销失败", str(exc))
            return

        QMessageBox.information(self, "撤销完成", f"成功恢复 {result.success_count} 个对象。")
        if self.current_folder is not None:
            self._load_folder(self.current_folder)

    @Slot()
    def restore_initial_order(self) -> None:
        self.model.restore_initial_order()
        self.statusBar().showMessage("已恢复初始顺序和屏蔽状态", 3000)

    def _selected_row(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return rows[0].row()

    def closeEvent(self, event) -> None:
        QApplication.instance().quit()
        event.accept()

