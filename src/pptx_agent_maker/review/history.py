"""The record of every hand edit taken into a manifest, one line per page (= `review --apply` writes it).

取り込みは manifest を書き換えて終わるので、人が何をどう直したかは、取り込んだ後にはどこにも残らない。ここは
取り込んだ頁ごとに 1 行、何がどう直ったかと、直す前と後の版の在処を、道具の置き場 (= `.pptx-agent-maker/`)
の `reviews.jsonl` に足す。読むのは、人の直しを後から集める側 (= 道具の外。資料の好みを拾う)。
"""

from __future__ import annotations

import json
from pathlib import Path

from .ledger import STATE

#: 取り込んだ直しの記録 (= 1 行 1 頁の JSON。足すだけで、前の行は書き換えない)
HISTORY = "reviews.jsonl"


def history_path(deck: Path) -> Path:
    """Where the record of the edits taken in beside this deck is kept."""
    return Path(deck).parent / STATE / HISTORY


def record(deck: Path, rows: list[dict]) -> Path:
    """Add one line per row to the record beside the deck, and say where it is."""
    path = history_path(deck)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as out:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return path
