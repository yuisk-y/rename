from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.file_model import FileTableModel


def ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_model_loads_files_and_folders(tmp_path: Path) -> None:
    ensure_app()
    (tmp_path / "文件.txt").write_text("data", encoding="utf-8")
    (tmp_path / "文件夹").mkdir()

    model = FileTableModel()
    model.load_folder(tmp_path)

    assert model.row_count_value() == 2
    assert model.active_count_value() == 2
    assert len(model.plans()) == 2


def test_excluded_item_is_gray_and_skipped_from_sequence(tmp_path: Path) -> None:
    ensure_app()
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")

    model = FileTableModel()
    model.load_folder(tmp_path)
    model.set_row_included(0, False)

    assert model.active_count_value() == 1
    assert len(model.plans()) == 1
    assert model.data(model.index(0, 1), Qt.ItemDataRole.DisplayRole) == "-"
    assert model.data(model.index(1, 1), Qt.ItemDataRole.DisplayRole) == "1"
    assert model.data(model.index(0, 6), Qt.ItemDataRole.DisplayRole) == "已屏蔽"
    assert model.data(model.index(0, 0), Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Unchecked


def test_sort_label_moves_item_to_target_sequence(tmp_path: Path) -> None:
    ensure_app()
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "c.txt").write_text("c", encoding="utf-8")

    model = FileTableModel()
    model.load_folder(tmp_path)

    assert model.setData(model.index(2, 2), "1", Qt.ItemDataRole.EditRole)

    assert model.data(model.index(0, 3), Qt.ItemDataRole.DisplayRole) == "c.txt"
    assert [plan.source.name for plan in model.plans()] == ["c.txt", "a.txt", "b.txt"]


def test_search_matches_without_filtering_rows(tmp_path: Path) -> None:
    ensure_app()
    (tmp_path / "需求与供给.pptx").write_text("a", encoding="utf-8")
    (tmp_path / "消费者理论.pptx").write_text("b", encoding="utf-8")

    model = FileTableModel()
    model.load_folder(tmp_path)

    matches = model.matching_rows("消费")
    model.set_search_highlight(matches, matches[0])

    assert matches == [0]
    assert model.row_count_value() == 2
    assert model.data(model.index(matches[0], 3), Qt.ItemDataRole.DisplayRole) == "消费者理论.pptx"

