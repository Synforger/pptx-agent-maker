"""Three looks a project picks for its pages: how tall the boxes stand, how a card is painted, how the bands are.

どれも資料全体の見た目なので、決めるのは案件の `[theme]` の 1 か所 (= 頁ごとに書ける口にすると、
頁によって見た目の違う資料ができる)。**書かなければ今までの見た目のまま** ― 既定の頁は 1 EMU も動かない。

* `box_height = "page"` ― 箱は字の分の高さに、本体が持つ残りの高さの等しい取り分を足して、頁の高さを使い切る
* `card_look = "outlined"` ― 色を運ぶカードは、地をほぼ紙の色にして、色は枠と見出しの字が持つ
* `band_look = "outlined"` ― 条件の帯は差し色の、結論の帯は灰の、枠と地と太字を持つ
"""

from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))
from support.pages import box_of, build, named  # noqa: E402

from pptx_agent_maker import DEFAULT, Page, checks  # noqa: E402
from pptx_agent_maker.layout.base.tokens import ThemeError, theme_from  # noqa: E402
from pptx_agent_maker.layout.parts.page import PageFullError  # noqa: E402
from pptx_agent_maker.write import add_page, new_deck, save  # noqa: E402

PAGE = theme_from({"box_height": "page"})
OUTLINED = theme_from({"card_look": "outlined"})
BANDED = theme_from({"band_look": "outlined"})
P = DEFAULT.palette
GAP_M = DEFAULT.spacing.gap_m
GAP_S = DEFAULT.spacing.gap_s


def row(*cells, **more):
    return {"cells": list(cells), **more}


def card(heading, body="", **more):
    return {"card": {"heading": heading, "body": body, **more}}


def compose(rows, theme=DEFAULT, **extra):
    return build({"type": "compose", "title": "A page", "rows": rows, **extra}, theme)


def body_of(theme=DEFAULT, **extra):
    """What a page leaves for its body, bands and footer taken."""
    return Page("A page", theme, **extra).body


def of_kind(built, kind):
    return [e for e in built.build() if e.kind == kind]


class WhereTheProjectSaysIt(unittest.TestCase):
    def test_left_unsaid_every_look_is_the_one_there_always_was(self) -> None:
        self.assertEqual(("text", "filled", "plain"), (DEFAULT.box_height, DEFAULT.card_look, DEFAULT.band_look))
        for settings in (None, {}, {"box_height": "text", "card_look": "filled", "band_look": "plain"}):
            with self.subTest(settings=settings):
                self.assertEqual(DEFAULT.box_height, theme_from(settings).box_height)
                self.assertEqual(DEFAULT.card_look, theme_from(settings).card_look)
                self.assertEqual(DEFAULT.band_look, theme_from(settings).band_look)

    def test_a_name_nobody_knows_is_refused_with_the_key_it_was_written_under(self) -> None:
        for key in ("box_height", "card_look", "band_look"):
            for value in ("wide", "", 1, True, None):
                with self.subTest(key=key, value=value), self.assertRaises(ThemeError) as refused:
                    theme_from({key: value})
                self.assertIn(f"theme.{key}", str(refused.exception))

    def test_a_name_of_another_look_is_not_taken_for_this_one(self) -> None:
        with self.assertRaises(ThemeError):
            theme_from({"card_look": "page"})
        with self.assertRaises(ThemeError):
            theme_from({"band_look": "filled"})

    def test_the_sizes_of_another_use_keep_the_looks(self) -> None:
        theme = theme_from({"box_height": "page", "card_look": "outlined", "band_look": "outlined"}).using("present")
        self.assertEqual(("page", "outlined", "outlined"), (theme.box_height, theme.card_look, theme.band_look))

    def test_a_page_written_the_old_way_is_not_moved(self) -> None:
        said = {"box_height": "text", "card_look": "filled", "band_look": "plain"}
        for data in (
            {"type": "cards", "title": "T", "cards": [["A", "a"], {"heading": "B", "tone": "accent"}],
             "condition": "c", "conclusion": "d"},
            {"type": "flow", "title": "T", "stages": [{"name": "s", "nodes": [["A", "a"]]},
                                                       {"name": "t", "nodes": [["B", "b"]]}]},
            {"type": "compose", "title": "T", "rows": [row(card("Goal", "one")), row(card("L", "l"), card("R", "r"))]},
        ):
            with self.subTest(type=data["type"]):
                self.assertEqual(build(data).build(), build(data, theme_from(said)).build())


