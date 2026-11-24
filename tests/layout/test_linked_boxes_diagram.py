"""Boxes joined by arrows across rows and columns are a shape diagram; a single row or column of them is not.

* a `compose` page whose `links` are three or more and join boxes in two rows and two columns or more carries a
  figure (= a fork, a swimlane, a web of links); one that joins boxes in a single row or column, or with fewer
  than three lines, is still refused (= words in boxes with arrows between them)
* the boxes such lines join are one diagram to the page checks: not boxes of one line, one part to
  `crowded_page`, a lead that is a picture to `no_lead`; their words still count to `wordy_page`
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))
from support.pages import build  # noqa: E402

from pptx_agent_maker.checks._internal.page_reading import (  # noqa: E402
    characters, diagram, is_a_picture, lead, one_line_boxes, parts)
from pptx_agent_maker.layout.tokens import theme_from  # noqa: E402
from pptx_agent_maker.layout.types.bodies.arrange import (  # noqa: E402
    LINKS_FOR_A_DIAGRAM, SPAN_FOR_A_DIAGRAM, shows_a_diagram)
from pptx_agent_maker.layout.geometry import Rect  # noqa: E402

PICTURE = "dot.png"
#: a tight spacing, so that six rows of cards fit one page
TIGHT = theme_from({"uses": {"tight": {"like": "read", "spacing": {"scale": 0.5}}}}).using("tight")


def box(name: str, row: int, column: int) -> dict:
    """A cell holding a card of one word, on the grid at (row, column) counted from 1."""
    return {"id": name, "at": [row, column], "card": {"heading": name}}


def link(first: str, second: str) -> dict:
    return {"from": first, "to": second}


def grid_page(cells: list[dict], links: list[dict], columns: int, rows: int, theme=None):
    data = {"type": "compose", "title": "A page", "grid": {"columns": [1] * columns, "rows": [1] * rows},
            "cells": cells}
    if links:
        data["links"] = links
    return build(data, theme) if theme else build(data)


#: a flow that forks on a condition: one box leads to two, and one of them goes on
FORK_CELLS = [box("start", 1, 1), box("yes", 1, 2), box("no", 2, 1), box("end", 2, 2)]
FORK_LINKS = [link("start", "yes"), link("start", "no"), link("yes", "end")]


def a_web():
    """The shape a company's page took: 6 rows by 5 columns, 20 cards, 9 lines (= 6 across, 2 down, 1 that bends)."""
    squares = [(row, column) for row in range(6) for column in range(5)]
    empty = {(1, 1), (1, 3), (3, 1), (3, 3), (5, 1), (5, 3), (0, 4), (2, 4), (4, 4), (5, 4)}
    chosen = [square for square in squares if square not in empty]
    cells = [box(f"b{number}", row + 1, column + 1) for number, (row, column) in enumerate(chosen)]
    name = {square: f"b{number}" for number, square in enumerate(chosen)}
    joined = [((0, 0), (0, 1)), ((0, 2), (0, 3)), ((2, 0), (2, 1)), ((2, 2), (2, 3)), ((4, 0), (4, 1)),
              ((4, 2), (4, 3)), ((0, 0), (1, 0)), ((2, 0), (3, 0)), ((0, 2), (2, 3))]
    return grid_page(cells, [link(name[a], name[b]) for a, b in joined], 5, 6, TIGHT)


def one_row(count: int, links: int):
    cells = [box(f"b{n}", 1, n + 1) for n in range(count)]
    return grid_page(cells, [link(f"b{n}", f"b{n + 1}") for n in range(links)], count, 1)


def one_column(count: int, links: int):
    cells = [box(f"b{n}", n + 1, 1) for n in range(count)]
    return grid_page(cells, [link(f"b{n}", f"b{n + 1}") for n in range(links)], 1, count)


