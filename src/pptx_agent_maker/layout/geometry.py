"""Rectangles that can only be divided, never placed by hand.

置き方を座標で書くのをやめ、**親の枠を割る**ことだけで頁を組む。そうすると 2 つが
構造で決まる ― 割って得た枠は必ず親の中に在り、兄弟どうしは重ならない。
置いてから番人で探す形 (= 枠外れを 1 行ぶん見逃す検査) が要らなくなる。

EMU (English Metric Units) で持つ。914400 EMU = 1 inch = 2.54 cm。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

EMU_PER_INCH = 914400
EMU_PER_CM = 360000


def cm(value: float) -> int:
    """Centimetres as EMU."""
    return round(value * EMU_PER_CM)


def pt(value: float) -> int:
    """Points as EMU (= 1/72 inch)."""
    return round(value * EMU_PER_INCH / 72)


@dataclass(frozen=True)
class Rect:
    """An area on the slide. Immutable: every operation returns a new one."""

    left: int
    top: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width < 0 or self.height < 0:
            raise ValueError(f"a rectangle cannot have negative extent: {self}")

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    def contains(self, other: "Rect") -> bool:
        """True when `other` sits entirely inside this rectangle."""
        return (
            other.left >= self.left
            and other.top >= self.top
            and other.right <= self.right
            and other.bottom <= self.bottom
        )

    def overlaps(self, other: "Rect") -> bool:
        """True when the two rectangles share any area (touching edges do not count)."""
        return (
            self.left < other.right
            and other.left < self.right
            and self.top < other.bottom
            and other.top < self.bottom
        )

    def inset(self, all: int = 0, *, x: int | None = None, y: int | None = None,
              left: int | None = None, top: int | None = None,
              right: int | None = None, bottom: int | None = None) -> "Rect":
        """Shrink inwards. Anything left unsaid falls back to the wider setting."""
        left = _first(left, x, all)
        right = _first(right, x, all)
        top = _first(top, y, all)
        bottom = _first(bottom, y, all)
        width = self.width - left - right
        height = self.height - top - bottom
        if width < 0 or height < 0:
            raise ValueError("inset is larger than the rectangle it is applied to")
        return Rect(self.left + left, self.top + top, width, height)

    def columns(self, weights: int | Sequence[float], gap: int = 0) -> list["Rect"]:
        """Divide left to right. An int means that many equal columns."""
        return self._divide(weights, gap, horizontal=True)

    def rows(self, weights: int | Sequence[float], gap: int = 0) -> list["Rect"]:
        """Divide top to bottom. An int means that many equal rows."""
        return self._divide(weights, gap, horizontal=False)

    def grid(self, rows: int, columns: int, gap: int = 0, row_gap: int | None = None) -> list[list["Rect"]]:
        """Rows of columns. The outer list is rows, each holding its cells."""
        return [band.columns(columns, gap) for band in self.rows(rows, _first(row_gap, gap))]

    def split_top(self, height: int, gap: int = 0) -> tuple["Rect", "Rect"]:
        """Take a fixed height off the top; the rest comes back with it.

        高さが中身で決まるもの (= 表) を置くための口。比で割ると、表が要る高さと
        割り当てた高さが食い違う。
        """
        if height > self.height:
            raise ValueError(f"{height} EMU does not fit in {self.height}")
        taken = Rect(self.left, self.top, self.width, height)
        # 枠ちょうどを取ったときは余りが無いだけで、割れないわけではない
        # (= 間の空きは、残りが在るときにだけ意味を持つ)
        left_over = max(self.height - height - gap, 0)
        rest = Rect(self.left, self.top + height + (gap if left_over else 0),
                    self.width, left_over)
        return taken, rest

    def fit(self, aspect: float) -> "Rect":
        """The largest centred rectangle of this aspect ratio (= width / height).

        絵は縦横比を保って収める。潰した絵を頁に置かないための唯一の口。
        """
        if aspect <= 0:
            raise ValueError("aspect ratio must be positive")
        if self.width / self.height > aspect:
            height = self.height
            width = round(height * aspect)
        else:
            width = self.width
            height = round(width / aspect)
        return Rect(
            self.left + (self.width - width) // 2,
            self.top + (self.height - height) // 2,
            width,
            height,
        )

    def _divide(self, weights: int | Sequence[float], gap: int, *, horizontal: bool) -> list["Rect"]:
        if isinstance(weights, int):
            weights = [1] * weights
        weights = list(weights)
        if not weights:
            raise ValueError("cannot divide into zero parts")
        if any(w <= 0 for w in weights):
            raise ValueError("every part needs a positive weight")

        extent = self.width if horizontal else self.height
        available = extent - gap * (len(weights) - 1)
        if available < 0:
            raise ValueError("the gaps alone are wider than the area being divided")

        total = sum(weights)
        parts: list[Rect] = []
        offset = 0
        for index, weight in enumerate(weights):
            # The last part takes the remainder, so rounding can neither leave a
            # sliver of the parent uncovered nor push the last edge past it.
            if index == len(weights) - 1:
                size = extent - offset
            else:
                size = round(available * weight / total)
            if horizontal:
                parts.append(Rect(self.left + offset, self.top, size, self.height))
            else:
                parts.append(Rect(self.left, self.top + offset, self.width, size))
            offset += size + gap
        return parts


def _first(*values: int | None) -> int:
    """The first value that was actually given, or 0."""
    for value in values:
        if value is not None:
            return value
    return 0