class TheBoxesTakeThePage(unittest.TestCase):
    CARDS = [["One", "first"], ["Two", "second " * 12], ["Three", "third"]]

    def test_the_cards_of_a_cards_page_fill_the_body_down_to_its_last_line(self) -> None:
        data = {"type": "cards", "title": "T", "cards": self.CARDS, "card_columns": 1,
                "condition": "c", "conclusion": "d", "footer": "f"}
        body = body_of(PAGE, condition="c", conclusion="d", footer="f")
        boxes = of_kind(build(data, PAGE), "box")
        self.assertEqual(body.bottom, max(box.rect.bottom for box in boxes))
        self.assertEqual(body.top, boxes[0].rect.top)
        # 字の高さの資料では、下が空く (= 今までの見た目)
        self.assertLess(max(box.rect.bottom for box in of_kind(build(data), "box")), body.bottom - GAP_M)

    def test_each_card_row_takes_an_equal_share_on_top_of_its_words(self) -> None:
        data = {"type": "cards", "title": "T", "cards": self.CARDS, "card_columns": 1}
        boxes = of_kind(build(data, PAGE), "box")
        heights = [box.rect.height for box in boxes]
        self.assertLessEqual(max(heights) - min(heights), 1, "the rows of one cards page share one height")
        for one, other in zip(boxes, boxes[1:]):
            self.assertEqual(GAP_M, other.rect.top - one.rect.bottom)

    def test_a_table_and_a_reading_keep_their_room_under_the_cards(self) -> None:
        data = {"type": "cards", "title": "T", "cards": self.CARDS, "card_columns": 3,
                "table": [["列", "値"], ["A", "1"]], "note": "How to read this"}
        built = build(data, PAGE)
        boxes, table, note = of_kind(built, "box"), of_kind(built, "table")[0], of_kind(built, "note")[0]
        self.assertLessEqual(max(box.rect.bottom for box in boxes) + GAP_M, table.rect.top)
        self.assertLessEqual(table.rect.bottom, note.rect.top)
        self.assertLessEqual(note.rect.top + DEFAULT.text_height("How to read this", note.rect.width),
                             body_of(PAGE).bottom + 1)

    def test_cards_above_another_body_stay_as_tall_as_their_words(self) -> None:
        """カードが本体を持つ頁では、本体 (= 図) の取る高さが先 (= カードが使い切ると、図が入らない)。"""
        data = {"type": "figure", "title": "T", "figure": "dot.png", "cards": [["A", "a"], ["B", "b"]]}
        self.assertEqual(of_kind(build(data), "box"), of_kind(build(data, PAGE), "box"))

    def test_cards_that_do_not_fit_are_still_refused(self) -> None:
        data = {"type": "cards", "title": "T", "cards": [[f"Card {n}", "a body " * 40] for n in range(8)],
                "card_columns": 1}
        with self.assertRaises(PageFullError):
            build(data, PAGE)


