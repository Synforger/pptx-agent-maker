"""The way an arrow runs between two boxes that do not face each other: out of one, through the gaps, into the other.

誰が呼ぶか: `arrange.links` (= 向き合わない 2 つのマスの線)。箱の並びだけを見る判定で、頁も要素も知らない。

道は直角の折れ線。箱 (= 結ぶ 2 つも、ほかの全部も) から `Room` の余白以上離れて走り、箱どうしの間の空いた通り道
(= 隣り合う縁の真ん中) と、結ぶ 2 つの辺の上の出入りの位置が曲がり角の候補になる。見つけるのは、次の順に一番
小さい道:

1. 横切る箱の数 (= 0 でなければ、塞がれていて、どの箱を横切るかを言って止める)
2. 引いてある線と重なる区間・触れる所の数 (= 同じ出入りの点を分け合う線 `kin` は数えない。そこから分かれる枝だから)
3. 引いてある線と交わる数
4. 曲がる回数 (= 4 回まで)
5. 長さ
6. 出る辺の向きの、2 つの箱の間の隙間の狭さ (= ここまで同じなら、隙間の狭い向きの辺から出る。それでも同じなら、横へ出る道が先)

`crossing_first` が False なら、3 の交わる数を 5 の長さの後に比べる (= 跳び越してでも短い道。`arrange` が、交わらない
道が長すぎる時の比べに使う)。
"""

from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass
from typing import Sequence

from ....geometry import Rect
from .crossings import APART, CROSS, END, Point, meet, segments

#: 辺の名前。番号は辺から外へ出る向きでもある (= 0 右、1 下、2 左、3 上)
SIDES = ("right", "bottom", "left", "top")
_STEPS = ((1, 0), (0, 1), (-1, 0), (0, -1))
#: 探索の状態 (= 点の番号 2 つ、進む向き、曲がった回数、曲がった直後か始まりか)
State = tuple[int, int, int, int, bool]
#: 1 本の道の曲がる回数の上限 (= PowerPoint の曲がるコネクタが表せる回数)
MAX_BENDS = 4


@dataclass(frozen=True)
class Port:
    """Where a line meets a box: the point on its edge, and the side (= an index of `SIDES`) it is on."""

    point: Point
    side: int


@dataclass(frozen=True)
class Room:
    """What a line keeps clear of, and where it may run."""

    #: 線が走ってよい範囲 (= 頁の本体)
    body: Rect
    #: 箱の縁から離れる幅 (= 横に走る線は縦の `margin_y`、縦に走る線は横の `margin_x`)
    margin_x: int
    margin_y: int
    #: 跳び越しの半円の半径 (= 交わりは両端からこの 2 倍以上離れた所だけ)
    hop: int


@dataclass(frozen=True)
class Route:
    """A path found: its points from the start to the end, the ports it uses, and what it runs across or against."""

    points: tuple[Point, ...]
    start: Port
    end: Port
    #: 横切る箱 (= 空でなければ通れていない)
    blocked: tuple[Rect, ...]
    #: 引いてある線と重なる・触れる数
    touching: int
    #: 引いてある線と交わる数
    crossing: int

    @property
    def bends(self) -> int:
        return len(self.points) - 2

    @property
    def length(self) -> int:
        return sum(abs(x2 - x1) + abs(y2 - y1) for (x1, y1), (x2, y2) in segments(self.points))


def middle_ports(rect: Rect) -> list[Port]:
    """The middle of each edge of a box, as ports."""
    x, y = rect.left + rect.width // 2, rect.top + rect.height // 2
    return [Port((rect.right, y), 0), Port((x, rect.bottom), 1), Port((rect.left, y), 2), Port((x, rect.top), 3)]


class NoRoute(Exception):
    """No way at all, even across boxes (= the ports cannot be reached within the bends allowed)."""


