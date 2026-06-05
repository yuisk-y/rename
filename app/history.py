from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class RenamePair:
    original: str
    renamed: str


@dataclass(frozen=True)
class RenameHistory:
    operated_at: str
    pairs: list[RenamePair]


def default_history_path() -> Path:
    root = os.environ.get("LOCALAPPDATA")
    if root:
        base = Path(root)
    else:
        base = Path.home() / "AppData" / "Local"
    return base / "TeachingFileSortRenamer" / "last_rename.json"


class HistoryStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_history_path()

    def save(self, pairs: list[RenamePair]) -> RenameHistory:
        history = RenameHistory(
            operated_at=datetime.now(timezone.utc).isoformat(),
            pairs=pairs,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "operated_at": history.operated_at,
                    "pairs": [asdict(pair) for pair in history.pairs],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return history

    def load(self) -> RenameHistory | None:
        if not self.path.exists():
            return None
        data = json.loads(self.path.read_text(encoding="utf-8"))
        pairs = [
            RenamePair(original=item["original"], renamed=item["renamed"])
            for item in data.get("pairs", [])
        ]
        if not pairs:
            return None
        return RenameHistory(operated_at=data.get("operated_at", ""), pairs=pairs)

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()