class ComposeRowsTakeThePage(unittest.TestCase):
    GOAL = [row(card("Goal", "one thing to reach")),
            row(card("Left", "holds it up " * 8), card("Right", "holds it too"))]

    def test_the_last_row_ends_where_the_body_ends(self) -> None:
        built = compose(self.GOAL, PAGE)
        self.assertEqual(body_of(PAGE).bottom, box_of(built, "Left").rect.bottom)
        self.assertEqual(body_of(PAGE).top, box_of(built, "Goal").rect.top)

    def test_a_row_with_more_words_stays_taller_by_exactly_its_words(self) -> None:
        text, page = compose(self.GOAL), compose(self.GOAL, PAGE)
        grown = [box_of(page, h).rect.height - box_of(text, h).rect.height for h in ("Goal", "Left")]
        self.assertGreater(grown[0], 0)
        self.assertLessEqual(abs(grown[0] - grown[1]), 1, "each row takes the same share on top of its words")
        self.assertGreater(box_of(page, "Left").rect.height, box_of(page, "Goal").rect.height)

    def test_the_rows_between_are_still_a_gap_apart(self) -> None:
        built = compose(self.GOAL, PAGE)
        self.assertEqual(GAP_M, box_of(built, "Left").rect.top - box_of(built, "Goal").rect.bottom)

    def test_rows_that_say_a_weight_share_the_page_in_that_ratio(self) -> None:
        built = compose([row(card("One"), weight=1), row(card("Two"), weight=2)], PAGE)
        one, two = box_of(built, "One").rect, box_of(built, "Two").rect
        self.assertAlmostEqual(2 * one.height, two.height, delta=3)
        self.assertEqual(body_of(PAGE).bottom, two.bottom)

    def test_a_picture_row_takes_the_rest_and_the_cards_stay_as_tall_as_their_words(self) -> None:
        rows = [row({"figure": "wide.png"}), row(card("Note", "under the picture"))]
        text, page = compose(rows), compose(rows, PAGE)
        self.assertEqual(box_of(text, "Note").rect, box_of(page, "Note").rect)

    def test_text_beside_a_card_stays_as_tall_as_its_words_at_the_top(self) -> None:
        rows = [row(card("Left", "a body " * 20), {"text": "Words beside"})]
        text, page = compose(rows), compose(rows, PAGE)
        self.assertEqual(named(text, "Words beside").rect, named(page, "Words beside").rect)
        self.assertGreater(box_of(page, "Left").rect.height, box_of(text, "Left").rect.height)

    def test_a_cell_of_rows_shares_what_its_row_has(self) -> None:
        rows = [row(card("Beside", "a body " * 30), {"rows": [row(card("Upper")), row(card("Lower"))]})]
        built = compose(rows, PAGE)
        beside, upper, lower = (box_of(built, h).rect for h in ("Beside", "Upper", "Lower"))
        self.assertEqual((beside.top, beside.bottom), (upper.top, lower.bottom))
        self.assertEqual(body_of(PAGE).bottom, beside.bottom)
        self.assertLessEqual(abs(upper.height - lower.height), 1)

    def test_a_row_whose_only_cards_are_in_a_cell_of_rows_grows_too(self) -> None:
        rows = [row({"text": "Words above"}), row({"rows": [row(card("Upper")), row(card("Lower"))]})]
        built = compose(rows, PAGE)
        self.assertEqual(body_of(PAGE).bottom, box_of(built, "Lower").rect.bottom)
        self.assertEqual(named(compose(rows), "Words above").rect, named(built, "Words above").rect)

    def test_rows_with_no_card_in_them_are_not_stretched(self) -> None:
        rows = [row({"text": "Only words"}), row({"points": ["one", "two"]})]
        self.assertEqual(compose(rows).build(), compose(rows, PAGE).build())

    def test_a_compose_that_does_not_fit_is_still_refused(self) -> None:
        with self.assertRaises(PageFullError):
            compose([row(card(f"Row {n}", "a body " * 30)) for n in range(6)], PAGE)


