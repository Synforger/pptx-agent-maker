"""Telling a person that a deck names a typeface this machine does not have.

LibreOffice は無い書体を描くたびに別の書体で置き換えることがあり、字のある頁は、何も変えていない
資料同士でも画素が違う。それを知らされないと「頁が変わった」と読んでしまう。ここは、どの書体を
名指しているかを読むこと、無い書体を見分けること、数も終わりの code も変えずに 1 行だけ出すことを見る。
"""

from __future__ import annotations

import io
import os
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.util import Inches

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "preview" / "src"))

from pptx_agent_maker.__main__ import main  # noqa: E402
from pptx_agent_maker.compare import (PageDifference, fonts_named, missing_fonts,  # noqa: E402
                                      render_font_note)
from pptx_agent_maker.compare.font_match import is_installed  # noqa: E402

#: `fc-match` の代わり。`Meiryo` には別の書体 (= Verdana) を答え、ほかは頼まれた名前をそのまま答える
FAKE_FC_MATCH = """#!/bin/sh
for last; do :; done
case "$last" in
  Meiryo) printf 'Verdana' ;;
  "Yu Gothic") printf 'YuGothic,游ゴシック体' ;;
  *) printf '%s' "$last" ;;
esac
"""


def write_deck(path: Path, *, latin: str | None = None, east_asian: str | None = None) -> Path:
    """A deck with one text box whose run names the given typefaces (= none, when None)."""
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    run = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(3), Inches(1)).text_frame.paragraphs[0].add_run()
    run.text = "words"
    if latin:
        run.font.name = latin
    if east_asian:
        properties = run._r.get_or_add_rPr()
        properties.append(properties.makeelement(qn("a:ea"), {"typeface": east_asian}))
    deck.save(str(path))
    return path


class ReadingTheTypefacesADeckNames(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_the_typefaces_the_words_of_the_pages_name_are_read_latin_and_east_asian(self) -> None:
        deck = write_deck(self.folder / "deck.pptx", latin="Plain Face", east_asian="Wide Face")
        self.assertEqual(fonts_named(deck), {"Plain Face", "Wide Face"})

    def test_a_deck_whose_words_name_no_typeface_names_none(self) -> None:
        self.assertEqual(fonts_named(write_deck(self.folder / "deck.pptx")), set())

    def test_a_typeface_the_words_take_from_the_theme_is_the_theme_s_typeface(self) -> None:
        deck = write_deck(self.folder / "deck.pptx", latin="+mn-lt")
        self.assertEqual(fonts_named(deck), {"Calibri"}, "the reference stood as it was, or was dropped")


class TellingWhichTypefacesAreMissing(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        fake = self.folder / "bin" / "fc-match"
        fake.parent.mkdir()
        fake.write_text(FAKE_FC_MATCH, encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        self.path = str(fake.parent)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_a_typeface_fc_match_answers_with_another_one_is_missing(self) -> None:
        with mock.patch.dict(os.environ, {"PATH": self.path}):
            self.assertEqual(missing_fonts({"Meiryo", "Arial"}), ["Meiryo"])

    def test_a_typeface_it_answers_with_the_same_family_under_another_spelling_is_there(self) -> None:
        with mock.patch.dict(os.environ, {"PATH": self.path}):
            self.assertEqual(missing_fonts({"Yu Gothic"}), [])

    def test_a_machine_without_fc_match_is_not_guessed_about(self) -> None:
        with mock.patch.dict(os.environ, {"PATH": str(self.folder)}):
            self.assertIsNone(missing_fonts({"Meiryo"}))

    def test_a_deck_naming_no_typeface_needs_no_fc_match(self) -> None:
        with mock.patch.dict(os.environ, {"PATH": str(self.folder)}):
            self.assertEqual(missing_fonts(set()), [])


class SpellingsOfOneFamily(unittest.TestCase):

    def test_case_spaces_and_hyphens_do_not_tell_families_apart(self) -> None:
        for requested, answered in [("Yu Gothic", ["YuGothic", "游ゴシック体"]), ("hiragino sans", ["Hiragino Sans"]),
                                    ("Noto-Sans", ["Noto Sans"])]:
            with self.subTest(requested=requested):
                self.assertTrue(is_installed(requested, answered))

    def test_a_stand_in_is_not_the_typeface(self) -> None:
        self.assertFalse(is_installed("Meiryo", ["Verdana"]))


class TheNoteTheCommandPrints(unittest.TestCase):

    def test_missing_typefaces_make_one_line_saying_why_pages_with_words_may_differ(self) -> None:
        note = render_font_note(["Consolas", "Meiryo"])
        self.assertEqual(note, "note: a deck names Consolas, Meiryo, which this machine does not have: LibreOffice "
                               "draws its words in a stand-in face that can change from one run to the next, so "
                               "pages with words may differ when nothing changed")

    def test_nothing_is_said_when_no_typeface_is_missing(self) -> None:
        self.assertIsNone(render_font_note([]))

    def test_a_machine_without_fc_match_says_so_in_one_line(self) -> None:
        note = render_font_note(None)
        self.assertIn("fc-match is not on this machine", note)
        self.assertNotIn("\n", note)


class TheCommandAndTheNote(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        folder = Path(self.tmp.name)
        fake = folder / "bin" / "fc-match"
        fake.parent.mkdir()
        fake.write_text(FAKE_FC_MATCH, encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        self.path = str(fake.parent)
        self.missing = write_deck(folder / "missing.pptx", latin="Meiryo")
        self.there = write_deck(folder / "there.pptx", latin="Arial")
        # 絵にする所は別の試験が実物で見る。ここは知らせの配線だけを、絵にせずに見る
        same_size = (100, 50)
        self.unchanged = [PageDifference(1, same_size, same_size, 0)]
        self.changed = [PageDifference(1, same_size, same_size, 7)]

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self, found: list[PageDifference], *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with (mock.patch.dict(os.environ, {"PATH": self.path}),
              mock.patch("pptx_agent_maker.compare.compare_decks", return_value=found),
              redirect_stdout(out), redirect_stderr(err)):
            code = main(["compare", *argv])
        return code, out.getvalue(), err.getvalue()

    def test_a_deck_naming_a_missing_typeface_is_told_on_the_error_stream_and_the_report_is_as_it_was(self) -> None:
        code, said, complained = self._run(self.unchanged, str(self.missing), str(self.missing))
        self.assertEqual(code, 0, "the note changed the end code")
        self.assertEqual(said.splitlines(), ["page 1: 0 px differ (0.0000%)", "changed 0 of 1 pages"])
        self.assertEqual(complained.splitlines(), [render_font_note(["Meiryo"])])

    def test_the_end_code_for_a_changed_page_stays_1_with_the_note(self) -> None:
        code, said, complained = self._run(self.changed, str(self.missing), str(self.missing))
        self.assertEqual(code, 1)
        self.assertIn("changed 1 of 1 pages", said)
        self.assertIn("Meiryo", complained)

    def test_a_missing_typeface_in_either_deck_is_told(self) -> None:
        _, _, complained = self._run(self.unchanged, str(self.there), str(self.missing))
        self.assertIn("a deck names Meiryo", complained)

    def test_decks_whose_typefaces_are_all_there_print_no_note(self) -> None:
        _, _, complained = self._run(self.unchanged, str(self.there), str(self.there))
        self.assertEqual(complained, "")


if __name__ == "__main__":
    unittest.main()
