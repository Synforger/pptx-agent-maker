"""Where along the edge of a box each line leaves or enters: equal steps, in the order that keeps the lines from crossing.

誰が呼ぶか: `arrange.links` (= 道を一度決めた後、同じ辺を使う線の出入りの位置を配る)。座標だけを見る判定。

1 つの箱の同じ辺を n 本が使う時、辺を n + 1 等分した点を順に配る。順は、辺から出て最初に曲がる向きで決まる:
辺に沿って小さい方へ曲がる線が先 (= 近くで曲がる線ほど先)、真っすぐ出る線、大きい方へ曲がる線 (= 近くで曲がる線
ほど後)。こう並べると、同じ辺から出る線どうしは交わらない。
"""

from __future__ import annotations

from dataclasses import dataclass

from ....geometry import Rect


@dataclass(frozen=True)
class Attach:
    """One end of one line on one side of a box."""

    link: int
    #: 線の終わりの端なら True、始まりの端なら False
    last: bool
    box: Rect
    #: 辺 (= `route_search.SIDES` の番号)
    side: int
    #: 辺から出て最初に曲がる向き。辺に沿って小さい方 -1、大きい方 +1、曲がらずに真っすぐ 0
    turn: int
    #: 最初の曲がり角までの、辺からの距離
    reach: int


def edge_span(box: Rect, side: int) -> tuple[int, int]:
    """The coordinates along the edge, from where it starts to where it ends (= x for a top or bottom edge, y for a left or right one)."""
    return (box.left, box.right) if side % 2 else (box.top, box.bottom)


def spread(attaches: list[Attach], straights: dict[int, tuple[int, int]]) -> dict[tuple[int, bool], int]:
    """The coordinate along its edge of each end of each line.

    `straights` は真っすぐな線の番号 → その 2 つの箱が向き合う範囲 (= 低い端と高い端)。真っすぐな線の 2 つの端は
    同じ座標でなければならないので、線の多い方の辺の点を使い (= 同じなら始まりの側)、向き合う範囲に収める。
    どちらの辺にもその線しか無い時は、範囲の真ん中 (= 1 本だけの線が辺の真ん中から出る、今までの形)。
    """
    groups: dict[tuple[Rect, int], list[Attach]] = {}
    for each in attaches:
        groups.setdefault((each.box, each.side), []).append(each)
    placed: dict[tuple[int, bool], int] = {}
    crowd: dict[tuple[int, bool], int] = {}
    for (box, side), group in groups.items():
        start, end = edge_span(box, side)
        for rank, each in enumerate(sorted(group, key=_order)):
            placed[(each.link, each.last)] = start + round((end - start) * (rank + 1) / (len(group) + 1))
            crowd[(each.link, each.last)] = len(group)
    for link, (low, high) in straights.items():
        first, second = (link, False), (link, True)
        if crowd[first] == crowd[second] == 1:
            at = (low + high) // 2
        else:
            at = min(max(placed[first if crowd[first] >= crowd[second] else second], low), high)
        placed[first] = placed[second] = at
    return placed


def _order(each: Attach) -> tuple[int, int, int, bool]:
    """Along the edge, from the small end: lines turning to the small side (nearest turn first), straight ones, then lines turning to the large side (farthest turn first)."""
    return each.turn, (each.reach if each.turn < 0 else -each.reach if each.turn > 0 else 0), each.link, each.last
