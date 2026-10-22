"""The gap under the title stands apart from the gap between the bands and the body.

題と条件の帯の間は広く、条件の帯と本体の間は詰める頁がある。どちらも `band_gap` 1 つで決めていた間は、
片方に合わせるともう片方がずれ、狭めた方の頁では道のりの段が入らずに止まった。
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pptx_agent_maker import DEFAULT, cm  # noqa: E402
from pptx_agent_maker.layout.geometry import Rect  # noqa: E402
from pptx_agent_maker.layout.tokens import SPACED, TIGHTENED, Under, theme_from  # noqa: E402
from pptx_agent_maker.layout.parts.page import Page  # noqa: E402

FRAME = {"condition": "A condition", "conclusion": "A conclusion", "footer": "A source"}


def using(**spacing):
    return theme_from({"uses": {"spaced": {"like": "read", "spacing": spacing}}}).using("spaced")


def body(theme):
    return Page("A page", theme, **FRAME).body


def condition_band(theme):
    page = Page("A page", theme, **FRAME)
    return next(element.rect for element in page.elements if element.kind == "band")


class TheGapUnderTheTitle(unittest.TestCase):

    def test_it_moves_the_condition_band_and_the_body_by_the_same_and_nothing_at_the_bottom(self) -> None:
        extra = cm(1.0) - DEFAULT.spacing.gap_m
        theme = using(title_gap=1.0)
        self.assertEqual(condition_band(DEFAULT).top + extra, condition_band(theme).top)
        self.assertEqual(body(DEFAULT).top + extra, body(theme).top)
        self.assertEqual(body(DEFAULT).bottom, body(theme).bottom)

    def test_the_gap_under_the_condition_band_stays_band_gap(self) -> None:
        theme = using(title_gap=1.0, band_gap=0.3)
        self.assertEqual(condition_band(theme).bottom + cm(0.3), body(theme).top)

    def test_unsaid_it_follows_band_gap_and_band_gap_follows_gap_m(self) -> None:
        self.assertEqual(cm(0.3), using(band_gap=0.3).spacing.title_gap)
        self.assertEqual(cm(0.2), using(gap_m=0.2).spacing.title_gap)
        self.assertEqual(cm(0.9), using(gap_m=0.2, band_gap=0.3, title_gap=0.9).spacing.title_gap)
        self.assertEqual(DEFAULT.spacing.band_gap, DEFAULT.spacing.title_gap)

    def test_a_page_whose_title_the_layout_places_is_set_the_same_way(self) -> None:
        seat = Rect(cm(1.2), cm(0.9), cm(20), cm(1.5))
        theme = replace(using(title_gap=1.4, band_gap=0.3), under=Under(title=True, title_frame=seat))
        self.assertEqual(seat.bottom + cm(1.4), Page("A page", theme).body.top)

    def test_it_follows_the_scale_and_a_use_may_write_it(self) -> None:
        self.assertIn("title_gap", SPACED)
        self.assertIn("title_gap", TIGHTENED)
        half = theme_from({"uses": {"spaced": {"like": "read", "spacing": {"scale": 0.5}}}}).using("spaced")
        self.assertEqual(round(DEFAULT.spacing.title_gap * 0.5), half.spacing.title_gap)


if __name__ == "__main__":
    unittest.main()
