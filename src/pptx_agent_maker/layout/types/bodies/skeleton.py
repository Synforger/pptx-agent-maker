"""The types allowed to carry no picture: the deck's own scaffolding."""

from __future__ import annotations

from ...base.geometry import Rect
from ...parts.elements import Ellipse, Fill, Text
from ...parts.look import Style
from ...parts.page import Card, Page, PageFullError
from ..core.read import Spec, read_tone
from ..core.registry import PageTypeError, register
from ..core.stack import card_height


@register("cards", needs=[], figure=False)
def _cards(page: Page, spec: Spec, area: Rect) -> None:
    """The cards are the page (= this week's plan, what a chapter concluded).

    カードは全型が添えられるので、この型の本体は空でよい ― `cards` を本体として
    置いた時点で、もう頁は組み上がっている。
    """
    if spec.get("cards") is None:
        raise PageTypeError("cards: this type is the cards; give it some")


@register("board", needs=["table"], figure=False)
def _board(page: Page, spec: Spec, area: Rect) -> None:
    """One table using the page (= the figures are the numbers).

    ⚠ **これは例外の型。**「表と文章だけの頁を出さない」の唯一の抜け道で、毎週
    積み上げる早見表のためにある (= 頁の面積は数字に使い、説明は指標の頁が持つ)。
    本文の頁をここに逃がさない。
    """


#: 章の番号の出し方 (= `numbers`)。丸の数字は字として在るのが 20 まで
NUMBERS = ("plain", "circled")
_CIRCLED = 0x2460


def _numbered(spec: Spec, count: int):
    """How a chapter's number is written in front of its name (= `1.` unless the page asks for circles)."""
    numbers = spec.get("numbers", "plain")
    if not isinstance(numbers, str) or numbers not in NUMBERS:
        raise PageTypeError(
            f"agenda: `numbers` is {numbers!r} — chapters are numbered {' or '.join(repr(n) for n in NUMBERS)}")
    if numbers == "circled" and count > 20:
        raise PageTypeError(
            f"agenda: {count} chapters cannot be numbered in circles — the circled numbers stop at 20")
    return (lambda number: chr(_CIRCLED + number - 1)) if numbers == "circled" else (lambda number: f"{number}.")


#: 目次の描き方 (= `look`)。`boxes` は字の高さの箱、`cards` は右の列を章の数で等分した角丸のカードに、
#: 番号を塗りの丸で置く (= 案件の資料で使ってきた目次の形)
LOOKS = ("boxes", "cards")
#: `cards` の右の列の見出し
CARDS_HEADING = "アジェンダ"
#: 章の名前と要旨を分ける記号 (= `名前 ― 要旨` は、名前を太字の 1 行目、要旨を細字の 2 行目にする)
SUMMARY = " ― "


