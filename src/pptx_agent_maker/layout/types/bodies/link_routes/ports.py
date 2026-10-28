"""Where along the edge of a box each line leaves or enters: the middle of what a straight line faces, one shared point for the bent lines that use an edge the same way.

誰が呼ぶか: `arrange.links` (= 道を一度決めた後、線ごとの出入りの位置を決める)。座標だけを見る判定。

真っすぐの線は、2 つの箱が向き合う範囲の真ん中から出て入る (= 片方がもう片方を覆う時は、狭い方の箱の真ん中)。
同じ辺に何本あっても、それぞれ相手の真ん中に立つので重ならない。同じ 2 つの箱を結ぶ真っすぐの線が 2 本以上
(= 行きと帰り) の時だけ、向き合う範囲を等しく割った点に分ける。

曲がる線は、1 つの箱の同じ辺を同じ向き (= 出る / 入る) で使う線どうしが 1 点を分け合い、そこから分かれる
(= 入る線はそこへ集まる)。分かれ目は交わりではないので、跳び越しの半円が付かずに読める。分け合う点は、同じ向きの
真っすぐの線がその辺に在ればその線の位置 (= 辺の真ん中に一番近い物。真っすぐの線から枝分かれする)、無ければ
辺の真ん中。そこが逆の向きの線の端から `clear` 未満なら、辺を等しく割った点へずらす (= 出る矢印と入る矢印が 1 点に
重なると、どちら向きか読めない)。ずらす先は、線が辺から出て最初に曲がる向きの側を先に見る (= 左へ曲がる線は左へ
ずらす。逆へずらすと、真ん中に立つ線と交わる)。その中で、ずらす前の点に近い物。
"""

from __future__ import annotations

from dataclasses import dataclass

from ....geometry import Rect


@dataclass(frozen=True)
class Attach:
    """One end of one line on one side of a box."""

    link: int
    #: 線の終わりの端 (= 箱へ入る) なら True、始まりの端 (= 箱から出る) なら False
    last: bool
    box: Rect
    #: 辺 (= `route_search.SIDES` の番号)
    side: int
    #: 辺から出て最初に曲がる向き。辺に沿って小さい方 -1、大きい方 +1、曲がらない (= 真っすぐの線) 0
    turn: int = 0


def edge_span(box: Rect, side: int) -> tuple[int, int]:
    """The coordinates along the edge, from where it starts to where it ends (= x for a top or bottom edge, y for a left or right one)."""
    return (box.left, box.right) if side % 2 else (box.top, box.bottom)


def positions(attaches: list[Attach], straights: dict[int, tuple[int, int]], clear: int) -> dict[tuple[int, bool], int]:
    """The coordinate along its edge of each end of each line.

    `straights` は真っすぐな線の番号 → その 2 つの箱が向き合う範囲 (= 低い端と高い端)。真っすぐな線の 2 つの端は
    同じ座標に立つ。`clear` は、向きの違う端どうしを離す幅。
    """
    placed: dict[tuple[int, bool], int] = {}
    ends: dict[int, list[Attach]] = {}
    for each in attaches:
        ends.setdefault(each.link, []).append(each)
    pairs: dict[tuple[frozenset, tuple[int, int]], list[int]] = {}
    for link, span in straights.items():
        pairs.setdefault((frozenset((each.box, each.side) for each in ends[link]), span), []).append(link)
    for (_, (low, high)), shared in pairs.items():
        for rank, link in enumerate(sorted(shared)):
            placed[(link, False)] = placed[(link, True)] = low + (high - low) * (rank + 1) // (len(shared) + 1)
    groups: dict[tuple[Rect, int], list[Attach]] = {}
    for each in attaches:
        groups.setdefault((each.box, each.side), []).append(each)
    for (box, side), group in groups.items():
        start, end = edge_span(box, side)
        middle = (start + end) // 2
        taken = {last: {placed[(each.link, last)] for each in group if each.last == last and each.link in straights}
                 for last in (False, True)}
        steps = [start + (end - start) * n // (len(group) + 1) for n in range(1, len(group) + 1)]
        for last in (False, True):
            bent = [each for each in group if each.last == last and each.link not in straights]
            if not bent:
                continue
            preferred = min(taken[last], key=lambda at: abs(at - middle), default=middle)
            turn = sum(each.turn for each in bent)
            aside = sorted(steps, key=lambda at: ((at - preferred) * turn < 0, abs(at - preferred)))
            at = next((candidate for candidate in (preferred, *aside)
                       if all(abs(candidate - other) >= clear for other in taken[not last])), preferred)
            taken[last].add(at)
            for each in bent:
                placed[(each.link, each.last)] = at
    return placed
