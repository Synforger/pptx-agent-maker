"""A table cell can stand on a ground as deep as its value: `{ text = "82%", shade = 3 }`.

数の大小を、セルの地の濃さでも見せる (= 表を読む前に、どこが濃いかが目に入る)。濃さはセルが自分で言う ―
0 から 4 の段で、4 が差し色そのもの。値から段を決めるのは書く人 (= 何を境に濃くするかは、その表が何を
言いたいかで決まる)。印のセル (= ハーベイボール) と同じ書き方で、字のまま置かれるので PowerPoint で直せる。
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))

from support.pages import build  # noqa: E402

from pptx_agent_maker import DEFAULT  # noqa: E402
from pptx_agent_maker.layout.base.tokens import contrast, theme_from  # noqa: E402
from pptx_agent_maker.layout.parts.elements import Mark, Shade, Table  # noqa: E402
from pptx_agent_maker.layout.types import PageTypeError  # noqa: E402
from pptx_agent_maker.layout.types.core.read import read_cell  # noqa: E402

TABLE = [["地域", "先月", "今月"],
         ["北", {"text": "12%", "shade": 1}, {"text": "48%", "shade": 2}],
         ["南", {"text": "71%", "shade": 3}, {"text": "96%", "shade": 4}],
         ["西", {"text": "3%", "shade": 0}, "―"]]


def table_of(page) -> Table:
    return next(e for e in page.build() if isinstance(e, Table))


class WhatACellSays(unittest.TestCase):
    def test_a_shaded_cell_is_its_words_and_how_deep_its_ground_is(self) -> None:
        cell = read_cell({"text": "82%", "shade": 3}, "a cell")
        self.assertIsInstance(cell, Shade)
        self.assertEqual(("82%", 3), (str(cell), cell.level))
        self.assertNotIsInstance(cell, Mark)
        self.assertEqual("82", str(read_cell({"text": 82, "shade": 1}, "a cell")))

    def test_the_depth_is_a_whole_number_of_quarters(self) -> None:
        for shade in (5, -1, 2.0, True, "2", None):
            with self.subTest(shade=shade), self.assertRaises(PageTypeError) as refused:
                read_cell({"text": "82%", "shade": shade}, "table: row 2, column 3")
            self.assertIn("table: row 2, column 3", str(refused.exception))
            self.assertIn("shade", str(refused.exception))

    def test_a_shade_needs_words_to_stand_under(self) -> None:
        for cell in ({"shade": 2}, {"text": "", "shade": 2}, {"text": "  ", "shade": 2}, {"text": "a"},
                     {"text": "a", "shade": 2, "mark": "ok"}, {"text": "a", "shade": 2, "harvey": 1}):
            with self.subTest(cell=cell), self.assertRaises(PageTypeError) as refused:
                read_cell(cell, "table: row 2, column 3")
            self.assertIn("table: row 2, column 3", str(refused.exception))

    def test_what_a_cell_may_be_is_said_whole_when_it_is_refused(self) -> None:
        with self.assertRaises(PageTypeError) as refused:
            read_cell({"colour": "red"}, "a cell")
        for way in ("harvey", "mark", "shade"):
            self.assertIn(way, str(refused.exception))


class WhereTheShadesAre(unittest.TestCase):
    def test_every_table_takes_shades_and_knows_where_they_are(self) -> None:
        wanted = {(1, 1): 1, (1, 2): 2, (2, 1): 3, (2, 2): 4}
        pages = {
            "under a body": build({"type": "figure", "title": "だい", "figure": "dot.png", "table": TABLE}),
            "a board": build({"type": "board", "title": "だい", "table": TABLE}),
            "a cell of a compose": build({"type": "compose", "title": "だい",
                                          "rows": [{"cells": [{"table": TABLE}]}]}),
        }
        for where, page in pages.items():
            with self.subTest(where):
                table = table_of(page)
                self.assertEqual(wanted, table.shades, "a cell of no depth is an ordinary cell")
                self.assertEqual(("北", "12%", "48%"), table.rows[1])

    def test_a_table_with_no_shade_is_the_table_it_was(self) -> None:
        plain = [[str(cell) if not isinstance(cell, dict) else cell["text"] for cell in row] for row in TABLE]
        flat = [[cell if not isinstance(cell, dict) else {"text": cell["text"], "shade": 0} for cell in row]
                for row in TABLE]
        self.assertEqual(build({"type": "board", "title": "だい", "table": plain}).build(),
                         build({"type": "board", "title": "だい", "table": flat}).build())

    def test_a_heading_cell_is_not_shaded(self) -> None:
        """見出しの行は差し色の地に紙の色の字。そこへ濃さを書いても、読める形にならない。"""
        bad = [["地域", {"text": "今月", "shade": 2}], ["北", "48%"]]
        with self.assertRaises((PageTypeError, ValueError)) as refused:
            build({"type": "board", "title": "だい", "table": bad}).build()
        self.assertIn("heading", str(refused.exception))

    def test_a_shaded_row_is_as_tall_as_a_row_of_words(self) -> None:
        plain = [[str(cell) if not isinstance(cell, dict) else cell["text"] for cell in row] for row in TABLE]
        self.assertEqual(table_of(build({"type": "board", "title": "だい", "table": plain})).rect,
                         table_of(build({"type": "board", "title": "だい", "table": TABLE})).rect)


class TheGrounds(unittest.TestCase):
    def test_the_deepest_is_the_accent_and_each_step_is_a_quarter_of_the_way(self) -> None:
        p = DEFAULT.palette
        self.assertEqual(p.accent, p.shade(4))
        self.assertEqual(p.paper, p.shade(0))
        steps = [int(p.shade(level)[0:2], 16) for level in range(5)]
        self.assertEqual(sorted(steps, reverse=True), steps, "each step is no lighter than the one before")
        self.assertEqual(5, len(set(p.shade(level) for level in range(5))))

    def test_a_project_that_changes_its_accent_changes_the_shades(self) -> None:
        theme = theme_from({"palette": {"accent": "C00000"}})
        self.assertEqual("C00000", theme.palette.shade(4))
        self.assertNotEqual(DEFAULT.palette.shade(2), theme.palette.shade(2))


class OnceBaked(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from pptx_agent_maker.write import add_page, new_deck, save

        cls.tmp = tempfile.TemporaryDirectory()
        deck = new_deck()
        add_page(deck, build({"type": "board", "title": "だい", "table": TABLE}).build())
        cls.deck = save(deck, Path(cls.tmp.name) / "shaded.pptx")
        with zipfile.ZipFile(cls.deck) as archive:
            xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        cls.cells = {"".join(re.findall(r"<a:t>(.*?)</a:t>", cell)): cell
                     for cell in re.findall(r"<a:tc[ >].*?</a:tc>", xml, re.S)}

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def ground(self, words: str) -> str:
        return re.search(r'<a:tcPr[^>]*>.*?<a:srgbClr val="([0-9A-F]{6})"', self.cells[words], re.S).group(1)

    def ink(self, words: str) -> str:
        return re.search(r'<a:rPr[^>]*>.*?<a:srgbClr val="([0-9A-F]{6})"', self.cells[words], re.S).group(1)

    def test_each_shaded_cell_stands_on_its_own_depth(self) -> None:
        p = DEFAULT.palette
        self.assertEqual([p.shade(1), p.shade(2), p.shade(3), p.shade(4)],
                         [self.ground(words) for words in ("12%", "48%", "71%", "96%")])

    def test_the_words_take_whichever_colour_reads_on_their_ground(self) -> None:
        p = DEFAULT.palette
        for words in ("12%", "48%", "71%", "96%"):
            with self.subTest(words):
                ground, ink = self.ground(words), self.ink(words)
                self.assertIn(ink, (p.ink, p.paper))
                self.assertGreaterEqual(contrast(ground, ink), contrast(ground, p.ink if ink == p.paper else p.paper))
        self.assertEqual(p.paper, self.ink("96%"))
        self.assertEqual(p.ink, self.ink("12%"))

    def test_a_cell_of_no_depth_and_a_cell_of_words_keep_the_rows_ground(self) -> None:
        self.assertEqual(self.ground("西"), self.ground("3%"))
        self.assertEqual(self.ground("西"), self.ground("―"))

    def test_the_checks_find_nothing(self) -> None:
        from pptx_agent_maker import checks

        self.assertEqual([], checks.run_all(self.deck))


if __name__ == "__main__":
    unittest.main()
