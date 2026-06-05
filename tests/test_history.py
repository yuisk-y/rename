from pathlib import Path

from app.history import HistoryStore, RenamePair


def test_history_save_and_load(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.json")
    store.save(
        [
            RenamePair(
                original=str(tmp_path / "原文件.txt"),
                renamed=str(tmp_path / "01. 原文件.txt"),
            )
        ]
    )

    loaded = store.load()

    assert loaded is not None
    assert loaded.pairs[0].original.endswith("原文件.txt")
    assert loaded.pairs[0].renamed.endswith("01. 原文件.txt")

