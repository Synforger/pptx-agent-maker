"""Arrangements a compose cell can hold: a ring, a tree, circles that overlap.

見張るのは 4 つ ― 箱が重ならずに枠の中に並ぶこと、並びの意味 (= 輪の向き、木の親子、重なりの共通部分) が
線と位置に出ること、収まらなければ縮めずに止まること、書き出した deck が検査を通ること。
"""

from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from pptx_agent_maker import checks  # noqa: E402
from pptx_agent_maker.layout import types  # noqa: E402
from pptx_agent_maker.layout.base.tokens import DEFAULT  # noqa: E402
from pptx_agent_maker.layout.parts.page import PageFullError  # noqa: E402
from pptx_agent_maker.layout.types.bodies import arrange  # noqa: E402
from pptx_agent_maker.layout.types.core.registry import PageTypeError  # noqa: E402
from pptx_agent_maker.write import add_page, aspect, new_deck, save  # noqa: E402

DATA = REPO / "tests" / "data"


def compose(*cells, **row):
    return types.build({"type": "compose", "title": "A page", "rows": [{"cells": list(cells), **row}]},
                       lambda name: DATA / name, aspect)


def kinds(page, kind):
    return [e for e in page.build() if e.kind == kind]


def crossing(a, b):
    return a.left < b.right and b.left < a.right and a.top < b.bottom and b.top < a.bottom


def inside(point, rect):
    return rect.left <= point[0] <= rect.right and rect.top <= point[1] <= rect.bottom


def middle(rect):
    return rect.left + rect.width / 2, rect.top + rect.height / 2


STEPS = [{"heading": "Plan", "body": "set the aim"}, {"heading": "Do", "body": "try it small"},
         {"heading": "Check", "body": "measure"}, {"heading": "Act", "body": "feed it back"}]
TREE = {"heading": "Head", "children": [
    {"heading": "Sales", "children": [{"heading": "East"}, {"heading": "West"}]},
    {"heading": "Build", "children": [{"heading": "Product"}, {"heading": "Base"}]},
    {"heading": "Office"}]}


class Ring(unittest.TestCase):

    def test_the_boxes_go_round_from_the_top_clockwise_without_touching(self):
        page = compose({"ring": STEPS})
        boxes = [e.rect for e in kinds(page, "box")]
        self.assertEqual(len(boxes), 4)
        (top, right, bottom, left) = [middle(box) for box in boxes]
        self.assertLess(top[1], right[1])
        self.assertGreater(right[0], top[0])
        self.assertGreater(bottom[1], right[1])
        self.assertLess(left[0], bottom[0])
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                self.assertFalse(crossing(a, b))
        area = page.body
        self.assertTrue(all(area.contains(box) for box in boxes))

    def test_six_boxes_keep_room_for_their_arrows_between_them(self):
        page = compose({"ring": [{"heading": f"Step {n}", "body": "what happens"} for n in range(6)]})
        boxes = [e.rect for e in kinds(page, "box")]
        gap = DEFAULT.spacing.gap_l
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                apart = max(b.left - a.right, a.left - b.right, b.top - a.bottom, a.top - b.bottom)
                self.assertGreaterEqual(apart, gap, "an arrow needs room between two boxes")

    def test_each_box_points_at_the_next_and_the_last_at_the_first(self):
        page = compose({"ring": STEPS})
        boxes = [e.rect for e in kinds(page, "box")]
        lines = kinds(page, "line")
        self.assertEqual(len(lines), 4)
        self.assertTrue(all(line.arrow for line in lines))
        for number, line in enumerate(lines):
            here, after = boxes[number], boxes[(number + 1) % 4]
            near = lambda point, box: abs(point[0] - middle(box)[0]) + abs(point[1] - middle(box)[1])
            self.assertLess(near(line.start, here), near(line.start, after), "starts by its own box")
            self.assertLess(near(line.end, after), near(line.end, here), "ends by the next one")
            for box in boxes:
                self.assertFalse(inside(line.start, box) or inside(line.end, box))

    def test_a_ring_is_three_to_eight_boxes(self):
        with self.assertRaises(PageTypeError):
            compose({"ring": STEPS[:2]})
        with self.assertRaises(PageTypeError):
            compose({"ring": STEPS * 3})

    def test_a_ring_with_no_room_stops_rather_than_shrinking(self):
        with self.assertRaises(PageFullError) as stopped:
            compose({"ring": [{"heading": "Word" * 6, "body": "long " * 30}] * 8}, {"text": "x"}, {"text": "y"},
                    {"text": "z"})
        self.assertIn("nothing will shrink", str(stopped.exception))


