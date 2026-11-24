"""The edges a link is written to leave and enter by, the lines that leave or enter one edge together, and the words on a bent line.

見張るのは 3 つ ― `out` / `in` に書いた辺から出て、書いた辺へ入ること (= 書いた辺が真っすぐの線の辺と同じなら、線は
真っすぐのまま動かない)、同じ箱の同じ辺から出る (= 同じ辺へ入る) と書いた線が 1 本の幹と横の線にまとまること、曲がる線の
`text` が、出る辺から最初に曲がるまでの区間のそばに立つこと (= 入らなければ、縮めずに止まる)。
"""

from __future__ import annotations

#: written when a page of words in boxes alone could be built (= `tests/conftest.py`)
FIGURE_RULE_LIFTED = True


import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))
from support.pages import box_of, build, named  # noqa: E402

from pptx_agent_maker.layout.parts.page import PageFullError  # noqa: E402
from pptx_agent_maker.layout.types.core.registry import PageTypeError  # noqa: E402


def card(name):
    return {"id": name, "card": {"heading": name.upper(), "body": "words"}}


def blank():
    return {"text": ""}


def row(*cells):
    return {"cells": list(cells)}


def compose(rows, links):
    return build({"type": "compose", "title": "A page", "rows": rows, "links": links})


def lines_of(page):
    return [e for e in page.build() if e.kind == "line"]


#: 2 つの箱が横に並ぶ頁 (= 上と下に空の段が在るので、線が箱の上と下を回れる)
SIDE_BY_SIDE = [row(blank(), blank()), row(card("a"), card("b")), row(blank(), blank())]
#: 親が 1 つ、その下に子が 3 つ (= まん中の子は親の真下)
PARENT_AND_CHILDREN = [row(blank(), card("p"), blank()), row(card("x"), card("y"), card("z"))]
#: 幅いっぱいの箱が 1 つ、その下に 2 つ (= 2 つとも上の箱と向き合うが、上の箱の真ん中の真下ではない)
WIDE_AND_TWO_BELOW = [row(card("p")), row(card("x"), card("y"))]
#: 右の上に 1 つ、左下に 2 つ (= 左下の 2 つから右上の 1 つへは、箱の上の空きを回って入る)
TWO_BELOW_LEFT = [row(blank(), blank(), blank()), row(blank(), blank(), card("q")), row(card("d1"), card("d2"), blank())]
#: 右上の箱から左下の箱へ (= 向き合わない)
UP_RIGHT_TO_DOWN_LEFT = [row(blank(), card("a")), row(card("b"), blank())]


class TheEdgeAWrittenLinkLeavesAndEntersBy(unittest.TestCase):
    """`out` and `in`: the line leaves by the edge written and goes into the box by the edge written; one written, the other as ever."""

    def test_edges_a_straight_line_already_uses_change_nothing(self):
        unwritten = lines_of(compose(SIDE_BY_SIDE, [{"from": "a", "to": "b"}]))[0].points()
        for written in ({"out": "right"}, {"in": "left"}, {"out": "right", "in": "left"}):
            with self.subTest(written=written):
                (line,) = lines_of(compose(SIDE_BY_SIDE, [{"from": "a", "to": "b", **written}]))
                self.assertEqual(unwritten, line.points())
                self.assertEqual(0, len(line.corners))

    def test_a_line_written_to_leave_by_another_edge_bends_and_leaves_by_it(self):
        page = compose(SIDE_BY_SIDE, [{"from": "a", "to": "b", "out": "bottom"}])
        (line,) = lines_of(page)
        a = box_of(page, "A").rect
        self.assertEqual(a.bottom, line.start[1])
        self.assertTrue(a.left < line.start[0] < a.right)
        self.assertTrue(line.corners, "leaving by the lower edge, it cannot reach the box beside it without a bend")

    def test_a_line_written_to_enter_by_another_edge_bends_and_goes_in_by_it(self):
        page = compose(SIDE_BY_SIDE, [{"from": "a", "to": "b", "in": "top"}])
        (line,) = lines_of(page)
        b = box_of(page, "B").rect
        self.assertEqual(b.top, line.end[1])
        self.assertTrue(b.left < line.end[0] < b.right)
        self.assertLess(line.points()[-2][1], b.top, "it comes down into the box")

    def test_both_written_the_line_leaves_by_the_one_and_enters_by_the_other(self):
        page = compose(SIDE_BY_SIDE, [{"from": "a", "to": "b", "out": "bottom", "in": "bottom"}])
        (line,) = lines_of(page)
        a, b = box_of(page, "A").rect, box_of(page, "B").rect
        self.assertEqual((a.bottom, b.bottom), (line.start[1], line.end[1]))
        self.assertGreater(min(y for _, y in line.points()[1:-1]), a.bottom, "it runs below both boxes")

    def test_a_link_written_to_leave_by_the_edge_it_would_leave_by_anyway_is_left_alone(self):
        page = compose(UP_RIGHT_TO_DOWN_LEFT, [{"from": "a", "to": "b"}])
        (unwritten,) = lines_of(page)
        a = box_of(page, "A").rect
        edge = "left" if unwritten.start[0] == a.left else "bottom"
        (line,) = lines_of(compose(UP_RIGHT_TO_DOWN_LEFT, [{"from": "a", "to": "b", "out": edge}]))
        self.assertEqual(unwritten.points(), line.points())

    def test_a_word_that_is_not_an_edge_stops_and_names_the_four(self):
        for key in ("out", "in"):
            with self.subTest(key=key), self.assertRaises(PageTypeError) as stopped:
                compose(SIDE_BY_SIDE, [{"from": "a", "to": "b", key: "middle"}])
            self.assertIn(f"`{key}`", str(stopped.exception))
            self.assertIn("top, bottom, left, right", str(stopped.exception))

    def test_an_edge_with_no_way_to_it_stops_and_says_which_box_is_in_the_way(self):
        """In a single row there is no lane above the boxes, so a line cannot come down into `b`."""
        with self.assertRaises(PageTypeError) as stopped:
            compose([row(card("a"), card("b"))], [{"from": "a", "to": "b", "in": "top"}])
        self.assertIn("finds no way through", str(stopped.exception))
        self.assertIn("'b'", str(stopped.exception))


