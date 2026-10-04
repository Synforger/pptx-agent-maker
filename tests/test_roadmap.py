"""The roadmap: stages to a goal as arrowheads, and the icon a box may carry.

見張るのは 3 つ ― 矢羽根が段の順に噛み合って並ぶこと、到達点が最後の段にだけ立つこと、
アイコンが縦横比を保ったまま箱の左上に収まり、頁の図解には数えられないこと。
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from pptx_agent_maker import checks  # noqa: E402
from pptx_agent_maker.layout import types  # noqa: E402
from pptx_agent_maker.layout.base.geometry import cm  # noqa: E402
from pptx_agent_maker.layout.parts.elements import Bar, Figure, Text  # noqa: E402
from pptx_agent_maker.layout.parts.page import Card, Page, PageFullError  # noqa: E402
from pptx_agent_maker.layout.base.tokens import DEFAULT  # noqa: E402
from pptx_agent_maker.layout.types.core.registry import PageTypeError  # noqa: E402
from pptx_agent_maker.write import add_page, aspect, new_deck, save  # noqa: E402

DATA = REPO / "tests" / "data"
SQUARE, WIDE = "dot.png", "wide.png"      # 8 x 8, 16 x 4


def build(spec):
    return types.build(spec, lambda name: DATA / name, aspect)


def road(stages, **extra):
    return build({"type": "roadmap", "title": "A road", "stages": stages, **extra})


def stage(name, *nodes, **more):
    return {"name": name, "nodes": list(nodes) or [["Work", "what it hands on"]], **more}


FOUR = [stage("Early | 0.4"), stage("Late | 0.5"), stage("Next | 0.6"), stage("Then | 1.0", goal=True)]


def arrows(built):
    return [e for e in built.build() if isinstance(e, Bar) and e.kind == "chevron"]


def named(built, text):
    return next(e for e in built.build() if getattr(e, "text", None) == text)


def box_of(built, heading):
    head = named(built, heading).rect
    return next(e for e in built.build() if e.kind == "box" and e.rect.contains(head))


class TheArrowheads(unittest.TestCase):
    """One arrowhead per stage, in order, each pointing into the next."""

    def test_one_per_stage_in_order_with_the_name_inside(self):
        built = road(FOUR)
        self.assertEqual([s["name"] for s in FOUR], [a.text for a in arrows(built)])

    def test_the_first_is_flat_on_the_left_and_the_rest_are_notched(self):
        self.assertEqual(["home", "chevron", "chevron", "chevron"], [a.shape for a in arrows(road(FOUR))])

    def test_each_starts_over_its_own_nodes_and_reaches_the_next(self):
        built = road([stage("One", ["A", "a"]), stage("Two", ["B", "b"]), stage("Three", ["C", "c"])])
        heads = arrows(built)
        for arrow, heading in zip(heads, "ABC"):
            self.assertEqual(box_of(built, heading).rect.left, arrow.rect.left)
        for this, following in zip(heads, heads[1:]):
            self.assertEqual(following.rect.left, this.rect.right)
        self.assertEqual(box_of(built, "C").rect.right, heads[-1].rect.right)

    def test_they_stand_in_one_row_of_one_height(self):
        heads = arrows(road(FOUR))
        self.assertEqual(1, len({(a.rect.top, a.rect.height) for a in heads}))

    def test_the_nodes_hang_under_them(self):
        built = road([stage("One", ["A", "a"], ["B", "b"]), stage("Two", ["C", "c"])])
        self.assertGreater(box_of(built, "A").rect.top, arrows(built)[0].rect.bottom)
        self.assertGreater(box_of(built, "B").rect.top, box_of(built, "A").rect.bottom)

    def test_a_long_name_breaks_and_every_arrowhead_grows_to_it(self):
        text = "a stage whose name runs long enough to break over a second line"
        built = road([stage(text), stage("Two")])
        long = arrows(built)[0]
        s = DEFAULT.spacing
        # 左の平らな矢羽根の文字の枠は、先の深さの半分だけ右が狭い (= プリセットが決める)
        room = long.rect.width - s.chevron_point // 2 - 2 * s.bar_pad_x
        self.assertGreater(DEFAULT.wraps(text, room, long.size, bold=True), 1, "the name does not break")
        self.assertGreaterEqual(long.rect.height,
                                DEFAULT.wrapped_height(text, room, long.size, bold=True) + 2 * s.bar_pad_y)
        self.assertEqual(long.rect.height, arrows(built)[1].rect.height)

    def test_no_arrow_stands_between_them(self):
        """向きは矢羽根が示す (= flow の「→」は要らない)。"""
        self.assertNotIn("marker", {e.kind for e in road(FOUR).build()})

    def test_the_stages_are_light_and_take_an_edge(self):
        palette = DEFAULT.palette
        for arrow in arrows(road(FOUR))[:-1]:
            self.assertEqual((palette.band, palette.ink, palette.edge(palette.band), DEFAULT.type.stage),
                             (arrow.fill, arrow.colour, arrow.outline, arrow.size))


class TheGoal(unittest.TestCase):
    """The last stage may be the goal: a dark ground, its name a size larger."""

    def test_the_goal_is_dark_and_its_name_larger(self):
        palette = DEFAULT.palette
        goal = arrows(road(FOUR))[-1]
        self.assertEqual((palette.accent, palette.paper, ""), (goal.fill, goal.colour, goal.outline))
        self.assertGreater(goal.size, DEFAULT.type.stage)
        self.assertEqual(DEFAULT.type.heading, goal.size)

    def test_without_it_the_last_stage_is_like_the_others(self):
        heads = arrows(road([stage("One"), stage("Two")]))
        self.assertEqual(heads[0].fill, heads[-1].fill)
        self.assertEqual(heads[0].size, heads[-1].size)

    def test_only_the_last_stage_can_be_it(self):
        with self.assertRaises(PageTypeError) as raised:
            road([stage("One", goal=True), stage("Two")])
        self.assertIn("stage 1", str(raised.exception))
        self.assertIn("only the last stage", str(raised.exception))

    def test_it_is_true_or_false(self):
        with self.assertRaises(PageTypeError) as raised:
            road([stage("One"), stage("Two", goal="yes")])
        self.assertIn("true or false", str(raised.exception))


class WhatARoadRefuses(unittest.TestCase):

    def refused(self, stages, *said, **extra):
        with self.assertRaises(PageTypeError) as raised:
            road(stages, **extra)
        for word in said:
            self.assertIn(word, str(raised.exception))

    def test_one_stage_is_not_a_road(self):
        self.refused([stage("Only")], "at least two stages")

    def test_a_stage_says_when_it_is(self):
        self.refused([stage("One"), {"nodes": [["A", "a"]]}], "stage 2", "no `name`")

    def test_a_stage_holds_something(self):
        self.refused([stage("One"), {"name": "Two", "nodes": []}], "has no nodes")

    def test_a_key_nobody_reads(self):
        self.refused([stage("One"), stage("Two", settled="x")], "stage 2", "does not take settled")

    def test_a_stage_is_a_table(self):
        self.refused([stage("One"), "Two"], "stage 2", "write it as a table")

    def test_align_rows_is_true_or_false(self):
        self.refused([stage("One"), stage("Two")], "`align_rows` is true or false", align_rows="yes")

    def test_what_does_not_fit_stops_the_page(self):
        many = [stage(f"S{n}", *[[f"N{n}{k}", "a body " * 12] for k in range(8)]) for n in range(3)]
        with self.assertRaises(PageFullError) as raised:
            road(many)
        self.assertIn("roadmap", str(raised.exception))


class ItsNodes(unittest.TestCase):
    """The nodes are written as a flow's are, and stack the same way."""

    def test_a_pair_or_a_table_with_a_tone(self):
        built = road([stage("One", ["Plain", "a"], {"heading": "Marked", "tone": "bad"}), stage("Two")])
        self.assertEqual(DEFAULT.palette.box, box_of(built, "Plain").colour)
        self.assertEqual(DEFAULT.palette.bad, box_of(built, "Marked").colour)

    def test_align_rows_lines_up_the_same_row_across_stages(self):
        stages = [stage("One", ["A", "a body long enough to break over several lines " * 4], ["B", "b"]),
                  stage("Two", ["C", "c"], ["D", "d"])]
        loose = road(stages)
        # 前提: 揃えなければ 2 行目はずれる (= ずれないなら揃えた効き目を見られない)
        self.assertNotEqual(box_of(loose, "B").rect.top, box_of(loose, "D").rect.top)
        built = road(stages, align_rows=True)
        self.assertEqual(box_of(built, "B").rect.top, box_of(built, "D").rect.top)
        self.assertEqual(box_of(built, "A").rect.height, box_of(built, "C").rect.height)

    def test_a_bad_node_names_its_stage_and_place(self):
        with self.assertRaises(PageTypeError) as raised:
            road([stage("One"), stage("Two", ["A", "a"], {"body": "no heading"})])
        self.assertIn("roadmap: stage 2, node 2", str(raised.exception))


