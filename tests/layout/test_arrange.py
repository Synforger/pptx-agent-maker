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

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from pptx_agent_maker import checks  # noqa: E402
from pptx_agent_maker.layout import types  # noqa: E402
from pptx_agent_maker.layout.tokens import DEFAULT  # noqa: E402
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


class Marks(unittest.TestCase):
    """絵の上の印: 名前は絵の左右の列に、点の高さに合わせて並び、点まで線が引かれる。"""

    MARKS = [{"at": [0.2, 0.3], "text": "Lens"}, {"at": [0.1, 0.8], "text": "Grip"},
             {"at": [0.9, 0.5], "text": "Button"}]

    def test_names_stand_beside_the_picture_on_the_side_of_their_point_with_a_line_to_it(self):
        page = types.build({"type": "compose", "title": "A page", "rows": [{"cells": [
            {"figure": "wide.png", "marks": self.MARKS}]}]}, lambda name: DATA / name, aspect)
        (picture,) = [e.rect for e in kinds(page, "figure")]
        self.assertEqual(picture.top, page.body.top, "the picture stands at the top of its cell, like any other")
        names = {t.text: t for t in kinds(page, "diagram_text")}
        self.assertLess(names["Lens"].rect.right, picture.left)
        self.assertLess(names["Grip"].rect.right, picture.left)
        self.assertGreater(names["Button"].rect.left, picture.right)
        self.assertEqual(names["Lens"].align, "right")
        self.assertLess(names["Lens"].rect.top, names["Grip"].rect.top, "in the order of their points")
        lines = kinds(page, "line")
        self.assertEqual(len(lines), 3)
        for line, (x, y) in zip(lines, ((0.2, 0.3), (0.1, 0.8), (0.9, 0.5))):
            self.assertAlmostEqual(line.end[0], picture.left + x * picture.width, delta=1)
            self.assertAlmostEqual(line.end[1], picture.top + y * picture.height, delta=1)
        self.assertEqual(len(kinds(page, "circle")), 3, "a dot on each point")

    def test_names_whose_points_crowd_are_pushed_apart_not_piled(self):
        crowd = [{"at": [0.1, 0.5], "text": f"Part {n}"} for n in range(4)]
        page = types.build({"type": "compose", "title": "A page", "rows": [{"cells": [
            {"figure": "wide.png", "marks": crowd}]}]}, lambda name: DATA / name, aspect)
        boxes = sorted((t.rect for t in kinds(page, "diagram_text")), key=lambda r: r.top)
        for upper, lower in zip(boxes, boxes[1:]):
            self.assertGreaterEqual(lower.top, upper.bottom + DEFAULT.spacing.gap_s)

    def test_names_whose_points_crowd_at_the_top_are_pushed_down_into_the_cell(self):
        crowd = [{"at": [0.1, 0.0], "text": f"Part {n}"} for n in range(4)]
        page = types.build({"type": "compose", "title": "A page", "rows": [{"cells": [
            {"figure": "dot.png", "marks": crowd}]}]}, lambda name: DATA / name, aspect)
        (picture,) = [e.rect for e in kinds(page, "figure")]
        self.assertEqual(picture.top, page.body.top, "a square picture stands from the top of a wide cell")
        boxes = sorted((t.rect for t in kinds(page, "diagram_text")), key=lambda r: r.top)
        self.assertGreaterEqual(boxes[0].top, page.body.top)
        for upper, lower in zip(boxes, boxes[1:]):
            self.assertGreaterEqual(lower.top, upper.bottom + DEFAULT.spacing.gap_s)

    def test_a_mark_off_the_picture_or_without_words_is_refused(self):
        for mark in ({"at": [1.2, 0.5], "text": "x"}, {"at": [0.5], "text": "x"}, {"at": [0.5, 0.5]}):
            with self.assertRaises(PageTypeError):
                compose({"figure": "wide.png", "marks": [mark]})
        with self.assertRaises(PageTypeError) as wrong:
            compose({"card": {"heading": "A"}, "marks": self.MARKS})
        self.assertIn("`marks` belong to a figure", str(wrong.exception))


class Links(unittest.TestCase):
    """マスどうしの線: `id` を付けたマスからマスへ、向き合う所に矢印を引く。"""

    def build(self, rows, links):
        return types.build({"type": "compose", "title": "A page", "rows": rows, "links": links},
                           lambda name: DATA / name, aspect)

    def test_cells_side_by_side_and_one_above_the_other_are_joined_across_their_gap(self):
        page = self.build([{"cells": [{"id": "a", "card": {"heading": "A"}}, {"id": "b", "card": {"heading": "B"}}]},
                           {"cells": [{"id": "c", "card": {"heading": "C"}}]}],
                          [{"from": "a", "to": "b"}, {"from": "a", "to": "c"}])
        a, b, c = (e.rect for e in kinds(page, "box"))
        across, down = kinds(page, "line")
        self.assertTrue(across.arrow and down.arrow)
        self.assertEqual((across.start[0], across.end[0]), (a.right, b.left))
        self.assertEqual(across.start[1], across.end[1])
        self.assertEqual((down.start[1], down.end[1]), (a.bottom, c.top))
        self.assertTrue(a.left < down.start[0] < a.right)

    def test_a_link_backwards_points_the_other_way(self):
        page = self.build([{"cells": [{"id": "a", "card": {"heading": "A"}}, {"id": "b", "card": {"heading": "B"}}]}],
                          [{"from": "b", "to": "a"}])
        a, b = (e.rect for e in kinds(page, "box"))
        (line,) = kinds(page, "line")
        self.assertEqual((line.start[0], line.end[0]), (b.left, a.right))

    def test_a_cell_that_holds_both_ends_does_not_stand_between_them(self):
        """Two cards in the rows of one cell are joined across their gap: the cell round them is not in the way."""
        page = self.build([{"cells": [{"rows": [{"cells": [{"id": "a", "card": {"heading": "A"}}]},
                                                {"cells": [{"id": "b", "card": {"heading": "B"}}]}]},
                                      {"card": {"heading": "Beside"}}]}],
                          [{"from": "a", "to": "b"}])
        (line,) = kinds(page, "line")
        self.assertTrue(line.arrow)

    def test_an_unknown_id_a_cell_between_or_cells_that_do_not_face_are_refused(self):
        row = [{"cells": [{"id": "a", "card": {"heading": "A"}}, {"card": {"heading": "M"}},
                          {"id": "b", "card": {"heading": "B"}}]}]
        with self.assertRaises(PageTypeError) as unknown:
            self.build(row, [{"from": "a", "to": "z"}])
        self.assertIn("'z'", str(unknown.exception))
        with self.assertRaises(PageTypeError) as between:
            self.build(row, [{"from": "a", "to": "b"}])
        self.assertIn("stands between", str(between.exception))
        corner = [{"cells": [{"id": "a", "card": {"heading": "A"}}, {"card": {"heading": "M"}}]},
                  {"cells": [{"text": "x", "weight": 3}, {"id": "b", "card": {"heading": "B"}}]}]
        with self.assertRaises(PageTypeError) as apart:
            self.build(corner, [{"from": "a", "to": "b"}])
        self.assertIn("do not face", str(apart.exception))
        with self.assertRaises(PageTypeError) as twice:
            self.build([{"cells": [{"id": "a", "text": "x"}, {"id": "a", "text": "y"}]}], [{"from": "a", "to": "a"}])
        self.assertIn("two cells have the id", str(twice.exception))
