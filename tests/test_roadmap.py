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
sys.path.insert(0, str(REPO / "tests"))
from support.pages import box_of, build, named  # noqa: E402

from pptx_agent_maker import checks  # noqa: E402
from pptx_agent_maker.layout import types  # noqa: E402
from pptx_agent_maker.layout.base.geometry import Rect, cm  # noqa: E402
from pptx_agent_maker.layout.parts.elements import Bar, Figure, Text  # noqa: E402
from pptx_agent_maker.layout.parts.look import Style  # noqa: E402
from pptx_agent_maker.layout.parts.page import Card, Page, PageFullError  # noqa: E402
from pptx_agent_maker.layout.base.tokens import DEFAULT, theme_from  # noqa: E402
from pptx_agent_maker.layout.types.core.read import Spec  # noqa: E402
from pptx_agent_maker.layout.types.core.registry import TYPES, PageTypeError  # noqa: E402
from pptx_agent_maker.layout.types.core.stack import card_height  # noqa: E402
from pptx_agent_maker.write import add_page, aspect, new_deck, save  # noqa: E402

DATA = REPO / "tests" / "data"
SQUARE, WIDE = "dot.png", "wide.png"      # 8 x 8, 16 x 4


def road(stages, **extra):
    return build({"type": "roadmap", "title": "A road", "stages": stages, **extra})


def stage(name, *nodes, **more):
    return {"name": name, "nodes": list(nodes) or [["Work", "what it hands on"]], **more}


FOUR = [stage("Early | 0.4"), stage("Late | 0.5"), stage("Next | 0.6"), stage("Then | 1.0", goal=True)]


def arrows(built):
    return [e for e in built.build() if isinstance(e, Bar) and e.kind == "chevron"]


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


def bare(name, **more):
    """A stage of an arrowhead alone."""
    return {"name": name, **more}


