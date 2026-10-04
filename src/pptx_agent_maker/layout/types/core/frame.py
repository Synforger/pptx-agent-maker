"""What any page may add around its body: cards above it, the legend, the table and the readings below."""

from __future__ import annotations

from ...base.geometry import Rect
from ...parts.page import Page, PageFullError
from .read import Spec
from .registry import PageTypeError
from .stack import _card_height


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


def _reserve_legend(page: Page, spec: Spec, area: Rect) -> tuple[Rect, list[str] | None]:
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


def _place_legend(page: Page, names: list[str] | None, area: Rect) -> None:
    """Put the legend just under what the body actually used (= the cards above it included)."""
    if not names:
        return
    used = max((element.rect.bottom for element in page.elements
                if area.top <= element.rect.top <= area.bottom), default=area.top)
    height = page.legend_height(area.width, names)
    page.legend(Rect(area.left, used + page.theme.spacing.gap_s, area.width, height), names)


def _place_cards(page: Page, spec: Spec, area: Rect) -> Rect:
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
    tall = _card_height(page, cards, area.width, columns)
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


def _reserve_trailing(page: Page, spec: Spec, area: Rect) -> tuple[Rect, Rect | None]:
    """Keep room under the body for the table and the reading.

    ⚠ **表の高さは折り返しを勘定して測る。**行数だけで見積もっていた間は、長いラベルが
    2 段に折り返したぶん表が伸び、下に置いたはずの読み方を飲み込んだ。
    """
    reserve = 0
    if spec.get("table") is not None:
        rows = spec.rows()
        widths = page.theme.column_widths(rows, area.width)
        reserve += page.theme.table_height(rows, widths) + page.theme.spacing.gap_m
    # ⚠ **要点は、置くときと同じ行で測る。**配列を文字列に直して測っていた間は、何行あっても
    # 1 行ぶんしか取らず、置いた要点が下の読み方に重なった
    for text in ("\n".join(_point_lines(spec)), spec.text("note")):
        if text:
            reserve += page.theme.text_height(text, area.width) + page.theme.spacing.gap_s
    if not reserve:
        return area, None
    if reserve >= area.height:
        raise PageFullError(
            f"the table and the reading need {reserve} EMU and the body has "
            f"{area.height} — this is two pages, not one"
        )
    body, _rest = area.split_top(area.height - reserve, gap=page.theme.spacing.gap_m)
    return body, area


def _point_lines(spec: Spec) -> list[str]:
    """The points a page hands over, one per line (= written as a list, or as lines of one string)."""
    points = spec.get("points")
    if not points:
        return []
    if isinstance(points, str):
        return [line for line in points.split("\n") if line.strip()]
    return [str(point) for point in points]


def _place_trailing(page: Page, spec: Spec, area: Rect | None) -> None:
    """Put the table and the reading under whatever the body actually used."""
    if area is None:
        return
    used = max((element.rect.bottom for element in page.elements
                if area.top <= element.rect.top <= area.bottom), default=area.top)
    rest = Rect(area.left, used + page.theme.spacing.gap_m, area.width,
                max(area.bottom - used - page.theme.spacing.gap_m, 1))
    if spec.get("table") is not None:
        placed = page.table(rest, spec.rows())
        rest = Rect(rest.left, placed.bottom + page.theme.spacing.gap_s, rest.width,
                    max(rest.bottom - placed.bottom - page.theme.spacing.gap_s, 1))
    note = spec.text("note")
    if spec.get("points"):
        lines = _point_lines(spec)
        # 読み方のぶんを先に除けてから要点を置く (= 足りないときに読み方が要点の上に
        # 重なるのを防ぐ。どちらも同じ「本体の下」を分け合う)
        kept = (page.theme.text_height(note, rest.width) + page.theme.spacing.gap_s
                if note else 0)
        tall = page.theme.text_height("\n".join(lines), rest.width)
        block, rest = rest.split_top(min(tall, max(rest.height - kept, 1)),
                                     gap=page.theme.spacing.gap_s)
        page.points(block, lines)
    if note:
        page.note(rest, note)