class AnIcon(unittest.TestCase):
    """A box may carry one picture, top left, its words beside it."""

    def cards(self, *cards):
        return build({"type": "cards", "title": "Cards", "cards": list(cards)})

    def test_it_sits_top_left_inside_its_box_at_its_own_proportions(self):
        built = self.cards({"heading": "One", "body": "a", "icon": WIDE})
        icon = next(e for e in built.build() if isinstance(e, Figure))
        box = box_of(built, "One").rect
        s = DEFAULT.spacing
        self.assertEqual("icon", icon.kind)
        self.assertEqual((box.left + s.pad, s.icon), (icon.rect.left, icon.rect.width))
        self.assertAlmostEqual(4.0, icon.rect.width / icon.rect.height, delta=0.01)
        self.assertGreaterEqual(icon.rect.top, box.top + s.pad)
        self.assertLessEqual(icon.rect.bottom, box.top + s.pad + s.icon)

    def test_the_words_stand_to_its_right(self):
        built = self.cards({"heading": "One", "body": "the body", "icon": SQUARE})
        s = DEFAULT.spacing
        icon = next(e for e in built.build() if isinstance(e, Figure)).rect
        for text in ("One", "the body"):
            self.assertEqual(icon.left + s.icon + s.gap_s, named(built, text).rect.left)

    def test_a_box_with_one_is_never_shorter_than_it(self):
        built = self.cards({"heading": "A", "icon": SQUARE}, ["B", ""])
        s = DEFAULT.spacing
        self.assertGreaterEqual(box_of(built, "A").rect.height, s.icon + 2 * s.pad)

    def test_words_beside_it_have_less_room_and_may_take_more_lines(self):
        others = [["Two", "b"], ["Three", "c"]]
        s, size = DEFAULT.spacing, DEFAULT.type.body
        width = box_of(self.cards(["One", "a"], *others), "One").rect.width
        room = width - 2 * s.pad - 2 * s.text_inset
        # アイコンのぶん狭い幅で 1 行多く折れる本文を、語を 1 つずつ足して探す (= 折れないなら比べる意味が無い)
        body = "word"
        while DEFAULT.wraps(body, room - s.icon - s.gap_s, size) == DEFAULT.wraps(body, room, size):
            body += " word"
        plain = box_of(self.cards({"heading": "One", "body": body}, *others), "One").rect
        iconic = box_of(self.cards({"heading": "One", "body": body, "icon": SQUARE}, *others), "One").rect
        self.assertGreater(iconic.height, plain.height)

    def test_a_box_without_one_is_as_before(self):
        self.assertEqual(self.cards(["One", "a"]).build(), self.cards({"heading": "One", "body": "a"}).build())

    def test_it_is_not_the_pages_figure(self):
        """アイコンだけで、図の要る頁を通さない。"""
        page = Page("Icons only")
        page.boxes(page.body.split_top(cm(3))[0], [Card("One", "a", icon=(DATA / SQUARE, 1.0))])
        with self.assertRaises(ValueError):
            page.build()

    def test_a_flow_node_and_a_roadmap_node_carry_one_too(self):
        flow = build({"type": "flow", "title": "F", "stages": [
            {"name": "One", "nodes": [{"heading": "Node", "icon": SQUARE}]}, {"name": "Two", "nodes": [["B", ""]]}]})
        roadmap = road([stage("One", {"heading": "Node", "icon": SQUARE}), stage("Two")])
        for built in (flow, roadmap):
            icon = next(e for e in built.build() if isinstance(e, Figure))
            self.assertTrue(box_of(built, "Node").rect.contains(icon.rect))

    def test_it_is_read_from_the_assets(self):
        asked = []

        def asset(name):
            asked.append(name)
            return DATA / name

        types.build({"type": "cards", "title": "C", "cards": [{"heading": "One", "icon": SQUARE}]}, asset, aspect)
        self.assertEqual([SQUARE], asked)

    def test_an_svg_is_refused_and_told_to_be_a_png(self):
        with self.assertRaises(PageTypeError) as raised:
            self.cards(["One", "a"], {"heading": "Two", "icon": "device.svg"})
        said = str(raised.exception)
        for word in ("cards: card 2", "device.svg", "PNG"):
            self.assertIn(word, said)

    def test_a_card_may_now_be_a_table_with_a_tone(self):
        built = self.cards({"heading": "One", "body": "a", "tone": "tint"})
        self.assertEqual(DEFAULT.palette.tint, box_of(built, "One").colour)

    def test_a_card_written_as_a_table_says_its_heading(self):
        with self.assertRaises(PageTypeError) as raised:
            self.cards(["One", "a"], {"body": "b"})
        self.assertIn("cards: card 2", str(raised.exception))


