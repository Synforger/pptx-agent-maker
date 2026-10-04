"""A declared page cannot place anything outside its frame, and refuses the pages
we were told not to make.

⚠ **表と文章だけの頁**、**空のセル**、**下限を割る文字**は、人の規律では守れずに
何度も出た。ここで組めない形にしてある。
"""

from __future__ import annotations

import sys
import unittest
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pptx_agent_maker import DEFAULT, Page, PageFullError  # noqa: E402
from pptx_agent_maker.layout.parts.elements import Figure, Table  # noqa: E402


def a_page() -> Page:
    page = Page(
        "Where the wait comes from",
        kicker="02 | results",
        condition="Same request mix, three builds, one build per column",
        conclusion="Most of the wait is the first read after a deploy",
        footer="measured on the load test of the day",
    )
    left, right = page.body.columns([2, 1], gap=DEFAULT.spacing.gap_m)
    page.figure(left, "example.png", 16 / 9, caption="p95 by endpoint")
    page.table(right, [["build", "p95"], ["A", "120 ms"], ["B", "340 ms"]])
    return page


class PageTest(unittest.TestCase):
    def test_everything_stays_within_the_frame(self) -> None:
        frame = DEFAULT.frame()
        for element in a_page().build():
            with self.subTest(kind=element.kind):
                self.assertTrue(frame.contains(element.rect), f"{element.kind} left the frame")

    def test_figures_and_tables_do_not_overlap(self) -> None:
        blocks = [e for e in a_page().build() if isinstance(e, (Figure, Table))]
        for a, b in combinations(blocks, 2):
            self.assertFalse(a.rect.overlaps(b.rect))

    def test_the_same_declaration_gives_the_same_coordinates(self) -> None:
        """A page built twice is the same page — no drift between weeks."""
        first = [(e.kind, e.rect) for e in a_page().build()]
        second = [(e.kind, e.rect) for e in a_page().build()]
        self.assertEqual(first, second)

    def test_a_pictures_name_sits_just_under_it_and_takes_only_its_lines(self) -> None:
        """名の帯を枠の 7 分の 1 で取っていた間は、縦に長い枠ほど名が絵から離れて浮いた。"""
        s, t = DEFAULT.spacing, DEFAULT.type
        for aspect in (4.0, 1.0, 0.5):
            with self.subTest(aspect):
                page = Page("A picture")
                page.figure(page.body, Path("a.png"), aspect, caption="what it shows")
                picture = next(e for e in page.build() if isinstance(e, Figure)).rect
                name = next(e for e in page.build() if e.kind == "caption").rect
                self.assertEqual(picture.bottom + s.gap_s, name.top)
                self.assertEqual(DEFAULT.line_height(t.caption), name.height)
                self.assertLessEqual(name.bottom, page.body.bottom)
                if aspect <= 1.0:
                    # 縦で決まる絵は、名の 1 行ぶんを除いた高さを全部使う
                    self.assertAlmostEqual(page.body.height - s.gap_s - name.height, picture.height, delta=2)

    def test_a_long_name_under_a_picture_takes_the_lines_it_needs(self) -> None:
        page = Page("A picture")
        text = "a name under a picture long enough to break over more than one line " * 4
        page.figure(page.body, Path("a.png"), 1.0, caption=text)
        name = next(e for e in page.build() if e.kind == "caption").rect
        self.assertGreater(name.height, DEFAULT.line_height(DEFAULT.type.caption))
        self.assertLessEqual(name.bottom, page.body.bottom)

    def test_a_page_without_a_figure_is_refused(self) -> None:
        page = Page("Numbers only")
        page.table(page.body, [["a", "b"], ["1", "2"]])
        with self.assertRaises(ValueError):
            page.build()

    def test_an_empty_cell_is_refused(self) -> None:
        page = Page("Scores")
        with self.assertRaises(ValueError):
            page.table(page.body, [["method", "score"], ["A", ""]])

    def test_type_below_the_floor_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            DEFAULT.pt(DEFAULT.type.minimum - 1)

    def test_the_frame_cannot_be_cut_after_body_is_handed_out(self) -> None:
        """The bug that put a band on top of a table: bands are all declared up front."""
        page = a_page()
        with self.assertRaises(RuntimeError):
            page._band("late band", conclusion=True)

    def test_bands_and_footer_never_overlap_the_body(self) -> None:
        """The frame's own furniture sits outside the area pages divide up."""
        page = a_page()
        furniture = {"title", "kicker", "rule", "band", "band_text", "footer"}
        for element in page.elements:
            if element.kind not in furniture:
                continue
            with self.subTest(kind=element.kind):
                self.assertFalse(page.body.overlaps(element.rect))

    def test_a_table_too_tall_for_its_area_is_refused(self) -> None:
        """A table does not shrink: PowerPoint grows the frame and it leaves the page."""
        page = a_page()
        narrow = page.body.rows(6)[0]
        with self.assertRaises(ValueError):
            page.table(narrow, [["a", "b"]] * 12)


