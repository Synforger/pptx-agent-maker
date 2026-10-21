"""A picture squeezed by height stops below a floor; a use may lower the floor for line drawings that read small."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pptx_agent_maker import DEFAULT, cm  # noqa: E402
from pptx_agent_maker.layout.base.geometry import Rect  # noqa: E402
from pptx_agent_maker.layout.base.tokens import SPACED, TIGHTENED, theme_from  # noqa: E402
from pptx_agent_maker.layout.parts.page import Page, PageFullError  # noqa: E402

WIDE = Path(__file__).resolve().parent / "data" / "wide.png"     # 16 x 4


def squeezed(theme, height):
    """A wide picture in a cell much wider than it, so its height is what holds it."""
    page = Page("A page", theme)
    return page.figure(Rect(page.body.left, page.body.top, cm(20), height), WIDE, 4.0)


class TheFloorOfAPicture(unittest.TestCase):

    def test_unsaid_it_is_the_side_of_an_icon(self) -> None:
        self.assertEqual(DEFAULT.spacing.icon, DEFAULT.spacing.figure_floor)
        with self.assertRaises(PageFullError):
            squeezed(DEFAULT, cm(0.5))
        squeezed(DEFAULT, cm(1.3))

    def test_a_use_may_lower_it(self) -> None:
        theme = theme_from({"uses": {"marks": {"like": "read", "spacing": {"figure_floor": 0.4}}}}).using("marks")
        self.assertEqual(cm(0.5), squeezed(theme, cm(0.5)).height)
        with self.assertRaises(PageFullError):
            squeezed(theme, cm(0.3))

    def test_it_is_written_and_scaled_like_the_other_distances(self) -> None:
        self.assertIn("figure_floor", SPACED)
        self.assertIn("figure_floor", TIGHTENED)


if __name__ == "__main__":
    unittest.main()
