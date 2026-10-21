"""Boxes stacked under a stage, counted the same way by a flow and a roadmap."""

from __future__ import annotations

from ...base.geometry import Rect
from ...parts.page import Card, Page
from .read import read_card, Spec
from .registry import PageTypeError


def card_height(page: Page, cards, width: int, columns: int) -> int:
    """How tall the tallest card has to be for its own words.

    ⚠ **カードに頁の高さを配らない** ― 3 行のカードが 12cm の枠に入ると、字のうしろに
    その差ぶんの空きが残る (= 焼いて初めて出た)。

    ⚠ **行数は箱が実際に折る数で数える** (= `wraps`)。全角 1 文字ぶんで数えていた間は、
    英数字の短い見出しが 2 行と数えられ、箱の中に 1 行ぶんの空白ができた。
    """
    s, ty = page.theme.spacing, page.theme.type
    columns = max(columns, 1)
    column = (width - s.gap_m * (columns - 1)) // columns
    inner = max(column - 2 * s.pad - 2 * s.text_inset, 1)   # 文字が使える幅
    tallest = 0
    for card in cards:
        # アイコンの在る箱は、文字がアイコンの右に寄るぶん狭く、アイコンより低くはならない
        room = max(inner - (s.icon + s.gap_s if card.style.icon else 0), 1)
        tall = page.theme.wrapped_height(card.heading, room, ty.heading, bold=True)
        if card.body:
            tall += s.gap_s + page.theme.wrapped_height(card.body, room, ty.body)
        tallest = max(tallest, tall, s.icon if card.style.icon else 0)
    return tallest + 2 * s.pad


def stage_stacks(page: Page, spec: Spec, stages: list, wide: int, aligned: bool,
            what: str) -> tuple[list[list[tuple[Card, int]]], int]:
    """Each stage's nodes with the height each takes, and how tall the tallest stage stands.

    流れ図と道のりが同じ数え方で積む (= 段の下のノードは、どちらでも同じ箱)。
    """
    gap = page.theme.spacing.gap_s
    stacks = []
    for number, stage in enumerate(stages, start=1):
        nodes = [read_card(spec, node, f"{what}: stage {number}, node {index}")
                 for index, node in enumerate(stage.get("nodes", []), start=1)]
        if not nodes:
            raise PageTypeError(f"{what}: stage {stage['name']!r} has no nodes")
        stacks.append([(node, card_height(page, [node], wide, 1)) for node in nodes])
    if aligned:
        # 行ごとに、その行で一番高いノードへ揃える (= 同じ順番のノードが同じ高さに並ぶ)
        rows = [max(column[index][1] for column in stacks if index < len(column))
                for index in range(max(len(column) for column in stacks))]
        stacks = [[(node, rows[index]) for index, (node, _tall) in enumerate(column)]
                  for column in stacks]
        return stacks, sum(rows) + gap * (len(rows) - 1)
    return stacks, max(sum(tall for _n, tall in column) + gap * (len(column) - 1)
                       for column in stacks)


def spread(extra: int, count: int) -> list[int]:
    """`extra` shared out equally among `count` boxes, the last taking what rounding leaves.

    `box_height = "page"` の資料で、字の分の高さを超えたぶんを箱へ配る 1 か所 (= 流れ・道のり・カード・
    組み立ての段のどれも、同じ配り方)。字の分に等しく足すので、字の多い箱は字の少ない箱より高いまま。
    """
    share, left = divmod(max(extra, 0), count)
    return [share] * (count - 1) + [share + left]


def grown(heights: list[int], room: int, gap: int) -> list[int]:
    """Boxes of these heights, stacked with `gap` between, grown by an equal share each until they fill `room`."""
    return [tall + more for tall, more in zip(heights, spread(room - sum(heights) - gap * (len(heights) - 1),
                                                               len(heights)))]


def fill_stacks(page: Page, stacks: list[list[tuple[Card, int]]], stack: int, room: int,
                aligned: bool) -> tuple[list[list[tuple[Card, int]]], int]:
    """The stacks of a flow or a roadmap grown to fill `room` (= when the deck says `box_height = "page"`).

    箱は自分の字の分の高さに、余った高さの等しい取り分を足す (= どの段も下端が揃う)。`aligned` は行ごとに
    足すので、段をまたいで同じ順番のノードの高さが揃ったまま。字の分で `room` に収まらない時と、字の分の
    高さの資料では、何も変えない (= 収まらないのを止めるのは呼ぶ側)。
    """
    if page.theme.box_height != "page" or room <= stack:
        return stacks, stack
    gap = page.theme.spacing.gap_s
    if aligned:
        rows = grown([max(column[index][1] for column in stacks if index < len(column))
                      for index in range(max(len(column) for column in stacks))], room, gap)
        return [[(node, rows[index]) for index, (node, _tall) in enumerate(column)] for column in stacks], room
    return [[(node, tall) for (node, _own), tall in zip(column, grown([own for _node, own in column], room, gap))]
            for column in stacks], room


def aligned_rows(spec: Spec, what: str) -> bool:
    aligned = spec.get("align_rows", False)
    if not isinstance(aligned, bool):
        raise PageTypeError(f"{what}: `align_rows` is true or false, not {aligned!r}")
    return aligned


def place_stack(page: Page, body: Rect, column: list[tuple[Card, int]]) -> None:
    for node, height in column:
        cell, body = body.split_top(height, gap=page.theme.spacing.gap_s)
        page.boxes(cell, [node])