class TheTitleBand(unittest.TestCase):
    """⚠ **題の帯を 1 行ぶんで固定していた間は、2 行に折れた題が本体の最初の物に重なった。**枠どうしは
    離れているので、重なりの検査は掴まない ― 字は枠の頭から下へ、折れた行ぶん伸びる。"""

    #: 24pt で 1 行に入るのは全角 36 字ほど
    ONE = "題は結論の文で書く"
    FOLDED = {2: "題は結論の文で書くので長くなりやすい。" * 3, 3: "題は結論の文で書くので長くなりやすい。" * 5}

    @staticmethod
    def _placed(page: Page, kind: str):
        return next(e for e in page.elements if e.kind == kind).rect

    def _reach(self, page: Page, lines: int) -> int:
        """Where the title's last line ends: its box's top, and a line of type for every line."""
        return self._placed(page, "title").top + lines * DEFAULT.line_height(DEFAULT.type.title)

    def test_the_sentences_chosen_fold_the_way_this_class_says(self) -> None:
        self.assertEqual(1, DEFAULT.title_lines(self.ONE))
        for lines, title in self.FOLDED.items():
            self.assertEqual(lines, DEFAULT.title_lines(title))

    def test_a_title_on_one_line_keeps_the_band_it_always_had(self) -> None:
        s = DEFAULT.spacing
        for kicker in ("", "01 | 背景"):
            with self.subTest(kicker=kicker):
                page = Page(self.ONE, kicker=kicker)
                self.assertEqual(DEFAULT.frame().top + s.title_height, self._placed(page, "rule").top)
                self.assertEqual(DEFAULT.frame().top + s.title_height + s.gap_m, page.body.top)

    def test_each_line_a_title_folds_to_moves_the_body_down_by_one_line(self) -> None:
        line = DEFAULT.line_height(DEFAULT.type.title)
        for kicker in ("", "01 | 背景"):
            top = Page(self.ONE, kicker=kicker).body.top
            for lines, title in self.FOLDED.items():
                with self.subTest(kicker=kicker, lines=lines):
                    self.assertEqual(top + (lines - 1) * line, Page(title, kicker=kicker).body.top)

    def test_a_folded_title_ends_as_far_above_the_body_as_a_title_on_one_line(self) -> None:
        for kicker in ("", "01 | 背景"):
            one = Page(self.ONE, kicker=kicker)
            clear = one.body.top - self._reach(one, 1)
            self.assertGreater(clear, 0)
            for lines, title in self.FOLDED.items():
                with self.subTest(kicker=kicker, lines=lines):
                    page = Page(title, kicker=kicker)
                    self.assertEqual(clear, page.body.top - self._reach(page, lines))

    def test_the_titles_box_runs_down_to_the_line_under_it(self) -> None:
        for kicker in ("", "01 | 背景"):
            for title in (self.ONE, *self.FOLDED.values()):
                with self.subTest(kicker=kicker, title=title[:12]):
                    page = Page(title, kicker=kicker)
                    self.assertEqual(self._placed(page, "rule").top, self._placed(page, "title").bottom)

    def test_the_small_words_above_a_title_stay_where_they_were(self) -> None:
        one = self._placed(Page(self.ONE, kicker="01 | 背景"), "kicker")
        for lines, title in self.FOLDED.items():
            with self.subTest(lines=lines):
                self.assertEqual(one, self._placed(Page(title, kicker="01 | 背景"), "kicker"))

    def test_a_title_a_few_characters_past_the_frame_folds(self) -> None:
        """題が使える幅は枠の幅 (= 頁の余白と、文字の枠の左右の余白を除く)。頁の幅で数えると、
        端の数文字が折れるのに 1 行と数える。"""
        em = DEFAULT.type.title * 12700
        room = DEFAULT.frame().width - 2 * DEFAULT.spacing.text_inset
        fits = int(room / (em * 1.0))          # 全角は太字でも 1 文字ぶん
        self.assertGreater(int(DEFAULT.slide.width / em), fits + 1,
                           "the slide is no wider than the frame by two characters")
        self.assertEqual(Page("字" * fits).body.top, Page(self.ONE).body.top)
        self.assertGreater(Page("字" * (fits + 1)).body.top, Page(self.ONE).body.top)

    def test_a_title_is_counted_in_the_weight_it_is_set_in(self) -> None:
        """題は太字で置く。同じ文でも太字は広く、細字で数えると折れる行を 1 行と数える。"""
        title = " ".join(["mmmm"] * 8)
        room = DEFAULT.frame().width - 2 * DEFAULT.spacing.text_inset
        self.assertEqual(1, DEFAULT.wraps(title, room, DEFAULT.type.title),
                         "the sentence chosen does not sit on the boundary this test is about")
        self.assertGreater(Page(title).body.top, Page(self.ONE).body.top)

    def test_a_title_too_long_for_the_page_is_refused_not_shrunk(self) -> None:
        with self.assertRaises(PageFullError):
            Page("題は結論の文で書くので長くなりやすい。" * 40)


if __name__ == "__main__":
    unittest.main()