class FlowsAndRoadsTakeThePage(unittest.TestCase):
    STAGES = [{"name": "In", "nodes": [["A", "a"], ["B", "b " * 60], ["C", "c"]], "settled": "decided"},
              {"name": "Out", "nodes": [["D", "d"]], "settled": "also decided"}]

    def test_every_stage_ends_where_the_body_ends_above_its_settled_line(self) -> None:
        built = build({"type": "flow", "title": "T", "stages": self.STAGES}, PAGE)
        text = build({"type": "flow", "title": "T", "stages": self.STAGES})
        tails = [box_of(built, h).rect.bottom for h in ("C", "D")]
        self.assertEqual(tails[0], tails[1])
        self.assertEqual(body_of(PAGE).bottom, named(built, "also decided").rect.bottom,
                         "the settled line is the last thing on the page")
        self.assertGreater(tails[0], box_of(text, "C").rect.bottom)

    def test_the_nodes_of_a_stage_keep_their_order_and_their_gap(self) -> None:
        built = build({"type": "flow", "title": "T", "stages": self.STAGES}, PAGE)
        boxes = [box_of(built, h).rect for h in ("A", "B", "C")]
        for one, other in zip(boxes, boxes[1:]):
            self.assertEqual(GAP_S, other.top - one.bottom)
        self.assertGreater(boxes[1].height, boxes[0].height, "more words, taller")

    def test_aligned_rows_stay_aligned_across_stages(self) -> None:
        stages = [{"name": "In", "nodes": [["A1", "a"], ["A2", "a " * 30]]},
                  {"name": "Out", "nodes": [["B1", "b " * 10], ["B2", "b"]]}]
        built = build({"type": "flow", "title": "T", "stages": stages, "align_rows": True}, PAGE)
        for one, other in (("A1", "B1"), ("A2", "B2")):
            self.assertEqual(box_of(built, one).rect.top, box_of(built, other).rect.top)
            self.assertEqual(box_of(built, one).rect.height, box_of(built, other).rect.height)

    def test_a_stage_with_fewer_nodes_keeps_to_the_rows_of_the_others(self) -> None:
        stages = [{"name": "In", "nodes": [["A1", "a"], ["A2", "a"], ["A3", "a"]]},
                  {"name": "Out", "nodes": [["B1", "b"]]}]
        built = build({"type": "flow", "title": "T", "stages": stages, "align_rows": True}, PAGE)
        self.assertEqual(box_of(built, "A1").rect.height, box_of(built, "B1").rect.height)
        self.assertEqual(body_of(PAGE).bottom, box_of(built, "A3").rect.bottom)

    def test_a_flow_that_runs_down_shares_the_height_between_its_stages(self) -> None:
        stages = [{"name": "One", "nodes": [["A", "a"]]}, {"name": "Two", "nodes": [["B", "long words " * 40]]}]
        data = {"type": "flow", "title": "T", "stages": stages, "direction": "down"}
        built, text = build(data, PAGE), build(data)
        self.assertEqual(body_of(PAGE).bottom, box_of(built, "B").rect.bottom)
        self.assertGreater(box_of(built, "A").rect.height, box_of(text, "A").rect.height)
        self.assertGreater(box_of(built, "B").rect.height, box_of(built, "A").rect.height)

    def test_a_roadmap_fills_the_height_under_its_arrowheads(self) -> None:
        stages = [{"name": "Now", "nodes": [["A", "a"], ["B", "b"]]},
                  {"name": "Goal", "nodes": [["C", "c " * 60]], "goal": True}]
        built = build({"type": "roadmap", "title": "T", "stages": stages}, PAGE)
        self.assertEqual(body_of(PAGE).bottom, box_of(built, "B").rect.bottom)
        self.assertEqual(body_of(PAGE).bottom, box_of(built, "C").rect.bottom)

    def test_an_agenda_of_boxes_gives_each_chapter_its_whole_share(self) -> None:
        data = {"type": "agenda", "title": "T", "buckets": [["One", ["a"]], ["Two", ["b"]]], "highlight": 1}
        built, text = build(data, PAGE), build(data)
        self.assertGreater(box_of(built, "1. One").rect.height, box_of(text, "1. One").rect.height)
        self.assertEqual(body_of(PAGE).bottom, box_of(built, "2. Two").rect.bottom)