class OnceBaked(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        built = road([stage("Early | 0.4", {"heading": "Core", "body": "a", "icon": WIDE}), stage("Late | 0.5"),
                      stage("Then | 1.0", goal=True)],
                     cards=[{"heading": "Card", "body": "b", "icon": SQUARE}])
        deck = new_deck()
        add_page(deck, built.build())
        cls.deck = save(deck, Path(cls.tmp.name) / "road.pptx")
        cls.heads = arrows(built)
        with zipfile.ZipFile(cls.deck) as archive:
            cls.xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_arrowheads_are_one_home_plate_then_chevrons(self):
        self.assertEqual(["homePlate", "chevron", "chevron"],
                         re.findall(r'<a:prstGeom prst="(homePlate|chevron)"', self.xml))

    def test_the_point_is_as_deep_as_the_token_says(self):
        """深さを既定に任せると、段の高さで尖りが変わり、次の段の切り欠きと噛み合わない。"""
        wanted = round(DEFAULT.spacing.chevron_point / self.heads[0].rect.height * 100000)
        found = [int(v) for v in re.findall(r'<a:gd name="adj" fmla="val (\d+)"/>', self.xml)]
        self.assertEqual(3, len(found))
        for value in found:
            self.assertAlmostEqual(wanted, value, delta=1)

    def test_a_name_and_its_arrowhead_are_one_shape(self):
        shape = next(s for s in re.findall(r"<p:sp>.*?</p:sp>", self.xml, re.S) if ">Early | 0.4<" in s)
        self.assertIn('prst="homePlate"', shape)

    def test_the_icons_are_pictures_without_their_file_names(self):
        pictures = re.findall(r"<p:pic>.*?</p:pic>", self.xml, re.S)
        self.assertEqual(2, len(pictures))
        for picture in pictures:
            self.assertNotIn("descr=", picture)

    def test_the_checks_find_nothing(self):
        self.assertEqual([], checks.run_all(self.deck))


if __name__ == "__main__":
    unittest.main()
