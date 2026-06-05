from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


WINDOWS_ILLEGAL_CHARS = set('<>:"/\\|?*')
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

_OLD_PREFIX_PATTERNS = [
    re.compile(r"^\s*\d{1,3}\s*[\.\u3001\-_]\s*"),
    re.compile(r"^\s*第\s*\d{1,3}\s*章\s*[\.\u3001\-_ ]*\s*"),
]


@dataclass(frozen=True)
class NamingOptions:
    start_number: int = 1
    digits: int = 2
    separator: str = ". "
    remove_old_number: bool = True


def strip_old_sequence(stem: str) -> str:
    """Remove conservative chapter/order prefixes from a filename stem."""
    cleaned = stem
    for pattern in _OLD_PREFIX_PATTERNS:
        new_value = pattern.sub("", cleaned, count=1).strip()
        if new_value != cleaned and new_value:
            return new_value
    return stem.strip()


def build_number(index: int, options: NamingOptions) -> str:
    number = options.start_number + index
    digits = max(1, options.digits)
    return str(number).zfill(digits)


def build_new_name(path: Path, index: int, options: NamingOptions) -> str:
    stem = path.stem
    if options.remove_old_number:
        stem = strip_old_sequence(stem)
    return f"{build_number(index, options)}{options.separator}{stem}{path.suffix}"


def has_windows_illegal_chars(name: str) -> bool:
    return any(ch in WINDOWS_ILLEGAL_CHARS or ord(ch) < 32 for ch in name)


def is_windows_reserved_name(name: str) -> bool:
    base = name.split(".")[0].rstrip(" .").upper()
    return base in WINDOWS_RESERVED_NAMES


def validate_windows_filename(name: str) -> list[str]:
    errors: list[str] = []
    if not name or not name.strip():
        errors.append("目标文件名为空")
        return errors

    if name != name.strip():
        errors.append("目标文件名首尾不能包含空白字符")

    if has_windows_illegal_chars(name):
        errors.append("目标文件名包含 Windows 非法字符")

    if is_windows_reserved_name(name):
        errors.append("目标文件名属于 Windows 保留名称")

    if name.endswith((" ", ".")):
        errors.append("目标文件名不能以空格或句点结尾")

    if len(name) > 240:
        errors.append("目标文件名过长")

    return errors


def validate_target_path(path: Path) -> list[str]:
    errors = validate_windows_filename(path.name)
    if len(str(path)) > 245:
        errors.append("目标路径过长，可能无法在 Windows 中重命名")
    return errors

