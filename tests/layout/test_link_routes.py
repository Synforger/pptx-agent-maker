"""The way an arrow runs between two cells that do not face each other: round the cells, through the gaps between them.

見張るのは 5 つ ― 箱をよけて空いた通り道を通ること (= 頼み主の見本: 右上から左下へ、1 回曲がる道が両方塞がる配置)、
曲がる回数が最少で同じなら短い道を選ぶこと、交わらずに引ける道があれば曲がる回数より先にそれを選ぶこと、
同じ辺から出入りする線の位置が等しい間隔で、線どうしが同じ区間を通らないこと、どうしても交わる所だけを後の線が
跳び越すこと。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))
from support.pages import box_of, build  # noqa: E402

from pptx_agent_maker import DEFAULT  # noqa: E402
from pptx_agent_maker.layout.geometry import Rect  # noqa: E402
from pptx_agent_maker.layout.tokens import theme_from  # noqa: E402
from pptx_agent_maker.layout.types.bodies.link_routes import (  # noqa: E402
    Attach, Room, RouteSearch, hops, middle_ports, spread)
from pptx_agent_maker.layout.types.bodies.link_routes.crossings import APART, CROSS, TOUCH, meet  # noqa: E402

S = DEFAULT.spacing
FILLED = theme_from({"grounds": {"Deep": "8B1E3F"}})


def card(heading, at, span=(1, 1), **cell):
    return {"card": {"heading": heading, "body": "words"}, "at": list(at), "span": list(span), **cell}


def grid_page(cells, columns, rows, links):
    return build({"type": "compose", "title": "A page", "grid": {"columns": list(columns), "rows": list(rows)},
                  "cells": cells, "links": links})


def lines_of(page):
    return [e for e in page.build() if e.kind == "line"]


def runs(points):
    return list(zip(points, points[1:]))


def passes_through(points, rect, margin=0):
    """Whether a polyline comes within `margin` of the inside of `rect` (= edge to edge; just touching the margin does not count)."""
    return any(rect.left - margin < max(x1, x2) and min(x1, x2) < rect.right + margin
               and rect.top - margin < max(y1, y2) and min(y1, y2) < rect.bottom + margin
               for (x1, y1), (x2, y2) in runs(points))


def search(first, second, others=(), drawn=(), body=Rect(0, 0, 3000, 2000), margin=50, hop=20, strict=True):
    room = Room(body, margin, margin, hop)
    return RouteSearch(first, second, list(others), list(drawn), room, middle_ports(first), middle_ports(second),
                       strict=strict).cheapest()


class TheLineFromTheTopRightToTheBottomLeft(unittest.TestCase):
    """The page the asker drew: a box top right, one below it, and a row of boxes to its left, so each of the two ways that bend once runs across a box."""

    COLUMNS, ROWS = (1.1, 1.3, 1.7, 1.8, 1.6, 2.2, 2.2), (1.15, 1.15, 0.56, 1.14)
    CELLS = [card("Data", (1, 7), id="data"), card("Utsu", (2, 7), (2, 1), id="utsu"), card("Sdk", (3, 3), (2, 1), id="sdk"),
             card("Hub", (1, 4), id="hub"), card("Lsl", (1, 5), (1, 2), id="lsl")]

    def page(self):
        return grid_page(self.CELLS, self.COLUMNS, self.ROWS, [{"from": "data", "to": "sdk"}])

    def test_the_line_is_drawn_and_runs_across_none_of_the_boxes(self):
        page = self.page()
        (line,) = lines_of(page)
        for name in ("Utsu", "Hub", "Lsl"):
            self.assertFalse(passes_through(line.points(), box_of(page, name).rect), name)

    def test_it_leaves_one_box_and_goes_into_the_other_by_an_edge_each(self):
        page = self.page()
        (line,) = lines_of(page)
        data, sdk = box_of(page, "Data").rect, box_of(page, "Sdk").rect
        on_edge = lambda point, box: ((point[0] in (box.left, box.right) and box.top <= point[1] <= box.bottom)
                                      or (point[1] in (box.top, box.bottom) and box.left <= point[0] <= box.right))
        self.assertTrue(on_edge(line.start, data))
        self.assertTrue(on_edge(line.end, sdk))
        self.assertTrue(line.arrow)

    def test_it_bends_twice_because_neither_way_that_bends_once_is_open(self):
        page = self.page()
        (line,) = lines_of(page)
        self.assertEqual(2, len(line.corners))
        data, sdk = box_of(page, "Data").rect, box_of(page, "Sdk").rect
        others = [box_of(page, name).rect for name in ("Utsu", "Hub", "Lsl")]
        data_x, data_y = data.left + data.width // 2, data.top + data.height // 2
        sdk_x, sdk_y = sdk.left + sdk.width // 2, sdk.top + sdk.height // 2
        sideways_first = [(data.left, data_y), (sdk_x, data_y), (sdk_x, sdk.top)]
        down_first = [(data_x, data.bottom), (data_x, sdk_y), (sdk.right, sdk_y)]
        for once in (sideways_first, down_first):
            self.assertTrue(any(passes_through(once, other) for other in others), once)

    def test_it_keeps_half_a_gap_from_every_box_it_does_not_join(self):
        page = self.page()
        (line,) = lines_of(page)
        for name in ("Utsu", "Hub", "Lsl"):
            self.assertFalse(passes_through(line.points(), box_of(page, name).rect, margin=S.gap_x // 2 - 1), name)


class TheRouteSearch(unittest.TestCase):
    A, B = Rect(100, 100, 400, 200), Rect(1500, 900, 400, 200)

    def test_two_boxes_corner_to_corner_in_the_open_are_joined_with_one_bend(self):
        route = search(self.A, self.B)
        self.assertEqual(1, route.bends)
        self.assertEqual((), route.blocked)

    def test_a_box_in_the_way_of_both_ways_that_bend_once_makes_it_bend_twice_through_the_gap(self):
        in_the_way = [Rect(1500, 100, 400, 200), Rect(100, 900, 400, 200)]
        route = search(self.A, self.B, in_the_way)
        self.assertEqual(2, route.bends)
        self.assertEqual((), route.blocked)
        for box in in_the_way:
            self.assertFalse(passes_through(route.points, box, margin=50 - 1))

    def test_a_gap_narrower_than_twice_the_margin_is_not_gone_through_and_one_as_wide_is(self):
        """A wall across the body with a gap in it: a line keeps `margin` (50) from each side, so it needs 100."""
        first, second = Rect(100, 1000, 200, 200), Rect(2000, 1000, 200, 200)
        for gap, open_way in ((90, False), (100, True)):
            wall = [Rect(1000, 0, 200, 700), Rect(1000, 700 + gap, 200, 1300 - gap)]
            self.assertEqual(open_way, search(first, second, wall).blocked == (), gap)

    def test_a_wall_across_the_whole_body_cannot_be_got_through_and_is_named(self):
        wall = Rect(0, 500, 3000, 200)
        route = search(self.A, self.B, [wall])
        self.assertEqual((wall,), route.blocked)

    def test_no_line_bends_more_than_four_times(self):
        for others in ([], [Rect(1500, 100, 400, 200)], [Rect(700, 0, 100, 1500), Rect(1100, 500, 100, 1500)]):
            self.assertLessEqual(search(self.A, self.B, others).bends, 4)

    def test_a_line_does_not_turn_at_the_edge_it_leaves_by(self):
        route = search(self.A, self.B)
        (x0, y0), (x1, y1) = route.points[:2]
        self.assertGreaterEqual(abs(x1 - x0) + abs(y1 - y0), 50)

    def test_a_way_that_crosses_no_line_is_taken_before_a_way_that_bends_less(self):
        """One bend would cross the line already drawn; going round it takes more bends and crosses nothing."""
        drawn = [((1000, 0), (1000, 1000))]
        route = search(self.A, self.B, drawn=drawn)
        self.assertEqual(0, route.crossing)
        self.assertGreater(route.bends, 1)

    def test_a_crossing_is_taken_when_every_way_round_is_shut(self):
        drawn = [((1000, 0), (1000, 2000))]
        route = search(self.A, self.B, drawn=drawn)
        self.assertEqual(1, route.crossing)
        self.assertEqual(1, route.bends)

    def test_a_line_does_not_turn_at_the_edge_of_the_box_it_goes_into(self):
        route = search(self.A, self.B)
        (x1, y1), (x2, y2) = route.points[-2:]
        self.assertGreaterEqual(abs(x2 - x1) + abs(y2 - y1), 50)

    def test_a_way_that_needs_five_bends_to_miss_the_lines_drawn_is_not_taken_a_crossing_is(self):
        """Two long lines make a lane that only a path of five bends gets through without crossing; four are all a line may have."""
        drawn = [((600, 0), (600, 1500)), ((800, 500), (800, 2000))]
        route = search(Rect(100, 100, 400, 200), Rect(1100, 1000, 400, 200), drawn=drawn)
        self.assertLessEqual(route.bends, 4)
        self.assertGreaterEqual(route.crossing, 1)

    def test_a_line_that_would_run_along_a_line_already_drawn_is_moved_off_it(self):
        first = search(self.A, self.B)
        second = search(self.A, self.B, drawn=[first.points])
        self.assertEqual(0, second.touching)
        self.assertNotEqual(first.points, second.points)


class TheMarginOfThePage(unittest.TestCase):
    def test_a_row_across_the_whole_page_is_gone_round_by_the_margin_of_the_body(self):
        """On a grid the squares leave half a gap round the boxes, which is room for a line along the edge of the body."""
        cells = [card("A", (1, 1), id="a"), card("Wall", (2, 1), (1, 3)), card("B", (3, 3), id="b")]
        page = grid_page(cells, (1, 1, 1), (1, 1, 1), [{"from": "a", "to": "b"}])
        (line,) = lines_of(page)
        wall = box_of(page, "Wall").rect
        self.assertFalse(passes_through(line.points(), wall))
        self.assertTrue(any(x == page.body.left for x, _ in line.points()) or any(x == page.body.right for x, _ in line.points()))


class TheMeetingOfTwoRuns(unittest.TestCase):
    def test_runs_that_go_through_each_other_cross_and_the_rest_touch_or_miss(self):
        horizontal = ((0, 100), (200, 100))
        self.assertEqual(CROSS, meet(horizontal, ((100, 0), (100, 200)), 10))
        self.assertEqual(APART, meet(horizontal, ((300, 0), (300, 200)), 10))
        self.assertEqual(TOUCH, meet(horizontal, ((100, 100), (100, 200)), 10), "an end on the other run")
        self.assertEqual(TOUCH, meet(horizontal, ((100, 100), (300, 100)), 10), "a stretch in common")
        self.assertEqual(APART, meet(horizontal, ((0, 120), (200, 120)), 10), "side by side")

    def test_a_crossing_too_near_an_end_of_the_run_is_a_touch(self):
        horizontal = ((0, 100), (200, 100))
        self.assertEqual(CROSS, meet(horizontal, ((10, 0), (10, 200)), 10))
        self.assertEqual(TOUCH, meet(horizontal, ((9, 0), (9, 200)), 10))
        self.assertEqual(TOUCH, meet(horizontal, ((191, 0), (191, 200)), 10))

    def test_a_line_hops_where_it_crosses_and_not_where_it_ends_on_another(self):
        drawn = [((100, 0), (100, 200)), ((50, 100), (50, 300))]
        self.assertEqual([(100, 100)], hops(((0, 100), (200, 100)), drawn, 10))
        self.assertEqual([], hops(((0, 100), (100, 100)), drawn[:1], 10), "ending on a line is not crossing it")

    def test_two_hops_closer_than_their_own_widths_are_not_both_made(self):
        drawn = [((100, 0), (100, 200)), ((110, 0), (110, 200))]
        self.assertEqual([(100, 100)], hops(((0, 100), (200, 100)), drawn, 10))

    def test_the_hops_come_in_the_order_the_line_goes(self):
        drawn = [((150, 0), (150, 200)), ((50, 0), (50, 200))]
        self.assertEqual([(50, 100), (150, 100)], hops(((0, 100), (200, 100)), drawn, 10))
        self.assertEqual([(150, 100), (50, 100)], hops(((200, 100), (0, 100)), drawn, 10))


class WhereTheLinesLeaveByOneEdge(unittest.TestCase):
    BOX = Rect(0, 0, 1000, 800)

    def attaches(self, *turns):
        return [Attach(number, False, self.BOX, 0, turn, reach) for number, (turn, reach) in enumerate(turns)]

    def test_lines_by_one_edge_stand_in_equal_steps_along_it(self):
        placed = spread(self.attaches((-1, 100), (-1, 200), (1, 100)), {})
        self.assertEqual([200, 400, 600], sorted(placed.values()))

    def test_a_single_line_leaves_by_the_middle(self):
        self.assertEqual({(0, False): 400}, spread(self.attaches((-1, 100)), {}))

    def test_lines_that_turn_up_stand_above_the_straight_one_and_those_that_turn_down_below_it(self):
        placed = spread(self.attaches((1, 100), (0, 0), (-1, 100)), {})
        self.assertLess(placed[(2, False)], placed[(1, False)])
        self.assertLess(placed[(1, False)], placed[(0, False)])

    def test_of_the_lines_that_turn_up_the_one_that_turns_nearer_stands_higher_and_of_those_that_turn_down_it_stands_lower(self):
        placed = spread(self.attaches((-1, 300), (-1, 100), (1, 300), (1, 100)), {})
        self.assertLess(placed[(1, False)], placed[(0, False)])
        self.assertLess(placed[(2, False)], placed[(3, False)])

    def test_each_edge_is_shared_out_on_its_own(self):
        other = Rect(2000, 0, 1000, 400)
        attaches = [Attach(0, False, self.BOX, 0, -1, 100), Attach(1, False, other, 0, -1, 100),
                    Attach(2, False, other, 0, 1, 100)]
        placed = spread(attaches, {})
        self.assertEqual(400, placed[(0, False)])
        self.assertEqual([133, 267], sorted((placed[(1, False)], placed[(2, False)])))

    def test_the_two_ends_of_a_straight_line_stand_level_where_the_boxes_face_each_other(self):
        here, there = Rect(0, 0, 1000, 800), Rect(2000, 200, 1000, 800)
        attaches = [Attach(0, False, here, 0, 0, 0), Attach(0, True, there, 2, 0, 0)]
        placed = spread(attaches, {0: (200, 800)})
        self.assertEqual(placed[(0, False)], placed[(0, True)])
        self.assertEqual(500, placed[(0, False)], "alone on both edges: the middle of where they face")

    def test_a_straight_line_stands_where_the_busier_edge_puts_it_kept_within_where_the_boxes_face(self):
        here, there = Rect(0, 0, 1000, 800), Rect(2000, 600, 1000, 800)
        attaches = [Attach(0, False, here, 0, 0, 0), Attach(0, True, there, 2, 0, 0),
                    Attach(1, False, here, 0, -1, 100), Attach(2, False, here, 0, -1, 200)]
        placed = spread(attaches, {0: (700, 800)})
        self.assertEqual(placed[(0, False)], placed[(0, True)])
        self.assertEqual(700, placed[(0, False)], "the busier edge puts it at 600, which is below where the boxes face")


class ThreeLinesLeavingOneBox(unittest.TestCase):
    """A box with a line straight across and two that go up: they leave at three points, share no run, and cross nothing."""

    def page(self):
        cells = [card("X", (3, 1), id="x"), card("S", (3, 4), id="s"), card("U1", (1, 2), id="u1"), card("U2", (1, 3), id="u2")]
        return grid_page(cells, (1, 1, 1, 1), (1, 1, 1), [{"from": "x", "to": "s"}, {"from": "x", "to": "u1"}, {"from": "x", "to": "u2"}])

    def test_the_three_leave_by_the_same_edge_at_equal_steps(self):
        page = self.page()
        x = box_of(page, "X").rect
        starts = sorted(line.start for line in lines_of(page))
        self.assertEqual({x.right}, {start[0] for start in starts})
        ys = [start[1] for start in starts]
        self.assertEqual([x.top + round(x.height * n / 4) for n in (1, 2, 3)], ys)

    def test_the_line_across_leaves_lowest_and_the_nearer_of_the_two_that_turn_up_leaves_highest(self):
        lines = lines_of(self.page())
        across, near, far = lines
        self.assertLess(near.start[1], far.start[1])
        self.assertLess(far.start[1], across.start[1])

    def test_no_two_of_them_run_along_the_same_stretch_or_cross(self):
        lines = lines_of(self.page())
        for number, one in enumerate(lines):
            for other in lines[number + 1:]:
                for run in runs(one.points()):
                    for there in runs(other.points()):
                        self.assertEqual(APART, meet(run, there, 1), (run, there))
        self.assertTrue(all(not line.hops for line in lines))


class LinesThatCrossAndOnesThatOnlyMeet(unittest.TestCase):
    """The cross of two straight lines: the second hops over the first, and only there."""

    def page(self):
        cells = [card("L", (2, 1), id="l"), card("R", (2, 3), id="r"), card("T", (1, 2), id="t"), card("B", (3, 2), id="b")]
        return grid_page(cells, (1, 1, 1), (1, 1, 1), [{"from": "l", "to": "r"}, {"from": "t", "to": "b"}])

    def test_the_line_drawn_later_hops_over_the_one_drawn_first(self):
        first, second = lines_of(self.page())
        self.assertEqual((), first.hops)
        self.assertEqual(1, len(second.hops))
        self.assertEqual((first.start[1] - second.start[1]), second.hops[0][1])
        self.assertEqual(0, second.hops[0][0])
        self.assertEqual(S.gap_s // 2, second.hop)

    def test_lines_that_do_not_cross_do_not_hop(self):
        cells = [card("L", (1, 1), id="l"), card("R", (1, 3), id="r"), card("T", (2, 1), id="t"), card("B", (2, 3), id="b")]
        page = grid_page(cells, (1, 1, 1), (1, 1), [{"from": "l", "to": "r"}, {"from": "t", "to": "b"}])
        self.assertTrue(all(not line.hops for line in lines_of(page)))

    def test_the_hop_stands_clear_of_the_ends_of_the_line_it_is_on(self):
        _first, second = lines_of(self.page())
        (hop_at,) = second.hop_points()
        self.assertGreater(abs(hop_at[1] - second.start[1]), 2 * second.hop)
        self.assertGreater(abs(second.end[1] - hop_at[1]), 2 * second.hop)

    def test_a_line_leaves_the_way_round_when_that_crosses_nothing(self):
        """Two diagonal links over four corner boxes: one goes round by the margin of the page, so neither hops."""
        cells = [card("A", (1, 1), id="a"), card("B", (1, 3), id="b"), card("C", (3, 1), id="c"), card("D", (3, 3), id="d")]
        page = grid_page(cells, (1, 1, 1), (1, 1, 1), [{"from": "a", "to": "d"}, {"from": "c", "to": "b"}])
        self.assertTrue(all(not line.hops for line in lines_of(page)))


if __name__ == "__main__":
    unittest.main()