class Tree(unittest.TestCase):

    def test_levels_go_down_and_each_parent_stands_over_its_children(self):
        page = compose({"tree": TREE})
        boxes = {e.rect: e for e in kinds(page, "box")}
        words = {t.text: t.rect for t in kinds(page, "box_heading")}
        holder = lambda name: next(box for box in boxes if box.contains(words[name]))
        head, sales, east, west = holder("Head"), holder("Sales"), holder("East"), holder("West")
        self.assertLess(head.bottom, sales.top)
        self.assertLess(sales.bottom, east.top)
        self.assertEqual(east.top, west.top)
        self.assertAlmostEqual(middle(sales)[0], (middle(east)[0] + middle(west)[0]) / 2, delta=2)
        self.assertEqual(len(boxes), 8)

    def test_lines_join_each_parent_to_its_children_and_nothing_else(self):
        page = compose({"tree": TREE})
        lines = kinds(page, "line")
        self.assertFalse(any(line.arrow for line in lines))
        # 子を持つ親ごとに、下へ 1 本・横へ 1 本 (= 子が 2 つ以上)・子へ 1 本ずつ
        self.assertEqual(len(lines), (1 + 1 + 3) + (1 + 1 + 2) * 2)
        self.assertTrue(all(line.start[0] == line.end[0] or line.start[1] == line.end[1] for line in lines))

    def test_a_tree_takes_the_height_of_its_levels(self):
        page = compose({"tree": TREE})
        boxes = [e.rect for e in kinds(page, "box")]
        self.assertEqual(max(box.bottom for box in boxes) - min(box.top for box in boxes),
                         arrange.tree_height(page, arrange.tree_root(None, TREE, "t"), page.body.width))

    def test_a_tree_too_deep_or_too_wide_is_refused(self):
        deep = {"heading": "1", "children": [{"heading": "2", "children": [{"heading": "3", "children": [
            {"heading": "4", "children": [{"heading": "5"}]}]}]}]}
        with self.assertRaises(PageTypeError):
            compose({"tree": deep})
        wide = {"heading": "Root", "children": [{"heading": f"Department-number-{n}"} for n in range(14)]}
        with self.assertRaises(PageFullError) as stopped:
            compose({"tree": wide})
        self.assertIn("row 1, cell 1", str(stopped.exception))


class Overlap(unittest.TestCase):

    def test_two_circles_cross_and_their_names_sit_in_their_own_parts(self):
        page = compose({"overlap": {"sets": ["Craft", "Trade"], "shared": "Product"}})
        circles = kinds(page, "circle")
        self.assertEqual(len(circles), 2)
        a, b = (c.rect for c in circles)
        self.assertTrue(crossing(a, b))
        self.assertEqual(a.width, a.height)
        self.assertTrue(all(0 < c.clear < 1 for c in circles), "where they cross shows through")
        names = {t.text: t.rect for t in kinds(page, "diagram_text")}
        self.assertLess(middle(names["Craft"])[0], b.left, "the first name is outside the second circle")
        self.assertGreater(middle(names["Trade"])[0], a.right, "and the second outside the first")
        self.assertLess(middle(names["Craft"])[0], middle(a)[0], "each name leans away from the other circle")
        self.assertGreater(middle(names["Trade"])[0], middle(b)[0])
        shared = middle(names["Product"])
        self.assertTrue(b.left < shared[0] < a.right)

    def test_three_circles_share_one_middle(self):
        page = compose({"overlap": {"sets": ["A", {"name": "B", "tone": "accent"}, "C"], "shared": "All"}})
        circles = [c.rect for c in kinds(page, "circle")]
        self.assertEqual(len(circles), 3)
        shared = middle(next(t.rect for t in kinds(page, "diagram_text") if t.text == "All"))
        for circle in circles:
            cx, cy = middle(circle)
            self.assertLess((shared[0] - cx) ** 2 + (shared[1] - cy) ** 2, (circle.width / 2) ** 2)
        self.assertEqual(kinds(page, "circle")[1].colour, DEFAULT.palette.accent)

    def test_one_set_or_four_are_refused(self):
        for sets in (["A"], ["A", "B", "C", "D"]):
            with self.assertRaises(PageTypeError):
                compose({"overlap": {"sets": sets}})


class Written(unittest.TestCase):

    def test_lines_arrowheads_and_see_through_circles_are_written_and_the_checks_find_nothing(self):
        deck = new_deck(DEFAULT)
        for cell in ({"ring": STEPS}, {"tree": TREE}, {"overlap": {"sets": ["A", "B"], "shared": "both"}}):
            add_page(deck, compose(cell).build(), DEFAULT)
        with tempfile.TemporaryDirectory() as tmp:
            saved = save(deck, Path(tmp) / "arrange.pptx")
            self.assertEqual([], checks.run_all(saved))
            with zipfile.ZipFile(saved) as archive:
                ring, tree, overlap = (archive.read(f"ppt/slides/slide{n}.xml").decode("utf-8") for n in (1, 2, 3))
        self.assertEqual(ring.count('<a:tailEnd type="triangle"'), 4)
        self.assertNotIn("<p:style>", ring + tree, "connectors take no theme style")
        self.assertIn('prst="ellipse"', overlap)
        self.assertIn('<a:alpha val="65000"/>', overlap)


if __name__ == "__main__":
    unittest.main()
