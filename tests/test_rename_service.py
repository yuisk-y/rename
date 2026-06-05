from pathlib import Path

import pytest

from app.history import HistoryStore
from app.rename_service import (
    RenameExecutionError,
    RenamePlan,
    RenameService,
    RenameValidationError,
    build_plans,
    precheck_rename,
)


def write_file(path: Path, content: str = "data") -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def service(tmp_path: Path, move_func=None) -> RenameService:
    return RenameService(
        history_store=HistoryStore(tmp_path / "history.json"),
        log_path=tmp_path / "app.log",
        move_func=move_func or NoneSafeMove(),
    )


class NoneSafeMove:
    def __call__(self, source: Path, target: Path) -> None:
        if target.exists():
            raise FileExistsError(target)
        source.rename(target)


def test_two_phase_swap_names_success(tmp_path: Path) -> None:
    a = write_file(tmp_path / "消费者理论.pptx", "a")
    b = write_file(tmp_path / "需求与供给.pptx", "b")

    plans = [
        RenamePlan(source=a, target=tmp_path / "需求与供给.pptx"),
        RenamePlan(source=b, target=tmp_path / "消费者理论.pptx"),
    ]

    result = service(tmp_path).rename(plans)

    assert result.success_count == 2
    assert (tmp_path / "消费者理论.pptx").read_text(encoding="utf-8") == "b"
    assert (tmp_path / "需求与供给.pptx").read_text(encoding="utf-8") == "a"


def test_duplicate_target_names_rejected(tmp_path: Path) -> None:
    a = write_file(tmp_path / "a.txt")
    b = write_file(tmp_path / "b.txt")
    plans = build_plans([a, b], ["01. 课程.txt", "01. 课程.txt"])

    errors = precheck_rename(plans)

    assert any("重复" in error for error in errors)


def test_existing_target_rejected(tmp_path: Path) -> None:
    source = write_file(tmp_path / "课程.txt")
    write_file(tmp_path / "01. 课程.txt")
    plans = [RenamePlan(source=source, target=tmp_path / "01. 课程.txt")]

    with pytest.raises(RenameValidationError) as exc_info:
        service(tmp_path).rename(plans)

    assert "目标已存在" in str(exc_info.value)


def test_failure_rolls_back(tmp_path: Path) -> None:
    a = write_file(tmp_path / "a.txt", "a")
    b = write_file(tmp_path / "b.txt", "b")
    calls = {"count": 0}

    def flaky_move(source: Path, target: Path) -> None:
        calls["count"] += 1
        if calls["count"] == 4:
            raise OSError("模拟失败")
        if target.exists():
            raise FileExistsError(target)
        source.rename(target)

    plans = build_plans([a, b], ["01. a.txt", "02. b.txt"])

    with pytest.raises(RenameExecutionError):
        service(tmp_path, move_func=flaky_move).rename(plans)

    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "a"
    assert (tmp_path / "b.txt").read_text(encoding="utf-8") == "b"
    assert not list(tmp_path.glob(".__renaming_*"))


def test_undo_restores_original_names(tmp_path: Path) -> None:
    original = write_file(tmp_path / "课程.txt")
    svc = service(tmp_path)

    svc.rename([RenamePlan(source=original, target=tmp_path / "01. 课程.txt")])
    result = svc.undo_last()

    assert result.success_count == 1
    assert (tmp_path / "课程.txt").exists()
    assert not (tmp_path / "01. 课程.txt").exists()


def test_missing_file_has_clear_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.txt"
    plans = [RenamePlan(source=missing, target=tmp_path / "01. missing.txt")]

    with pytest.raises(RenameValidationError) as exc_info:
        service(tmp_path).rename(plans)

    assert "对象不存在" in str(exc_info.value)


def test_empty_folder_has_no_plans(tmp_path: Path) -> None:
    files = [path for path in tmp_path.iterdir() if path.is_file()]
    assert files == []
    assert build_plans(files, []) == []


def test_chinese_file_rename(tmp_path: Path) -> None:
    source = write_file(tmp_path / "需求与供给.pptx")
    result = service(tmp_path).rename(
        [RenamePlan(source=source, target=tmp_path / "01. 需求与供给.pptx")]
    )

    assert result.success_count == 1
    assert (tmp_path / "01. 需求与供给.pptx").exists()


def test_folder_rename_supported(tmp_path: Path) -> None:
    source = tmp_path / "课程资料"
    source.mkdir()
    (source / "说明.txt").write_text("nested", encoding="utf-8")

    result = service(tmp_path).rename(
        [RenamePlan(source=source, target=tmp_path / "01. 课程资料")]
    )

    assert result.success_count == 1
    assert (tmp_path / "01. 课程资料").is_dir()
    assert (tmp_path / "01. 课程资料" / "说明.txt").read_text(encoding="utf-8") == "nested"
