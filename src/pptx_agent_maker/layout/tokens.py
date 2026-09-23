"""One table of sizes, colours and type. Pages reference it; they never pick their own.

**デザインが毎回変わるのは、頁が自分で寸法と色を決めるから。**同じ役割の頁を
別の週に書くと、書いた人 (や私) の気分で 2 pt ずれ、灰色が 3 種類に増える。
ここを 1 枚に閉じ込め、頁からは名前でしか触れないようにする。

An entire deck's look is this file. Change a token, every page moves together.

A project may swap two of them for its own — the typeface and the palette, through
`theme_from` at the bottom. Sizes and spacing stay here: a project that can move its
own margins is a project whose pages change shape from one round to the next.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, fields

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

    def line_height(self, size: float | None = None) -> int:
        """One line of type, including its leading."""
        return round(pt(self.type.body if size is None else size) * 1.45)

    def lines(self, text: str, width: int, size: float | None = None) -> int:
        """How many lines this text takes at that width.

        ⚠ **全角 1 文字ぶんの幅で数える** ― 日本語の頁なので、これが実寸に近く、
        英数字まじりでは多めに出る (= 余らせるほうへ外す)。折り返しを勘定せずに
        枠を割ると、見出しが本文に重なり、表の下の読み方が表の中へ入る
        (= どちらも実際に焼いて初めて出た)。
        """
        size = self.type.body if size is None else size
        per_line = max(int(width / pt(size)), 1)
        return max(sum(-(-len(line) // per_line) for line in str(text).split("\n")), 1)

    def text_height(self, text: str, width: int, size: float | None = None) -> int:
        """The height that text actually needs at that width."""
        return self.lines(text, width, size) * self.line_height(size)

    def table_row_height(self) -> int:
        """One row: the line box plus the cell padding. Nothing renders shorter."""
        return self.line_height() + 2 * self.spacing.cell_pad_y

    def table_height(self, rows, widths: list[int] | None = None) -> int:
        """What a table will actually occupy.

        行数だけを渡すと 1 行 1 段として数える。中身と列幅を渡すと**折り返しを
        勘定する** ― 長いラベルの列は 2 段にも 3 段にもなる。
        """
        if isinstance(rows, int):
            return rows * self.table_row_height()
        if widths is None:
            return len(rows) * self.table_row_height()
        total = 0
        for row in rows:
            tallest = 1
            for cell, width in zip(row, widths):
                usable = width - 2 * self.spacing.cell_pad_x
                tallest = max(tallest, self.lines(cell, max(usable, 1)))
            total += tallest * self.line_height() + 2 * self.spacing.cell_pad_y
        return total

    def column_widths(self, rows, total: int) -> list[int]:
        """Share the width out by how much each column has to say.

        均等に割ると、長いラベルの列だけが折り返して表が縦に伸び、下に置いたはずの
        読み方を飲み込む。中身の最大の長さに比例させ、どの列にも下限を置く。
        """
        columns = max(len(row) for row in rows)
        want = [max((len(str(row[i])) if i < len(row) else 0) for row in rows) or 1
                for i in range(columns)]
        floor = total // (columns * 3)
        room = total - floor * columns
        scale = sum(want)
        widths = [floor + round(room * w / scale) for w in want]
        widths[-1] = total - sum(widths[:-1])
        return widths

    def pt(self, size: float) -> int:
        """A type size in EMU, refusing anything below the floor."""
        if size < self.type.minimum:
            raise ValueError(f"{size}pt is below the {self.type.minimum}pt floor")
        return pt(size)


DEFAULT = Theme()


#: 色は 6 桁の 16 進で書く (= pptx がそう持つので、途中で変換しない)
_HEX = re.compile(r"\A[0-9A-Fa-f]{6}\Z")
#: 案件が自分で決めてよいもの。これ以外は道具が持つ
_MINE = ("font", "palette")


class ThemeError(ValueError):
    """The project asked for a look that cannot be read."""


def theme_from(settings: dict | None) -> Theme:
    """The look a project sets for itself: its typeface and its colours, nothing else.

    ⚠ **寸法と文字の大きさは受け取らない。**案件ごとに余白と級数が動くと、同じ役割の
    頁が週をまたいで別の形になる (= 前の世代が壊れた道)。**意匠 (= どの書体で、どの色で)
    は案件のもの、版面の割り方は道具のもの**という線をここで引く。

    ⚠ **知らないキーは捨てずに拒む。**綴り違いを黙って落とすと、書いた人は意匠を変えた
    つもりで、焼いた頁は既定のまま出る。
    """
    if not settings:
        return DEFAULT

    _refuse_unknown(sorted(set(settings) - set(_MINE)), "theme", _MINE)

    family = str(settings.get("font", Type().family)).strip()
    if not family:
        raise ThemeError("theme.font is empty — name a typeface, or leave the key out")

    colours = settings.get("palette") or {}
    known = tuple(f.name for f in fields(Palette))
    _refuse_unknown(sorted(set(colours) - set(known)), "theme.palette", known)
    for name, value in colours.items():
        if not _HEX.match(str(value)):
            raise ThemeError(
                f"theme.palette.{name} is {value!r} — a colour is six hex digits "
                'with no "#", as in "1F5FA9"'
            )

    return Theme(
        type=Type(family=family),
        palette=Palette(**{name: str(value).upper() for name, value in colours.items()}),
    )


def _refuse_unknown(unknown: list[str], where: str, known) -> None:
    if unknown:
        raise ThemeError(
            f"{where} does not take {', '.join(unknown)} (= it takes "
            f"{', '.join(sorted(known))}). A key nobody reads is a change that "
            "silently never happened."
        )
