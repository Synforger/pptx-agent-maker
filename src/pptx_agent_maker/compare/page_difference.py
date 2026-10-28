"""What comparing one page of two decks found: how many pixels differ, or that a side has no such page.

`pictures.py` makes these, `report.py` prints them.
"""

from __future__ import annotations

from dataclasses import dataclass

Size = tuple[int, int]


@dataclass(frozen=True)
class PageDifference:
    """One page position of the two decks.

    ⚠ **比べられない頁に数を入れない。**片方に頁が無い、または頁の寸法が違う頁は、画素を並べて数えられない。
    0 で埋めると「変わっていない」と読めるので、数は持たず `ratio` も `None` を返す。
    ``before_size`` / ``after_size`` はその側の頁の絵の寸法で、頁が無い側は `None`。
    """

    number: int
    before_size: Size | None
    after_size: Size | None
    differing_pixels: int = 0

    @property
    def is_comparable(self) -> bool:
        """Both decks have this page, drawn at the same size."""
        return self.before_size is not None and self.before_size == self.after_size

    @property
    def pixel_count(self) -> int | None:
        """How many pixels the page has, or None when its two sides cannot be laid over each other."""
        if not self.is_comparable:
            return None
        width, height = self.before_size
        return width * height

    @property
    def ratio(self) -> float | None:
        """The share of the page's pixels that differ, or None when the page was not compared."""
        count = self.pixel_count
        return None if count is None else self.differing_pixels / count

    @property
    def is_changed(self) -> bool:
        """A page one deck lacks or draws at another size counts as changed, like one with differing pixels."""
        return not self.is_comparable or self.differing_pixels > 0
