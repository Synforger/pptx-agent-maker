"""The types allowed to carry no picture: the deck's own scaffolding."""

from __future__ import annotations

from ...base.geometry import Rect
from ...parts.page import Card, Page, PageFullError
from ..core.read import Spec
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


@register("agenda", needs=["buckets"], takes=["highlight"], figure=False)
def _agenda(page: Page, spec: Spec, area: Rect) -> None:
    """Every item on the left, the buckets on the right, this chapter marked.

    進行型の目次 (= 章の頭ごとに 1 枚置き、その章だけを強調する)。⚠ **実頁の無い
    小項目を書かない** ― 目次に残すと翌週がそれを輸入して持ち越す。

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
        head = f"{number}. {title}"
        mark = "◀ この章" if number == here else ""
        tall = card_height(page, [Card(head, mark)], band.width, 1)
        if tall > band.height:
            raise PageFullError(
                f"agenda: chapter {number} needs {tall} EMU of height and its share of the page is "
                f"{band.height} — fewer chapters, or shorter names; it will not shrink")
        cell, _rest = band.split_top(tall)
        page.boxes(cell, [Card(head, mark)])
