"""The small words above a title can stand beside it instead: on the title's own line, in the accent colour.

題の上の小さい字 (= 章の番号と名前) は、資料によっては題の左に同じ行で、差し色の太字で置く。資料全体の
見た目なので、決めるのは案件の `[theme]` の 1 か所 ― 頁ごとに書ける口にすると、頁によって置き場所の違う
資料ができる。
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

from pptx_agent_maker import DEFAULT, Page, PageFullError  # noqa: E402
from pptx_agent_maker.layout.base.tokens import ThemeError, theme_from  # noqa: E402

BESIDE = theme_from({"kicker": "beside"})
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
    def test_the_small_words_stand_on_the_titles_line_before_it(self) -> None:
        page = Page(ONE, BESIDE, kicker=KICKER)
        kicker, title = placed(page, "kicker_beside"), placed(page, "title")
        self.assertFalse(any(e.kind == "kicker" for e in page.elements))
        self.assertLess(kicker.rect.left, title.rect.left)
        self.assertLessEqual(kicker.rect.right, title.rect.left)
        middle = title.rect.top + title.rect.height // 2
        self.assertEqual(middle, kicker.rect.top + kicker.rect.height // 2)

    def test_they_are_set_like_the_title_in_the_accent_colour(self) -> None:
        kicker = placed(Page(ONE, BESIDE, kicker=KICKER), "kicker_beside")
        self.assertEqual((DEFAULT.type.title, DEFAULT.palette.accent, True), (kicker.size, kicker.colour, kicker.bold))

    def test_their_box_is_as_wide_as_they_run(self) -> None:
        kicker = placed(Page(ONE, BESIDE, kicker=KICKER), "kicker_beside")
        self.assertEqual(DEFAULT.width(KICKER, DEFAULT.type.title, bold=True), kicker.rect.width)

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

    def test_beside_a_folded_title_they_stand_on_its_first_line(self) -> None:
        page = Page("題" * 60, BESIDE, kicker=KICKER)
        kicker, title = placed(page, "kicker_beside"), placed(page, "title")
        line = BESIDE.line_height(BESIDE.type.title)
        block_top = title.rect.top + (title.rect.height - 2 * line) // 2
        self.assertEqual(block_top + line // 2, kicker.rect.top + kicker.rect.height // 2)

    def test_small_words_that_leave_the_title_no_room_are_refused(self) -> None:
        with self.assertRaises(PageFullError) as refused:
            Page(ONE, BESIDE, kicker="章" * 40)
        self.assertIn("kicker", str(refused.exception))

    def test_a_sticker_still_stands_at_the_right_end(self) -> None:
        page = Page(ONE, BESIDE, kicker=KICKER, sticker="暫定")
        self.assertEqual(placed(Page(ONE, sticker="暫定"), "sticker").rect, placed(page, "sticker").rect)
        self.assertLess(placed(page, "title").rect.right, placed(page, "sticker").rect.left)


class OnceBaked(unittest.TestCase):
    def test_the_small_words_are_one_unwrapped_line_centred_on_the_titles(self) -> None:
        from pptx_agent_maker.write import add_page, new_deck, save

        with tempfile.TemporaryDirectory() as tmp:
            deck = new_deck(BESIDE)
            add_page(deck, Page(ONE, BESIDE, kicker=KICKER, needs_figure=False).build(), BESIDE)
            with zipfile.ZipFile(save(deck, Path(tmp) / "one.pptx")) as archive:
                xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        shape = next(s for s in re.findall(r"<p:sp>.*?</p:sp>", xml, re.S) if f">{KICKER}<" in s)
        for said in ('wrap="none"', 'anchor="ctr"', 'lIns="0"', "<a:noAutofit/>", ' b="1"',
                     f'<a:srgbClr val="{DEFAULT.palette.accent}"/>'):
            self.assertIn(said, shape, said)

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
