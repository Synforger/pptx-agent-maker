"""What any page may add around its body: cards above it, the legend, the table and the readings below."""

from __future__ import annotations

from ...base.geometry import Rect
from ...parts.page import Page, PageFullError
from .read import Spec
from .registry import PageTypeError
from .stack import card_height


def _named_grounds(data, names: tuple[str, ...]) -> set[str]:
    """Every ground a project named that this page's tables ask for, however deep they sit."""
    found: set[str] = set()
    if isinstance(data, dict):
        if str(data.get("tone", "")) in names:
            found.add(str(data["tone"]))
        for value in data.values():
            found |= _named_grounds(value, names)
    elif isinstance(data, list):
        for value in data:
            found |= _named_grounds(value, names)
    return found


def reserve_legend(page: Page, spec: Spec, area: Rect) -> tuple[Rect, list[str] | None]:
    """Keep a line under the body for the legend, when the page uses a ground a project named.

    ⚠ **色に意味を持たせたら凡例を置く** (= 作法)。書く人に任せると、色だけが意味を運ぶ頁が残る。
    消すのは `legend = false` を書いた頁だけ。並びは `[theme.grounds]` に書いた順で、どの頁でも同じ。
    """
    shown = spec.get("legend", True)
    if not isinstance(shown, bool):
        raise PageTypeError(f"`legend` is true or false, not {shown!r}")
    used = _named_grounds(spec.data, page.theme.ground_names())
    names = [name for name in page.theme.ground_names() if name in used]
    if not shown or not names:
        return area, None
    tall = page.legend_height(area.width, names) + page.theme.spacing.gap_s
    if tall >= area.height:
        raise PageFullError(f"the legend alone needs {tall} EMU and the body has {area.height}")
    body, _rest = area.split_top(area.height - tall)
    return body, names


def used_bottom(page: Page, area: Rect) -> int:
    """How far down the things placed in an area reach (= its top, when nothing is in it).

    本体は渡された枠を使い切るとは限らない。下に続く物 (= 凡例、表、読み方) は、取っておいた場所の
    頭ではなく、本体が実際に使った所のすぐ下から置く。
    """
    return max((element.rect.bottom for element in page.elements
                if area.top <= element.rect.top <= area.bottom), default=area.top)


def place_legend(page: Page, names: list[str] | None, area: Rect) -> None:
    """Put the legend just under what the body actually used (= the cards above it included)."""
    if not names:
        return
    used = used_bottom(page, area)
    height = page.legend_height(area.width, names)
    page.legend(Rect(area.left, used + page.theme.spacing.gap_s, area.width, height), names)


def place_cards(page: Page, spec: Spec, area: Rect) -> Rect:
    """Cards above the body, only as tall as their own words."""
    if spec.get("cards") is None:
        return area
    cards = spec.cards()
    if not cards:
        raise PageTypeError("cards: the list is empty")
    columns = int(spec.get("card_columns", len(cards)))
    if columns < 1:
        raise PageTypeError("`card_columns` must be at least 1")
    lines = -(-len(cards) // columns)
    tall = card_height(page, cards, area.width, columns)
    wanted = tall * lines + page.theme.spacing.gap_m * (lines - 1)
    if wanted >= area.height:
        raise PageFullError(
            f"the cards alone need {wanted} EMU and the body has {area.height} — "
            "fewer cards, or shorter ones; they will not shrink"
        )
    band, rest = area.split_top(wanted, gap=page.theme.spacing.gap_m)
    for index, row in enumerate(band.rows(lines, gap=page.theme.spacing.gap_m)):
        page.boxes(row, cards[index * columns:(index + 1) * columns])
    return rest


def _below(page: Page, spec: Spec, width: int) -> list[tuple[str, int, int]]:
    """What sits under the body, top to bottom: (what it is, the gap above it, its own height).

    ⚠ **取る側と置く側が、同じ並びを読む。**別々に勘定していた間は、本体のすぐ下の空き (= 広い方) を
    下の最初の物が表の時にしか数えず、要点や読み方だけの頁は、取った場所が置く場所より 0.3cm
    短かった (= 短いぶんは、次の物との空きに食い込んでいた)。

    ⚠ **表の高さは折り返しを勘定して測る。**行数だけで見積もっていた間は、長いラベルが
    2 段に折り返したぶん表が伸び、下に置いたはずの読み方を飲み込んだ。

    ⚠ **要点は、置くときと同じ行で測る。**配列を文字列に直して測っていた間は、何行あっても
    1 行ぶんしか取らず、置いた要点が下の読み方に重なった。
    """
    theme, s = page.theme, page.theme.spacing
    found: list[tuple[str, int]] = []
    if spec.get("table") is not None:
        rows = spec.rows()
        found.append(("table", theme.table_height(rows, theme.column_widths(rows, width))))
    if spec.get("points"):
        found.append(("points", theme.text_height("\n".join(_point_lines(spec)), width)))
    if spec.text("note"):
        found.append(("note", theme.text_height(spec.text("note"), width)))
    # 本体との間は広く、下に続く物どうしの間は狭く
    return [(what, s.gap_m if index == 0 else s.gap_s, tall) for index, (what, tall) in enumerate(found)]


def reserve_trailing(page: Page, spec: Spec, area: Rect) -> tuple[Rect, Rect | None]:
    """Keep room under the body for the table, the points and the reading (= as much as `_below` says)."""
    reserve = sum(gap + tall for _what, gap, tall in _below(page, spec, area.width))
    if not reserve:
        return area, None
    if reserve >= area.height:
        raise PageFullError(
            f"the table and the reading need {reserve} EMU and the body has "
            f"{area.height} — this is two pages, not one"
        )
    body, _rest = area.split_top(area.height - reserve)
    return body, area


def _point_lines(spec: Spec) -> list[str]:
    """The points a page hands over, one per line (= written as a list, or as lines of one string)."""
    points = spec.get("points")
    if not points:
        return []
    if isinstance(points, str):
        return [line for line in points.split("\n") if line.strip()]
    return [str(point) for point in points]


def place_trailing(page: Page, spec: Spec, area: Rect | None) -> None:
    """Put the table, the points and the reading under whatever the body actually used."""
    if area is None:
        return
    top = used_bottom(page, area)
    for what, gap, tall in _below(page, spec, area.width):
        rect = Rect(area.left, top + gap, area.width, tall)
        if what == "table":
            page.table(rect, spec.rows())
        elif what == "points":
            page.points(rect, _point_lines(spec))
        else:
            # 読み方はいつも最後で、残りを全部使う (= 本体が枠を使い切らなかった頁では、取ったより広い)
            rect = Rect(rect.left, rect.top, rect.width, max(area.bottom - rect.top, tall))
            page.note(rect, spec.text("note"))
        top = rect.bottom
