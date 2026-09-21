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

from pptx_agent_maker import DEFAULT, Page  # noqa: E402
from pptx_agent_maker.page import Figure, Table  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
