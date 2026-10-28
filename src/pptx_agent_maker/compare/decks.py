"""Compare two built decks page by page: draw both, lay the pictures over each other.

`pptx-agent-maker compare` calls this and prints what `report.py` makes of it.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from .bake import bake_pages, open_pages
from .page_difference import PageDifference
from .pictures import compare_pictures


def compare_decks(before: Path, after: Path) -> list[PageDifference]:
    """One `PageDifference` per page position of the two decks.

    ⚠ **2 つの資料は 1 本ずつ描く。**変換は 1 本が CPU 1 コアと数百 MB を使うので、同時に走らせない。
    LibreOffice は書体を置き換える時に、同じ資料でも描くたびに字の形を変えることがある (= 資料が名指した
    書体がこの機械に無い時)。違う画素の数は、その揺れも含む。
    """
    for deck in (before, after):
        if not deck.is_file():
            raise FileNotFoundError(f"deck not found: {deck}")
    with tempfile.TemporaryDirectory(prefix="pptx-compare-") as scratch:
        work = Path(scratch)
        pages_before = bake_pages(before, work / "before")
        pages_after = bake_pages(after, work / "after")
        return compare_pictures(open_pages(pages_before), open_pages(pages_after))