def _agenda_cards(page: Page, area: Rect, buckets: list[tuple[str, list[str]]], here: int, item: int) -> None:
    """The agenda drawn as cards: the list on the left, a heading and one card per chapter on the right.

    左の一覧は章を `•`、小項目を一段下げた `–` で書き、今の章だけ差し色の太字にする (= `highlight_item`
    は今の章の小項目を 1 つ差し色の太字にする。章の途中から入り直す頁のため)。右のカードは列の高さを
    章の数で等分し、番号は塗りの丸に置く。今の章は差し色の丸に紙の色の数字、差し色のごく薄い地、
    差し色の題。ほかの章は灰の丸に灰の数字、灰の地、灰の題 (= 灰の丸に白の数字は読めない)。枠は引かない。
    """
    theme = page.theme
    t, s, p = theme.type, theme.spacing, theme.palette
    listing, right = area.columns([1, 1], gap=s.gap_l)
    rows: list[tuple[str, str, bool, int]] = []
    for number, (title, items) in enumerate(buckets, start=1):
        marked = number == here
        rows.append((f"\u2022 {title.split(SUMMARY, 1)[0]}", p.accent if marked else p.muted, marked, 0))
        for index, entry in enumerate(items, start=1):
            picked = marked and index == item
            rows.append((f"\u2013 {entry}", p.accent if picked else p.muted, picked, s.gap_m))
    heights = [theme.wrapped_height(text, max(listing.width - indent - 2 * s.text_inset, 1), t.body, bold=bold)
               for text, _colour, bold, indent in rows]
    if sum(heights) > listing.height:
        raise PageFullError(
            f"agenda: the list of items needs {sum(heights)} EMU of height and has {listing.height} — "
            "fewer items, or two pages; it will not shrink")
    top = listing.top
    for (text, colour, bold, indent), tall in zip(rows, heights):
        page.elements.append(Text("agenda_item", Rect(listing.left + indent, top, listing.width - indent, tall),
                                  text, t.body, colour, bold=bold))
        top += tall
    head, stack = right.split_top(theme.line_height(t.heading), gap=s.gap_s)
    page.elements.append(Text("agenda_heading", head, CARDS_HEADING, t.heading, p.ink, bold=True))
    disc = theme.line_height(t.heading) + s.gap_s
    for band, (number, (title, _items)) in zip(stack.rows(len(buckets), gap=s.gap_s),
                                                enumerate(buckets, start=1)):
        marked = number == here
        colour = p.accent if marked else p.muted
        name, _, summary = title.partition(SUMMARY)
        circle = Rect(band.left + s.pad, band.top + (band.height - disc) // 2, disc, disc)
        words = Rect(circle.right + s.gap_s, band.top + s.pad,
                     max(band.right - s.pad - circle.right - s.gap_s, 1), max(band.height - 2 * s.pad, 1))
        width = max(words.width - 2 * s.text_inset, 1)
        named = theme.wrapped_height(name, width, t.stage, bold=True)
        said = theme.wrapped_height(summary, width, t.body) if summary else 0
        if max(named + said, disc) > band.height - 2 * s.pad:
            raise PageFullError(
                f"agenda: chapter {number} needs {max(named + said, disc) + 2 * s.pad} EMU of height and its "
                f"share of the page is {band.height} — fewer chapters, or shorter names; it will not shrink")
        page.elements.append(Fill("agenda_card", band, p.thinned(p.FAINT) if marked else p.wash, rounded=True))
        page.elements.append(Ellipse("agenda_disc", circle, p.accent if marked else p.rule))
        page.elements.append(Text("agenda_number", circle, str(number), t.heading,
                                  p.paper if marked else p.muted, bold=True, align="center"))
        top = words.top + (words.height - named - said) // 2
        page.elements.append(Text("agenda_chapter", Rect(words.left, top, words.width, named), name, t.stage,
                                  colour, bold=True))
        if summary:
            page.elements.append(Text("agenda_summary", Rect(words.left, top + named, words.width, said),
                                      summary, t.body, colour))


@register("agenda", needs=["buckets"],
          takes=["highlight", "highlight_tone", "numbers", "look", "highlight_item"], figure=False)
def _agenda(page: Page, spec: Spec, area: Rect) -> None:
    """Every item on the left, the buckets on the right, this chapter marked.

    進行型の目次 (= 章の頭ごとに 1 枚置き、その章だけを強調する)。⚠ **実頁の無い
    小項目を書かない** ― 目次に残すと翌週がそれを輸入して持ち越す。

    強調は、書かなければ章の名前の下の言葉 (= `◀ この章`)。`highlight_tone` を書けば、その章の箱が
    その地になり、言葉は置かない (= 地が言っていることを、もう 1 度言葉で言わない)。`numbers = "circled"`
    は章の番号を丸の数字で書く。

    ⚠ **一覧も章の箱も、自分の言葉ぶんの高さが取れなければ止まる。**取れる高さに切り詰めて置いて
    いた間は、箱の中の字が箱の下の線に乗った (= 狭いマスに入れた目次で、焼いて出た)。
    """
    buckets = [(str(title), [str(item) for item in items])
               for title, items in spec.get("buckets")]
    if not buckets:
        raise PageTypeError("agenda: `buckets` is empty — an agenda with no chapters")
    here = int(spec.get("highlight", 0))
    if here and not 1 <= here <= len(buckets):
        raise PageTypeError(
            f"agenda: `highlight` is {here}, but there are {len(buckets)} buckets"
        )
    look = spec.get("look", "boxes")
    if not isinstance(look, str) or look not in LOOKS:
        raise PageTypeError(f"agenda: `look` is {look!r} — an agenda is drawn as {' or '.join(map(repr, LOOKS))}")
    item = spec.get("highlight_item")
    if item is not None:
        if look != "cards":
            raise PageTypeError("agenda: `highlight_item` marks an item of the list `look = \"cards\"` draws")
        if not here or not isinstance(item, int) or not 1 <= item <= len(buckets[here - 1][1]):
            raise PageTypeError(
                f"agenda: `highlight_item` is {item!r} — the number of an item of the chapter `highlight` names")
    if look == "cards":
        for taken in ("highlight_tone", "numbers"):
            if spec.get(taken) is not None:
                raise PageTypeError(
                    f"agenda: `{taken}` is for the boxes; the cards number their chapters in discs and "
                    "mark this one in the accent")
        _agenda_cards(page, area, buckets, here, item or 0)
        return
    ground = spec.get("highlight_tone")
    if ground is not None:
        if not here:
            raise PageTypeError(
                "agenda: `highlight_tone` is the ground of the chapter `highlight` names, and no chapter is named")
        ground = read_tone(spec, {"tone": ground}, "agenda: `highlight_tone`", "box")
    number_of = _numbered(spec, len(buckets))
    listing, right = area.columns([1, 1], gap=page.theme.spacing.gap_l)
    lines: list[str] = []
    for title, items in buckets:
        lines.append(title)
        lines.extend(f"    {item}" for item in items)
    listed = page.points_height(listing.width, lines)
    if listed > listing.height:
        raise PageFullError(
            f"agenda: the list of items needs {listed} EMU of height and has {listing.height} — "
            "fewer items, or two pages; it will not shrink")
    page.points(listing, lines)
    for band, (number, (title, _items)) in zip(
            right.rows(len(buckets), gap=page.theme.spacing.gap_m),
            enumerate(buckets, start=1)):
        head = f"{number_of(number)} {title}"
        marked = number == here
        card = Card(head, "◀ この章" if marked and ground is None else "",
                    Style(ground) if marked and ground is not None else Style())
        tall = card_height(page, [card], band.width, 1)
        if tall > band.height:
            raise PageFullError(
                f"agenda: chapter {number} needs {tall} EMU of height and its share of the page is "
                f"{band.height} — fewer chapters, or shorter names; it will not shrink")
        cell, _rest = band.split_top(tall)
        page.boxes(cell, [card])
