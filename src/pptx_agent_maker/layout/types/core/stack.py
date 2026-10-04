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


def aligned_rows(spec: Spec, what: str) -> bool:
    aligned = spec.get("align_rows", False)
    if not isinstance(aligned, bool):
        raise PageTypeError(f"{what}: `align_rows` is true or false, not {aligned!r}")
    return aligned


def place_stack(page: Page, body: Rect, column: list[tuple[Card, int]]) -> None:
    for node, height in column:
        cell, body = body.split_top(height, gap=page.theme.spacing.gap_s)
        page.boxes(cell, [node])
