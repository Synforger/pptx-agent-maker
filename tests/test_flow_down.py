"""A flow that runs down the page: `direction = "down"`.

段を上から下へ並べ、段の中のノードは横に並べる (= 左から右の流れ図を、そのまま転置した形)。ノードが
2 つ以上の段は、そこで横に分かれる ― 分岐と合流は、段ごとのノードの数で書ける。段の名前は左に立つ。
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))

from pptx_agent_maker import PageFullError, checks  # noqa: E402
from pptx_agent_maker.layout import types  # noqa: E402
from pptx_agent_maker.layout.base.tokens import DEFAULT  # noqa: E402
from pptx_agent_maker.layout.types.core.registry import PageTypeError  # noqa: E402
from pptx_agent_maker.write import add_page, new_deck, save  # noqa: E402

LONG = "a body long enough to run over several lines of a node, so this one stands taller than the rest"


def page(stages, **extra):
    return types.build({"type": "flow", "title": "A flow", "direction": "down", "stages": stages, **extra},
                       lambda name: Path(name), lambda path: 1.0, DEFAULT)


def stage(name, *nodes, **more):
    return {"name": name, "nodes": list(nodes), **more}


THREE = [stage("受付", ["申請", "窓口で受ける"]),
         stage("審査", ["書類", "要件を見る"], ["現地", "実物を見る"]),
         stage("決定", ["通知", "結果を返す"])]


def of(built, kind: str):
    return [e for e in built.build() if e.kind == kind]


def box(built, heading: str):
    head = next(e for e in built.build() if getattr(e, "text", None) == heading).rect
    return next(e.rect for e in built.build() if e.kind == "box" and e.rect.contains(head))


class WhereThingsLand(unittest.TestCase):
    def test_the_stages_run_from_the_top_down(self) -> None:
        built = page(THREE)
        tops = [box(built, heading).top for heading in ("申請", "書類", "通知")]
        self.assertEqual(sorted(tops), tops)
        self.assertEqual(3, len(set(tops)))

    def test_the_nodes_of_one_stage_stand_side_by_side(self) -> None:
        built = page(THREE)
        left, right = box(built, "書類"), box(built, "現地")
        self.assertEqual((left.top, left.height), (right.top, right.height))
        self.assertLess(left.right, right.left)
        self.assertEqual(left.width, right.width)

    def test_a_stage_of_one_node_takes_the_width_its_stage_has(self) -> None:
        built = page(THREE)
        one, left, right = box(built, "申請"), box(built, "書類"), box(built, "現地")
        self.assertEqual((left.left, right.right), (one.left, one.right))

    def test_the_arrow_points_down_and_stands_between_two_stages(self) -> None:
        built = page(THREE)
        arrows = of(built, "marker")
        self.assertEqual(["↓", "↓"], [arrow.text for arrow in arrows])
        first = arrows[0].rect
        self.assertGreaterEqual(first.top, box(built, "申請").bottom)
        self.assertLessEqual(first.bottom, box(built, "書類").top)
        self.assertEqual((box(built, "申請").left, box(built, "申請").right), (first.left, first.right))

    def test_the_name_of_a_stage_stands_at_its_left(self) -> None:
        built = page(THREE)
        names = {e.text: e.rect for e in of(built, "label")}
        self.assertEqual({"受付", "審査", "決定"}, set(names))
        for name, heading in (("受付", "申請"), ("審査", "書類"), ("決定", "通知")):
            with self.subTest(name):
                self.assertLessEqual(names[name].right, box(built, heading).left)
                self.assertEqual((box(built, heading).top, box(built, heading).height),
                                 (names[name].top, names[name].height))
        self.assertEqual(1, len({rect.left for rect in names.values()}))
        self.assertEqual(1, len({rect.width for rect in names.values()}))

    def test_the_column_of_names_is_as_wide_as_the_longest_name(self) -> None:
        short = {e.text: e.rect for e in of(page(THREE), "label")}["受付"].width
        longer = [THREE[0], stage("審査と本人の確認", *THREE[1]["nodes"]), THREE[2]]
        names = {e.text: e.rect for e in of(page(longer), "label")}
        self.assertGreater(names["受付"].width, short)
        self.assertEqual(DEFAULT.width("審査と本人の確認", DEFAULT.type.stage, bold=True), names["受付"].width)

    def test_the_name_of_a_stage_is_one_bold_line_that_does_not_fold(self) -> None:
        """⚠ 列の幅は字の幅ちょうど。折り返す枠に入れていた間は、焼いた絵で名前が 1 文字ずつ縦に折れた。"""
        for name in of(page(THREE), "label"):
            self.assertEqual((DEFAULT.type.stage, True, DEFAULT.palette.ink), (name.size, name.bold, name.colour))
        self.assertEqual([], of(page(THREE), "lane"))

    def test_a_stage_is_as_tall_as_its_tallest_node_and_no_taller(self) -> None:
        built = page([stage("一", ["短い", "x"], ["長い", LONG]), stage("二", ["次", "y"])])
        self.assertEqual(box(built, "短い").height, box(built, "長い").height)
        alone = page([stage("一", ["短い", "x"]), stage("二", ["次", "y"])])
        self.assertGreater(box(built, "短い").height, box(alone, "短い").height)

    def test_what_is_settled_stands_under_its_stages_nodes(self) -> None:
        built = page([stage("一", ["a", "b"], settled="ここで決まる"), stage("二", ["c", "d"])])
        note = next(e.rect for e in of(built, "note"))
        self.assertGreaterEqual(note.top, box(built, "a").bottom)
        self.assertLessEqual(note.bottom, of(built, "marker")[0].rect.top)
        self.assertEqual(box(built, "a").left, note.left)

    def test_everything_stays_in_the_body_and_nothing_overlaps(self) -> None:
        built = page(THREE)
        placed = [e.rect for e in built.build() if e.kind in {"box", "marker", "label"}]
        for index, one in enumerate(placed):
            self.assertTrue(DEFAULT.frame().contains(one))
            for other in placed[index + 1:]:
                self.assertFalse(one.overlaps(other), f"{one} overlaps {other}")

    def test_it_counts_as_the_pages_diagram(self) -> None:
        self.assertTrue(page(THREE).build())


class WhatItRefuses(unittest.TestCase):
    def test_a_direction_nobody_knows(self) -> None:
        for direction in ("up", "", 1, True):
            with self.subTest(direction=direction), self.assertRaises(PageTypeError) as refused:
                types.build({"type": "flow", "title": "A flow", "direction": direction, "stages": THREE},
                            lambda name: Path(name), lambda path: 1.0, DEFAULT)
            self.assertIn("direction", str(refused.exception))

    def test_rows_aligned_across_stages_belong_to_a_flow_that_runs_right(self) -> None:
        with self.assertRaises(PageTypeError) as refused:
            page(THREE, align_rows=True)
        self.assertIn("align_rows", str(refused.exception))

    def test_more_stages_than_the_page_holds_stop_and_are_not_shrunk(self) -> None:
        many = [stage(f"段 {number}", ["見出し", LONG]) for number in range(1, 9)]
        with self.assertRaises(PageFullError) as stopped:
            page(many)
        self.assertIn("flow", str(stopped.exception))

    def test_a_stage_with_no_nodes_and_a_flow_of_one_stage(self) -> None:
        with self.assertRaises(PageTypeError):
            page([stage("一"), stage("二", ["a", "b"])])
        with self.assertRaises(PageTypeError):
            page([stage("一", ["a", "b"])])

    def test_only_the_flow_reads_a_direction(self) -> None:
        with self.assertRaises(PageTypeError) as refused:
            types.build({"type": "figure", "title": "t", "figure": "a.png", "direction": "down"},
                        lambda name: Path(name), lambda path: 1.0, DEFAULT)
        self.assertIn("does not take direction", str(refused.exception))


class LeftUnsaid(unittest.TestCase):
    def test_a_flow_runs_to_the_right_as_it_always_did(self) -> None:
        def right(**extra):
            return types.build({"type": "flow", "title": "A flow", "stages": THREE, **extra},
                               lambda name: Path(name), lambda path: 1.0, DEFAULT).build()

        self.assertEqual(right(), right(direction="right"))
        self.assertEqual({"→"}, {e.text for e in right() if e.kind == "marker"})


class OnceBaked(unittest.TestCase):
    def test_the_checks_find_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            deck = new_deck()
            add_page(deck, page(THREE).build())
            self.assertEqual([], checks.run_all(save(deck, Path(tmp) / "down.pptx")))


if __name__ == "__main__":
    unittest.main()
