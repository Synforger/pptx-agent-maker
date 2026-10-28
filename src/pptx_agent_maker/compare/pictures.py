"""Lay the pages of two decks' pictures over each other and count the pixels that differ.

Takes pictures already drawn; `bake.py` draws them and `decks.py` joins the two.
"""

from __future__ import annotations

from collections.abc import Iterable
from itertools import zip_longest

from PIL import Image, ImageChops

from .page_difference import PageDifference


def count_differing_pixels(before: Image.Image, after: Image.Image) -> int:
    """How many pixels of two same-sized pictures are not the same colour.

    ⚠ **差は 3 つの色の成分のどれか 1 つでも違えば数える。**灰色に直してから数えると、青の 1 段の違いが
    灰色では 0 に丸まって落ちる。
    """
    difference = ImageChops.difference(before.convert("RGB"), after.convert("RGB"))
    red, green, blue = difference.split()
    any_component = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    width, height = before.size
    return width * height - any_component.histogram()[0]


def compare_pictures(before: Iterable[Image.Image], after: Iterable[Image.Image]) -> list[PageDifference]:
    """One `PageDifference` per page position, the longer deck's pages included.

    ⚠ **絵は 1 枚ずつ読まれる並びで受ける。**頁の多い資料を全頁分メモリに載せない (= 呼び手が頁ごとに開く)。
    頁の数が違う時、足りない側の頁は寸法が `None` の頁として残る。
    """
    found: list[PageDifference] = []
    for number, (picture_before, picture_after) in enumerate(zip_longest(before, after), start=1):
        size_before = None if picture_before is None else picture_before.size
        size_after = None if picture_after is None else picture_after.size
        differing = 0
        if size_before is not None and size_before == size_after:
            differing = count_differing_pixels(picture_before, picture_after)
        found.append(PageDifference(number, size_before, size_after, differing))
    return found
