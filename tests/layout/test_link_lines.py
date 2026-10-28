"""A line of a page written into the file: straight, bent at right angles, or hopping over the lines it crosses.

見張るのは 5 つ ― 曲がる線が、曲がり角が計算どおりの所に出る 1 つのプリセットのコネクタで書かれること (= 4 つの向き)、
プリセットで書けない線 (= 曲がり角 3 つ以上・縦に出て縦に入る線) と跳び越す線が図形の線で書かれ、点と半円が
合うこと、辺の真ん中から出入りする曲がる線だけが箱の接続点に付くこと、書いた deck が検査を通ること、
プリセットの上限 (`PRESET_BENDS`) を上げれば曲がり角 4 つまでプリセットで書けること。
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))
from support.connectors import connectors, drawn, free_forms  # noqa: E402
from support.pages import box_of, build  # noqa: E402

from pptx_agent_maker import DEFAULT, checks  # noqa: E402
from pptx_agent_maker.layout.parts.page import Page  # noqa: E402
from pptx_agent_maker.layout.tokens import theme_from  # noqa: E402
from pptx_agent_maker.write import add_page, new_deck, save  # noqa: E402
from pptx_agent_maker.write import lines as written  # noqa: E402

CM = 360000


def at(*points):
    """Points given in centimetres, as EMU."""
    return [(round(x * CM), round(y * CM)) for x, y in points]


def slide_of(page, theme=DEFAULT):
    """The XML of the one slide a page makes, once saved (= and read back through the checks, which must find nothing)."""
    deck = new_deck(theme)
    add_page(deck, page.build(), theme)
    with tempfile.TemporaryDirectory() as tmp:
        saved = save(deck, Path(tmp) / "lines.pptx")
        found = checks.run_all(saved)
        with zipfile.ZipFile(saved) as archive:
            xml = archive.read("ppt/slides/slide1.xml").decode()
    assert found == [], found
    return xml


def line_page(*lines, hops=(), hop=0):
    """A page of nothing but the lines given, each a list of points: the first and the last are its ends."""
    page = Page("A page", DEFAULT)
    page.drew_a_diagram()
    for points in lines:
        page.line(points[0], points[-1], arrow=True, corners=points[1:-1], hops=hops, hop=hop)
    return page


def path_points(shape):
    """The points of a free-form shape's path, on the slide (= the frame's corner added to each)."""
    x, y = (int(v) for v in re.search(r'<a:off x="(-?\d+)" y="(-?\d+)"', shape).groups())
    return [(x + int(px), y + int(py)) for px, py in re.findall(r'<a:pt x="(-?\d+)" y="(-?\d+)"/>', shape)]


class ABentLineIsOneConnectorWhenAPresetDrawsIt(unittest.TestCase):
    TWICE = {
        "right then down then right": at((2, 3), (4, 3), (4, 5), (7, 5)),
        "left then down then left": at((14, 3), (11, 3), (11, 6), (8, 6)),
        "right then up then right": at((2, 9), (3, 9), (3, 7.5), (6, 7.5)),
        "left then up then left": at((14, 9), (12, 9), (12, 8), (9, 8)),
        "right then down": at((2, 3), (6, 3), (6, 5)),
        "down then right": at((2, 3), (2, 5), (6, 5)),
    }

    def test_each_direction_is_one_connector_whose_corners_are_where_the_line_says(self):
        for name, points in self.TWICE.items():
            with self.subTest(name):
                (connector,) = connectors(slide_of(line_page(points)))
                found, head, _frame = drawn(connector)
                self.assertEqual({tuple(points), tuple(points[::-1])}.intersection({tuple(found)}), {tuple(found)})
                self.assertEqual(points[-1], found[-1] if head == "end" else found[0])

    def test_two_bends_are_the_preset_with_three_runs_and_one_adjustment(self):
        (connector,) = connectors(slide_of(line_page(self.TWICE["right then down then right"])))
        self.assertIn('prst="bentConnector3"', connector)
        self.assertEqual(1, connector.count("<a:gd "))
        self.assertIn(f'fmla="val {round((4 - 2) / (7 - 2) * 100000)}"', connector)

    def test_a_line_that_goes_the_other_way_is_the_same_connector_turned_about_never_mirrored_sideways_or_turned_a_quarter(self):
        for points in self.TWICE.values():
            (connector,) = connectors(slide_of(line_page(points)))
            self.assertNotIn("flipH", connector)
            self.assertNotIn('rot="5400000"', connector)
            self.assertNotIn('rot="16200000"', connector)

    def test_the_head_is_at_the_end_of_the_line_drawn_from_its_end_when_the_preset_cannot_start_where_the_line_does(self):
        (connector,) = connectors(slide_of(line_page(self.TWICE["down then right"])))
        self.assertIn("<a:headEnd", connector)
        self.assertNotIn("<a:tailEnd", connector)
        (connector,) = connectors(slide_of(line_page(self.TWICE["right then down"])))
        self.assertIn("<a:tailEnd", connector)

    def test_the_theme_line_style_is_not_inherited(self):
        xml = slide_of(line_page(self.TWICE["right then down then right"]))
        self.assertNotIn("<p:style>", xml)


class TheLineRemembersWhereItGoes(unittest.TestCase):
    def test_a_page_keeps_every_point_of_a_line_as_its_start_and_the_way_from_it(self):
        points = at((2, 3), (2, 5), (9, 5), (9, 8))
        (line,) = [e for e in line_page(points).build() if e.kind == "line"]
        self.assertEqual(points, line.points())
        self.assertEqual(points[0], line.start)
        self.assertEqual(points[-1], line.end)

    def test_the_box_round_a_line_holds_its_corners_even_when_they_lie_outside_the_box_round_its_ends(self):
        points = at((2, 3), (2, 9), (12, 9), (12, 4))
        (line,) = [e for e in line_page(points).build() if e.kind == "line"]
        self.assertEqual((2 * CM, 3 * CM, 10 * CM, 6 * CM), (line.rect.left, line.rect.top, line.rect.width, line.rect.height))

    def test_the_hops_go_where_the_line_goes_when_the_page_is_moved_down(self):
        """What is placed is moved with `Line.start`: the corners and the hops are kept as distances from it."""
        page = Page("A page", DEFAULT)
        page.drew_a_diagram()
        page.line(*at((2, 3)), *at((9, 3)), arrow=True, hops=at((5, 3)), hop=1000)
        (line,) = [e for e in page.build() if e.kind == "line"]
        self.assertEqual([(5 * CM, 3 * CM)], line.hop_points())
        self.assertEqual((3 * CM, 0), line.hops[0])


class ALineThatNoPresetDrawsIsAFreeForm(unittest.TestCase):
    def test_down_then_across_then_down_is_a_free_form_through_its_corners(self):
        points = at((2, 3), (2, 5), (9, 5), (9, 8))
        xml = slide_of(line_page(points))
        self.assertEqual([], connectors(xml))
        (shape,) = free_forms(xml)
        self.assertEqual(points, path_points(shape))
        self.assertIn("<a:tailEnd", shape)

    def test_three_and_four_bends_are_free_forms_while_the_limit_is_two(self):
        for points in (at((2, 3), (4, 3), (4, 5), (7, 5), (7, 8)), at((2, 3), (4, 3), (4, 5), (7, 5), (7, 8), (9, 8))):
            with self.subTest(bends=len(points) - 2):
                xml = slide_of(line_page(points))
                self.assertEqual([], connectors(xml))
                self.assertEqual(points, path_points(free_forms(xml)[0]))

    def test_a_free_form_is_a_shape_not_a_connector_because_a_viewer_redraws_a_connector_its_own_way(self):
        xml = slide_of(line_page(at((2, 3), (2, 5), (9, 5), (9, 8))))
        self.assertNotIn("<p:cxnSp>", xml)

    def test_a_free_form_has_no_fill_and_no_theme_style(self):
        shape = free_forms(slide_of(line_page(at((2, 3), (2, 5), (9, 5), (9, 8)))))[0]
        self.assertIn("<a:noFill/>", shape)
        self.assertNotIn("<p:style>", shape)

    def test_with_the_limit_raised_three_and_four_bends_and_down_across_down_are_presets_that_draw_where_the_line_goes(self):
        cases = {3: at((2, 3), (4, 3), (4, 5), (7, 5), (7, 8)), 4: at((2, 3), (4, 3), (4, 5), (7, 5), (7, 8), (9, 8)),
                 2: at((2, 3), (2, 5), (9, 5), (9, 8))}
        cases["2 up"] = cases[2][::-1]
        for name, points in cases.items():
            with self.subTest(name), mock.patch.object(written, "PRESET_BENDS", 4):
                (connector,) = connectors(slide_of(line_page(points)))
                found, _head, _frame = drawn(connector)
                found = [point for number, point in enumerate(found) if number == 0 or point != found[number - 1]]
                found = found if points[0] == found[0] else found[::-1]
                self.assertEqual(len(points), len(found))
                # 調整値は 10 万分率で持つので、曲がり角は枠の 10 万分の 1 (= 数十 EMU) までのずれで読み戻る
                for want, got in zip(points, found):
                    self.assertLessEqual(max(abs(want[0] - got[0]), abs(want[1] - got[1])), 60, (want, got))
                self.assertIn("bentConnector", connector)


class ALineThatHopsIsAFreeFormWithHalfCircles(unittest.TestCase):
    def test_a_sideways_run_has_a_half_circle_above_the_hop_and_a_downward_run_one_to_the_right(self):
        points = at((2, 6), (10, 6), (10, 12))
        hops = at((5, 6), (10, 9))
        radius = round(0.15 * CM)
        page = Page("A page", DEFAULT)
        page.drew_a_diagram()
        page.line(points[0], points[-1], arrow=True, corners=points[1:-1], hops=hops, hop=radius)
        (shape,) = free_forms(slide_of(page))
        self.assertEqual(2, shape.count("<a:arcTo"))
        self.assertEqual(2, len(re.findall(rf'<a:arcTo wR="{radius}" hR="{radius}"', shape)))
        self.assertIn('stAng="10800000" swAng="10800000"', shape, "left to right over the hop: from the left of the circle through the top")
        self.assertIn('stAng="16200000" swAng="10800000"', shape, "downwards over the hop: from the top of the circle through the right")
        found = path_points(shape)
        self.assertIn((hops[0][0] - radius, 6 * CM), found)
        self.assertIn((10 * CM, hops[1][1] - radius), found)
        self.assertEqual(points[-1], found[-1])

    def test_a_line_that_goes_up_hops_to_the_right_too_from_the_bottom_of_the_circle(self):
        radius = round(0.15 * CM)
        page = Page("A page", DEFAULT)
        page.drew_a_diagram()
        page.line(at((6, 10))[0], at((6, 2))[0], arrow=True, hops=at((6, 5)), hop=radius)
        (shape,) = free_forms(slide_of(page))
        self.assertIn('stAng="5400000" swAng="-10800000"', shape)

    def test_a_line_drawn_the_other_way_hops_the_other_way_round(self):
        radius = round(0.15 * CM)
        page = Page("A page", DEFAULT)
        page.drew_a_diagram()
        page.line(at((10, 6))[0], at((2, 6))[0], arrow=True, hops=at((5, 6)), hop=radius)
        (shape,) = free_forms(slide_of(page))
        self.assertIn('stAng="0" swAng="-10800000"', shape)

    def test_the_frame_holds_the_half_circle_too(self):
        radius = round(0.15 * CM)
        page = Page("A page", DEFAULT)
        page.drew_a_diagram()
        page.line(at((2, 6))[0], at((10, 6))[0], arrow=True, hops=at((5, 6)), hop=radius)
        (shape,) = free_forms(slide_of(page))
        self.assertIn(f'<a:off x="{2 * CM}" y="{6 * CM - radius}"/>', shape)


class ALineIsAttachedToTheBoxesItJoinsOnlyWhereItMeetsTheMiddleOfAnEdge(unittest.TestCase):
    def page(self, links, cells, columns=(1, 1, 1), rows=(1, 1)):
        return build({"type": "compose", "title": "A page", "grid": {"columns": list(columns), "rows": list(rows)},
                      "cells": cells, "links": links})

    def shapes_by_name(self, xml):
        return {name: int(ident) for ident, name in re.findall(r'<p:cNvPr id="(\d+)" name="([^"]*)"', xml)}

    @staticmethod
    def cell(heading, at, **extra):
        return {"card": {"heading": heading, "body": "words"}, "at": list(at), **extra}

    def test_a_bent_line_that_leaves_and_enters_by_the_middle_of_an_edge_is_attached_to_both_boxes(self):
        page = self.page([{"from": "a", "to": "b"}], [self.cell("A", (1, 1), id="a"), self.cell("B", (2, 3), id="b")])
        (connector,) = connectors(slide_of(page))
        begin, end = (re.search(rf'<a:{tag} id="(\d+)" idx="(\d)"/>', connector) for tag in ("stCxn", "endCxn"))
        self.assertIsNotNone(begin)
        self.assertIsNotNone(end)
        self.assertNotEqual(begin.group(1), end.group(1))

    def attached(self, connector):
        """(shape id, site) of the begin and of the end of a connector, as written."""
        return tuple((int(found.group(1)), int(found.group(2))) if found else None
                     for found in (re.search(rf'<a:{tag} id="(\d+)" idx="(\d)"/>', connector) for tag in ("stCxn", "endCxn")))

    def shape_at(self, xml, rect):
        """The id of the shape of the slide that stands exactly on `rect`."""
        for ident, left, top, width, height in re.findall(
                r'<p:cNvPr id="(\d+)" name="[^"]*"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="(-?\d+)" y="(-?\d+)"/>'
                r'<a:ext cx="(\d+)" cy="(\d+)"/>', xml):
            if (int(left), int(top), int(width), int(height)) == (rect.left, rect.top, rect.width, rect.height):
                return int(ident)
        raise AssertionError(f"no shape on {rect}")

    def test_each_end_is_attached_to_the_shape_of_its_box_at_the_site_of_the_side_it_uses(self):
        """A rectangle's connection sites run top, left, bottom, right (= 0 to 3): the line leaves A by its right edge (= 3) and goes into B by its top (= 0)."""
        page = self.page([{"from": "a", "to": "b"}], [self.cell("A", (1, 1), id="a"), self.cell("B", (2, 2), id="b")], columns=(1, 1))
        xml = slide_of(page)
        (connector,) = connectors(xml)
        self.assertEqual(((self.shape_at(xml, box_of(page, "A").rect), 3), (self.shape_at(xml, box_of(page, "B").rect), 0)),
                         self.attached(connector))

    def test_a_connector_the_preset_can_only_draw_backwards_has_the_attachments_of_its_ends_swapped_with_it(self):
        """A line that leaves A by its lower edge and goes into B by its left edge is drawn from B, so B is the begin of the connector."""
        cells = [self.cell("A", (1, 1), id="a"), self.cell("B", (2, 2), id="b")]
        theme = theme_from({"uses": {"tall": {"like": "read", "spacing": {"gap_x": 3.0, "gap_y": 0.5}}}}).using("tall")
        page = build({"type": "compose", "title": "A page", "grid": {"columns": [1, 1], "rows": [1, 1]}, "cells": cells,
                      "links": [{"from": "a", "to": "b"}]}, theme)
        xml = slide_of(page, theme)
        (connector,) = connectors(xml)
        self.assertIn("<a:headEnd", connector)
        self.assertEqual(((self.shape_at(xml, box_of(page, "B").rect), 1), (self.shape_at(xml, box_of(page, "A").rect), 2)),
                         self.attached(connector))

    def test_a_line_that_leaves_by_a_place_other_than_the_middle_is_not_attached_there(self):
        """X spans two rows and S faces only its lower one: the straight line stands below the middle of X's right edge, and the line to U2 branches off it there."""
        cells = [self.cell("X", (2, 1), span=[2, 1], id="x"), self.cell("S", (3, 4), id="s"), self.cell("U1", (1, 2), id="u1"),
                 self.cell("U2", (1, 3), id="u2")]
        page = self.page([{"from": "x", "to": "s"}, {"from": "x", "to": "u1"}, {"from": "x", "to": "u2"}], cells,
                         columns=(1, 1, 1, 1), rows=(1, 1, 1))
        _across, to_u1, to_u2 = [e for e in page.build() if e.kind == "line"]
        x = box_of(page, "X").rect
        self.assertNotEqual(x.top + x.height // 2, to_u2.start[1], "the branch leaves where the straight line does")
        self.assertIsNone(to_u2.begins_on)
        self.assertEqual(x.left + x.width // 2, to_u1.start[0], "the line to U1 leaves by the middle of the top edge")
        self.assertIsNotNone(to_u1.begins_on)

    def test_a_straight_line_is_not_attached(self):
        page = self.page([{"from": "a", "to": "b"}], [self.cell("A", (1, 1), id="a"), self.cell("B", (1, 3), id="b")])
        (connector,) = connectors(slide_of(page))
        self.assertNotIn("Cxn id=", connector)

    def test_a_free_form_is_not_attached(self):
        cells = [self.cell("Data", (1, 7), id="data"), self.cell("Utsu", (2, 7), span=[2, 1], id="utsu"),
                 self.cell("Sdk", (3, 3), span=[2, 1], id="sdk"), self.cell("Hub", (1, 4)), self.cell("Lsl", (1, 5), span=[1, 2])]
        page = self.page([{"from": "data", "to": "sdk"}], cells, columns=(1.1, 1.3, 1.7, 1.8, 1.6, 2.2, 2.2), rows=(1.15, 1.15, 0.56, 1.14))
        xml = slide_of(page)
        self.assertNotIn("Cxn id=", xml)


if __name__ == "__main__":
    unittest.main()


class ADottedLineIsWrittenDotted(unittest.TestCase):
    """構想の段の流れ (= 線の `tentative`) は、真っすぐな線も曲がる線も跳び越す線も、線の書式の破線で書く。"""

    def test_every_kind_of_line_written_dashed_carries_the_dash_before_its_head(self) -> None:
        cm = 360000
        for corners, hops in (((), ()), (((5 * cm, 3 * cm),), ()), ((), ((4 * cm, 3 * cm),))):
            with self.subTest(corners=corners, hops=hops):
                page = Page("A page", DEFAULT)
                page.drew_a_diagram()
                page.line((3 * cm, 3 * cm), (5 * cm, 6 * cm) if corners else (8 * cm, 3 * cm), arrow=True,
                          corners=corners, hops=hops, hop=cm // 10 if hops else 0, dashed=True)
                xml = slide_of(page)
                self.assertRegex(xml, r'<a:prstDash val="dash"/>.*<a:tailEnd', "the dash comes before the head")

    def test_a_line_not_written_dashed_carries_no_dash(self) -> None:
        self.assertNotIn("prstDash", slide_of(line_page([(360000, 360000), (3 * 360000, 360000)])))
