"""The body written as rows of cells, nested as deep as it needs: `compose`.

**型は組み方の短縮形で、組み方そのものではない。**型だけで頁を組んでいた間は、型が想定して
いない組み方 (= 上に目標を 1 枚、下に柱を 2 枚) を書くたびに道具を直すことになり、直すまでは
指定の方を曲げて組んでいた。ここでは本体を**段 (= 上から下) とマス (= 左から右)** の入れ子で
書き、マスには部品を 1 つ置く。部品は今の型そのものも含む (= 線表を 1 マスに丸ごと入れる)。

守っているものは型の頁と同じ 3 つ:

* **座標を書く口は無い** ― 段とマスは枠を割るだけなので、頁からはみ出すことも、物どうしが
  重なることも、割り方の上で起きない
* **大きさと色は `tokens.py` の 1 枚から** ― 段とマスの間も、決まった間隔しか取れない
* **知らないキーは拒む** ― どの段のどのマスかを付けて言う

高さの決まり:

* カード・表・文章・要点だけの段は、**中身の言葉ぶんの高さ**になる (= 頁の高さを配らない)。
  同じ段のカードは、その段で一番高いカードに揃う
* 絵や型の入った段、`weight` を書いた段は、**残りの高さを `weight` の比で分け合う**
* そういう段の中に置いたカードや文章は、自分の高さのまま上に寄る

⚠ **この型は図を要らない頁として扱う。**カードだけで組む頁 (= 目標と柱) を拒むと、また指定を
曲げて組むことになる。
"""

from __future__ import annotations

from numbers import Real

from ...base.geometry import Rect
from ...parts.page import Card, Page, PageFullError
from ..core.registry import TYPES, PageTypeError, register
from ..core.read import Spec, read_card, read_table, only_keys
from ..core.stack import card_height
from .chart import place_chart

#: マスに 1 つ置ける部品のうち、ここで直に組む物
PARTS = ("card", "figure", "table", "text", "points", "chart")
#: マスに丸ごと入れられる型 (= その型の書き方のまま)。`cards` はマスごとの `card` で、
#: 入れ子は `rows` で書くので、この 2 つは入れない
BODIES = ("figures", "figure_grid", "flow", "roadmap", "timeline", "board", "agenda")


@register("compose", needs=["rows"], figure=False)
def _compose(page: Page, spec: Spec, area: Rect) -> None:
    """Rows top to bottom, cells left to right, one part in each cell (or more rows)."""
    _stack(page, spec, spec.get("rows"), area, "compose")


def _stack(page: Page, spec: Spec, rows, area: Rect, where: str) -> None:
    """Lay rows down inside `area`: natural rows at their own height, the rest sharing what is left."""
    gap = page.theme.spacing.gap_m
    laid = _measure(page, spec, rows, area.width, where)
    fixed = sum(height for _row, _cells, height, _weight in laid if height is not None)
    shares = sum(weight for _row, _cells, height, weight in laid if height is None)
    left_over = area.height - fixed - gap * (len(laid) - 1)
    if left_over < 0 or (shares and left_over <= 0):
        raise PageFullError(
            f"{where}: the rows need {fixed + gap * (len(laid) - 1)} EMU of height before any "
            f"picture or diagram gets room, and there are {area.height} — fewer or shorter "
            "parts, or two pages; nothing will shrink")
    top = area.top
    for number, (row, cells, height, weight) in enumerate(laid, start=1):
        tall = height if height is not None else int(left_over * weight / shares)
        for index, (cell, column, natural) in enumerate(cells, start=1):
            _place(page, spec, cell, Rect(area.left + column.left, top, column.width, tall),
                   natural, height is not None, f"{where}: row {number}, cell {index}")
        top += tall + gap


def _measure(page: Page, spec: Spec, rows, width: int, where: str):
    """Each row with its cells, the row's own height (None = it shares the rest) and its share."""
    if not isinstance(rows, list) or not rows:
        raise PageTypeError(f"{where}: `rows` is empty — write at least one [[…rows]] with its cells")
    gap = page.theme.spacing.gap_m
    laid = []
    for number, row in enumerate(rows, start=1):
        what = f"{where}: row {number}"
        only_keys(row, {"cells", "weight"}, what)
        cells = row.get("cells")
        if not isinstance(cells, list) or not cells:
            raise PageTypeError(f"{what} has no cells — write [[…cells]] under it, one per part")
        for index, cell in enumerate(cells, start=1):
            only_keys(cell, {"weight", "rows", "caption", *PARTS, *BODIES}, f"{what}, cell {index}")
        weights = [_weight(cell, f"{what}, cell {index}") for index, cell in enumerate(cells, start=1)]
        columns = Rect(0, 0, width, 1).columns(weights, gap=gap)
        measured = [(cell, column, _natural(page, spec, cell, column.width, f"{what}, cell {index}"))
                    for index, (cell, column) in enumerate(zip(cells, columns), start=1)]
        shares = "weight" in row
        naturals = [natural for _cell, _column, natural in measured]
        height = None if shares or None in naturals else max(naturals)
        laid.append((row, measured, height, _weight(row, what)))
    return laid


def _weight(item: dict, what: str) -> float:
    value = item.get("weight", 1)
    if isinstance(value, bool) or not isinstance(value, Real) or value <= 0:
        raise PageTypeError(f"{what}: `weight` is a number above 0 (= a share), not {value!r}")
    return float(value)