class WhatCountsAsADiagram(unittest.TestCase):

    def test_a_web_of_cards_over_six_rows_and_five_columns_is_built(self):
        self.assertTrue(a_web().build())

    def test_a_fork_over_two_rows_and_two_columns_is_built(self):
        self.assertTrue(grid_page(FORK_CELLS, FORK_LINKS, 2, 2).build())

    def test_a_row_of_boxes_joined_by_five_arrows_is_refused(self):
        with self.assertRaises(ValueError) as refused:
            one_row(6, 5).build()
        self.assertIn("no figure", str(refused.exception))

    def test_a_column_of_boxes_joined_by_arrows_is_refused(self):
        with self.assertRaises(ValueError) as refused:
            one_column(4, 3).build()
        self.assertIn("no figure", str(refused.exception))

    def test_two_arrows_across_two_rows_and_two_columns_are_refused(self):
        with self.assertRaises(ValueError) as refused:
            grid_page(FORK_CELLS, FORK_LINKS[:2], 2, 2).build()
        self.assertIn("no figure", str(refused.exception))

    def test_the_refusal_names_the_arrows_that_count_and_those_that_do_not(self):
        with self.assertRaises(ValueError) as refused:
            one_row(3, 2).build()
        said = str(refused.exception)
        self.assertIn("three arrows or more across rows and columns", said)
        self.assertIn("single row or column", said)


class TheEdgeOfTheValues(unittest.TestCase):

    def test_three_lines_over_two_rows_and_two_columns_pass_and_two_do_not(self):
        self.assertEqual((3, 2), (LINKS_FOR_A_DIAGRAM, SPAN_FOR_A_DIAGRAM))
        boxes = [Rect(0, 0, 10, 10), Rect(20, 0, 10, 10), Rect(0, 20, 10, 10)]
        self.assertTrue(shows_a_diagram(3, boxes))
        self.assertFalse(shows_a_diagram(2, boxes))

    def test_boxes_in_one_row_or_one_column_do_not_pass_however_many_lines(self):
        row = [Rect(left, 0, 10, 10) for left in (0, 20, 40)]
        column = [Rect(0, top, 10, 10) for top in (0, 20, 40)]
        self.assertFalse(shows_a_diagram(9, row))
        self.assertFalse(shows_a_diagram(9, column))


class TheBoxesAreOneDiagram(unittest.TestCase):

    def with_a_picture(self, links: list[dict]):
        """The fork's four boxes, a picture beside them, and `links` between the boxes."""
        data = {"type": "compose", "title": "A page", "grid": {"columns": [1, 1, 1], "rows": [1, 1]},
                "cells": [*FORK_CELLS, {"figure": PICTURE, "at": [1, 3], "span": [2, 1]}]}
        if links:
            data["links"] = links
        return build(data)

    def test_boxes_of_one_line_are_counted_alone_but_not_once_they_are_joined(self):
        self.assertEqual(4, one_line_boxes(self.with_a_picture([])))
        self.assertEqual(0, one_line_boxes(self.with_a_picture(FORK_LINKS)))

    def test_the_joined_boxes_are_one_part_to_crowded_page(self):
        kinds = [kind for kind, _where in parts(self.with_a_picture(FORK_LINKS))]
        self.assertEqual(["diagram", "figure"], sorted(kinds))
        self.assertEqual(5, len(parts(self.with_a_picture([]))))

    def test_the_diagram_is_the_rectangle_round_every_joined_box(self):
        page = grid_page(FORK_CELLS, FORK_LINKS, 2, 2)
        shape = diagram(page)
        self.assertEqual(4, len(page.diagram_boxes))
        for joined in page.diagram_boxes:
            self.assertTrue(shape.contains(joined))

    def test_the_diagram_can_lead_the_page(self):
        page = grid_page(FORK_CELLS, FORK_LINKS, 2, 2)
        self.assertEqual("diagram", lead(page))
        self.assertTrue(is_a_picture(lead(page)))

    def test_the_words_of_the_boxes_still_count_to_wordy_page(self):
        page = grid_page(FORK_CELLS, FORK_LINKS, 2, 2)
        self.assertEqual(len("startyesnoend"), characters(page))

    def test_a_page_with_fewer_lines_keeps_its_boxes_apart(self):
        page = self.with_a_picture(FORK_LINKS[:2])
        self.assertEqual((), page.diagram_boxes)
        self.assertEqual(4, one_line_boxes(page))


if __name__ == "__main__":
    unittest.main()
