"""Arrangements a compose cell can hold: a ring, a tree, circles that overlap.

見張るのは 4 つ ― 箱が重ならずに枠の中に並ぶこと、並びの意味 (= 輪の向き、木の親子、重なりの共通部分) が
線と位置に出ること、収まらなければ縮めずに止まること、書き出した deck が検査を通ること。
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))

from support.pages import box_of  # noqa: E402

from pptx_agent_maker import checks  # noqa: E402
from pptx_agent_maker.layout import types  # noqa: E402
from pptx_agent_maker.layout.tokens import DEFAULT, theme_from  # noqa: E402
from pptx_agent_maker.layout.parts.page import Page, PageFullError  # noqa: E402
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


class BentLinks(unittest.TestCase):
    """Cells that do not face each other (= corner to corner) are joined by a line that bends once at a right angle."""

    def corner(self, from_, to, *, across_gap, down_gap):
        """A 2 x 2 page of A B / C D whose gaps are as asked; the two cells the link does not use hold no words."""
        spacing = {"gap_x": across_gap, "gap_y": down_gap}
        theme = theme_from({"uses": {"gapped": {"like": "read", "spacing": spacing}}}).using("gapped")
        cell = lambda name: {"id": name.lower(), "card": {"heading": name}} if name in (from_, to) else {"text": ""}
        rows = [{"cells": [cell("A"), cell("B")]}, {"cells": [cell("C"), cell("D")]}]
        page = types.build({"type": "compose", "title": "A page", "rows": rows,
                            "links": [{"from": from_.lower(), "to": to.lower()}]}, lambda name: DATA / name, aspect, theme)
        (line,) = kinds(page, "line")
        return page, line, box_of(page, from_).rect, box_of(page, to).rect

    def test_when_the_gap_across_is_the_narrower_the_line_leaves_sideways_and_goes_into_the_other_from_above_or_below(self):
        _page, line, a, d = self.corner("A", "D", across_gap=0.5, down_gap=3)
        self.assertEqual("across", line.bend)
        self.assertEqual((a.right, a.top + a.height // 2), line.start)
        self.assertEqual((d.left + d.width // 2, d.top), line.end)
        self.assertTrue(line.arrow)

    def test_when_the_gap_down_is_the_narrower_the_line_leaves_downwards_and_goes_into_the_other_from_the_side(self):
        _page, line, a, d = self.corner("A", "D", across_gap=3, down_gap=0.5)
        self.assertEqual("down", line.bend)
        self.assertEqual((a.left + a.width // 2, a.bottom), line.start)
        self.assertEqual((d.left, d.top + d.height // 2), line.end)

    def test_gaps_that_are_equal_leave_sideways(self):
        _page, line, _a, _d = self.corner("A", "D", across_gap=1, down_gap=1)
        self.assertEqual("across", line.bend)

    def test_every_one_of_the_four_corners_is_read_from_the_cell_the_line_leaves(self):
        gaps = {"across_gap": 0.5, "down_gap": 3}
        _p, line, d, a = self.corner("D", "A", **gaps)              # up and to the left
        self.assertEqual(((d.left, d.top + d.height // 2), (a.left + a.width // 2, a.bottom)), (line.start, line.end))
        _p, line, b, c = self.corner("B", "C", **gaps)              # down and to the left
        self.assertEqual(((b.left, b.top + b.height // 2), (c.left + c.width // 2, c.top)), (line.start, line.end))
        _p, line, c, b = self.corner("C", "B", **gaps)              # up and to the right
        self.assertEqual(((c.right, c.top + c.height // 2), (b.left + b.width // 2, b.bottom)), (line.start, line.end))
        gaps = {"across_gap": 3, "down_gap": 0.5}
        _p, line, d, a = self.corner("D", "A", **gaps)
        self.assertEqual(((d.left + d.width // 2, d.top), (a.right, a.top + a.height // 2)), (line.start, line.end))
        _p, line, c, b = self.corner("C", "B", **gaps)
        self.assertEqual(((c.left + c.width // 2, c.top), (b.left, b.top + b.height // 2)), (line.start, line.end))
        self.assertEqual("down", line.bend)

    def test_cells_that_face_each_other_are_still_joined_by_a_straight_line(self):
        page = Links().build([{"cells": [{"id": "a", "card": {"heading": "A"}}, {"id": "b", "card": {"heading": "B"}}]},
                              {"cells": [{"id": "c", "card": {"heading": "C"}}]}],
                             [{"from": "a", "to": "b"}, {"from": "a", "to": "c"}])
        self.assertEqual(["", ""], [line.bend for line in kinds(page, "line")])

    def test_a_cell_the_line_runs_across_stops_the_page_and_the_error_says_which_line_and_which_cell(self):
        rows = [{"cells": [{"id": "a", "card": {"heading": "A"}}, {"id": "m", "card": {"heading": "M"}}]},
                {"cells": [{"id": "c", "card": {"heading": "C"}}, {"id": "b", "card": {"heading": "B"}}]}]
        with self.assertRaises(PageTypeError) as raised:
            Links().build(rows, [{"from": "a", "to": "b"}])
        message = str(raised.exception)
        self.assertIn("link 1: the line from 'a' to 'b' bends once", message)
        self.assertIn("runs across the cell 'm'", message)
        self.assertIn("out of 'a' sideways, then vertically into 'b'", message)
        with self.assertRaises(PageTypeError) as other_way:
            Links().build(rows, [{"from": "b", "to": "a"}])
        self.assertIn("runs across the cell 'c'", str(other_way.exception))

    def test_a_cell_on_the_second_leg_of_a_line_that_leaves_downwards_stops_the_page_too(self):
        spacing = {"gap_x": 3, "gap_y": 0.5}
        theme = theme_from({"uses": {"gapped": {"like": "read", "spacing": spacing}}}).using("gapped")
        rows = [{"cells": [{"id": "a", "card": {"heading": "A"}}, {"text": ""}, {"text": ""}]},
                {"cells": [{"text": ""}, {"id": "x", "card": {"heading": "X"}}, {"id": "b", "card": {"heading": "B"}}]}]
        with self.assertRaisesRegex(PageTypeError, r"out of 'a' vertically, then sideways into 'b'\) and runs across "
                                                   r"the cell 'x'"):
            types.build({"type": "compose", "title": "A page", "rows": rows, "links": [{"from": "a", "to": "b"}]},
                        lambda name: DATA / name, aspect, theme)

    def test_a_page_asked_for_a_line_that_bends_neither_across_nor_down_is_refused(self):
        page = Page("A page", DEFAULT)
        with self.assertRaisesRegex(ValueError, "a line bends 'across' or 'down', not 'sideways'"):
            page.line((0, 0), (10, 10), bend="sideways")

    def test_a_cell_with_no_id_in_the_way_is_named_by_where_it_stands(self):
        rows = [{"cells": [{"id": "a", "card": {"heading": "A"}}, {"card": {"heading": "M"}}]},
                {"cells": [{"card": {"heading": "C"}}, {"id": "b", "card": {"heading": "B"}}]}]
        with self.assertRaisesRegex(PageTypeError, r"runs across a cell with no id \(\d+\.\d cm from the left, \d+\.\d cm from the top\)"):
            Links().build(rows, [{"from": "a", "to": "b"}])

    def test_a_bent_line_carries_no_words(self):
        rows = [{"cells": [{"id": "a", "card": {"heading": "A"}}, {"text": ""}]},
                {"cells": [{"text": ""}, {"id": "b", "card": {"heading": "B"}}]}]
        with self.assertRaisesRegex(PageTypeError, "a bent line carries no words"):
            Links().build(rows, [{"from": "a", "to": "b", "text": "then"}])

    def test_the_colour_of_a_bent_line_is_the_colour_of_its_tone(self):
        rows = [{"cells": [{"id": "a", "card": {"heading": "A"}}, {"text": ""}]},
                {"cells": [{"text": ""}, {"id": "b", "card": {"heading": "B"}}]}]
        (line,) = kinds(Links().build(rows, [{"from": "a", "to": "b", "tone": "bad"}]), "line")
        self.assertEqual(DEFAULT.palette.bad, line.colour)
        self.assertEqual("across", line.bend)


class TheBentLineInTheFile(unittest.TestCase):
    """A bent line is one connector that bends once (= `bentConnector2`); the file draws it where the link says, the head where it points."""

    SLIDE = "ppt/slides/slide1.xml"

    def connectors(self, rows, links, theme=DEFAULT):
        page = types.build({"type": "compose", "title": "A page", "rows": rows, "links": links},
                           lambda name: DATA / name, aspect, theme)
        deck = new_deck(theme)
        add_page(deck, page.build(), theme)
        with tempfile.TemporaryDirectory() as tmp:
            saved = save(deck, Path(tmp) / "bent.pptx")
            self.assertEqual([], checks.run_all(saved))
            with zipfile.ZipFile(saved) as archive:
                xml = archive.read(self.SLIDE).decode()
        return page, re.findall(r"<p:cxnSp>.*?</p:cxnSp>", xml, re.S)

    @staticmethod
    def drawn(connector):
        """(where it begins, where it turns, where it ends, which end has the head, the frame) as the file says it is drawn.

        プリセットの道は枠の左上から右へ進み、右の辺で下へ曲がる。枠の中で反転し (= 左右、上下)、真ん中を軸に回る。
        """
        x, y = (int(v) for v in re.search(r'<a:off x="(-?\d+)" y="(-?\d+)"', connector).groups())
        w, h = (int(v) for v in re.search(r'<a:ext cx="(\d+)" cy="(\d+)"', connector).groups())
        turned = re.search(r'<a:xfrm[^>]*\brot="(\d+)"', connector)
        degrees = int(turned.group(1)) // 60000 if turned else 0
        points = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2)]
        if 'flipH="1"' in connector:
            points = [(-px, py) for px, py in points]
        if 'flipV="1"' in connector:
            points = [(px, -py) for px, py in points]
        cos, sin = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}[degrees]
        centre = (x + w / 2, y + h / 2)
        begin, corner, end = ((round(centre[0] + px * cos - py * sin), round(centre[1] + px * sin + py * cos))
                              for px, py in points)
        head = "end" if "<a:tailEnd" in connector else "begin" if "<a:headEnd" in connector else ""
        return begin, corner, end, head, (x, y, w, h)

    def corner(self, from_, to, across_gap, down_gap):
        spacing = {"gap_x": across_gap, "gap_y": down_gap}
        theme = theme_from({"uses": {"gapped": {"like": "read", "spacing": spacing}}}).using("gapped")
        cell = lambda n: {"id": n.lower(), "card": {"heading": n}} if n in (from_, to) else {"text": ""}
        return self.connectors([{"cells": [cell("A"), cell("B")]}, {"cells": [cell("C"), cell("D")]}],
                               [{"from": from_.lower(), "to": to.lower()}], theme)

    def test_a_line_that_leaves_sideways_is_drawn_from_its_start_to_its_end_with_the_head_at_its_end(self):
        page, (connector,) = self.corner("A", "D", 0.5, 3)
        (line,) = kinds(page, "line")
        self.assertIn('prst="bentConnector2"', connector)
        begin, corner, end, head, _frame = self.drawn(connector)
        self.assertEqual((line.start, (line.end[0], line.start[1]), line.end, "end"), (begin, corner, end, head))

    def test_a_line_that_leaves_downwards_is_drawn_from_its_end_to_its_start_with_the_head_at_its_beginning(self):
        page, (connector,) = self.corner("A", "D", 3, 0.5)
        (line,) = kinds(page, "line")
        begin, corner, end, head, _frame = self.drawn(connector)
        # the preset turns at the x of its far end, so it is drawn backwards: its turn is under the start and level with the end
        self.assertEqual((line.end, (line.start[0], line.end[1]), line.start, "begin"), (begin, corner, end, head))

    def test_the_four_corners_in_both_bends_are_each_one_connector_that_turns_where_the_line_turns(self):
        for from_, to in (("A", "D"), ("D", "A"), ("B", "C"), ("C", "B")):
            for gaps in ((0.5, 3), (3, 0.5)):
                with self.subTest(from_=from_, to=to, gaps=gaps):
                    page, (connector,) = self.corner(from_, to, *gaps)
                    (line,) = kinds(page, "line")
                    begin, corner, end, head, _frame = self.drawn(connector)
                    turn = (line.end[0], line.start[1]) if line.bend == "across" else (line.start[0], line.end[1])
                    self.assertEqual(turn, corner)
                    self.assertEqual({line.start, line.end}, {begin, end})
                    self.assertEqual(line.end, end if head == "end" else begin)

    def test_a_bent_line_stays_inside_the_box_round_its_two_ends_so_it_cannot_leave_the_page(self):
        for from_, to in (("A", "D"), ("D", "A"), ("B", "C"), ("C", "B")):
            for gaps in ((0.5, 3), (3, 0.5)):
                with self.subTest(from_=from_, to=to, gaps=gaps):
                    page, (connector,) = self.corner(from_, to, *gaps)
                    (line,) = kinds(page, "line")
                    self.assertEqual((line.rect.left, line.rect.top, line.rect.width, line.rect.height),
                                     self.drawn(connector)[4])
                    self.assertNotIn("rot=\"5400000\"", connector)
                    self.assertNotIn("rot=\"16200000\"", connector)

    def test_a_straight_line_stays_a_straight_connector(self):
        _page, (connector,) = self.connectors([{"cells": [{"id": "a", "card": {"heading": "A"}},
                                                          {"id": "b", "card": {"heading": "B"}}]}],
                                              [{"from": "a", "to": "b"}])
        self.assertIn('prst="line"', connector)
        self.assertIn("<a:tailEnd", connector)
        self.assertNotIn("<a:headEnd", connector)


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

    def test_an_unknown_id_or_a_cell_between_are_refused(self):
        row = [{"cells": [{"id": "a", "card": {"heading": "A"}}, {"card": {"heading": "M"}},
                          {"id": "b", "card": {"heading": "B"}}]}]
        with self.assertRaises(PageTypeError) as unknown:
            self.build(row, [{"from": "a", "to": "z"}])
        self.assertIn("'z'", str(unknown.exception))
        with self.assertRaises(PageTypeError) as between:
            self.build(row, [{"from": "a", "to": "b"}])
        self.assertIn("stands between", str(between.exception))
        with self.assertRaises(PageTypeError) as twice:
            self.build([{"cells": [{"id": "a", "text": "x"}, {"id": "a", "text": "y"}]}], [{"from": "a", "to": "a"}])
        self.assertIn("two cells have the id", str(twice.exception))
