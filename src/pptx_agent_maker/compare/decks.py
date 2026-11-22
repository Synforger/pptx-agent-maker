"""Compare two built decks page by page: draw both, lay the pictures over each other.

`pptx-agent-maker compare` calls this and prints what `report.py` makes of it.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from .bake import bake_decks, open_pages
from .page_difference import PageDifference
from .pictures import compare_pictures


def compare_decks(before: Path, after: Path) -> list[PageDifference]:
    """One `PageDifference` per page position of the two decks.

    ⚠ **2 つの資料は 1 回の変換にまとめて渡す** (= 理由は `bake.bake_decks`)。書体がこの機械に無い時、代わりの
    書体は前後で揃うが、次の回には変わりうる。違う画素の数を、別の回の数と比べない。
    """
    for deck in (before, after):
        if not deck.is_file():
            raise FileNotFoundError(f"deck not found: {deck}")
    with tempfile.TemporaryDirectory(prefix="pptx-compare-") as scratch:
        pages_before, pages_after = bake_decks([before, after], Path(scratch))
        return compare_pictures(open_pages(pages_before), open_pages(pages_after))
