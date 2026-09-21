"""One table of sizes, colours and type. Pages reference it; they never pick their own.

**デザインが毎回変わるのは、頁が自分で寸法と色を決めるから。**同じ役割の頁を
別の週に書くと、書いた人 (や私) の気分で 2 pt ずれ、灰色が 3 種類に増える。
ここを 1 枚に閉じ込め、頁からは名前でしか触れないようにする。

An entire deck's look is this file. Change a token, every page moves together.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .geometry import Rect, cm, pt

SLIDE_16_9 = Rect(0, 0, 12192000, 6858000)


@dataclass(frozen=True)
class Type:
    """Type sizes in points. `minimum` is the floor anything printed must clear."""

    title: float = 24
    heading: float = 16
    body: float = 12
    caption: float = 10
    minimum: float = 10
    family: str = "Meiryo"


@dataclass(frozen=True)
class Palette:
    """Colours by meaning, not by name. `good`/`bad` mark a reading, never decoration."""

    ink: str = "1A1A1A"
    muted: str = "6B6B6B"
    accent: str = "1F5FA9"
    good: str = "1F5FA9"
    bad: str = "B3261E"
    band: str = "EAF0F8"
    box: str = "FFF4E5"
    rule: str = "D9D9D9"
    paper: str = "FFFFFF"


@dataclass(frozen=True)
class Spacing:
    """The only distances a page may use."""

    margin_x: int = cm(1.2)
    margin_top: int = cm(0.9)
    margin_bottom: int = cm(0.9)
    gap_s: int = cm(0.3)
    gap_m: int = cm(0.6)
    gap_l: int = cm(1.0)
    pad: int = cm(0.35)
    title_height: int = cm(1.5)
    cell_pad_y: int = cm(0.08)
    cell_pad_x: int = cm(0.18)
    band_height: int = cm(1.1)
    footer_height: int = cm(0.7)


@dataclass(frozen=True)
class Theme:
    """Everything a page is allowed to know about how the deck looks."""

    slide: Rect = SLIDE_16_9
    type: Type = field(default_factory=Type)
    palette: Palette = field(default_factory=Palette)
    spacing: Spacing = field(default_factory=Spacing)

    def frame(self) -> Rect:
        """The slide minus its margins — where every page starts."""
        s = self.spacing
        return self.slide.inset(left=s.margin_x, right=s.margin_x,
                                top=s.margin_top, bottom=s.margin_bottom)

    def table_row_height(self) -> int:
        """One row: the line box plus the cell padding. Nothing renders shorter."""
        return round(pt(self.type.body) * 1.45) + 2 * self.spacing.cell_pad_y

    def table_height(self, rows: int) -> int:
        """What a table of this many rows will actually occupy."""
        return rows * self.table_row_height()

    def pt(self, size: float) -> int:
        """A type size in EMU, refusing anything below the floor."""
        if size < self.type.minimum:
            raise ValueError(f"{size}pt is below the {self.type.minimum}pt floor")
        return pt(size)


DEFAULT = Theme()
