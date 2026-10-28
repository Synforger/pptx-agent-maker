"""The report `compare` prints: a line a page, then how many pages changed."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "preview" / "src"))

from pptx_agent_maker.compare import PageDifference, changed_count, render_report  # noqa: E402

SIZE = (100, 50)


def compared(number: int, differing: int = 0) -> PageDifference:
    return PageDifference(number, SIZE, SIZE, differing)


class ReadingTheReport(unittest.TestCase):

    def test_one_line_a_page_and_the_count_of_changed_pages_last(self) -> None:
        report = render_report([compared(1), compared(2, 250), compared(3)]).splitlines()
        self.assertEqual(report, ["page 1: 0 px differ (0.0000%)",
                                  "page 2: 250 px differ (5.0000%)",
                                  "page 3: 0 px differ (0.0000%)",
                                  "changed 1 of 3 pages"])

    def test_a_page_one_deck_lacks_is_said_so_and_counts_as_changed(self) -> None:
        differences = [compared(1), PageDifference(2, SIZE, None), PageDifference(3, None, SIZE)]
        report = render_report(differences).splitlines()
        self.assertEqual(report[1], "page 2: not in the after deck")
        self.assertEqual(report[2], "page 3: not in the before deck")
        self.assertNotIn("0 px", "\n".join(report[1:3]), "a missing page was written as a count of zero")
        self.assertEqual(report[-1], "changed 2 of 3 pages")

    def test_a_page_drawn_at_another_size_says_both_sizes(self) -> None:
        report = render_report([PageDifference(1, (100, 50), (120, 50))])
        self.assertIn("page 1: drawn at another size (before 100x50, after 120x50)", report)

    def test_a_deck_that_starts_numbering_at_zero_names_the_printed_number_too(self) -> None:
        report = render_report([compared(1), compared(2, 1)], first_number=0)
        self.assertIn("page 2 (printed 1): 1 px differ", report)

    def test_a_deck_that_did_not_change_counts_no_page(self) -> None:
        self.assertEqual(changed_count([compared(1), compared(2)]), 0)


if __name__ == "__main__":
    unittest.main()
