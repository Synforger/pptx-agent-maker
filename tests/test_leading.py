"""A deck or a use may write the height of a line; the layout counts with it and the writer sets it.

⚠ **書かなければ今まで** ― 見積りは 1.45 倍、行間は書体任せ。書いた時は、見積りと書き出しの行間が同じ値になり、
描かれる行の高さが書体に依らない (= 1 行が 1.2 倍の書体で、2 行の箱が骨組みより背高になった)。
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support.pages import build  # noqa: E402
from pptx_agent_maker import DEFAULT  # noqa: E402
from pptx_agent_maker.layout.base.geometry import pt  # noqa: E402
from pptx_agent_maker.layout.base.tokens import LEADING, ThemeError, theme_from  # noqa: E402
from pptx_agent_maker.write import add_page, new_deck, save  # noqa: E402

PAGE = {"type": "cards", "title": "A page", "cards": [["One", "two\nthree"]], "table": [["a", "b"], ["c", "d"]]}


def written(theme) -> str:
    page = build(PAGE, theme)
    deck = new_deck(theme)
    add_page(deck, page.build(), page.theme)
    with tempfile.TemporaryDirectory() as tmp:
        return zipfile.ZipFile(save(deck, Path(tmp) / "deck.pptx")).read("ppt/slides/slide1.xml").decode("utf-8")


class TheHeightOfALine(unittest.TestCase):

    def test_unsaid_the_layout_counts_as_before_and_the_typeface_sets_the_spacing(self) -> None:
        self.assertEqual(round(pt(DEFAULT.type.body) * LEADING), DEFAULT.line_height())
        self.assertNotIn("<a:lnSpc>", written(DEFAULT))

    def test_a_deck_that_writes_it_counts_with_it_and_sets_every_paragraph_to_it(self) -> None:
        theme = theme_from({"leading": 1.2})
        self.assertEqual(round(pt(theme.type.body) * 1.2), theme.line_height())
        xml = written(theme)
        spacings = re.findall(r'<a:lnSpc><a:spcPts val="(\d+)"/></a:lnSpc>', xml)
        self.assertTrue(spacings)
        self.assertIn(str(round(theme.type.body * 1.2 * 100)), spacings, "the body's lines are not set at 1.2")

    def test_a_use_writes_its_own_and_a_use_that_does_not_follows_the_deck(self) -> None:
        settings = {"leading": 1.3, "uses": {"tight": {"like": "read", "leading": 1.15}, "plain": {"like": "read"}}}
        theme = theme_from(settings)
        body = pt(theme.type.body)
        self.assertEqual(round(body * 1.15), theme.using("tight").line_height())
        self.assertEqual(round(body * 1.3), theme.using("plain").line_height())

    def test_a_height_out_of_reach_is_refused(self) -> None:
        for value in (0.8, 2.5, True, "1.2"):
            with self.subTest(value=value), self.assertRaises(ThemeError):
                theme_from({"leading": value})
        with self.assertRaises(ThemeError):
            theme_from({"uses": {"u": {"like": "read", "leading": 3}}})


if __name__ == "__main__":
    unittest.main()
