"""A table in the plain look, and a row that divides a table.

* `[theme] table_look = "plain"` ― a grey heading row in the body's colour and bold, a ground of the paper under
  every row, and grey rules round every cell. The look a project picks for all its tables; `"accent"` is the one
  there always was (= a heading row on the accent, the rows under it banded, no rules).
* `{ band = "…", tone = "accent" }` among the rows ― one row across every column, saying what the rows under it
  are. It may be written in any look; the look decides how it is painted.
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
from pptx_agent_maker.layout.base.tokens import Band, TABLE_LOOKS, ThemeError, theme_from  # noqa: E402
from pptx_agent_maker.layout.parts.elements import Table  # noqa: E402
from pptx_agent_maker.layout.types import PageTypeError  # noqa: E402
from pptx_agent_maker.layout.types.core.read import read_table  # noqa: E402

PLAIN = theme_from({"table_look": "plain"})

ROWS = [["Method", "Year", "Output"],
        {"band": "Group one", "tone": "accent"},
        ["Alpha", "2020", "a picture"],
        ["Beta", "2021", "a number"],
        {"band": "Group two"},
        ["Gamma", "2022", "a table"]]


def table_of(page) -> Table:
    return next(e for e in page.build() if isinstance(e, Table))


def board(rows, theme=DEFAULT):
    return build({"type": "board", "title": "Methods", "table": rows}, theme)


class TheLookAProjectPicks(unittest.TestCase):
    def test_the_look_there_always_was_is_the_one_left_unsaid(self) -> None:
        self.assertEqual(("accent", "plain"), TABLE_LOOKS)
        self.assertEqual("accent", DEFAULT.table_look)
        for settings in (None, {}, {"table_look": "accent"}):
            with self.subTest(settings=settings):
                self.assertEqual("accent", theme_from(settings).table_look)

    def test_a_project_that_says_plain_gets_it_in_every_use(self) -> None:
        self.assertEqual("plain", PLAIN.table_look)
        for use in ("read", "present", "sheet"):
            self.assertEqual("plain", PLAIN.using(use).table_look)

    def test_a_name_nobody_knows_is_refused_not_read_as_the_look_there_always_was(self) -> None:
        for name in ("outlined", "filled", "", None, True):
            with self.subTest(name=name), self.assertRaises(ThemeError) as refused:
                theme_from({"table_look": name})
            self.assertIn("table_look", str(refused.exception))
            self.assertIn("'plain'", str(refused.exception))

    def test_the_look_of_the_tables_is_not_the_look_of_the_cards(self) -> None:
        theme = theme_from({"card_look": "outlined", "band_look": "outlined"})
        self.assertEqual("accent", theme.table_look)
        self.assertEqual("filled", PLAIN.card_look)


class AnyRowThatDividesATable(unittest.TestCase):
    def test_a_band_is_one_cell_with_the_tone_it_asked_for(self) -> None:
        rows = read_table(ROWS, "table")
        self.assertEqual(6, len(rows))
        for number, words, tone in ((1, "Group one", "accent"), (4, "Group two", "")):
            with self.subTest(row=number):
                self.assertEqual(1, len(rows[number]))
                self.assertIsInstance(rows[number][0], Band)
                self.assertEqual((words, tone), (str(rows[number][0]), rows[number][0].tone))
        self.assertEqual(["Alpha", "2020", "a picture"], [str(cell) for cell in rows[2]])

    def test_a_band_is_written_the_same_whatever_the_look(self) -> None:
        """The reading takes no theme: the look decides how a band is painted, not whether it may be written."""
        for theme in (DEFAULT, PLAIN):
            with self.subTest(look=theme.table_look):
                table = table_of(board(ROWS, theme))
                self.assertEqual({1, 4}, set(table.bands))

    def test_a_band_says_its_words_in_band_and_nothing_else_but_its_tone(self) -> None:
        for band in ({"band": ""}, {"band": "  "}, {"tone": "accent"}, {"band": "x", "colour": "red"},
                     {"band": "x", "text": "y"}, {"band": "x", "tone": 3}):
            with self.subTest(band=band), self.assertRaises(PageTypeError) as refused:
                read_table([["a", "b"], band, ["c", "d"]], "table")
            self.assertIn("table: row 2", str(refused.exception))

    def test_the_heading_row_is_cells_and_something_stands_under_a_band(self) -> None:
        with self.assertRaises(PageTypeError) as refused:
            read_table([{"band": "Group"}, ["a", "b"]], "table")
        self.assertIn("heading", str(refused.exception))
        with self.assertRaises(PageTypeError) as refused:
            read_table([["a", "b"], ["c", "d"], {"band": "Group"}], "table")
        self.assertIn("row 3", str(refused.exception))

    def test_a_row_that_is_neither_a_list_nor_a_band_is_refused(self) -> None:
        with self.assertRaises(PageTypeError):
            read_table([["a", "b"], "c, d"], "table")

    def test_every_table_takes_bands(self) -> None:
        pages = {
            "under a body": build({"type": "figure", "title": "T", "figure": "dot.png", "table": ROWS}),
            "a board": board(ROWS),
            "a cell of a compose": build({"type": "compose", "title": "T",
                                          "rows": [{"cells": [{"table": ROWS}]}]}),
        }
        for where, page in pages.items():
            with self.subTest(where):
                self.assertEqual({1, 4}, set(table_of(page).bands))

    def test_a_tone_nobody_names_is_refused_where_the_grounds_are_known(self) -> None:
        with self.assertRaises((PageTypeError, ValueError)) as refused:
            board([["a", "b"], {"band": "x", "tone": "teal"}, ["c", "d"]]).build()
        self.assertIn("teal", str(refused.exception))
        named = theme_from({"grounds": {"Inside": "EAF0F8"}})
        table = table_of(board([["a", "b"], {"band": "x", "tone": "Inside"}, ["c", "d"]], named))
        self.assertEqual({1}, set(table.bands))


class WhenAPageIsHandedRowsDirectly(unittest.TestCase):
    """`Page.table` is the one place that knows the grounds, so it checks what the reading could not."""

    def test_a_table_of_one_column_is_cells_not_bands(self) -> None:
        table = table_of(board([["Name"], ["Alpha"], ["Beta"]]))
        self.assertEqual({}, table.bands)
        self.assertEqual((("Name",), ("Alpha",), ("Beta",)), table.rows)

    def test_the_heading_row_may_not_be_a_band(self) -> None:
        from pptx_agent_maker.layout.base.geometry import Rect
        from pptx_agent_maker.layout.parts.page import Page

        page = Page("T", DEFAULT)
        with self.assertRaises(ValueError) as refused:
            page.table(Rect(0, 0, 8_000_000, 2_000_000), [[Band("Group")], ["a", "b"]])
        self.assertIn("heading", str(refused.exception))
        placed = page.table(Rect(0, 0, 8_000_000, 2_000_000), [[Band("Group")], ["a", "b"]], header=False)
        self.assertGreater(placed.height, 0)


    def test_a_table_with_no_heading_row_may_begin_with_a_band_and_is_as_wide_as_its_cells(self) -> None:
        from pptx_agent_maker.layout.base.geometry import Rect
        from pptx_agent_maker.layout.parts.page import Page
        from pptx_agent_maker.write import add_page, new_deck, save

        page = Page("T", DEFAULT)
        page.figure(Rect(914400, 3_800_000, 2_000_000, 1_000_000), REPO / "tests" / "data" / "dot.png", 1.0)
        page.table(Rect(914400, 1_500_000, 8_000_000, 2_000_000), [[Band("Group")], ["a", "b", "c"]], header=False)
        deck = new_deck(DEFAULT)
        add_page(deck, page.build(), page.theme)
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(save(deck, Path(tmp) / "bare.pptx")) as archive:
                xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        self.assertEqual(3, len(re.findall(r"<a:gridCol ", xml)))
        self.assertEqual(['gridSpan="3"', 'hMerge="1"', 'hMerge="1"'], re.findall(r'gridSpan="\d"|hMerge="1"', xml))


class WhatABandIsMeasuredAs(unittest.TestCase):
    def test_a_long_band_does_not_widen_the_first_column(self) -> None:
        theme = DEFAULT
        total = 8_000_000
        short = [["Name", "Year"], ["Alpha", "2020"]]
        divided = [["Name", "Year"], [Band("A band that says a great deal more than any cell does", "")], ["Alpha", "2020"]]
        self.assertEqual(theme.column_widths(short, total), theme.column_widths(divided, total))

    def test_a_band_stands_across_the_whole_table_and_is_one_row_when_its_words_fit(self) -> None:
        theme = DEFAULT
        widths = theme.column_widths([["Name", "Year", "Output"], ["a", "b", "c"]], 8_000_000)
        flat = [["Name", "Year", "Output"], ["a", "b", "c"]]
        banded = [["Name", "Year", "Output"], [Band("A band that is longer than the first column is wide", "")],
                  ["a", "b", "c"]]
        self.assertGreater(theme.lines(banded[1][0], widths[0] - 2 * theme.spacing.cell_pad_x), 1,
                           "the words would wrap if they were set in the first column")
        self.assertEqual(theme.table_height(flat, widths) + theme.table_row_height(),
                         theme.table_height(banded, widths))

    def test_a_band_wider_than_the_table_takes_the_lines_it_needs_across_the_whole_width(self) -> None:
        theme = DEFAULT
        widths = [1_000_000, 1_000_000]
        words = "ab " * 60
        rows = [["Name", "Year"], [Band(words, "")], ["a", "b"]]
        lines = theme.wraps(words, sum(widths) - 2 * theme.spacing.cell_pad_x, bold=True)
        self.assertGreater(lines, 1)
        flat = [["Name", "Year"], ["a", "b"]]
        self.assertEqual(theme.table_height(flat, widths) + lines * theme.line_height() + 2 * theme.spacing.cell_pad_y,
                         theme.table_height(rows, widths))

    def test_the_table_the_page_places_is_as_tall_as_the_measure_said(self) -> None:
        table = table_of(board(ROWS))
        widths = DEFAULT.column_widths(read_table(ROWS, "table"), table.rect.width)
        self.assertEqual(DEFAULT.table_height(read_table(ROWS, "table"), widths), table.rect.height)
        self.assertEqual(tuple(widths), table.widths)


class HowABandIsPainted(unittest.TestCase):
    def test_a_band_without_a_tone_is_the_heading_ground_in_the_body_colour_in_both_looks(self) -> None:
        for theme in (DEFAULT, PLAIN):
            with self.subTest(look=theme.table_look):
                ground, words = table_of(board(ROWS, theme)).bands[4]
                self.assertEqual((theme.palette.wash, theme.palette.ink), (ground, words))

    def test_a_tone_that_carries_a_colour_says_it_in_the_words_of_a_plain_table(self) -> None:
        for tone in ("accent", "good", "bad"):
            with self.subTest(tone=tone):
                rows = [["a", "b"], {"band": "x", "tone": tone}, ["c", "d"]]
                ground, words = table_of(board(rows, PLAIN)).bands[1]
                self.assertEqual(getattr(PLAIN.palette, tone), words)
                self.assertEqual(PLAIN.palette.thinned(PLAIN.palette.CARD_WASH, getattr(PLAIN.palette, tone)), ground)

    def test_a_tone_that_carries_a_colour_paints_the_row_of_an_accent_table(self) -> None:
        rows = [["a", "b"], {"band": "x", "tone": "accent"}, ["c", "d"]]
        ground, words = table_of(board(rows)).bands[1]
        self.assertEqual(DEFAULT.palette.accent, ground)
        self.assertEqual(DEFAULT.palette.paper, words)

    def test_a_light_ground_is_the_ground_of_the_row_in_both_looks(self) -> None:
        for theme in (DEFAULT, PLAIN):
            for tone in ("box", "band", "tint"):
                with self.subTest(look=theme.table_look, tone=tone):
                    rows = [["a", "b"], {"band": "x", "tone": tone}, ["c", "d"]]
                    ground, words = table_of(board(rows, theme)).bands[1]
                    self.assertEqual((getattr(theme.palette, tone), theme.palette.ink), (ground, words))


class OnceBaked(unittest.TestCase):
    @staticmethod
    def bake(theme) -> tuple[str, Path]:
        return OnceBaked.bake_rows(ROWS, theme)

    @staticmethod
    def bake_rows(rows, theme) -> tuple[str, Path]:
        from pptx_agent_maker.write import add_page, new_deck, save

        tmp = tempfile.mkdtemp()
        deck = new_deck(theme)
        page = board(rows, theme)
        add_page(deck, page.build(), page.theme)
        path = save(deck, Path(tmp) / "table.pptx")
        with zipfile.ZipFile(path) as archive:
            return archive.read("ppt/slides/slide1.xml").decode("utf-8"), path

    @classmethod
    def setUpClass(cls) -> None:
        cls.plain_xml, cls.plain_deck = cls.bake(PLAIN)
        cls.accent_xml, cls.accent_deck = cls.bake(DEFAULT)

    @staticmethod
    def rows(xml: str) -> list[list[str]]:
        return [re.findall(r"<a:tc[ >].*?</a:tc>", row, re.S) for row in re.findall(r"<a:tr .*?</a:tr>", xml, re.S)]

    @staticmethod
    def fill(cell: str) -> str:
        properties = re.search(r"<a:tcPr[^>]*>(.*?)</a:tcPr>", cell, re.S).group(1)
        return re.search(r"<a:solidFill><a:srgbClr val=\"([0-9A-F]{6})\"/></a:solidFill>\s*$", properties).group(1)

    @staticmethod
    def ink(cell: str) -> str:
        return re.search(r"<a:rPr[^>]*>.*?<a:srgbClr val=\"([0-9A-F]{6})\"", cell, re.S).group(1)

    @staticmethod
    def bold(cell: str) -> str:
        return re.search(r"<a:rPr[^>]* b=\"(\d)\"", cell).group(1)

    def test_the_heading_of_a_plain_table_is_the_wash_in_the_body_colour_and_bold(self) -> None:
        p = PLAIN.palette
        for cell in self.rows(self.plain_xml)[0]:
            self.assertEqual(p.wash, self.fill(cell))
            self.assertEqual(p.ink, self.ink(cell))
            self.assertEqual("1", self.bold(cell))

    def test_every_row_under_it_stands_on_the_paper_with_no_banding(self) -> None:
        p = PLAIN.palette
        for row in (self.rows(self.plain_xml)[2], self.rows(self.plain_xml)[3], self.rows(self.plain_xml)[5]):
            for cell in row:
                self.assertEqual(p.paper, self.fill(cell))
                self.assertEqual(p.ink, self.ink(cell))
                self.assertEqual("0", self.bold(cell))

    def test_every_cell_has_a_rule_on_all_four_sides_in_the_colour_of_the_rules(self) -> None:
        for row in self.rows(self.plain_xml):
            for cell in row:
                for side in ("lnL", "lnR", "lnT", "lnB"):
                    self.assertRegex(cell, rf'<a:{side} w="{PLAIN.spacing.hairline}"[^>]*><a:solidFill>'
                                           rf'<a:srgbClr val="{PLAIN.palette.rule}"/>')

    def test_the_rules_come_before_the_ground_as_the_schema_says(self) -> None:
        """PowerPoint repairs a file whose cell properties are out of order."""
        for row in self.rows(self.plain_xml):
            for cell in row:
                properties = re.search(r"<a:tcPr[^>]*>(.*?)</a:tcPr>", cell, re.S).group(1)
                self.assertRegex(properties, r"^<a:lnL .*?</a:lnL><a:lnR .*?</a:lnR><a:lnT .*?</a:lnT>"
                                             r"<a:lnB .*?</a:lnB><a:solidFill>.*</a:solidFill>$")

    def test_a_table_of_the_look_there_always_was_gets_no_rules(self) -> None:
        for row in self.rows(self.accent_xml):
            for cell in row:
                self.assertNotRegex(cell, r"<a:ln[LRTB]\b")

    def test_a_band_is_one_cell_across_every_column(self) -> None:
        for xml in (self.plain_xml, self.accent_xml):
            rows = self.rows(xml)
            for number, words in ((1, "Group one"), (4, "Group two")):
                with self.subTest(row=number):
                    first, *spanned = rows[number]
                    self.assertEqual(3, len(rows[number]))
                    self.assertIn('gridSpan="3"', first)
                    self.assertEqual(f"<a:t>{words}</a:t>", re.search(r"<a:t>.*?</a:t>", first).group(0))
                    for cell in spanned:
                        self.assertIn('hMerge="1"', cell)
                        self.assertNotIn("<a:t>", cell)

    def test_the_words_of_a_band_are_bold_in_the_tone_it_asked_for(self) -> None:
        p = PLAIN.palette
        one, two = self.rows(self.plain_xml)[1][0], self.rows(self.plain_xml)[4][0]
        self.assertEqual(("1", p.accent), (self.bold(one), self.ink(one)))
        self.assertEqual(("1", p.ink), (self.bold(two), self.ink(two)))
        accent = DEFAULT.palette
        one = self.rows(self.accent_xml)[1][0]
        self.assertEqual((accent.accent, accent.paper, "1"), (self.fill(one), self.ink(one), self.bold(one)))

    def test_a_plain_band_is_ruled_on_every_cell_it_spans(self) -> None:
        for cell in self.rows(self.plain_xml)[1]:
            for side in ("lnL", "lnR", "lnT", "lnB"):
                self.assertIn(f"<a:{side} ", cell)

    def test_the_stripe_of_the_rows_goes_on_as_if_the_bands_were_not_there(self) -> None:
        """A band is not a row of the body: the rows under it are striped as they would be without it."""
        undivided, _path = self.bake_rows([row for row in ROWS if isinstance(row, list)], DEFAULT)
        kept = [self.fill(row[0]) for row in self.rows(undivided)]
        divided = [self.fill(row[0]) for number, row in enumerate(self.rows(self.accent_xml)) if number not in (1, 4)]
        self.assertEqual(kept, divided)
        p = DEFAULT.palette
        self.assertEqual([p.accent, p.paper, p.band, p.paper], kept)

    def test_the_checks_find_nothing_in_either_look(self) -> None:
        from pptx_agent_maker import checks

        for deck in (self.plain_deck, self.accent_deck):
            with self.subTest(deck=deck.name):
                self.assertEqual([], checks.run_all(deck))


class ARuleIsNotTheGroundOfItsCell(unittest.TestCase):
    """The rules of a cell are written before its ground; the checks read the ground, not the first colour."""

    def test_words_on_a_deep_ground_between_grey_rules_are_judged_on_the_deep_ground(self) -> None:
        from pptx_agent_maker import checks
        from pptx_agent_maker.write import add_page, new_deck, save

        rows = [["Region", "Share"], ["North", {"text": "96%", "shade": 4}], ["South", {"text": "10%", "shade": 1}]]
        with tempfile.TemporaryDirectory() as tmp:
            deck = new_deck(PLAIN)
            page = board(rows, PLAIN)
            add_page(deck, page.build(), page.theme)
            path = save(deck, Path(tmp) / "deep.pptx")
            self.assertEqual([], checks.run_all(path))
