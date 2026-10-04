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

    def test_equal_parts_are_equal_and_stand_the_gap_apart(self) -> None:
        """⚠ 間隔を引かずに割ると、最後の 1 つだけが間隔のぶん痩せる。外へは出ないので、枠の中に在るか
        だけを見る test は通る。"""
        parent = Rect(100, 20, 1000, 400)
        columns = parent.columns(3, gap=50)
        self.assertEqual([(100, 300), (450, 300), (800, 300)], [(part.left, part.width) for part in columns])
        rows = parent.rows(4, gap=40)
        self.assertEqual([(20, 70), (130, 70), (240, 70), (350, 70)], [(part.top, part.height) for part in rows])
        self.assertEqual({(20, 400)}, {(part.top, part.height) for part in columns})
        self.assertEqual({(100, 1000)}, {(part.left, part.width) for part in rows})

    def test_weighted_parts_share_what_the_gaps_leave(self) -> None:
        parent = Rect(0, 0, 1000, 10)
        self.assertEqual([(0, 600), (700, 300)], [(part.left, part.width) for part in parent.columns([2, 1], gap=100)])
        self.assertEqual([(0, 225), (275, 225), (550, 450)],
                         [(part.left, part.width) for part in parent.columns([1, 1, 2], gap=50)])

    def test_rectangles_that_only_touch_do_not_overlap_whichever_one_is_asked(self) -> None:
        """⚠ 並びの順に 1 回ずつ訊くだけでは、判定の片側しか通らない (= 逆から訊いた時の端の扱いを誰も
        見ていなかった)。"""
        middle = Rect(100, 100, 50, 50)
        beside = {"left": Rect(50, 100, 50, 50), "right": Rect(150, 100, 50, 50),
                  "above": Rect(100, 50, 50, 50), "below": Rect(100, 150, 50, 50)}
        for where, other in beside.items():
            with self.subTest(where):
                self.assertFalse(middle.overlaps(other))
                self.assertFalse(other.overlaps(middle))
        # 1 つ内へ寄せれば重なる (= 端の扱いが「離れている」側へ倒れすぎていない)
        for where, (dx, dy) in {"left": (1, 0), "right": (-1, 0), "above": (0, 1), "below": (0, -1)}.items():
            with self.subTest(nudged=where):
                other = beside[where]
                nudged = Rect(other.left + dx, other.top + dy, other.width, other.height)
                self.assertTrue(middle.overlaps(nudged))
                self.assertTrue(nudged.overlaps(middle))

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