class LinesThatLeaveOneEdgeTogether(unittest.TestCase):
    """Two or more links written with the same `out` from one box leave by one trunk and part along a cross line, as a tree's lines do."""

    LINKS = [{"from": "p", "to": child, "out": "bottom"} for child in ("x", "y", "z")]

    def test_they_start_at_one_point_and_the_trunk_is_the_first_run_of_all_three(self):
        page = compose(PARENT_AND_CHILDREN, self.LINKS)
        lines = lines_of(page)
        p = box_of(page, "P").rect
        self.assertEqual({(p.left + p.width // 2, p.bottom)}, {line.start for line in lines})
        bent = [line.points() for line in lines if line.corners]
        self.assertEqual(1, len({points[1] for points in bent}), "the two that part turn at one point")
        self.assertEqual(p.left + p.width // 2, bent[0][1][0])

    def test_the_cross_line_is_one_level_and_each_branch_goes_down_into_the_top_of_its_box(self):
        page = compose(PARENT_AND_CHILDREN, self.LINKS)
        lines = lines_of(page)
        p = box_of(page, "P").rect
        levels = {points[1][1] for points in (line.points() for line in lines) if len(points) > 2}
        self.assertEqual(1, len(levels))
        (level,) = levels
        self.assertTrue(p.bottom < level < box_of(page, "X").rect.top)
        for line, name in zip(lines, ("X", "Y", "Z")):
            child = box_of(page, name).rect
            self.assertEqual(child.top, line.end[1])
            self.assertEqual(child.left + child.width // 2, line.end[0])
            self.assertLess(line.points()[-2][1], child.top)

    def test_the_child_in_front_of_the_trunk_is_reached_along_it(self):
        lines = lines_of(compose(PARENT_AND_CHILDREN, self.LINKS))
        self.assertEqual(0, len(lines[1].corners))
        self.assertEqual(lines[1].start[0], lines[1].end[0])

    def test_written_alike_the_children_beside_the_parent_leave_by_the_trunk_too(self):
        """Unwritten, the child below is straight and the two beside it leave by the sides; written, all three share the trunk."""
        unwritten = lines_of(compose(PARENT_AND_CHILDREN, [{"from": "p", "to": child} for child in ("x", "y", "z")]))
        written = lines_of(compose(PARENT_AND_CHILDREN, self.LINKS))
        self.assertEqual(3, len({line.start for line in unwritten}))
        self.assertEqual(1, len({line.start for line in written}))

    def test_children_that_face_the_parent_but_not_its_middle_leave_by_the_trunk_all_the_same(self):
        page = compose(WIDE_AND_TWO_BELOW, [{"from": "p", "to": child, "out": "bottom"} for child in ("x", "y")])
        lines = lines_of(page)
        p = box_of(page, "P").rect
        self.assertEqual({(p.left + p.width // 2, p.bottom)}, {line.start for line in lines})
        self.assertTrue(all(line.corners for line in lines), "each part along the cross line")

    def test_a_branch_with_no_edge_written_goes_into_the_edge_facing_the_trunk(self):
        """Nothing is written for the edge in: a box below the trunk is entered by its top, though a side is nearer for the one far off."""
        rows = [row(blank(), card("p"), blank(), blank()), row(card("x"), blank(), blank(), card("z"))]
        page = compose(rows, [{"from": "p", "to": "x", "out": "bottom"}, {"from": "p", "to": "z", "out": "bottom"}])
        for line, name in zip(lines_of(page), ("X", "Z")):
            child = box_of(page, name).rect
            self.assertEqual(child.top, line.end[1], name)

    def test_a_box_beside_the_trunk_is_not_given_an_edge_it_does_not_face(self):
        """`out = "bottom"` to a box higher than the parent: no edge faces the trunk, so the way picks it (= it is not forced to the top)."""
        rows = [row(card("x"), blank()), row(blank(), card("p")), row(blank(), card("y"))]
        page = compose(rows, [{"from": "p", "to": "x", "out": "bottom"}, {"from": "p", "to": "y", "out": "bottom"}])
        x = box_of(page, "X").rect
        line = lines_of(page)[0]
        self.assertNotEqual(x.top, line.end[1], "the line goes into x from below or the side, not by its top")

    def test_a_link_written_alone_is_no_trunk_and_keeps_its_straight_line(self):
        page = compose(PARENT_AND_CHILDREN, [{"from": "p", "to": "y", "out": "bottom"}])
        (line,) = lines_of(page)
        self.assertEqual(0, len(line.corners))

    def test_links_that_leave_by_different_edges_do_not_share_a_trunk(self):
        page = compose([row(blank(), card("p"), card("x")), row(card("y"), blank(), blank())],
                       [{"from": "p", "to": "x", "out": "right"}, {"from": "p", "to": "y", "out": "left"}])
        lines = lines_of(page)
        self.assertEqual(2, len({line.start for line in lines}))

    def test_a_trunk_that_has_no_way_stops_naming_the_box_in_its_way(self):
        rows = [row(card("p")), row(card("wall")), row(card("x"), card("y"))]
        with self.assertRaises(PageTypeError) as stopped:
            compose(rows, [{"from": "p", "to": "x", "out": "bottom", "in": "top"},
                           {"from": "p", "to": "y", "out": "bottom", "in": "top"}])
        self.assertIn("wall", str(stopped.exception))


class LinesThatEnterOneEdgeTogether(unittest.TestCase):
    """Two or more links written with the same `in` to one box leave their boxes, join along a cross line and enter by one trunk."""

    LINKS = [{"from": child, "to": "p", "in": "bottom"} for child in ("x", "y", "z")]

    def test_they_end_at_one_point_on_the_edge_and_the_trunk_is_the_last_run_of_all_three(self):
        page = compose(PARENT_AND_CHILDREN, self.LINKS)
        lines = lines_of(page)
        p = box_of(page, "P").rect
        self.assertEqual({(p.left + p.width // 2, p.bottom)}, {line.end for line in lines})
        bent = [line.points() for line in lines if line.corners]
        self.assertEqual(1, len({points[-2] for points in bent}), "the two that join turn at one point")

    def test_each_line_leaves_the_top_of_its_own_box(self):
        page = compose(PARENT_AND_CHILDREN, self.LINKS)
        for line, name in zip(lines_of(page), ("X", "Y", "Z")):
            child = box_of(page, name).rect
            self.assertEqual((child.left + child.width // 2, child.top), line.start)

    def test_the_trunk_goes_round_the_boxes_the_way_a_bent_line_does(self):
        """Two boxes low on the left go into one high on the right by its top: down, across, up between the columns, across, down."""
        page = compose(TWO_BELOW_LEFT, [{"from": "d1", "to": "q", "out": "bottom", "in": "top"},
                                        {"from": "d2", "to": "q", "out": "bottom", "in": "top"}])
        first, second = (line.points() for line in lines_of(page))
        self.assertEqual(second[2:], first[2:], "they run as one from the level below the boxes on")
        self.assertEqual(4, len(first) - 2, "four bends")
        q = box_of(page, "Q").rect
        self.assertEqual((q.left + q.width // 2, q.top), first[-1])
        self.assertLess(first[-2][1], q.top)
        for name in ("D1", "D2", "Q"):
            box = box_of(page, name).rect
            self.assertFalse(any(box.left < max(x1, x2) and min(x1, x2) < box.right
                                 and box.top < max(y1, y2) and min(y1, y2) < box.bottom
                                 for (x1, y1), (x2, y2) in zip(first[1:-1], first[2:])), name)

    def test_two_boxes_that_face_the_one_they_enter_join_along_the_cross_line_all_the_same(self):
        """Even where each could go straight (= the boxes face), written alike they go into one point of the edge."""
        page = compose(WIDE_AND_TWO_BELOW, [{"from": child, "to": "p", "in": "bottom"} for child in ("x", "y")])
        lines = lines_of(page)
        p = box_of(page, "P").rect
        self.assertEqual({(p.left + p.width // 2, p.bottom)}, {line.end for line in lines})
        self.assertTrue(all(line.corners for line in lines))


class WordsOnABentLine(unittest.TestCase):
    """`text` on a bent line stands beside its first run: above a sideways one, to the right of a vertical one."""

    def test_the_words_stand_above_the_first_run_out_of_the_box_the_line_leaves(self):
        page = compose(UP_RIGHT_TO_DOWN_LEFT, [{"from": "a", "to": "b", "out": "left", "in": "top", "text": "Yes"}])
        (line,) = lines_of(page)
        words = named(page, "Yes").rect
        corner = line.points()[1]
        self.assertLess(words.bottom, line.start[1])
        self.assertTrue(corner[0] <= words.left and words.right <= line.start[0])

    def test_the_words_stand_to_the_right_of_a_first_run_that_goes_down(self):
        page = compose([row(card("a"), blank(), blank()), row(blank(), blank(), card("b"))],
                       [{"from": "a", "to": "b", "out": "bottom", "in": "left", "text": "Yes"}])
        (line,) = lines_of(page)
        words = named(page, "Yes").rect
        corner = line.points()[1]
        self.assertGreater(words.left, line.start[0])
        self.assertTrue(line.start[1] <= words.top and words.bottom <= corner[1])

    def test_a_line_with_no_words_and_one_with_words_are_drawn_alike(self):
        written = {"from": "a", "to": "b", "out": "left", "in": "top"}
        plain = lines_of(compose(UP_RIGHT_TO_DOWN_LEFT, [written]))[0]
        with_words = lines_of(compose(UP_RIGHT_TO_DOWN_LEFT, [{**written, "text": "Yes"}]))[0]
        self.assertEqual(plain.points(), with_words.points())

    def test_words_that_need_more_height_than_the_first_run_has_stop_and_say_how_much(self):
        long_words = "a long wording that has to be set over many lines " * 3
        with self.assertRaises(PageFullError) as stopped:
            compose(UP_RIGHT_TO_DOWN_LEFT, [{"from": "a", "to": "b", "out": "left", "in": "top", "text": long_words}])
        message = str(stopped.exception)
        self.assertIn("above the first run of the line", message)
        self.assertIn("nothing will shrink", message)

    def test_words_above_a_first_run_stay_under_the_cell_above_it(self):
        """The words may rise to the top of the page, but not into a cell: 4 lines fit under the page's top, not under the cell."""
        link = {"from": "a", "to": "b", "out": "left", "in": "top", "text": "word " * 20}
        beside = [row(blank(), card("t")), row(blank(), card("a")), row(card("b"), blank())]
        over = [row(card("t"), blank()), row(blank(), card("a")), row(card("b"), blank())]
        compose(beside, [link])
        with self.assertRaises(PageFullError):
            compose(over, [link])

    def test_words_on_a_line_that_leaves_an_edge_with_others_stop_because_the_first_run_is_theirs_too(self):
        links = [{"from": "p", "to": "x", "out": "bottom", "text": "Yes"}, {"from": "p", "to": "z", "out": "bottom"}]
        with self.assertRaises(PageTypeError) as stopped:
            compose(PARENT_AND_CHILDREN, links)
        self.assertIn("together with 1 other line", str(stopped.exception))

    def test_words_on_lines_that_enter_one_edge_together_stand_by_the_first_run_of_each(self):
        """Two boxes one above the other, each leaving by its left edge into the top of a box below: the words stand over each one's own run."""
        rows = [row(blank(), card("a")), row(blank(), card("b")), row(card("d"), blank())]
        page = compose(rows, [{"from": "a", "to": "d", "out": "left", "in": "top", "text": "Yes"},
                              {"from": "b", "to": "d", "out": "left", "in": "top", "text": "No"}])
        first, second = lines_of(page)
        self.assertEqual(first.end, second.end)
        self.assertEqual(first.points()[-2][0], second.points()[-2][0], "they go down into the box along one run")
        for line, words in ((first, "Yes"), (second, "No")):
            rect = named(page, words).rect
            self.assertLess(rect.bottom, line.start[1])
            self.assertTrue(line.points()[1][0] <= rect.left and rect.right <= line.start[0])

    def test_words_on_a_first_run_shorter_than_a_line_stop_and_say_how_much_is_missing(self):
        """The first run of a line that goes up to the cross line is half a gap: there is no room for words beside it."""
        links = [{"from": "x", "to": "p", "in": "bottom", "text": "Yes"}, {"from": "z", "to": "p", "in": "bottom"}]
        with self.assertRaises(PageFullError) as stopped:
            compose(PARENT_AND_CHILDREN, links)
        self.assertIn("to the right of the first run of the line", str(stopped.exception))
        self.assertIn("nothing will shrink", str(stopped.exception))


if __name__ == "__main__":
    unittest.main()
