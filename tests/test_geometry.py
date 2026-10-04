"""Dividing a rectangle must never produce one that escapes it.

⚠ ここが崩れると、頁を組んでから枠外れを探す形に戻る。端数の出る割り方
(= 3 等分・重みつき・隙間つき) を混ぜて確かめる。
"""

from __future__ import annotations

import sys
import unittest
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pptx_agent_maker.layout.base.geometry import Rect, cm  # noqa: E402

PARENT = Rect(0, 0, 12192000, 6858000)
DIVISIONS = [
    (3, 0), (3, cm(0.5)), (7, cm(0.3)),
    ([2, 1], cm(0.6)), ([1, 1, 2, 3], cm(0.25)), ([1.5, 1], 0),
]


class DivisionTest(unittest.TestCase):
    def test_parts_stay_inside_the_parent(self) -> None:
        for weights, gap in DIVISIONS:
            for parts in (PARENT.columns(weights, gap), PARENT.rows(weights, gap)):
                with self.subTest(weights=weights, gap=gap):
                    for part in parts:
                        self.assertTrue(PARENT.contains(part), f"{part} escaped {PARENT}")

    def test_siblings_never_overlap(self) -> None:
        for weights, gap in DIVISIONS:
            for parts in (PARENT.columns(weights, gap), PARENT.rows(weights, gap)):
                with self.subTest(weights=weights, gap=gap):
                    for a, b in combinations(parts, 2):
                        self.assertFalse(a.overlaps(b), f"{a} overlaps {b}")

    def test_the_last_part_reaches_the_parent_edge(self) -> None:
        """Rounding must not leave a sliver: 3 equal columns of an odd width still fill it."""
        for weights, gap in DIVISIONS:
            with self.subTest(weights=weights, gap=gap):
                self.assertEqual(PARENT.columns(weights, gap)[-1].right, PARENT.right)
                self.assertEqual(PARENT.rows(weights, gap)[-1].bottom, PARENT.bottom)

    def test_a_grid_keeps_every_cell_inside(self) -> None:
        cells = [cell for row in PARENT.grid(3, 4, gap=cm(0.4)) for cell in row]
        self.assertEqual(len(cells), 12)
        for cell in cells:
            self.assertTrue(PARENT.contains(cell))
        for a, b in combinations(cells, 2):
            self.assertFalse(a.overlaps(b))

    def test_gaps_wider_than_the_area_are_refused(self) -> None:
        with self.assertRaises(ValueError):
            Rect(0, 0, cm(2), cm(2)).columns(5, gap=cm(1))

    def test_inset_larger_than_the_rectangle_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            Rect(0, 0, cm(2), cm(2)).inset(cm(2))


class SpanTest(unittest.TestCase):
    """A place given as a fraction of the width still comes out of dividing the parent."""

    def test_a_span_stays_inside_and_keeps_the_height(self) -> None:
        parent = Rect(100, 50, 1000, 300)
        part = parent.span(0.25, 0.5)
        self.assertTrue(parent.contains(part))
        self.assertEqual((part.left, part.width, part.top, part.height), (350, 250, 50, 300))

    def test_spans_that_meet_share_an_edge_and_do_not_overlap(self) -> None:
        parent = Rect(0, 0, 1001, 10)
        first, second = parent.span(0, 1 / 3), parent.span(1 / 3, 1)
        self.assertEqual(first.right, second.left)
        self.assertEqual(second.right, parent.right)
        self.assertFalse(first.overlaps(second))

    def test_a_span_outside_the_parent_or_running_backwards_is_refused(self) -> None:
        parent = Rect(0, 0, 100, 10)
        for start, end in ((-0.1, 0.5), (0.5, 1.2), (0.6, 0.4)):
            with self.subTest(start=start, end=end):
                with self.assertRaises(ValueError):
                    parent.span(start, end)


class FitTest(unittest.TestCase):
    def test_an_image_keeps_its_aspect_and_stays_inside(self) -> None:
        for aspect in (16 / 9, 1.0, 3 / 4, 2.35):
            for area in (PARENT, PARENT.columns(3)[1], PARENT.rows([1, 2])[0]):
                with self.subTest(aspect=aspect):
                    placed = area.fit(aspect)
                    self.assertTrue(area.contains(placed))
                    self.assertAlmostEqual(placed.width / placed.height, aspect, places=2)

    def test_fit_is_centred(self) -> None:
        placed = Rect(0, 0, cm(20), cm(10)).fit(1.0)
        self.assertEqual(placed.left + placed.width // 2, cm(10))


if __name__ == "__main__":
    unittest.main()