class TheWidthOfAStage(unittest.TestCase):
    """A stage may say `weight`: its share of the width, 1 when it says nothing."""

    def widths(self, stages, **extra):
        return [a.rect.width for a in arrows(road(stages, **extra))]

    def test_without_a_weight_the_stages_share_the_width_equally(self):
        plain = road(FOUR).build()
        ones = road([{**s, "weight": 1} for s in FOUR]).build()
        self.assertEqual(plain, ones)
        # 最後の矢羽根は列の幅ちょうど、ほかは列の幅に間の空きを足した幅
        widths = self.widths(FOUR)
        self.assertLessEqual(max(widths[:-1]) - min(widths[:-1]), 1)
        self.assertLessEqual(abs(widths[0] - DEFAULT.spacing.gap_m - widths[-1]), 1)

    def test_the_arrowheads_are_as_wide_as_their_weights_say(self):
        stages = [stage("One", weight=3), stage("Two", weight=2), stage("Three", weight=1, goal=True)]
        heads = arrows(road(stages))
        # 矢羽根は自分の列から次の列の頭まで伸びる (= 列の間の空きは矢羽根が持つ)。最後は列の幅
        self.assertEqual(heads[1].rect.left, heads[0].rect.right)
        self.assertEqual(heads[2].rect.left, heads[1].rect.right)
        last = heads[2].rect.width
        gap = DEFAULT.spacing.gap_m
        self.assertAlmostEqual(1.0, (heads[1].rect.width - gap) / (2 * last), delta=0.02)
        self.assertAlmostEqual(1.0, (heads[0].rect.width - gap) / (3 * last), delta=0.02)

    def test_some_stages_may_say_it_and_the_rest_take_one(self):
        heads = arrows(road([stage("One", weight=3), stage("Two"), stage("Three")]))
        rest = heads[1].rect.width - DEFAULT.spacing.gap_m
        self.assertAlmostEqual(3.0, (heads[0].rect.width - DEFAULT.spacing.gap_m) / rest, delta=0.05)
        self.assertLessEqual(abs(heads[1].rect.width - heads[2].rect.width), DEFAULT.spacing.gap_m + 2)

    def test_a_weight_may_be_a_fraction(self):
        heads = arrows(road([stage("One", weight=0.5), stage("Two"), stage("Three", weight=1.5)]))
        self.assertLess(heads[0].rect.width, heads[1].rect.width)
        self.assertGreater(heads[2].rect.width, heads[1].rect.width - DEFAULT.spacing.gap_m)

    def test_the_arrowheads_still_nest_and_the_first_and_last_edges_stay_on_the_body(self):
        built = road([stage("One", weight=1), stage("Two", weight=4), stage("Three", weight=2)])
        heads = arrows(built)
        for this, following in zip(heads, heads[1:]):
            self.assertEqual(following.rect.left, this.rect.right)
        body = Page("A road").body
        self.assertEqual(body.left, heads[0].rect.left)
        self.assertEqual(body.right, heads[-1].rect.right)

    def test_the_nodes_stand_under_the_column_of_their_own_stage(self):
        built = road([stage("One", ["A", "a"], weight=3), stage("Two", ["B", "b"], weight=1)])
        heads = arrows(built)
        self.assertEqual(heads[0].rect.left, box_of(built, "A").rect.left)
        self.assertEqual(heads[1].rect.left, box_of(built, "B").rect.left)
        self.assertGreater(box_of(built, "A").rect.width, box_of(built, "B").rect.width)

    def test_a_node_breaks_over_the_width_of_its_own_column(self):
        """⚠ 幅の違う段のノードを 1 つの段の幅で数えると、細い段は字が箱からあふれ、広い段は空きが残る。"""
        body = "a body long enough to break over several lines in a narrow column " * 2
        built = road([stage("Wide", ["Node", body], weight=3), stage("Narrow", ["Node too", body], weight=1)])
        wide, narrow = box_of(built, "Node"), box_of(built, "Node too")
        self.assertGreater(narrow.rect.height, wide.rect.height, "the narrow column breaks into more lines")
        for box, heading in ((wide, "Node"), (narrow, "Node too")):
            self.assertEqual(card_height(Page("A road"), [Card(heading, body)], box.rect.width, 1),
                             box.rect.height)

    def test_align_rows_still_lines_up_the_rows_of_stages_of_different_widths(self):
        body = "a body long enough to break over several lines in a narrow column " * 2
        built = road([stage("Wide", ["A", body], ["B", "b"], weight=3), stage("Narrow", ["C", body], ["D", "d"])],
                     align_rows=True)
        self.assertEqual(box_of(built, "B").rect.top, box_of(built, "D").rect.top)
        self.assertEqual(box_of(built, "A").rect.height, box_of(built, "C").rect.height)
        self.assertEqual(card_height(Page("A road"), [Card("C", body)], box_of(built, "C").rect.width, 1),
                         box_of(built, "C").rect.height)

    def test_a_name_breaks_over_the_width_its_arrowhead_has(self):
        text = "a stage whose name runs long enough to break over a second line"
        heads = arrows(road([stage(text, weight=1), stage("Two", weight=3)]))
        even = arrows(road([stage(text), stage("Two")]))
        self.assertGreater(heads[0].rect.height, even[0].rect.height)

    def test_a_weight_is_a_number_above_nothing(self):
        for bad in (0, -1, True, "2", None, [1]):
            with self.subTest(weight=bad):
                with self.assertRaises(PageTypeError) as raised:
                    road([stage("One"), stage("Two", weight=bad)])
                said = str(raised.exception)
                self.assertIn("roadmap: stage 2", said)
                self.assertIn("`weight` is a number above 0", said)

    def test_a_bare_stage_takes_its_width_too(self):
        heads = arrows(road([bare("One", weight=3), bare("Two"), bare("Three", goal=True)]))
        self.assertGreater(heads[0].rect.width, 2 * heads[1].rect.width)


def boxes(built):
    return [e for e in built.build() if e.kind == "box"]


