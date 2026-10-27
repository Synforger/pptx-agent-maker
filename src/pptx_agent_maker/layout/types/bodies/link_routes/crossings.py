"""Where a straight run of a line meets the runs already drawn: a crossing, a shared stretch, or a touch.

誰が呼ぶか: `route_search` (= 1 区間ごとの費用)、`arrange.links` (= 引き終えた線が別の線を跳び越す所)。
どれも座標だけを見る判定で、頁も要素も知らない。
"""

from __future__ import annotations

Point = tuple[int, int]
Segment = tuple[Point, Point]

#: `meet` の答え。重ならない / 互いを貫いて交わる / 区間の端が相手の途中に当たる (= 曲がらずに通り抜ければ交わり、
#: そこで曲がれば T 字になる。どちらかは、その先を見ないと決まらない) / それ以外で触れる (= 同じ区間を通る・
#: 相手の端が自分の上にある・端に近すぎる所で交わる)
APART, CROSS, END, TOUCH = "apart", "cross", "end", "touch"


def segments(points: tuple[Point, ...] | list[Point]) -> list[Segment]:
    """The straight runs of a polyline, in order."""
    return list(zip(points, points[1:]))


def meet(run: Segment, other: Segment, clear: int) -> str:
    """How two runs, each along an axis, meet: `APART`, `CROSS`, `END` or `TOUCH`. A crossing counts only `clear` or more away from both ends of `run`.

    交わる所が `run` の端に近いと、そこで跳び越す半円が曲がり角や端にかかる。そういう交わりは `TOUCH` と数える。
    """
    (ax1, ay1), (ax2, ay2) = run
    (bx1, by1), (bx2, by2) = other
    ax1, ax2, ay1, ay2 = min(ax1, ax2), max(ax1, ax2), min(ay1, ay2), max(ay1, ay2)
    bx1, bx2, by1, by2 = min(bx1, bx2), max(bx1, bx2), min(by1, by2), max(by1, by2)
    across, across_other = ay1 == ay2, by1 == by2
    if across and across_other:
        return TOUCH if ay1 == by1 and max(ax1, bx1) <= min(ax2, bx2) else APART
    if not across and not across_other:
        return TOUCH if ax1 == bx1 and max(ay1, by1) <= min(ay2, by2) else APART
    if not across:                                  # `run` is the vertical one: look at it as the horizontal one
        (ax1, ay1, ax2, ay2), (bx1, by1, bx2, by2) = (ay1, ax1, ay2, ax2), (by1, bx1, by2, bx2)
    # a は水平 (= x が a の範囲、y が一定)、b は垂直 (= y が b の範囲、x が一定)
    if not (ax1 <= bx1 <= ax2 and by1 <= ay1 <= by2):
        return APART
    if ay1 in (by1, by2):                           # 相手の端が自分の上にある
        return TOUCH
    if bx1 in (ax1, ax2):                           # 自分の端が相手の途中に当たる
        return END
    return CROSS if bx1 - ax1 >= clear and ax2 - bx1 >= clear else TOUCH


def crossing_point(run: Segment, other: Segment) -> Point:
    """Where two runs that cross each other cross (= the x of the vertical one, the y of the horizontal one)."""
    horizontal, vertical = (run, other) if run[0][1] == run[1][1] else (other, run)
    return vertical[0][0], horizontal[0][1]


def hops(points: tuple[Point, ...], drawn: list[tuple[Point, ...]], radius: int) -> list[Point]:
    """Where a line along `points` crosses lines already drawn, in order along it, each far enough from its ends to be hopped.

    半円の跳び越しは、曲がり角や端から `radius` 以上離れた所にだけ置く。近すぎる交わりは跳ばない。同じ区間で
    2 つの跳び越しが重なる (= 隣の交わりまで `2 * radius` に満たない) 時は、後の方を跳ばない。
    """
    found: list[Point] = []
    for run in segments(points):
        on_run: list[Point] = []
        for line in drawn:
            for other in segments(line):
                if meet(run, other, radius) == CROSS:
                    on_run.append(crossing_point(run, other))
        on_run.sort(key=lambda at: abs(at[0] - run[0][0]) + abs(at[1] - run[0][1]))
        kept: list[Point] = []
        for at in on_run:
            if not kept or abs(at[0] - kept[-1][0]) + abs(at[1] - kept[-1][1]) >= 2 * radius:
                kept.append(at)
        found.extend(kept)
    return found
