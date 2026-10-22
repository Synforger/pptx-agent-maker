"""The small words above a title can stand beside it instead: on the title's own line, in the accent colour.

題の上の小さい字 (= 章の番号と名前) は、資料によっては題の左に同じ行で、差し色の太字で置く。資料全体の
見た目なので、決めるのは案件の `[theme]` の 1 か所 ― 頁ごとに書ける口にすると、頁によって置き場所の違う
資料ができる。字の大きさも資料全体で 1 つ (= `[theme.type] kicker`)。題より小さくしても、題と同じ段落の
頭の字として書くので、字の下の線は題と揃う。
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from dataclasses import replace  # noqa: E402

from pptx_agent_maker import DEFAULT, Page, PageFullError  # noqa: E402
from pptx_agent_maker.layout.geometry import Rect, cm  # noqa: E402
from pptx_agent_maker.layout.tokens import ThemeError, Under, theme_from  # noqa: E402

BESIDE = theme_from({"kicker": "beside"})
SMALLER = theme_from({"kicker": "beside", "type": {"kicker": 13}})
ONE = "題は結論の文で書く"
KICKER = "01 | 背景"


def placed(page: Page, kind: str):
    return next(e for e in page.elements if e.kind == kind)


class WhereTheProjectSaysIt(unittest.TestCase):
    def test_left_unsaid_the_small_words_stand_above(self) -> None:
        self.assertEqual("above", DEFAULT.kicker)
        self.assertEqual(Page(ONE, kicker=KICKER).elements, Page(ONE, theme_from({"kicker": "above"}), kicker=KICKER).elements)

    def test_a_place_nobody_knows_is_refused(self) -> None:
        for place in ("left", "", 1, True):
            with self.subTest(place=place), self.assertRaises(ThemeError) as refused:
                theme_from({"kicker": place})
            self.assertIn("theme.kicker", str(refused.exception))


class BesideTheTitle(unittest.TestCase):
    def test_the_small_words_lead_the_titles_first_line(self) -> None:
        page = Page(ONE, BESIDE, kicker=KICKER)
        title = placed(page, "title")
        self.assertFalse(any(e.kind.startswith("kicker") for e in page.elements), "no box of their own")
        self.assertEqual(KICKER, title.lead.text)
        self.assertEqual(BESIDE.kicker_lead(KICKER), title.lead.width)
        self.assertEqual(placed(Page(ONE, kicker=KICKER), "title").rect.left, title.rect.left,
                         "the title's box starts where it always did; the words stand in from it")

    def test_they_are_set_like_the_title_in_the_accent_colour(self) -> None:
        lead = placed(Page(ONE, BESIDE, kicker=KICKER), "title").lead
        self.assertEqual((DEFAULT.type.title, DEFAULT.palette.accent), (lead.size, lead.colour))

    def test_they_take_their_width_and_a_gap_before_the_title(self) -> None:
        lead = placed(Page(ONE, BESIDE, kicker=KICKER), "title").lead
        self.assertEqual(DEFAULT.spacing.text_inset + DEFAULT.width(KICKER, DEFAULT.type.title, bold=True), lead.width)

    def test_the_band_and_the_body_are_where_they_always_were(self) -> None:
        for kicker in ("", KICKER):
            with self.subTest(kicker=kicker):
                self.assertEqual(Page(ONE, kicker=kicker).body, Page(ONE, BESIDE, kicker=kicker).body)
        self.assertEqual(Page(ONE).elements, Page(ONE, BESIDE).elements, "a page with no small words is untouched")

    def test_the_title_folds_in_the_room_the_small_words_leave(self) -> None:
        nearly = "題" * 35
        self.assertEqual(1, DEFAULT.title_lines(nearly, kicker=KICKER), "above, the small words take no room")
        self.assertEqual(2, BESIDE.title_lines(nearly, kicker=KICKER))
        self.assertEqual(1, BESIDE.title_lines(nearly), "with no small words the title has the whole band")
        page = Page(nearly, BESIDE, kicker=KICKER)
        self.assertEqual(Page("題" * 60).body, page.body, "the body starts under a band of two lines")

    def test_small_words_that_leave_the_title_no_room_are_refused(self) -> None:
        with self.assertRaises(PageFullError) as refused:
            Page(ONE, BESIDE, kicker="章" * 40)
        self.assertIn("kicker", str(refused.exception))

    def test_a_sticker_still_stands_at_the_right_end(self) -> None:
        page = Page(ONE, BESIDE, kicker=KICKER, sticker="暫定")
        self.assertEqual(placed(Page(ONE, sticker="暫定"), "sticker").rect, placed(page, "sticker").rect)
        self.assertLess(placed(page, "title").rect.right, placed(page, "sticker").rect.left)


class SmallerThanTheTitle(unittest.TestCase):
    """The size of the small words is the project's to say (= `[theme.type] kicker`), wherever they stand."""

    def test_left_unsaid_they_keep_the_size_of_where_they_stand(self) -> None:
        self.assertEqual(DEFAULT.type.caption, DEFAULT.kicker_size)
        self.assertEqual(DEFAULT.type.title, BESIDE.kicker_size)

    def test_beside_the_title_they_are_set_and_measured_in_the_size_said(self) -> None:
        lead = placed(Page(ONE, SMALLER, kicker=KICKER), "title").lead
        self.assertEqual(13, lead.size)
        self.assertEqual(SMALLER.spacing.text_inset + SMALLER.width(KICKER, 13, bold=True), lead.width)
        self.assertLess(lead.width, BESIDE.kicker_lead(KICKER))

    def test_smaller_small_words_leave_the_title_more_room(self) -> None:
        title = "題" * 33
        self.assertEqual(2, BESIDE.title_lines(title, kicker=KICKER))
        self.assertEqual(1, SMALLER.title_lines(title, kicker=KICKER))

    def test_beside_the_title_their_size_does_not_move_the_band(self) -> None:
        self.assertEqual(Page(ONE, BESIDE, kicker=KICKER).body, Page(ONE, SMALLER, kicker=KICKER).body)

    def test_above_the_title_they_are_set_in_the_size_said_and_their_row_grows_with_it(self) -> None:
        above = theme_from({"type": {"kicker": 13}})
        kicker = placed(Page(ONE, above, kicker=KICKER), "kicker")
        self.assertEqual(13, kicker.size)
        self.assertEqual(round(DEFAULT.spacing.kicker_height * 13 / DEFAULT.type.caption), above.spacing.kicker_height)
        self.assertEqual(above.spacing.kicker_height, kicker.rect.height)
        self.assertEqual(DEFAULT.spacing.title_height - DEFAULT.spacing.kicker_height,
                         above.spacing.title_height - above.spacing.kicker_height, "the title's own row is untouched")

    def test_a_use_can_say_it_too(self) -> None:
        theme = theme_from({"kicker": "beside", "uses": {"headed": {"like": "read", "kicker": 13}}})
        self.assertEqual(13, theme.using("headed").kicker_size)
        self.assertEqual(theme.type.title, theme.kicker_size, "the other uses keep the title's size")

    def test_the_decks_size_reaches_every_use_it_named_that_writes_none(self) -> None:
        """実際に出た形: 資料の `[theme.type]` に 1 回書いた大きさが、名前を付けた使い方の頁にも届く。"""
        theme = theme_from({"kicker": "beside", "type": {"kicker": 13},
                            "uses": {"detail": {"like": "read", "body": 11}, "own": {"like": "read", "kicker": 11}}})
        self.assertEqual(13, theme.kicker_size)
        self.assertEqual(13, theme.using("detail").kicker_size)
        self.assertEqual(11, theme.using("own").kicker_size, "a use that writes its own keeps it")
        lead = placed(Page(ONE, theme.using("detail"), kicker=KICKER), "title").lead
        self.assertEqual(13, lead.size)

    def test_the_other_roles_of_the_deck_stay_with_the_use_it_is_set_in(self) -> None:
        theme = theme_from({"type": {"kicker": 13, "body": 14}, "uses": {"detail": {"like": "read"}}})
        self.assertEqual(DEFAULT.type.body, theme.using("detail").type.body)

    def test_the_toolkits_own_uses_keep_their_size(self) -> None:
        theme = theme_from({"kicker": "beside", "type": {"kicker": 13}})
        self.assertEqual(theme.using("present").type.title, theme.using("present").kicker_size)

    def test_a_use_whose_floor_the_decks_size_falls_below_is_said(self) -> None:
        with self.assertRaises(ThemeError) as refused:
            theme_from({"kicker": "beside", "type": {"kicker": 13}, "uses": {"shown": {"like": "present"}}})
        for said in ("theme.type.kicker", "'shown'", "[theme.uses.shown]"):
            self.assertIn(said, str(refused.exception))
        theme_from({"kicker": "beside", "type": {"kicker": 13}, "uses": {"shown": {"like": "present", "kicker": 14}}})

    def test_a_size_below_the_floor_is_refused(self) -> None:
        with self.assertRaises(ThemeError) as refused:
            theme_from({"kicker": "beside", "type": {"kicker": 8}})
        self.assertIn("kicker", str(refused.exception))


