"""broken_words: a word wider than the room its box has for words is told, since it breaks in the middle.

見張るのは 5 つ ― 字の枠でも表のマスでも、語が字の使える幅より広ければ言い、収まれば言わないこと、折れてよい所
(= 空白・ハイフン・スラッシュ・全角の字) で割ってから測ること、折らない枠と大きさの分からない字は言わないこと、
宣言で組んだ頁の狭い列の札で実際に言うこと、止めずに知らせること。
"""

from __future__ import annotations

#: written when a page of words in boxes alone could be built (= `tests/conftest.py`)
FIGURE_RULE_LIFTED = True


import sys
import tempfile
import unittest
from pathlib import Path

from pptx import Presentation
from pptx.util import Emu, Pt

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))

from support.pages import build  # noqa: E402
from pptx_agent_maker.checks import stopping  # noqa: E402
from pptx_agent_maker.checks.rules import broken_words  # noqa: E402
from pptx_agent_maker.write import add_page, new_deck, save  # noqa: E402

#: 1 cm = 360000 EMU
CM = 360000
#: 12pt の英大文字 9 字が 1 行に入らない幅と、入る幅 (= 左右の内余白 0.254 cm を含む)
NARROW, WIDE = 2 * CM, 8 * CM


class Fixture(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def box(self, words: str, width: int, *, size: float | None = 12, wrap: bool = True) -> list:
        """The findings over a deck of one text box of that width holding these words."""
        deck = Presentation()
        slide = deck.slides.add_slide(deck.slide_layouts[6])
        frame = slide.shapes.add_textbox(Emu(CM), Emu(CM), Emu(width), Emu(2 * CM)).text_frame
        frame.word_wrap = wrap
        run = frame.paragraphs[0].add_run()
        run.text = words
        if size is not None:
            run.font.size = Pt(size)
        return self.found(deck)

    def table(self, rows: list[list[str]], widths: list[int], *, merge: tuple[int, int] | None = None) -> list:
        """The findings over a deck of one table with columns of these widths (= `merge` joins two cells of row 1)."""
        deck = Presentation()
        slide = deck.slides.add_slide(deck.slide_layouts[6])
        shape = slide.shapes.add_table(len(rows), len(widths), Emu(CM), Emu(CM), Emu(sum(widths)), Emu(2 * CM))
        for index, width in enumerate(widths):
            shape.table.columns[index].width = Emu(width)
        for r, cells in enumerate(rows):
            for c, words in enumerate(cells):
                cell = shape.table.cell(r, c)
                cell.text = words
                for run in cell.text_frame.paragraphs[0].runs:
                    run.font.size = Pt(12)
        if merge:
            shape.table.cell(0, merge[0]).merge(shape.table.cell(0, merge[1]))
        return self.found(deck)

    def found(self, deck) -> list:
        path = Path(self.tmp.name) / "deck.pptx"
        deck.save(path)
        return broken_words.run(path, {})


class AWordInATextBox(Fixture):
    def test_a_word_wider_than_the_box_is_told_with_its_width_and_the_room(self) -> None:
        (hit,) = self.box("ABCDEFGHI", NARROW)
        self.assertEqual(("broken_words", 1, "'ABCDEFGHI'"), (hit.check, hit.page, hit.what))
        self.assertRegex(hit.why, r"is \d\.\d\d cm wide and its box has 1\.49 cm for words")

    def test_the_same_word_in_a_wide_box_and_short_words_in_a_narrow_one_are_not_told(self) -> None:
        self.assertEqual([], self.box("ABCDEFGHI", WIDE))
        self.assertEqual([], self.box("AB CD EF GH", NARROW))

    def test_full_width_letters_break_anywhere_and_are_not_told(self) -> None:
        self.assertEqual([], self.box("全角の字は一字ずつ折れてよい長い文", NARROW))

    def test_a_word_is_split_after_a_hyphen_and_a_slash_before_it_is_measured(self) -> None:
        self.assertEqual([], self.box("ABC-DEF-GHI/JKL", NARROW))
        (hit,) = self.box("ABCDEFGHI-JK", NARROW)
        self.assertEqual("'ABCDEFGHI-'", hit.what)

    def test_a_box_that_does_not_wrap_and_a_run_of_no_size_are_not_told(self) -> None:
        self.assertEqual([], self.box("ABCDEFGHI", NARROW, wrap=False))
        self.assertEqual([], self.box("ABCDEFGHI", NARROW, size=None))


class AWordInATable(Fixture):
    def test_a_word_wider_than_its_column_is_told_and_one_that_fits_is_not(self) -> None:
        (hit,) = self.table([["Name", "Kind"], ["ABCDEFGHIJ", "x"]], [NARROW, WIDE])
        self.assertEqual("'ABCDEFGHIJ'", hit.what)
        self.assertEqual([], self.table([["Name", "Kind"], ["x", "ABCDEFGHIJ"]], [NARROW, WIDE]))

    def test_a_cell_across_two_columns_has_the_room_of_both(self) -> None:
        self.assertEqual([], self.table([["ABCDEFGHIJ", ""], ["a", "b"]], [NARROW, NARROW], merge=(0, 1)))


class ABuiltPage(Fixture):
    def test_the_heading_of_a_card_in_a_narrow_column_is_told_and_in_a_wide_one_it_is_not(self) -> None:
        def page(*others: str) -> list:
            cells = [{"card": {"heading": "ABCDEFGHI", "body": "x"}}] + [{"card": {"heading": o, "body": "y"}} for o in others]
            deck = new_deck()
            add_page(deck, build({"type": "compose", "title": "A page", "rows": [{"cells": cells}]}).build())
            return broken_words.run(save(deck, Path(self.tmp.name) / "built.pptx"), {})

        self.assertEqual(["'ABCDEFGHI'"], [hit.what for hit in page(*[f"c{i}" for i in range(7)])])
        self.assertEqual([], page("c1"))


class HowItIsTold(Fixture):
    def test_it_does_not_stop_a_build_and_a_project_may_switch_it_off(self) -> None:
        hits = self.box("ABCDEFGHI", NARROW)
        self.assertTrue(hits)
        self.assertEqual([], stopping(hits))
        self.assertEqual([], broken_words.run(Path(self.tmp.name) / "deck.pptx", {"broken_words": False}))


if __name__ == "__main__":
    unittest.main()
