"""A page whose requester said no figure is wanted passes the figure rule, and the build report says so.

The page writes `no_figure = "<their words>"`; the build prints one line for each page let through
(`page 2: carries no figure — <their words>`), also when the checks are skipped.
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))

from pptx_agent_maker.__main__ import main  # noqa: E402
from pptx_agent_maker.project import create  # noqa: E402
from deck.test_deck import a_specimen  # noqa: E402

TABLE_PAGE = ('[[pages]]\nkind = "declare"\ntype = "board"\ntitle = "A table"\n'
              'footer = "the sheet"\ntable = [["Column", "Value"], ["A", "1"]]\n')
WORDS = "asked for the table alone"


class TheBuildReport(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        create(self.root)
        a_specimen(self.root / "specimen.pptx", ["first"])

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def build(self, pages: str, *flags: str) -> tuple[int, str]:
        (self.root / "deck.toml").write_text(f'specimen = "specimen.pptx"\nout = "deck.pptx"\n{pages}',
                                             encoding="utf-8")
        said = io.StringIO()
        with contextlib.redirect_stdout(said), contextlib.redirect_stderr(said):
            code = main(["build", str(self.root), "deck", *flags])
        return code, said.getvalue()

    def test_a_table_alone_with_their_words_is_built_and_reported_on_one_line(self):
        _code, said = self.build(TABLE_PAGE + f'no_figure = "{WORDS}"\n')
        self.assertIn(f"page 1: carries no figure — {WORDS}", said.splitlines())
        self.assertNotIn("error", said)

    def test_each_page_let_through_has_its_own_line(self):
        pages = (TABLE_PAGE + f'no_figure = "{WORDS}"\n') * 2
        _code, said = self.build(pages)
        lines = [line for line in said.splitlines() if "carries no figure" in line]
        self.assertEqual([f"page 1: carries no figure — {WORDS}", f"page 2: carries no figure — {WORDS}"], lines)

    def test_the_line_is_there_when_the_checks_are_skipped(self):
        _code, said = self.build(TABLE_PAGE + f'no_figure = "{WORDS}"\n', "--skip-checks")
        self.assertIn(f"page 1: carries no figure — {WORDS}", said)

    def test_a_deck_with_no_such_page_prints_no_such_line(self):
        _code, said = self.build('[[pages]]\nkind = "copy"\npage = 1\n')
        self.assertNotIn("carries no figure", said)

    def test_a_table_alone_without_their_words_is_refused(self):
        code, said = self.build(TABLE_PAGE)
        self.assertEqual(1, code)
        self.assertIn("this page has no figure", said)
        self.assertNotIn("carries no figure", said)

    def test_a_third_page_without_a_figure_says_it_is_page_3_of_the_manifest(self):
        copied = '[[pages]]\nkind = "copy"\npage = 1\n'
        for flags in ((), ("--skip-checks",)):
            with self.subTest(flags=flags):
                code, said = self.build(copied * 2 + TABLE_PAGE, *flags)
                self.assertEqual(1, code)
                self.assertIn("page 3 of the manifest", said)
                self.assertIn("this page has no figure", said)

    def test_an_empty_reason_is_refused_and_says_to_write_one(self):
        for value in ('""', "1"):
            with self.subTest(value=value):
                code, said = self.build(TABLE_PAGE + f"no_figure = {value}\n")
                self.assertEqual(1, code)
                self.assertIn("words of the person who asked", said)


if __name__ == "__main__":
    unittest.main()