class OnceBaked(unittest.TestCase):
    def baked(self, theme) -> str:
        """The title's shape of a page with the small words beside it, as written into the file."""
        from pptx_agent_maker.write import add_page, new_deck, save

        with tempfile.TemporaryDirectory() as tmp:
            deck = new_deck(theme)
            add_page(deck, Page(ONE, theme, kicker=KICKER, needs_figure=False).build(), theme)
            with zipfile.ZipFile(save(deck, Path(tmp) / "one.pptx")) as archive:
                xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        return next(s for s in re.findall(r"<p:sp>.*?</p:sp>", xml, re.S) if f">{KICKER}<" in s)

    def run_of(self, words: str, shape: str) -> str:
        """The run that carries these words."""
        return next(run for run in re.findall(r"<a:r>.*?</a:r>", shape, re.S) if f"<a:t>{words}</a:t>" in run)

    def test_the_small_words_and_the_title_are_one_paragraph(self) -> None:
        """同じ段落の run なので、字の下の線を揃えるのは描く側。大きさが違っても揃う。"""
        shape = self.baked(SMALLER)
        self.assertEqual(1, shape.count("<a:p>"), "one paragraph in one box")
        self.assertEqual([KICKER, "\t", ONE], re.findall(r"<a:t>(.*?)</a:t>", shape, re.S))
        width = SMALLER.kicker_lead(KICKER)
        for said in (f'marL="{width}"', f'indent="{-width}"', f'<a:tab pos="{width}" algn="l"/>'):
            self.assertIn(said, shape, said)
        for said in ('sz="1300"', 'b="1"', f'<a:srgbClr val="{DEFAULT.palette.accent}"/>'):
            self.assertIn(said, self.run_of(KICKER, shape), said)
        self.assertIn(f'sz="{round(SMALLER.type.title * 100)}"', self.run_of(ONE, shape))

    def test_on_the_layouts_title_the_small_words_still_carry_their_own_look(self) -> None:
        seat = Rect(cm(1.2), cm(0.5), cm(31.5), cm(1.6))
        shape = self.baked(replace(SMALLER, under=Under(title=True, title_frame=seat)))
        self.assertIn('<p:ph type="title"/>', shape)
        for said in ('sz="1300"', 'b="1"', f'<a:srgbClr val="{DEFAULT.palette.accent}"/>'):
            self.assertIn(said, self.run_of(KICKER, shape), said)
        self.assertNotIn("srgbClr", self.run_of(ONE, shape), "the title itself keeps the template's look")

    def test_a_declared_page_counts_its_title_in_the_room_left(self) -> None:
        """題の行を数えるのは 1 か所。検査も、頁が帯を取ったのと同じ数を読む。"""
        from types import SimpleNamespace

        from pptx_agent_maker.checks.declared import long_title

        def entry(title: str):
            return SimpleNamespace(kind="declare", data={"title": title, "kicker": KICKER})

        fits_above = "題" * 72        # 2 行 (= 上に置けば通る)
        manifest = SimpleNamespace(entries=[entry(fits_above)])
        self.assertEqual([], long_title.run(manifest, DEFAULT, {}))
        self.assertEqual(1, len(long_title.run(manifest, BESIDE, {})))


if __name__ == "__main__":
    unittest.main()
