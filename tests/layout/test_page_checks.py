"""The four checks of how much a declared page asks of its reader: words, boxes of one line, parts, a lead.

Each is held to a page made to hit it (= the way a deck reads when it is all words in boxes), to a page that
passes all four (= a picture that leads, a few words), and to the edge of its value.
"""

from __future__ import annotations

import contextlib
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests"))

from support.pages import build  # noqa: E402

#: this file tests the four checks, so they stay on (= `tests/conftest.py`)
PAGE_CHECKS_KEPT = True

from pptx_agent_maker.checks.declared import crowded_page, no_lead, one_line_boxes, wordy_page  # noqa: E402
from pptx_agent_maker.__main__ import main  # noqa: E402
from pptx_agent_maker.project import create  # noqa: E402
from pptx_agent_maker.project.files.manifest import Entry  # noqa: E402

CHECKS = (wordy_page, one_line_boxes, crowded_page, no_lead)
PICTURE = "dot.png"
CHART = {"kind": "column", "categories": ["Now", "Next"], "series": [{"name": "Count", "values": [1, 2]}]}


def declared(data: dict):
    """One declared page: its manifest, and the page its type built (= the rule of figures lifted, as `tests/conftest.py` does)."""
    page = {"type": "figure", "title": "A page", **data}
    manifest = SimpleNamespace(entries=(Entry(kind="declare", data=page),))
    return manifest, {1: build(page)}


def red(data: dict, config: dict | None = None) -> dict[str, str]:
    """The checks that find the page, each with what it says."""
    manifest, pages = declared(data)
    return {check.NAME: found[0].why for check in CHECKS
            if (found := check.run(manifest, None, config or {}, pages))}


def cells(*parts: dict) -> dict:
    return {"type": "compose", "rows": [{"cells": list(parts)}]}


def node(name: str) -> dict:
    return {"heading": name}


FOUR_CARDS = {"figure": PICTURE, "cards": [{"heading": f"Point {n}", "body": "a sentence that says one whole thing about it"}
                                              for n in range(4)]}
NINE_NODES = cells({"flow": {"stages": [{"name": f"Stage {s}", "nodes": [node(f"Step {s}{n}") for n in range(3)]}
                                        for s in range(3)]}}, {"figure": PICTURE})
CODE_AND_TABLE = cells({"text": "def run(page):\n    return page.build()", "role": "mono"},
                       {"table": [["Key", "Value"], *[[f"key {n}", str(n)] for n in range(12)]]},
                       {"figure": PICTURE, "weight": 0.2})


class ThePagesOfWordsInBoxes(unittest.TestCase):

    def test_four_cards_of_sentences_are_too_many_words(self):
        self.assertIn("wordy_page", red(FOUR_CARDS))

    def test_nine_boxes_of_one_line_are_a_list_in_boxes_and_too_many_parts(self):
        found = red(NINE_NODES)
        self.assertIn("one_line_boxes", found)
        self.assertIn("crowded_page", found)

    def test_code_and_a_long_table_beside_a_small_picture_have_no_lead(self):
        self.assertIn("no_lead", red(CODE_AND_TABLE))

    def test_the_refusals_say_how_many_and_the_way_out(self):
        self.assertRegex(red(FOUR_CARDS)["wordy_page"], r"\d+ characters.*120 at most.*notes")
        self.assertRegex(red(NINE_NODES)["one_line_boxes"], r"\d+ boxes hold one line.*join them into one box")
        self.assertRegex(red(NINE_NODES)["crowded_page"], r"\d+ parts.*8 at most.*split the page")
        self.assertRegex(red(CODE_AND_TABLE)["no_lead"], r"largest part.*is a table.*picture, a chart or a shape")


class TheBuildRunsThem(unittest.TestCase):
    """`build` hands the pages its types built to the checks, and a page they find stops it (= exit 1)."""

    def built(self, page: str, checks: str = "") -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "project"
            create(root)
            shutil.copy(REPO / "tests" / "data" / PICTURE, root / "assets" / PICTURE)
            settings = root / "workspace.toml"
            text = settings.read_text(encoding="utf-8")
            settings.write_text(text.replace("\n[checks]\n", "\n[checks]\n" + checks), encoding="utf-8")
            (root / "w1.toml").write_text('specimen = "specimen.pptx"\nout = "w1.pptx"\n\n' + page, encoding="utf-8")
            said = io.StringIO()
            with contextlib.redirect_stdout(said), contextlib.redirect_stderr(said):
                return main(["build", str(root), "w1"]), said.getvalue()

    PAGE = ('[[pages]]\nkind = "declare"\ntype = "figure"\ntitle = "A page"\nfigure = "dot.png"\n'
            'footer = "Source: made up"\nnote = "' + "x" * 121 + '"\n')

    def test_a_page_the_checks_find_stops_the_build(self):
        code, said = self.built(self.PAGE)
        self.assertEqual(1, code, said)
        self.assertIn("FAIL  wordy_page", said)

    def test_a_project_that_switches_the_check_off_builds(self):
        code, said = self.built(self.PAGE, "wordy_page = false\n")
        self.assertEqual(0, code, said)
        self.assertIn("ok    wordy_page", said)


class ThePagesThatPass(unittest.TestCase):

    def test_a_picture_that_leads_with_a_few_words_passes_all_four(self):
        self.assertEqual({}, red({"figure": PICTURE, "caption": "A short reading"}))

    def test_a_chart_that_leads_with_a_few_words_passes_all_four(self):
        self.assertEqual({}, red({"type": "chart", "chart": CHART, "note": "A short reading"}))

    def test_the_agenda_is_not_judged(self):
        self.assertEqual({}, red({"type": "agenda", "buckets": [["One", ["a " * 80]], ["Two", ["b"]]], "highlight": 1}))

    def test_a_project_may_switch_each_check_off(self):
        for check, data in ((wordy_page, FOUR_CARDS), (one_line_boxes, NINE_NODES), (no_lead, CODE_AND_TABLE)):
            with self.subTest(check.NAME):
                self.assertNotIn(check.NAME, red(data, {check.NAME: False}))


class TheEdgeOfEachValue(unittest.TestCase):

    def test_a_hundred_and_twenty_characters_pass_and_one_more_is_red(self):
        self.assertNotIn("wordy_page", red({"figure": PICTURE, "note": "x" * 120}))
        self.assertIn("wordy_page", red({"figure": PICTURE, "note": "x" * 121}))

    def test_spaces_are_not_counted(self):
        self.assertNotIn("wordy_page", red({"figure": PICTURE, "note": " ".join("x" * 120)}))
        self.assertIn("wordy_page", red({"figure": PICTURE, "note": " ".join("x" * 121)}))

    def test_two_boxes_of_one_line_pass_and_three_are_red(self):
        for count, expected in ((2, False), (3, True)):
            with self.subTest(count):
                found = red(cells(*[{"card": node(f"Box {n}")} for n in range(count)], {"figure": PICTURE}))
                self.assertEqual(expected, "one_line_boxes" in found)

    def test_eight_parts_pass_and_nine_are_red(self):
        for cards, expected in ((7, False), (8, True)):
            with self.subTest(cards):
                found = red({"figure": PICTURE, "card_columns": 4,
                             "cards": [{"heading": f"P{n}", "body": "words"} for n in range(cards)]})
                self.assertEqual(expected, "crowded_page" in found)


if __name__ == "__main__":
    unittest.main()
