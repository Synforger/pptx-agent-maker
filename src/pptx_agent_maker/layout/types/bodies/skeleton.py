"""The types allowed to carry no picture: the deck's own scaffolding."""

from __future__ import annotations

from ...base.geometry import Rect
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


@register("agenda", needs=["buckets"], takes=["highlight", "highlight_tone", "numbers"], figure=False)
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