class ACardCarriesItsColourOnItsLine(unittest.TestCase):
    def painted(self, theme, **style):
        return box_of(build({"type": "cards", "title": "T", "cards": [{"heading": "Head", "body": "words", **style}]},
                            theme), "Head")

    def heading(self, theme, **style):
        built = build({"type": "cards", "title": "T", "cards": [{"heading": "Head", "body": "words", **style}]}, theme)
        return named(built, "Head"), named(built, "words")

    def test_a_card_that_says_a_reading_is_nearly_paper_with_its_colour_on_the_line_and_the_heading(self) -> None:
        for tone, hue in (("accent", P.accent), ("good", P.good), ("bad", P.bad)):
            with self.subTest(tone=tone):
                box, (head, body) = self.painted(OUTLINED, tone=tone), self.heading(OUTLINED, tone=tone)
                self.assertEqual(P.thinned(P.CARD_WASH, hue), box.colour)
                self.assertEqual(hue, box.outline)
                self.assertEqual((hue, True), (head.colour, head.bold))
                self.assertEqual(P.ink, body.colour)
                self.assertTrue(box.rounded)

    def test_the_ground_is_nearly_paper(self) -> None:
        box = self.painted(OUTLINED, tone="bad")
        for channel in range(3):
            self.assertGreaterEqual(int(box.colour[2 * channel:2 * channel + 2], 16), 0xF0)

    def test_the_same_card_filled_is_painted_as_it_always_was(self) -> None:
        box, (head, _body) = self.painted(DEFAULT, tone="accent"), self.heading(DEFAULT, tone="accent")
        self.assertEqual((P.accent, False), (box.colour, box.rounded))
        self.assertEqual(P.paper, head.colour)

    def test_a_ground_with_no_meaning_is_what_it_was(self) -> None:
        for tone in ("box", "band", "tint"):
            with self.subTest(tone=tone):
                box, (head, _body) = self.painted(OUTLINED, tone=tone), self.heading(OUTLINED, tone=tone)
                was = self.painted(DEFAULT, tone=tone)
                self.assertEqual((was.colour, was.outline), (box.colour, box.outline))
                self.assertEqual(P.ink, head.colour)

    def test_a_tentative_card_is_drawn_in_ink_and_not_dashed(self) -> None:
        box, (head, _body) = self.painted(OUTLINED, tentative=True), self.heading(OUTLINED, tentative=True)
        self.assertEqual((P.paper, P.ink, False), (box.colour, box.outline, box.dashed))
        self.assertEqual(P.ink, head.colour)

    def test_a_strong_card_keeps_its_colour_and_draws_a_heavy_line(self) -> None:
        box = self.painted(OUTLINED, tone="accent", strong=True)
        self.assertEqual((P.accent, True), (box.outline, box.heavy))

    def test_a_ground_a_project_named_follows_the_same_rule(self) -> None:
        theme = theme_from({"card_look": "outlined", "grounds": {"Deep": "8B1E3F", "Pale": "EAF0F8"}})
        deep, pale = self.painted(theme, tone="Deep"), self.painted(theme, tone="Pale")
        self.assertEqual(("8B1E3F", theme.palette.thinned(P.CARD_WASH, "8B1E3F")), (deep.outline, deep.colour))
        self.assertEqual(self.painted(theme_from({"grounds": {"Pale": "EAF0F8"}}), tone="Pale").colour, pale.colour)
        self.assertEqual(self.heading(theme, tone="Deep")[0].colour, "8B1E3F")

    def test_a_card_of_a_flow_a_roadmap_and_a_compose_is_painted_the_same_way(self) -> None:
        stages = [{"name": "S", "nodes": [{"heading": "Node", "tone": "bad"}]},
                  {"name": "T", "nodes": [["Other", "o"]]}]
        for data in ({"type": "flow", "title": "T", "stages": stages},
                     {"type": "roadmap", "title": "T", "stages": stages},
                     {"type": "compose", "title": "T", "rows": [row(card("Node", tone="bad"))]}):
            with self.subTest(type=data["type"]):
                self.assertEqual((P.bad, True), (box_of(build(data, OUTLINED), "Node").outline,
                                                 box_of(build(data, OUTLINED), "Node").rounded))

    def test_a_thinner_colour_is_the_paper_at_nothing_and_the_colour_at_all(self) -> None:
        self.assertEqual(P.paper, P.thinned(0, P.bad))
        self.assertEqual(P.bad, P.thinned(1, P.bad))
        self.assertEqual(P.thinned(0.3), P.thinned(0.3, P.accent))


