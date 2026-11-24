"""The rule "every page carries a figure": what counts as one, what does not, and what the refusal says.

A figure is a chart, a picture, or a shape that shows how things relate (a timeline's bars, circles that
overlap, boxes joined across rows and columns: `test_linked_boxes_diagram.py`). Words in boxes do not count,
however they are joined in a row: cards, tables, a flow, a road, a ring of boxes, a tree of boxes. Only the
agenda may carry none. The `cards` type reads a picture of its own, and is refused without one.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests"))

from support.pages import build  # noqa: E402

from pptx_agent_maker.layout import types  # noqa: E402
from pptx_agent_maker.layout.tokens import theme_from  # noqa: E402
from pptx_agent_maker.layout.types.core.registry import PageTypeError  # noqa: E402


PICTURE = "dot.png"
STAGES = [{"name": "In", "nodes": [["A", "first"]]}, {"name": "Out", "nodes": [["B", "then"]]}]
ROAD = [{"name": "Start", "nodes": [["A", "first"]]}, {"name": "Goal", "nodes": [["B", "then"]], "goal": True}]
CARDS = [["1", "one"], ["2", "two"]]
TABLE = [["Column", "Value"], ["A", "1"]]
RING = [["Plan", "decide"], ["Do", "try"], ["Check", "count"]]
TREE = {"heading": "Root", "children": [{"heading": "Left"}, {"heading": "Right"}]}
CHART = {"kind": "column", "categories": ["Now", "Next"], "series": [{"name": "Count", "values": [1, 2]}]}
TIMELINE = {"periods": ["Now", "Next"], "lanes": [{"name": "Work", "bars": [{"from": 0, "to": 1, "text": "Decide"}]}]}


def page(kind: str, **body):
    return build({"type": kind, "title": "A page", **body})


def composed(*cells):
    return page("compose", rows=[{"cells": list(cells)}])


#: pages made of words in boxes alone (= how a page with no picture or chart is built)
WORDS_ONLY = {
    "a flow": lambda: page("flow", stages=STAGES),
    "a flow going down": lambda: page("flow", stages=STAGES, direction="down"),
    "a road": lambda: page("roadmap", stages=ROAD),
    "a table alone": lambda: page("board", table=TABLE),
    "cards without a picture": lambda: page("cards", cards=CARDS),
    "a ring of boxes": lambda: composed({"ring": RING}),
    "a tree of boxes": lambda: composed({"tree": TREE}),
    "cards and a table in a compose": lambda: composed({"card": ["Goal", "one"]}, {"table": TABLE}),
    "a flow alone in a compose": lambda: composed({"flow": {"stages": STAGES}}),
    "a road alone in a compose": lambda: composed({"roadmap": {"stages": ROAD}}),
}

#: pages that carry a figure, or that are the agenda
SHOWN = {
    "the agenda": lambda: page("agenda", buckets=[["One", ["a"]], ["Two", ["b"]]], highlight=1),
    "a picture": lambda: page("figure", figure=PICTURE),
    "pictures side by side": lambda: page("figures", figures=[PICTURE, PICTURE]),
    "a chart": lambda: page("chart", chart=CHART),
    "a timeline": lambda: page("timeline", **TIMELINE),
    "circles that overlap": lambda: composed({"overlap": {"sets": ["A", "B"], "shared": "both"}}),
    "a flow beside a picture": lambda: composed({"flow": {"stages": STAGES}}, {"figure": PICTURE}),
    "a flow beside a chart": lambda: composed({"flow": {"stages": STAGES}}, {"chart": CHART}),
    "cards beside a chart": lambda: composed({"card": ["Goal", "one"]}, {"chart": CHART}),
    "a picture with cards added": lambda: page("figure", figure=PICTURE, cards=CARDS),
    "cards with a picture of their own": lambda: page("cards", cards=CARDS, figure=PICTURE),
    "a chart with a table added": lambda: page("chart", chart=CHART, table=TABLE),
}


class WhatCounts(unittest.TestCase):

    def test_a_page_of_words_in_boxes_is_refused(self):
        for name, make in WORDS_ONLY.items():
            with self.subTest(name):
                with self.assertRaises(ValueError) as refused:
                    make().build()
                self.assertIn("no figure", str(refused.exception))

    def test_a_page_with_a_picture_a_chart_or_a_shape_that_shows_a_relation_is_built(self):
        for name, make in SHOWN.items():
            with self.subTest(name):
                self.assertTrue(make().build())

    def test_only_the_agenda_may_carry_no_figure(self):
        self.assertEqual(["agenda"], types.skeleton())

    def test_the_listing_marks_only_the_agenda(self):
        marked = [line.split()[0] for line in types.describe().splitlines() if "may carry no picture" in line]
        self.assertEqual(["agenda"], marked)


class WhenTheRequesterSaidNoFigure(unittest.TestCase):
    """A page whose requester said no figure is wanted writes their words in `no_figure`, and is let through."""

    WORDS = "asked for the table alone"

    def test_a_table_alone_with_their_words_is_built_on_any_type(self):
        for name, make in {"a board": lambda: page("board", table=TABLE, no_figure=self.WORDS),
                           "cards": lambda: page("cards", cards=CARDS, no_figure=self.WORDS),
                           "a flow": lambda: page("flow", stages=STAGES, no_figure=self.WORDS),
                           "a compose": lambda: page("compose", rows=[{"cells": [{"table": TABLE}]}],
                                                     no_figure=self.WORDS)}.items():
            with self.subTest(name):
                self.assertTrue(make().build())

    def test_the_words_are_read_back_without_the_spaces_round_them(self):
        self.assertEqual(self.WORDS, types.no_figure_reason({"no_figure": f"  {self.WORDS}\n"}))
        self.assertEqual("", types.no_figure_reason({}))

    def test_an_empty_value_or_one_that_is_not_words_is_refused_with_the_reason_asked_for(self):
        for value in ("", "   ", True, 1, ["asked"], {"by": "them"}):
            with self.subTest(value=value):
                with self.assertRaises(PageTypeError) as refused:
                    page("board", table=TABLE, no_figure=value)
                self.assertIn("no_figure", str(refused.exception))
                self.assertIn("words of the person who asked", str(refused.exception))

    def test_a_table_alone_without_them_is_still_refused(self):
        with self.assertRaises(ValueError) as refused:
            page("board", table=TABLE).build()
        self.assertIn("no figure", str(refused.exception))

    def test_the_listing_names_the_key_among_those_any_type_reads(self):
        on_any = next(line for line in types.describe().splitlines() if "on any type" in line)
        self.assertIn("no_figure", on_any)


class TheCardsType(unittest.TestCase):

    def test_a_picture_goes_in_the_room_under_the_cards_even_where_boxes_fill_the_page(self):
        theme = theme_from({"box_height": "page"})
        built = build({"type": "cards", "title": "A page", "cards": CARDS, "figure": PICTURE}, theme).build()
        boxes = [e for e in built if e.kind == "box"]
        picture = next(e for e in built if e.kind == "figure")
        self.assertGreaterEqual(picture.rect.top, max(box.rect.bottom for box in boxes))

    def test_the_cards_are_a_type_of_the_listing(self):
        self.assertIn("cards", types.names())

    def test_a_name_no_type_ever_had_gets_the_list_of_types(self):
        with self.assertRaises(PageTypeError) as refused:
            page("nothing")
        self.assertIn("the deck may use only", str(refused.exception))


class WhatTheRefusalSays(unittest.TestCase):

    def setUp(self):
        with self.assertRaises(ValueError) as refused:
            page("board", table=TABLE).build()
        self.said = str(refused.exception)

    def test_it_names_what_counts(self):
        for word in ("chart", "picture", "timeline", "overlapping circles"):
            self.assertIn(word, self.said)

    def test_it_names_what_does_not_count(self):
        for word in ("words in boxes", "cards", "tables", "arrows"):
            self.assertIn(word, self.said)

    def test_it_says_the_way_out(self):
        for word in ("`figure`", "`chart`", "`compose`", "`no_figure = "):
            self.assertIn(word, self.said)


if __name__ == "__main__":
    unittest.main()
