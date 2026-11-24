"""What a built page holds, read off the elements the type placed: its words, its boxes, its parts, its lead.

The checks that judge how much a declared page asks of the reader (= `declared/wordy_page.py`,
`one_line_boxes.py`, `crowded_page.py`, `no_lead.py`) share these counts. Nothing here reads a file or
a deck: it takes a `Page` and answers, so a test can call it with a page it built.

⚠ **数える物は、人が頁を見て「1 つ」と数える物。** 箱の中の字は箱の一部で、箱とは別に数えない。線表の棒・
期間・レーンと、円の重なりは、まとめて 1 つの形の図 (= `diagram`) として数える (= 棒 1 本ずつ数えると、
線表が必ず「詰め込み」になる)。
"""

from __future__ import annotations

from typing import Iterator

from ...layout.geometry import Rect
from ...layout.parts.elements import Bar, Chart, Diamond, Ellipse, Fill, Figure, Table, Text
from ...layout.parts.page import Page

#: 頁の枠を作る字 (= 題・小見出し・札・出所) と、向きの印。語数に数えない
FRAME_TEXT = frozenset({"title", "kicker", "sticker", "footer", "marker"})
#: 箱の字として箱が持つ Text の kind
IN_A_BOX = frozenset({"box_heading", "box_body", "code"})
#: 箱として数える物
BOX_FILLS = frozenset({"box", "code_box"})
BOX_BARS = frozenset({"chevron", "voice"})
#: 文字の塊として数える Text の kind (= 帯・読み方・要点・本文)
TEXT_CHUNKS = frozenset({"band_text", "note", "points", "text", "display", "caption"})
#: 形の図を作る物 (= 線表と円の重なり)
DIAGRAM_BARS = frozenset({"bar", "span", "period"})
DIAGRAM_TEXT = frozenset({"lane", "diagram_text"})


def _letters(text: object) -> int:
    """How many characters a text has, spaces left out."""
    return len("".join(str(text).split()))


def characters(page: Page) -> int:
    """The characters of every word on the page but its frame (= title, kicker, sticker, footer) and a chart's own."""
    total = 0
    for element in page.elements:
        if isinstance(element, Text) and element.kind not in FRAME_TEXT:
            total += _letters(element.text)
        elif isinstance(element, Bar):
            total += _letters(element.text)
        elif isinstance(element, Table):
            total += sum(_letters(cell) for row in element.rows for cell in row)
    return total


def _lines_of(page: Page, text: str, width: int, size: float) -> int:
    return page.theme.wraps(text, max(width - 2 * page.theme.spacing.text_inset, 1), size)


def one_line_boxes(page: Page) -> int:
    """How many boxes hold their words on one line (= a heading alone is one line, too)."""
    texts = [e for e in page.elements if isinstance(e, Text) and e.kind in IN_A_BOX]
    count = 0
    for element in page.elements:
        if isinstance(element, Fill) and element.kind in BOX_FILLS:
            held = [t for t in texts if element.rect.contains(t.rect)]
            lines = sum(_lines_of(page, t.text, t.rect.width, t.size) for t in held)
            count += 1 if held and lines == 1 else 0
        elif isinstance(element, Bar) and element.kind in BOX_BARS:
            count += 1 if _lines_of(page, element.text, element.rect.width, element.size) == 1 else 0
    return count


def diagram(page: Page) -> Rect | None:
    """The rectangle round the page's shape diagram (= a timeline's bars, overlapping circles), or None."""
    shapes = [e.rect for e in page.elements
              if (isinstance(e, Bar) and e.kind in DIAGRAM_BARS) or isinstance(e, Diamond)
              or (isinstance(e, Ellipse) and e.kind == "circle")
              or (isinstance(e, Text) and e.kind in DIAGRAM_TEXT)]
    if not shapes:
        return None
    left, top = min(r.left for r in shapes), min(r.top for r in shapes)
    return Rect(left, top, max(r.right for r in shapes) - left, max(r.bottom for r in shapes) - top)


def parts(page: Page) -> list[tuple[str, Rect]]:
    """Each thing the reader counts on the page, as (what it is, where): `figure`, `chart`, `table`, `diagram`, `box`, `text`."""
    found: list[tuple[str, Rect]] = []
    for element in page.elements:
        if isinstance(element, Figure) and element.kind == "figure":
            found.append(("figure", element.rect))
        elif isinstance(element, Chart):
            found.append(("chart", element.rect))
        elif isinstance(element, Table):
            found.append(("table", element.rect))
        elif isinstance(element, Fill) and element.kind in BOX_FILLS:
            found.append(("box", element.rect))
        elif isinstance(element, Bar) and element.kind in BOX_BARS:
            found.append(("box", element.rect))
        elif isinstance(element, Text) and element.kind in TEXT_CHUNKS:
            found.append(("text", element.rect))
    shape = diagram(page)
    if shape is not None:
        found.append(("diagram", shape))
    return found


def lead(page: Page) -> str | None:
    """What the page's largest part is (= `figure`, `chart`, `table`, `diagram`, `box` or `text`), None for an empty page."""
    found = parts(page)
    if not found:
        return None
    return max(found, key=lambda part: part[1].width * part[1].height)[0]


def is_a_picture(kind: str | None) -> bool:
    """Whether a lead is something to look at, not words (= a figure, a chart, a shape diagram)."""
    return kind in ("figure", "chart", "diagram")


def judged(manifest, pages: dict | None) -> Iterator[tuple[int, str, Page]]:
    """The declared pages these checks judge, as (number in the manifest, its title, the built page).

    The agenda is the deck's own scaffolding and is not judged; neither is a page that was not built.
    """
    for number, entry in enumerate(manifest.entries, start=1):
        if entry.kind == "declare" and entry.data.get("type") != "agenda" and number in (pages or {}):
            yield number, str(entry.data.get("title", ""))[:60], pages[number]