def _part(cell: dict, what: str) -> str:
    """The one thing a cell holds."""
    named = [key for key in ("rows", *PARTS, *BODIES) if key in cell]
    if not named:
        raise PageTypeError(
            f"{what} holds nothing — give it one of: {', '.join(('rows',) + PARTS + BODIES)}")
    if len(named) > 1:
        raise PageTypeError(
            f"{what} holds {', '.join(named)} — one part per cell; put the others in cells beside it")
    if "caption" in cell and named[0] != "figure":
        raise PageTypeError(f"{what}: `caption` belongs to a figure, and this cell holds {named[0]}")
    return named[0]


def _natural(page: Page, spec: Spec, cell: dict, width: int, what: str) -> int | None:
    """How tall a cell is for its own words, or None when it takes whatever room it is given."""
    part = _part(cell, what)
    theme, s = page.theme, page.theme.spacing
    if part == "card":
        return card_height(page, [_the_card(spec, cell, what)], width, 1)
    if part == "table":
        rows = _table(cell, what)
        return theme.table_height(rows, theme.column_widths(rows, width))
    if part == "text":
        return theme.wrapped_height(str(cell["text"]), max(width - 2 * s.text_inset, 1))
    if part == "points":
        return page.points_height(width, _points(cell, what))
    if part == "rows":
        laid = _measure(page, spec, cell["rows"], width, what)
        if any(height is None for _row, _cells, height, _weight in laid):
            return None
        return sum(height for _r, _c, height, _w in laid) + s.gap_m * (len(laid) - 1)
    return None                                   # 絵と型は、渡された高さをそのまま使う


def _place(page: Page, spec: Spec, cell: dict, rect: Rect, natural: int | None, own_row: bool,
           what: str) -> None:
    """Put one cell's part in its rect.

    `own_row` は、段が中身の言葉ぶんの高さの段か (= その段のカードは段の高さに揃える)。
    残りを分け合う段では、自分の高さを持つ部品は自分の高さのまま上に寄る (= 頁の高さを配らない)。

    ⚠ **分け合う段が、自分の高さを持つ部品より低ければ止まる。**段の高さに切り詰めて置いていた間は、
    カードの字が箱からはみ出し、文章の枠は字より短かった。入れ子の段と表は、自分で同じことを言う。
    """
    part = _part(cell, what)
    if natural is not None and natural > rect.height and part in ("card", "text", "points"):
        raise PageFullError(
            f"{what}: this {part} needs {natural} EMU of height and its row has {rect.height} — "
            "give the row a larger `weight`, or take something off the page; nothing will shrink")
    fitted = rect if natural is None else Rect(rect.left, rect.top, rect.width, min(natural, rect.height))
    try:
        if part == "card":
            page.boxes(rect if own_row else fitted, [_the_card(spec, cell, what)])
        elif part == "table":
            page.table(fitted, _table(cell, what))
        elif part == "text":
            page.text(fitted, str(cell["text"]))
        elif part == "points":
            page.points(fitted, _points(cell, what))
        elif part == "rows":
            _stack(page, spec, cell["rows"], rect, what)
        elif part == "chart":
            place_chart(page, spec, cell["chart"], rect, f"{what}, chart")
        elif part == "figure":
            # 絵は横幅いっぱいで上に寄る (= 同じ段の表や文章と上端が揃う)。縦が足りなければ縮む
            source, aspect = Spec({"figure": cell["figure"]}, spec.asset, spec.aspect, spec.theme).figure()
            caption = str(cell.get("caption", ""))
            s, ty = page.theme.spacing, page.theme.type
            wanted = round(rect.width / aspect) + (
                s.gap_s + page.theme.wrapped_height(caption, max(rect.width - 2 * s.text_inset, 1),
                                                    ty.caption) if caption else 0)
            page.figure(Rect(rect.left, rect.top, rect.width, min(wanted, rect.height)), source,
                        aspect, caption=caption)
        else:
            if not isinstance(cell[part], dict):
                raise PageTypeError(f"{what}: `{part}` is a table of that type's own keys")
            _body(page, spec, part, cell[part], rect, what)
    except (PageTypeError, PageFullError) as reason:
        if str(reason).startswith(what):
            raise
        raise type(reason)(f"{what}: {reason}") from reason
    except ValueError as reason:
        raise PageTypeError(f"{what}: {reason}") from reason


def _body(page: Page, spec: Spec, name: str, data: dict, rect: Rect, what: str) -> None:
    """A whole page type, laid into one cell, read the way that type reads it."""
    filler, needs, takes, _figure = TYPES[name]
    missing = sorted(needs - data.keys())
    if missing:
        raise PageTypeError(f"{name}: missing {', '.join(missing)} — this type is not that part without it")
    unknown = sorted(data.keys() - needs - takes)
    if unknown:
        raise PageTypeError(
            f"{name}: does not take {', '.join(unknown)} inside a cell (= it reads "
            f"{', '.join(sorted(needs | takes))}; cards, tables and words go in cells of their own)")
    filler(page, Spec(data, spec.asset, spec.aspect, spec.theme), rect)


def _the_card(spec: Spec, cell: dict, what: str) -> Card:
    return read_card(spec, cell["card"], f"{what}, card")


def _table(cell: dict, what: str) -> list[list[str]]:
    return read_table(cell["table"], f"{what}: table")


def _points(cell: dict, what: str) -> list[str]:
    items = cell["points"]
    if isinstance(items, str):
        items = items.split("\n")
    if not isinstance(items, list):
        raise PageTypeError(f"{what}: `points` is a list of lines")
    lines = [str(item) for item in items if str(item).strip()]
    if not lines:
        raise PageTypeError(f"{what}: `points` is empty — drop the cell rather than leaving it blank")
    return lines