class TheBandsHaveALineAndAColour(unittest.TestCase):
    def bands(self, theme):
        page = Page("T", theme, condition="If this holds", conclusion="Then that follows")
        return (next(e for e in page.elements if e.kind == "band"),
                named_in(page, "If this holds"), [e for e in page.elements if e.kind == "band"][1],
                named_in(page, "Then that follows"))

    def test_the_condition_is_the_accent_on_a_nearly_white_ground_in_bold(self) -> None:
        band, words, _under, _words = self.bands(BANDED)
        self.assertEqual((P.thinned(P.BAND_WASH), P.accent, True), (band.colour, band.outline, band.rounded))
        self.assertEqual((P.accent, True, BANDED.type.heading), (words.colour, words.bold, words.size))

    def test_the_conclusion_is_grey_with_its_words_in_ink_at_the_body_size(self) -> None:
        _band, _words, band, words = self.bands(BANDED)
        self.assertEqual((P.thinned(P.BAND_WASH, P.muted), P.muted, True), (band.colour, band.outline, band.rounded))
        self.assertEqual((P.ink, True, BANDED.type.body), (words.colour, words.bold, words.size))

    def test_the_two_are_told_apart_by_colour(self) -> None:
        top, _w, bottom, _v = self.bands(BANDED)
        self.assertNotEqual((top.colour, top.outline), (bottom.colour, bottom.outline))

    def test_plain_bands_are_the_grey_ones_with_no_line(self) -> None:
        top, words, bottom, under = self.bands(DEFAULT)
        self.assertEqual((P.band, ""), (top.colour, top.outline))
        self.assertEqual((P.rule, ""), (bottom.colour, bottom.outline))
        self.assertEqual((False, True), (words.bold, under.bold))

    def test_the_bands_stand_where_they_stood(self) -> None:
        plain = Page("T", DEFAULT, condition="c", conclusion="d")
        outlined = Page("T", BANDED, condition="c", conclusion="d")
        self.assertEqual(plain.body, outlined.body)
        self.assertEqual([e.rect for e in plain.elements], [e.rect for e in outlined.elements])


def named_in(page, text):
    return next(e for e in page.elements if getattr(e, "text", None) == text)


class WhatIsWrittenIsAFileThatOpens(unittest.TestCase):
    def test_a_page_in_all_three_looks_is_written_and_passes_the_checks(self) -> None:
        theme = theme_from({"box_height": "page", "card_look": "outlined", "band_look": "outlined"})
        data = {"type": "cards", "title": "A page", "condition": "If this holds", "conclusion": "Then that follows",
                "cards": [{"heading": "Read", "body": "what it says", "tone": "accent"},
                          {"heading": "Careful", "body": "what to mind", "tone": "bad"},
                          {"heading": "Open", "body": "not yet", "tentative": True}]}
        deck = new_deck(theme)
        add_page(deck, build(data, theme).build(), theme)
        with tempfile.TemporaryDirectory() as tmp:
            saved = save(deck, Path(tmp) / "looks.pptx")
            self.assertEqual([], checks.run_all(saved))
            xml = zipfile.ZipFile(saved).read("ppt/slides/slide1.xml").decode("utf-8")
        self.assertEqual(5, xml.count('prst="roundRect"'), "three cards and two bands")
        for colour in (P.accent, P.bad, P.muted):
            self.assertIn(f'<a:srgbClr val="{colour}"/>', xml)


if __name__ == "__main__":
    unittest.main()