class ABareRoad(unittest.TestCase):
    """A stage may leave its `nodes` out: the arrowhead stands alone, and a flow still wants its nodes."""

    def test_a_road_of_arrowheads_alone_is_a_row_of_them_and_nothing_under(self):
        built = road([bare("Early | 0.4"), bare("Late | 0.5"), bare("Then | 1.0", goal=True)])
        self.assertEqual(["Early | 0.4", "Late | 0.5", "Then | 1.0"], [a.text for a in arrows(built)])
        self.assertEqual([], boxes(built))

    def test_the_arrowheads_are_the_same_with_nodes_under_them_or_without(self):
        names = ["Early | 0.4", "Late | 0.5", "Then | 1.0"]
        alone = arrows(road([bare(name) for name in names]))
        held = arrows(road([stage(name) for name in names]))
        self.assertEqual([(a.rect, a.shape, a.size, a.fill) for a in held],
                         [(a.rect, a.shape, a.size, a.fill) for a in alone])

    def test_an_empty_list_is_the_same_as_leaving_it_out(self):
        names = ["One", "Two", "Three"]
        self.assertEqual(road([bare(name) for name in names]).build(),
                         road([bare(name, nodes=[]) for name in names]).build())

    def test_the_stages_that_hold_nodes_keep_them_under_their_own_arrowhead_and_the_rest_stand_empty(self):
        built = road([stage("One", ["A", "a"]), bare("Two"), stage("Three", ["C", "c"], ["D", "d"])])
        heads = arrows(built)
        self.assertEqual([heads[0].rect.left, heads[2].rect.left], [box_of(built, "A").rect.left,
                                                                      box_of(built, "C").rect.left])
        self.assertEqual(3, len(boxes(built)))
        for box in boxes(built):
            self.assertFalse(heads[1].rect.left < box.rect.left < heads[1].rect.right,
                             "a box stands under the arrowhead that holds nothing")
        self.assertGreater(box_of(built, "D").rect.top, box_of(built, "C").rect.bottom)

    def test_the_tallest_stage_alone_decides_how_far_down_the_nodes_reach(self):
        built = road([stage("One", ["A", "a"]), bare("Two"), stage("Three", ["C", "c"], ["D", "d"])])
        s = DEFAULT.spacing
        self.assertEqual(box_of(built, "D").rect.bottom,
                         max(b.rect.bottom for b in boxes(built)))
        self.assertEqual(arrows(built)[0].rect.bottom + s.gap_s, box_of(built, "A").rect.top)

    def test_align_rows_lines_up_the_stages_that_hold_nodes_and_lets_the_rest_be(self):
        stages = [stage("One", ["A", "a body long enough to break over several lines " * 4], ["B", "b"]),
                  bare("Two"), stage("Three", ["C", "c"], ["D", "d"])]
        built = road(stages, align_rows=True)
        self.assertEqual(box_of(built, "B").rect.top, box_of(built, "D").rect.top)
        self.assertEqual(box_of(built, "A").rect.height, box_of(built, "C").rect.height)
        self.assertEqual([], boxes(road([bare("One"), bare("Two")], align_rows=True)))

    def test_align_rows_counts_its_rows_over_every_stage_not_the_first(self):
        built = road([bare("Zero"), stage("One", ["A", "a"], ["B", "b"]), stage("Two", ["C", "c"], ["D", "d"])],
                     align_rows=True)
        self.assertEqual(box_of(built, "B").rect.top, box_of(built, "D").rect.top)

    def test_a_body_as_tall_as_the_arrowheads_holds_a_road_of_them_alone(self):
        """⚠ 矢羽根だけの道のりが要る高さは、帯の高さちょうど (= 空のノードの上の隙間は要らない)。"""
        stages = [bare("One"), bare("Two")]
        height = arrows(road(stages))[0].rect.height

        def fill(room):
            page = Page("A page")
            spec = Spec({"stages": stages}, lambda name: DATA / name, aspect)
            TYPES["roadmap"][0](page, spec, Rect(page.body.left, page.body.top, page.body.width, room))

        fill(height)
        with self.assertRaises(PageFullError):
            fill(height - 1)

    def test_it_needs_only_the_height_of_its_arrowheads(self):
        """前提: 同じ段にノードを書けば頁に収まらない (= 収まるのは、ノードを省いたから)。"""
        many = [stage(f"S{n}", *[[f"N{n}{k}", "a body " * 12] for k in range(8)]) for n in range(3)]
        with self.assertRaises(PageFullError):
            road(many)
        self.assertEqual(3, len(arrows(road([bare(s["name"]) for s in many]))))

    def test_what_an_arrowhead_may_carry_it_carries_alone(self):
        built = road([bare("One", tone="tint", icon=SQUARE), bare("Two", goal=True)])
        palette = DEFAULT.palette
        self.assertEqual(palette.tint, arrows(built)[0].fill)
        self.assertEqual(palette.accent, arrows(built)[1].fill)
        self.assertEqual(1, len([e for e in built.build() if isinstance(e, Figure)]))

    def test_it_still_says_when_an_arrowhead_has_no_name(self):
        with self.assertRaises(PageTypeError) as raised:
            road([bare("One"), {"nodes": []}])
        self.assertIn("no `name`", str(raised.exception))

    def test_a_flow_still_holds_something_in_every_stage(self):
        for nodes in ({}, {"nodes": []}):
            with self.subTest(nodes=nodes):
                with self.assertRaises(PageTypeError) as raised:
                    build({"type": "flow", "title": "A flow", "stages": [
                        {"name": "One", "nodes": [["A", "a"]]}, {"name": "Two", **nodes}]})
                self.assertIn("has no nodes", str(raised.exception))
        with self.assertRaises(PageTypeError):
            build({"type": "flow", "title": "A flow", "direction": "down", "stages": [
                {"name": "One", "nodes": [["A", "a"]]}, {"name": "Two"}]})


