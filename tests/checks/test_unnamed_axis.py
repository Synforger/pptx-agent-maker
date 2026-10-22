"""A declared chart of categories whose value axis has no name is said, wherever on the page it stands.

値の軸の名前は、縦のグラフは `y`、横棒は `x`。項目の軸の名前は知らせない (= 項目そのものが何かを言う)。点の
グラフは名前が無ければ型が止め、点の列と `bare` の棒は値の軸を持たない。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from pptx_agent_maker.checks import DECLARED  # noqa: E402
from pptx_agent_maker.checks.declared import unnamed_axis  # noqa: E402

COUNTS = {"categories": ["A", "B"], "series": [{"name": "n", "values": [1, 2]}]}


def page(chart: dict | None = None, *, kind: str = "declare", **keys) -> SimpleNamespace:
    data = {"type": "chart", "title": "A chart", **({"chart": {**COUNTS, **chart}} if chart is not None else {}), **keys}
    return SimpleNamespace(kind=kind, data=data)


def said(*pages, config=None) -> list[tuple[int, str]]:
    found = unnamed_axis.run(SimpleNamespace(entries=list(pages)), None, config or {})
    return [(finding.page, finding.check) for finding in found]


class TheValueAxis(unittest.TestCase):
    def test_a_chart_whose_value_axis_has_no_name_is_said(self) -> None:
        for kind in ("column", "line", "stacked", "bar"):
            with self.subTest(kind):
                self.assertEqual([(1, "unnamed_axis")], said(page({"kind": kind})))

    def test_the_value_axis_is_up_on_a_column_and_across_on_a_bar(self) -> None:
        self.assertEqual([], said(page({"kind": "column", "y": "Count (n)"})))
        self.assertEqual([(1, "unnamed_axis")], said(page({"kind": "column", "x": "Group"})))
        self.assertEqual([], said(page({"kind": "bar", "x": "Count (n)"})))
        self.assertEqual([(1, "unnamed_axis")], said(page({"kind": "bar", "y": "Group"})))

    def test_a_waterfall_names_its_value_axis_like_a_column(self) -> None:
        self.assertEqual([(1, "unnamed_axis")], said(page({"kind": "waterfall"})))
        self.assertEqual([], said(page({"kind": "waterfall", "y": "Profit (k$)"})))

    def test_charts_with_no_value_axis_to_name_are_not_said(self) -> None:
        self.assertEqual([], said(page({"kind": "column", "bare": True})))
        self.assertEqual([], said(page({"kind": "strip"})))
        self.assertEqual([], said(page({"kind": "scatter"})))

    def test_a_chart_in_a_cell_is_said_once_for_each_chart_on_its_page(self) -> None:
        cells = {"type": "compose", "title": "Two charts",
                 "rows": [{"cells": [{"chart": {**COUNTS, "kind": "column"}},
                                     {"chart": {**COUNTS, "kind": "bar", "x": "Count"}},
                                     {"chart": {**COUNTS, "kind": "line"}}]}]}
        self.assertEqual([(1, "unnamed_axis"), (1, "unnamed_axis")],
                         said(SimpleNamespace(kind="declare", data=cells)))

    def test_a_page_that_is_copied_and_a_page_with_no_chart_are_not_read(self) -> None:
        self.assertEqual([], said(page({"kind": "column"}, kind="copy"), page()))

    def test_the_page_is_counted_in_the_order_of_the_manifest(self) -> None:
        self.assertEqual([(2, "unnamed_axis")], said(page({"kind": "column", "y": "n"}), page({"kind": "column"})))

    def test_a_project_may_switch_it_off(self) -> None:
        self.assertEqual([], said(page({"kind": "column"}), config={"unnamed_axis": False}))

    def test_it_runs_with_the_other_checks_of_a_manifest(self) -> None:
        self.assertIn(unnamed_axis, DECLARED)


if __name__ == "__main__":
    unittest.main()