class RouteSearch:
    """The cheapest path from one of the `starts` to one of the `ends`, found over the coordinates the gaps and the ports give.

    `drawn` は引いてある線 (= 折れ線の点の並び)。`strict` が False なら、重なる・触れるを数えない (= 出入りの
    位置がまだ配られていない探索では、同じ辺の中ほどから出る線どうしが必ず重なって見える)。`kin` は `drawn` のうち、
    この線と同じ点から出る線・同じ点へ入る線で、重なっても数えない (= 枝分かれと合流)。交わりは数える。
    """

    def __init__(self, first: Rect, second: Rect, others: Sequence[Rect], drawn: Sequence[tuple[Point, ...]],
                 room: Room, starts: Sequence[Port], ends: Sequence[Port], *, strict: bool,
                 kin: Sequence[tuple[Point, ...]] = (), crossing_first: bool = True):
        self.room, self.starts, self.ends, self.strict = room, list(starts), list(ends), strict
        self.crossing_first = crossing_first
        self.kin = {run for line in kin for run in segments(line)}
        self.boxes = [first, second, *others]
        self.inflated = [(r.left - room.margin_x, r.top - room.margin_y, r.right + room.margin_x, r.bottom + room.margin_y)
                         for r in self.boxes]
        self.runs = [run for line in drawn for run in segments(line)]
        self.xs = self._coordinates(horizontal=True)
        self.ys = self._coordinates(horizontal=False)
        self.edges: dict[tuple[int, int, int, int, bool], tuple[tuple[int, ...], int, int, int]] = {}

    # -- 公開の口 ----------------------------------------------------------

    def cheapest(self) -> Route:
        """The path of the least cost. `blocked` of the result lists the boxes it runs across (= none when a way is open)."""
        count = itertools.count()
        queue: list = []
        best: dict[State, tuple] = {}
        came: dict[State, tuple] = {}
        for port in self.starts:
            state = (self.xs.index(port.point[0]), self.ys.index(port.point[1]), port.side, 0, True)
            start_cost = (0, 0, 0, 0, 0, self._gap_along(port.side) * len(SIDES) + port.side)
            best[state] = start_cost
            came[state] = (None, ())
            heapq.heappush(queue, (self._rank(start_cost), next(count), state, start_cost))
        while queue:
            _, _, state, cost = heapq.heappop(queue)
            if best.get(state) != cost:
                continue
            reached = self._end_port(state)
            if reached is not None:
                return self._route(state, came, reached, cost)
            for step_cost, following, crossed in self._moves(state):
                total = tuple(a + b for a, b in zip(cost, step_cost))
                if following not in best or self._rank(total) < self._rank(best[following]):
                    best[following] = total
                    came[following] = (state, crossed)
                    heapq.heappush(queue, (self._rank(total), next(count), following, total))
        raise NoRoute("no path between the two ports")

    def _rank(self, cost: tuple) -> tuple:
        """The order costs are compared in: as they are, or with the crossings after the length."""
        if self.crossing_first:
            return cost
        blocked, touching, crossing, bends, length, gap = cost
        return blocked, touching, bends, length, crossing, gap

    def _gap_along(self, side: int) -> int:
        """The gap between the two boxes along the axis a line leaving by `side` sets out on (= 0 when they overlap along it)."""
        a, b = self.boxes[0], self.boxes[1]
        if side % 2 == 0:
            return max(b.left - a.right, a.left - b.right, 0)
        return max(b.top - a.bottom, a.top - b.bottom, 0)

    # -- 探す場所 ----------------------------------------------------------

    def _coordinates(self, horizontal: bool) -> list[int]:
        """The candidate coordinates along one axis: the middle of each gap, the ports, and the lanes just outside everything."""
        low, high = (self.room.body.left, self.room.body.right) if horizontal else (self.room.body.top, self.room.body.bottom)
        margin = self.room.margin_x if horizontal else self.room.margin_y
        spans = [(r.left, r.right) if horizontal else (r.top, r.bottom) for r in self.boxes]
        edges = sorted({edge for span in spans for edge in span})
        found = {(a + b) // 2 for a, b in zip(edges, edges[1:])}
        (first_low, first_high), (second_low, second_high) = spans[0], spans[1]
        found.update(((first_high + second_low) // 2, (first_low + second_high) // 2))
        found.update(coordinate for coordinate in (edges[0] - margin, edges[-1] + margin) if low <= coordinate <= high)
        found = {coordinate for coordinate in found if low <= coordinate <= high}
        found.update(port.point[0 if horizontal else 1] for port in (*self.starts, *self.ends))
        return sorted(found)

    # -- 動き方 ------------------------------------------------------------

    def _moves(self, state: State):
        """What can follow a state: one more step the way it faces, or a turn to either side (while bends are left).

        線が別の線の上の点を通り抜けるなら (= 曲がらずに進む) 交わりで、そこで曲がるなら T 字 (= 触れる。曲がった先の
        区間が、その線に重なるので `_edge` が数える)。通り抜けるか曲がるかは、その点を出る時に決まる。`fresh` は
        曲がった直後か始まりの状態で、続けて曲がる (= 長さ 0 の区間) ことと、同じ点の交わりを二重に数えることを防ぐ。
        """
        i, j, way, bends, fresh = state
        di, dj = _STEPS[way]
        ni, nj = i + di, j + dj
        if 0 <= ni < len(self.xs) and 0 <= nj < len(self.ys):
            blocked, touching, crossing, length = self._edge(i, j, ni, nj, bends == 0)
            through = 0 if fresh else self._through(i, j, way)
            yield (len(blocked), touching, crossing + through, 0, length, 0), (ni, nj, way, bends, False), blocked
        if fresh or bends >= MAX_BENDS:
            return
        for turned in ((way + 1) % 4, (way + 3) % 4):
            yield (0, 0, 0, 1, 0, 0), (i, j, turned, bends + 1, True), ()

    def _end_port(self, state: State) -> Port | None:
        """The end port a state has arrived at (= standing on it, facing into the box), if any."""
        i, j, way, _, _ = state
        for port in self.ends:
            if (port.side + 2) % 4 == way and (self.xs[i], self.ys[j]) == port.point:
                return port
        return None

    # -- 1 区間の費用 ------------------------------------------------------

    def _edge(self, i: int, j: int, ni: int, nj: int, leaving: bool) -> tuple[tuple[int, ...], int, int, int]:
        """The boxes a step runs across, how many lines it touches and crosses, and its length."""
        key = (i, j, ni, nj, leaving)
        if key not in self.edges:
            run = ((self.xs[i], self.ys[j]), (self.xs[ni], self.ys[nj]))
            tunnel = self._into_a_box(run)
            blocked = tuple(index for index, box in enumerate(self.inflated)
                            if not (index == 0 and leaving) and not (index == 1 and tunnel) and _inside(run, box))
            touching = crossing = 0
            for other in self.runs:
                met = meet(run, other, 2 * self.room.hop)
                if met in (APART, END):
                    continue
                if met == CROSS:
                    crossing += 1
                elif self.strict and other not in self.kin:
                    touching += 1
            length = abs(run[1][0] - run[0][0]) + abs(run[1][1] - run[0][1])
            self.edges[key] = (blocked, touching, crossing, length)
        return self.edges[key]

    def _through(self, i: int, j: int, way: int) -> int:
        """How many lines already drawn cross, at this point, the line that passes through it the way `way` runs."""
        x, y = self.xs[i], self.ys[j]
        sideways = way % 2 == 0
        return sum(1 for (x1, y1), (x2, y2) in self.runs
                   if (x1 == x2 and sideways and x1 == x and min(y1, y2) < y < max(y1, y2))
                   or (y1 == y2 and not sideways and y1 == y and min(x1, x2) < x < max(x1, x2)))

    def _into_a_box(self, run: tuple[Point, Point]) -> bool:
        """Whether a step runs straight into one of the end ports from outside (= the last run of a line, which may close in on the box)."""
        (x1, y1), (x2, y2) = run
        for port in self.ends:
            px, py = port.point
            if port.side == 0 and y1 == y2 == py and x2 < x1 and x2 >= px:
                return True
            if port.side == 2 and y1 == y2 == py and x2 > x1 and x2 <= px:
                return True
            if port.side == 1 and x1 == x2 == px and y2 < y1 and y2 >= py:
                return True
            if port.side == 3 and x1 == x2 == px and y2 > y1 and y2 <= py:
                return True
        return False

    # -- 見つけた道を組む --------------------------------------------------

    def _route(self, state: State, came: dict, reached: Port, cost: tuple) -> Route:
        corners: list[Point] = []
        crossed: list[int] = []
        follow = state
        while follow is not None:
            before, blocked = came[follow]
            crossed.extend(blocked)
            if before is not None and before[2] != follow[2]:
                corners.append((self.xs[follow[0]], self.ys[follow[1]]))
            follow = before
        corners.reverse()
        origin = self._origin(state, came)
        points = (origin.point, *corners, reached.point)
        return Route(points, origin, reached, tuple(self.boxes[index] for index in dict.fromkeys(crossed)), cost[1], cost[2])

    def _origin(self, state: State, came: dict) -> Port:
        while came[state][0] is not None:
            state = came[state][0]
        for port in self.starts:
            if (self.xs[state[0]], self.ys[state[1]]) == port.point and port.side == state[2]:
                return port
        raise NoRoute("a path that does not begin at a port")


def _inside(run: tuple[Point, Point], box: tuple[int, int, int, int]) -> bool:
    """Whether a run goes through the inside of a box (= touching its edge does not count)."""
    left, top, right, bottom = box
    (x1, y1), (x2, y2) = run
    if y1 == y2:
        return top < y1 < bottom and min(x1, x2) < right and left < max(x1, x2)
    return left < x1 < right and min(y1, y2) < bottom and top < max(y1, y2)