class ABareRoadOnAPage(unittest.TestCase):
    """In a deck that says `box_height = "page"` the nodes share the height left; arrowheads alone share nothing."""

    PAGE = theme_from({"box_height": "page"})

    def bottom(self):
        return Page("A page", self.PAGE).body.bottom

    def test_the_nodes_of_the_stages_that_hold_any_reach_the_bottom_of_the_body(self):
        for extra, last in (({}, "C"), ({"align_rows": True}, "B")):
            with self.subTest(**extra):
                built = build({"type": "roadmap", "title": "T", "stages": [
                    stage("One", ["A", "a"], ["B", "b"]), bare("Two"), stage("Three", ["C", "c"])], **extra}, self.PAGE)
                self.assertEqual(self.bottom(), box_of(built, "B").rect.bottom)
                self.assertEqual(self.bottom(), box_of(built, last).rect.bottom)

    def test_a_road_of_arrowheads_alone_stays_as_tall_as_they_are(self):
        for extra in ({}, {"align_rows": True}):
            with self.subTest(**extra):
                built = build({"type": "roadmap", "title": "T", "stages": [bare("One"), bare("Two", goal=True)],
                               **extra}, self.PAGE)
                plain = road([bare("One"), bare("Two", goal=True)])
                self.assertEqual([], boxes(built))
                self.assertEqual([a.rect.height for a in arrows(plain)], [a.rect.height for a in arrows(built)])


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
            road([stage("One"), stage("Two", ["A", "a"], {"heading": "B", "colour": "red"})])
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
        page.boxes(page.body.split_top(cm(3))[0], [Card("One", "a", Style(icon=(DATA / SQUARE, 1.0)))])
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

    def test_a_card_written_as_a_table_names_its_place_when_it_is_wrong(self):
        with self.assertRaises(PageTypeError) as raised:
            self.cards(["One", "a"], {"heading": "Two", "colour": "red"})
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
