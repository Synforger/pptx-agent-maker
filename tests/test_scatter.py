"""A chart of points: `kind = "scatter"`.

2 つの量の関係を見せる図 (= 一方が増えると他方がどうなるか、どこに固まっているか)。項目と系列で書く 5 つの
グラフとは数の形が違う ― 点は x と y の 1 組で、系列はその集まり。**軸が何かを言わない散布図は読めない**ので、
軸の名前 (= `x` と `y`) は必ず書く。数は deck の中に持ち、PowerPoint の「データの編集」で直せる。
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
sys.path.insert(0, str(REPO / "tests"))

from support.pages import build  # noqa: E402

from pptx_agent_maker import DEFAULT, checks  # noqa: E402
from pptx_agent_maker.layout.parts.elements import Chart  # noqa: E402
from pptx_agent_maker.layout.types import PageTypeError  # noqa: E402

A = {"name": "A 案", "points": [[1, 2.5], [2, 3.5], [3.5, 5]]}
B = {"name": "B 案", "points": [[1.5, 1], [4, 2]]}


def page(**chart) -> dict:
    return {"type": "chart", "title": "だい", "footer": "でどころ",
            "chart": {"kind": "scatter", "x": "かけた時間 (h)", "y": "満足度", "series": [A, B], **chart}}


def chart_of(spec: dict) -> Chart:
    return next(e for e in build(spec).build() if isinstance(e, Chart))


def refused(**chart) -> str:
    try:
        build(page(**chart)).build()
    except PageTypeError as reason:
        return str(reason)
    raise AssertionError("the chart was built")


class WhatIsDrawn(unittest.TestCase):
    def test_a_series_is_its_points_each_an_x_and_a_y(self) -> None:
        chart = chart_of(page())
        self.assertEqual("scatter", chart.plot)
        self.assertEqual(["A 案", "B 案"], [series.name for series in chart.series])
        self.assertEqual([(1, 2, 3.5), (1.5, 4)], [series.xs for series in chart.series])
        self.assertEqual([(2.5, 3.5, 5), (1, 2)], [series.values for series in chart.series])

    def test_the_axes_say_what_they_are(self) -> None:
        chart = chart_of(page())
        self.assertEqual(("かけた時間 (h)", "満足度"), (chart.x_title, chart.y_title))
        self.assertTrue(chart.axis, "a scatter is read off its axes")

    def test_the_first_series_leads_and_the_rest_are_grey_like_every_chart(self) -> None:
        p = DEFAULT.palette
        self.assertEqual([p.accent, p.muted], [series.colour for series in chart_of(page()).series])
        self.assertEqual([p.muted, p.accent], [s.colour for s in chart_of(page(highlight="B 案")).series])
        toned = chart_of(page(series=[A, {**B, "tone": "good"}]))
        self.assertEqual(p.good, toned.series[1].colour)

    def test_the_legend_is_there_only_with_more_than_one_series(self) -> None:
        self.assertTrue(chart_of(page()).legend)
        self.assertFalse(chart_of(page(series=[A])).legend)

    def test_it_counts_as_the_pages_figure(self) -> None:
        self.assertTrue(build(page()).build())

    def test_it_goes_into_a_cell_of_a_compose(self) -> None:
        spec = {"type": "compose", "title": "だい",
                "rows": [{"cells": [{"chart": page()["chart"]}, {"card": ["見出し", "本文"]}]}]}
        self.assertEqual("scatter", chart_of(spec).plot)


class NumbersFromAFile(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def chart(self, text: str) -> Chart:
        from pptx_agent_maker.layout import types
        from pptx_agent_maker.write import aspect

        (self.dir / "points.csv").write_text(text, encoding="utf-8")
        spec = {"type": "chart", "title": "だい",
                "chart": {"kind": "scatter", "x": "x", "y": "y", "data": "points.csv"}}
        built = types.build(spec, lambda name: self.dir / name, aspect, DEFAULT)
        return next(e for e in built.build() if isinstance(e, Chart))

    def test_the_first_column_is_x_and_each_later_column_a_series(self) -> None:
        chart = self.chart("x,A,B\n1,2.5,\n2,3.5,1\n4,,2\n")
        self.assertEqual(["A", "B"], [series.name for series in chart.series])
        self.assertEqual([(1, 2), (2, 4)], [series.xs for series in chart.series])
        self.assertEqual([(2.5, 3.5), (1, 2)], [series.values for series in chart.series])

    def test_a_cell_that_is_not_a_number_says_where(self) -> None:
        with self.assertRaises(PageTypeError) as refused_:
            self.chart("x,A\n1,two\n")
        self.assertIn("row 2, column 2", str(refused_.exception))

    def test_a_series_with_no_point_at_all_is_refused(self) -> None:
        with self.assertRaises(PageTypeError) as refused_:
            self.chart("x,A,B\n1,2,\n2,3,\n")
        self.assertIn("B", str(refused_.exception))


class WhatIsRefused(unittest.TestCase):
    def test_an_axis_with_no_name(self) -> None:
        for axis in ("x", "y"):
            for name in (None, "", "  ", 3):
                with self.subTest(axis=axis, name=name):
                    spec = page()
                    if name is None:
                        del spec["chart"][axis]
                    else:
                        spec["chart"][axis] = name
                    with self.assertRaises(PageTypeError) as reason:
                        build(spec).build()
                    self.assertIn(f"`{axis}`", str(reason.exception))

    def test_points_that_are_not_pairs_of_numbers(self) -> None:
        for points in ([], [[1]], [[1, 2, 3]], [[1, "2"]], [[1, True]], "1,2", [[1, float("nan")]]):
            with self.subTest(points=points):
                self.assertIn("points", refused(series=[{"name": "A 案", "points": points}]))

    def test_values_in_place_of_points_and_the_other_way_round(self) -> None:
        self.assertIn("points", refused(series=[{"name": "A 案", "values": [1, 2]}]))
        with self.assertRaises(PageTypeError) as reason:
            build({"type": "chart", "title": "だい",
                   "chart": {"kind": "column", "categories": ["a"], "series": [A]}}).build()
        self.assertIn("points", str(reason.exception))

    def test_what_belongs_to_the_charts_of_categories(self) -> None:
        for key, value in (("categories", ["a", "b"]), ("unit", "%"), ("labels", False), ("totals", []),
                           ("callouts", [{"at": "a", "text": "ここ"}])):
            with self.subTest(key=key):
                said = refused(**{key: value})
                self.assertIn(key, said)
                self.assertIn("scatter", said)

    def test_axis_names_on_a_chart_of_categories(self) -> None:
        for axis in ("x", "y"):
            with self.subTest(axis=axis), self.assertRaises(PageTypeError) as reason:
                build({"type": "chart", "title": "だい",
                       "chart": {"kind": "column", "categories": ["a"], axis: "なまえ",
                                 "series": [{"name": "s", "values": [1]}]}}).build()
            self.assertIn(axis, str(reason.exception))

    def test_a_highlight_that_names_no_series_and_a_series_named_twice(self) -> None:
        self.assertIn("highlight", refused(highlight="C 案"))
        self.assertIn("twice", refused(series=[A, A]))
        self.assertIn("tone", refused(highlight="A 案", series=[A, {**B, "tone": "good"}]))


class AsWrittenOut(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from pptx_agent_maker.write import add_page, new_deck, save

        cls.tmp = tempfile.TemporaryDirectory()
        deck = new_deck()
        add_page(deck, build(page()).build())
        cls.deck = save(deck, Path(cls.tmp.name) / "scatter.pptx")
        with zipfile.ZipFile(cls.deck) as archive:
            cls.names = archive.namelist()
            cls.xml = archive.read("ppt/charts/chart1.xml").decode("utf-8") if "ppt/charts/chart1.xml" in cls.names else ""
            cls.xml = cls.xml or next(archive.read(n).decode("utf-8") for n in cls.names
                                      if n.startswith("ppt/charts/") and n.endswith(".xml"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_it_is_a_scatter_chart_with_its_numbers_inside(self) -> None:
        self.assertIn("<c:scatterChart>", self.xml)
        self.assertEqual(2, len(re.findall(r"<c:ser>", self.xml)))
        self.assertTrue(any(name.startswith("ppt/embeddings/") for name in self.names),
                        "the numbers a person edits are not in the deck")
        for number in ("<c:v>3.5</c:v>", "<c:v>1.5</c:v>", "<c:v>5</c:v>"):
            self.assertIn(number, self.xml)

    def test_the_points_are_marks_with_no_line_between_them(self) -> None:
        for series in re.findall(r"<c:ser>.*?</c:ser>", self.xml, re.S):
            shape = series.split("<c:marker>")[0]
            self.assertRegex(shape, r"<a:ln[^>]*>\s*<a:noFill/>")
            self.assertIn('<c:symbol val="circle"/>', series)
        first = re.findall(r"<c:ser>.*?</c:ser>", self.xml, re.S)[0]
        self.assertIn(f'<a:srgbClr val="{DEFAULT.palette.accent}"/>', first.split("<c:marker>")[1])

    def test_both_axes_carry_their_names_and_no_grid(self) -> None:
        for name in ("かけた時間 (h)", "満足度"):
            self.assertIn(f">{name}<", self.xml)
        self.assertNotIn("<c:majorGridlines", self.xml)
        self.assertEqual(2, self.xml.count("<c:valAx>"))

    def test_it_has_no_title_of_its_own_and_a_legend_for_two_series(self) -> None:
        self.assertIn('<c:autoTitleDeleted val="1"/>', self.xml)
        self.assertIn("<c:legend>", self.xml)

    def test_the_checks_find_nothing_and_python_pptx_opens_it(self) -> None:
        from pptx import Presentation

        self.assertEqual([], checks.run_all(self.deck))
        self.assertEqual(1, len(Presentation(str(self.deck)).slides))


if __name__ == "__main__":
    unittest.main()
