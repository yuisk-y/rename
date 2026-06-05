from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.history import HistoryStore, RenamePair
from app.naming import validate_target_path


MoveFunc = Callable[[Path, Path], None]


@dataclass(frozen=True)
class RenamePlan:
    source: Path
    target: Path


@dataclass(frozen=True)
class RenameResult:
    success_count: int
    pairs: list[RenamePair]


class RenameValidationError(Exception):
    def __init__(self, messages: list[str]) -> None:
        self.messages = messages
        super().__init__("\n".join(messages))


class RenameExecutionError(Exception):
    pass


def configure_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        encoding="utf-8",
    )


def default_log_path() -> Path:
    return HistoryStore().path.with_name("app.log")


def safe_move(source: Path, target: Path) -> None:
    if target.exists():
        raise FileExistsError(f"目标已存在：{target.name}")
    source.rename(target)


def build_plans(paths: list[Path], target_names: list[str]) -> list[RenamePlan]:
    if len(paths) != len(target_names):
        raise ValueError("源对象数量与目标名称数量不一致")
    return [
        RenamePlan(source=path, target=path.with_name(target_name))
        for path, target_name in zip(paths, target_names)
    ]


def precheck_rename(plans: list[RenamePlan]) -> list[str]:
    errors: list[str] = []
    seen_targets: dict[str, Path] = {}
    sources = {plan.source.resolve() for plan in plans if plan.source.exists()}

    for plan in plans:
        source = plan.source
        target = plan.target
        label = source.name

        if not source.exists():
            errors.append(f"{label}：对象不存在")
            continue
        if not source.is_file() and not source.is_dir():
            errors.append(f"{label}：不是文件或文件夹")
            continue
        if source.parent != target.parent:
            errors.append(f"{label}：目标路径必须位于原文件夹")

        try:
            source.stat()
        except OSError as exc:
            errors.append(f"{label}：无法读取对象状态：{exc}")

        if not os.access(source.parent, os.W_OK):
            errors.append(f"{label}：当前用户可能没有重命名权限")
        if source.is_file() and not os.access(source, os.W_OK):
            errors.append(f"{label}：当前用户可能没有修改文件权限")

        for message in validate_target_path(target):
            errors.append(f"{label} → {target.name}：{message}")

        target_key = target.name.casefold()
        if target_key in seen_targets:
            errors.append(
                f"{label} → {target.name}：目标名称与 {seen_targets[target_key].name} 重复"
            )
        else:
            seen_targets[target_key] = source

        if target.exists() and target.resolve() not in sources:
            errors.append(f"{label} → {target.name}：目标已存在，不能覆盖")

    return errors


class RenameService:
    def __init__(
        self,
        history_store: HistoryStore | None = None,
        move_func: MoveFunc = safe_move,
        log_path: Path | None = None,
    ) -> None:
        self.history_store = history_store or HistoryStore()
        self.move_func = move_func
        configure_logging(log_path or default_log_path())

    def validate_or_raise(self, plans: list[RenamePlan]) -> None:
        errors = precheck_rename(plans)
        if errors:
            raise RenameValidationError(errors)

    def rename(self, plans: list[RenamePlan]) -> RenameResult:
        return self._rename(plans, record_history=True)

    def undo_last(self) -> RenameResult:
        history = self.history_store.load()
        if history is None:
            raise RenameValidationError(["没有可撤销的重命名记录"])

        plans = [
            RenamePlan(source=Path(pair.renamed), target=Path(pair.original))
            for pair in history.pairs
        ]
        self.validate_or_raise(plans)
        result = self._rename(plans, record_history=False)
        self.history_store.clear()
        return result

    def rename_without_history(self, plans: list[RenamePlan]) -> RenameResult:
        return self._rename(plans, record_history=False)

    def _rename(self, plans: list[RenamePlan], record_history: bool) -> RenameResult:
        self.validate_or_raise(plans)
        temp_plans: list[tuple[Path, Path, Path]] = []
        moved_to_temp: list[tuple[Path, Path]] = []
        moved_to_final: list[tuple[Path, Path]] = []

        for plan in plans:
            temp = self._unique_temp_path(plan.source)
            temp_plans.append((plan.source, temp, plan.target))

        try:
            for source, temp, _target in temp_plans:
                self.move_func(source, temp)
                moved_to_temp.append((temp, source))

            for source, temp, target in temp_plans:
                self.move_func(temp, target)
                moved_to_final.append((target, source))
        except Exception as exc:  # noqa: BLE001 - rollback must catch all rename failures
            logging.exception("批量重命名失败，开始回滚")
            rollback_errors = self._rollback(moved_to_final, moved_to_temp)
            detail = str(exc)
            if rollback_errors:
                detail += "\n回滚时也遇到问题：\n" + "\n".join(rollback_errors)
            raise RenameExecutionError(detail) from exc

        pairs = [
            RenamePair(original=str(plan.source), renamed=str(plan.target))
            for plan in plans
            if plan.source != plan.target
        ]
        if pairs and record_history:
            self.history_store.save(pairs)
        return RenameResult(success_count=len(pairs), pairs=pairs)

    def _unique_temp_path(self, source: Path) -> Path:
        for _ in range(100):
            temp_name = f".__renaming_{uuid.uuid4().hex}{source.suffix}.tmp"
            temp_path = source.with_name(temp_name)
            if not temp_path.exists():
                return temp_path
        raise RenameExecutionError("无法生成唯一临时名称")

    def _rollback(
        self,
        moved_to_final: list[tuple[Path, Path]],
        moved_to_temp: list[tuple[Path, Path]],
    ) -> list[str]:
        errors: list[str] = []

        for current, original in reversed(moved_to_final):
            if not current.exists():
                continue
            try:
                if original.exists():
                    errors.append(f"无法回滚 {current.name}：原路径已被占用")
                    continue
                self.move_func(current, original)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{current.name} → {original.name}：{exc}")
                logging.exception("回滚最终对象失败：%s -> %s", current, original)

        for temp, original in reversed(moved_to_temp):
            if not temp.exists():
                continue
            try:
                if original.exists():
                    errors.append(f"无法回滚临时对象 {temp.name}：原路径已被占用")
                    continue
                self.move_func(temp, original)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{temp.name} → {original.name}：{exc}")
                logging.exception("回滚临时对象失败：%s -> %s", temp, original)

        return errors

