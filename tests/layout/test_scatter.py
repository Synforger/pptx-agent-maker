"""A chart of points: `kind = "scatter"`.

2 つの量の関係を見せる図 (= 一方が増えると他方がどうなるか、どこに固まっているか)。項目と系列で書く 5 つの
グラフとは数の形が違う ― 点は x と y の 1 組で、系列はその集まり。**軸が何かを言わない散布図は読めない**ので、
軸の名前 (= `x` と `y`) は必ず書く。数は deck の中に持ち、PowerPoint の「データの編集」で直せる。
"""

from __future__ import annotations

import math
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))

from support.pages import build  # noqa: E402

from pptx_agent_maker import DEFAULT, checks  # noqa: E402
from pptx_agent_maker.layout.parts.elements import Chart  # noqa: E402
from pptx_agent_maker.layout.types.bodies import chart as chart_body  # noqa: E402
from pptx_agent_maker.layout.types import PageTypeError  # noqa: E402
from pptx_agent_maker import PageFullError  # noqa: E402

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
        self.assertEqual([p.muted, p.bad],
                         [s.colour for s in chart_of(page(highlight="B 案", highlight_tone="bad")).series])
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


def named_page(**chart) -> dict:
    """A scatter whose points carry names (= `[x, y, "its name"]`)."""
    return page(series=[
        {"name": "A 案", "points": [[1, 2.5, "Alpha study"], [2, 3.5, "Beta"], [3.5, 5]]},
        {"name": "B 案", "points": [[1.5, 1], [4, 2, "Delta"]]},
    ], **chart)


def written_out(spec: dict) -> tuple[str, str]:
    """The chart's XML and the slide's XML, once the page is written into a deck."""
    from pptx_agent_maker.write import add_page, new_deck, save

    with tempfile.TemporaryDirectory() as tmp:
        deck = new_deck()
        add_page(deck, build(spec).build())
        saved = save(deck, Path(tmp) / "scatter.pptx")
        with zipfile.ZipFile(saved) as archive:
            return (archive.read("ppt/charts/chart1.xml").decode("utf-8"),
                    archive.read("ppt/slides/slide1.xml").decode("utf-8"))


class ANameBesidePoint(unittest.TestCase):
    """⚠ **点の名前は点の横に置く。**名前と数字を、点の右 (= 縁では左) に。置く場所は点の位置から計算するので、
    描く範囲と軸は道具が決めて書き出す (= 名前を付けた散布図だけ。注記を持つグラフと同じ)。"""

    S, LINE = DEFAULT.spacing, DEFAULT.line_height()

    def test_a_chart_with_no_name_is_left_to_powerpoint(self) -> None:
        chart = chart_of(page())
        self.assertEqual((None, []), (chart.plane, [series.labels for series in chart.series if series.labels]))
        xml, _slide = written_out(page())
        for mark in ("manualLayout", "<c:max ", "<c:majorUnit", "<c:dLbl>"):
            self.assertNotIn(mark, xml)

    def test_only_the_points_with_a_name_carry_words(self) -> None:
        chart = chart_of(named_page())
        self.assertEqual([[0, 1], [1]], [[label.index for label in series.labels] for series in chart.series])
        self.assertEqual("Alpha study\n(1.0, 2.5)", chart.series[0].labels[0].text)
        self.assertEqual([chart_body.MARK] * 2, [series.mark for series in chart.series])
        self.assertEqual({DEFAULT.type.caption}, {label.size for series in chart.series for label in series.labels})

    def test_the_numbers_are_printed_to_the_places_written(self) -> None:
        chart = chart_of(page(series=[{"name": "A 案", "points": [[1200, 2, "Big"], [3, 4.25]]}]))
        self.assertEqual("Big\n(1,200, 2.00)", chart.series[0].labels[0].text)

    def test_the_words_stand_to_the_right_of_the_point_and_to_the_left_at_the_edge(self) -> None:
        chart = chart_of(page(series=[{"name": "A 案", "points": [[1, 1, "First"], [9, 5, "The very last one of them all"]]}]))
        self.assertEqual([False, True], [label.left for series in chart.series for label in series.labels])

    def test_the_axes_cover_every_point_with_room_round_them(self) -> None:
        chart = chart_of(named_page())
        (x_low, x_high, x_step), (y_low, y_high, y_step) = chart.plane.x, chart.plane.y
        self.assertLess(x_low, 1)
        self.assertGreater(x_high, 4)
        self.assertLess(y_low, 1)
        self.assertGreater(y_high, 5)
        for low, high, step in ((x_low, x_high, x_step), (y_low, y_high, y_step)):
            self.assertAlmostEqual(0, (high - low) / step - round((high - low) / step), places=6)
            self.assertIn(round(step / 10 ** math.floor(math.log10(step)), 6), (1, 2, 5, 10))   # 1, 2 or 5 of a power of ten

    def test_the_plot_leaves_room_for_the_axes_words_and_the_legend(self) -> None:
        chart = chart_of(named_page())
        x, y, w, h = chart.plane.inner
        rect = chart.rect
        self.assertGreater(x * rect.width, 2 * self.LINE)                                     # the name of y and its numbers
        self.assertGreaterEqual((1 - y - h) * rect.height, 3 * self.LINE + self.LINE)         # numbers, name of x, legend
        self.assertGreater(1 - x - w, 0)

    def test_words_that_would_print_over_each_other_stop_the_page(self) -> None:
        with self.assertRaises(PageFullError) as stopped:
            chart_of(page(series=[{"name": "A 案", "points": [[1, 1, "One"], [1.01, 1.01, "Two"], [5, 5]]}]))
        self.assertIn("would print over each other", str(stopped.exception))

    def test_words_that_do_not_fit_in_the_chart_stop_the_page(self) -> None:
        with self.assertRaises(PageFullError) as stopped:
            chart_of(page(series=[{"name": "A 案", "points": [[1, 1, "x" * 400], [5, 5]]}]))
        self.assertIn("do not fit beside its point", str(stopped.exception))

    def test_a_name_is_a_few_words_on_one_line(self) -> None:
        for name in ("", "  ", 3, "two\nlines"):
            with self.subTest(name=name):
                self.assertIn("name of a point", refused(series=[{"name": "A 案", "points": [[1, 1, name]]}]))

    def test_written_out_each_name_is_a_label_of_its_own_and_no_other_point_has_one(self) -> None:
        xml, _slide = written_out(named_page())
        self.assertEqual(3, len(re.findall(r"<c:dLbl>", xml)))
        for words in ("Alpha study", "(1.0, 2.5)", "Beta", "Delta"):
            self.assertIn(f"<a:t>{words}</a:t>", xml)
        self.assertEqual(['<c:dLblPos val="r"/>'] * 3, re.findall(r"<c:dLblPos[^>]*/>", xml))
        words = "".join(re.findall(r"<c:dLbl>.*?</c:dLbl>", xml, re.S))
        self.assertEqual({str(round(DEFAULT.type.caption * 100))}, set(re.findall(r'sz="(\d+)"', words)))
        self.assertEqual(3, words.count('<a:bodyPr wrap="none"'))
        self.assertEqual(2, xml.count('<c:showVal val="0"/>'), "a point with no name prints no number")

    def test_written_out_a_name_at_the_edge_is_set_to_the_left(self) -> None:
        xml, _slide = written_out(page(series=[{"name": "A 案", "points": [[1, 1, "First"], [9, 5, "The very last one of them all"]]}]))
        self.assertEqual(['<c:dLblPos val="r"/>', '<c:dLblPos val="l"/>'], re.findall(r"<c:dLblPos[^>]*/>", xml))

    def test_written_out_the_marks_are_the_size_the_words_were_placed_for(self) -> None:
        xml, _slide = written_out(named_page())
        self.assertEqual([f'<c:size val="{chart_body.MARK}"/>'] * 2, re.findall(r"<c:size [^>]*/>", xml))

    def test_written_out_the_plot_is_pinned_where_the_page_worked_it_out(self) -> None:
        xml, _slide = written_out(named_page())
        self.assertIn('<c:layoutTarget val="inner"/>', xml)
        for axis in re.findall(r"<c:valAx>.*?</c:valAx>", xml, re.S):
            for mark in ("<c:min ", "<c:max ", "<c:majorUnit "):
                self.assertIn(mark, axis)
        self.assertNotIn("<c:logBase", xml)
        self.assertNotIn('<c:orientation val="maxMin"/>', xml)


class AGridOfItsOwn(unittest.TestCase):
    """⚠ **格子は散布図だけ。**読み手が点の位置を目盛りに当てて読む図なので、薄い線を両方の軸に引く
    (= 項目のグラフは、目盛りの線を引かない決まり。範囲を言った `scale` だけが例外)。"""

    def test_it_is_a_light_line_on_both_axes(self) -> None:
        chart = chart_of(page(grid=True))
        self.assertEqual(DEFAULT.palette.rule, chart.grid)
        xml, _slide = written_out(page(grid=True))
        self.assertEqual(2, xml.count("<c:majorGridlines>"))
        for lines in re.findall(r"<c:majorGridlines>.*?</c:majorGridlines>", xml, re.S):
            self.assertIn(f'<a:srgbClr val="{DEFAULT.palette.rule}"/>', lines)
            self.assertIn(f'w="{DEFAULT.spacing.hairline}"', lines)

    def test_without_it_there_is_none(self) -> None:
        for chart in (page(), page(grid=False)):
            self.assertEqual("", chart_of(chart).grid)
            self.assertNotIn("<c:majorGridlines", written_out(chart)[0])

    def test_it_is_true_or_false(self) -> None:
        self.assertIn("`grid` is true or false", refused(grid="yes"))

    def test_it_is_for_a_scatter_not_for_the_charts_of_categories(self) -> None:
        with self.assertRaises(PageTypeError) as reason:
            build({"type": "chart", "title": "だい",
                   "chart": {"kind": "column", "categories": ["a"], "grid": True,
                             "series": [{"name": "s", "values": [1]}]}}).build()
        self.assertIn("grid", str(reason.exception))

    def test_a_grid_and_names_go_together(self) -> None:
        chart = chart_of(named_page(grid=True))
        self.assertEqual((DEFAULT.palette.rule, True), (chart.grid, chart.plane is not None))


ROWS = ["Street scenes\nphotographs", "Product shots", "Portraits\nfaces blurred\nconsented"]
SMALL = {"name": "Small", "values": [[3, 12, 40], [8], [15, 15, 250]]}
LARGE = {"name": "Large", "values": [[900], [], [60, 2000]]}


def strip_page(**chart) -> dict:
    return {"type": "chart", "title": "だい", "footer": "でどころ",
            "chart": {"kind": "strip", "axis": "log", "ticks": [1, 10, 100, 1000, 10000], "categories": ROWS,
                      "series": [SMALL, LARGE], **chart}}


def refused_strip(**chart) -> str:
    try:
        build(strip_page(**chart)).build()
    except PageTypeError as reason:
        return str(reason)
    raise AssertionError("the strip was built")


class AStripOfPoints(unittest.TestCase):
    """⚠ **`strip` は行ごとの点の列。**行 = 項目、横 = 対数の軸、1 件 = 点 1 つ。PowerPoint の散布図で描く
    (= 数は deck の中に在り、「データの編集」で直せる)。縦は行の番号で、点どうしが覆い合わないよう行の中で
    縦にずらす。"""

    S, LINE = DEFAULT.spacing, DEFAULT.line_height()

    def inner(self, chart: Chart):
        x, y, w, h = chart.plane.inner
        return (chart.rect.left + x * chart.rect.width, chart.rect.top + y * chart.rect.height,
                w * chart.rect.width, h * chart.rect.height)

    def test_one_point_for_each_number_on_the_row_it_belongs_to(self) -> None:
        chart = chart_of(strip_page())
        self.assertEqual(("scatter", ["Small", "Large"]), (chart.plot, [series.name for series in chart.series]))
        self.assertEqual(((3, 12, 40, 8, 15, 15, 250), (900, 60, 2000)), tuple(series.xs for series in chart.series))
        for series, rows in zip(chart.series, ([1] * 3 + [2] + [3] * 3, [1, 3, 3])):
            for y, row in zip(series.values, rows):
                self.assertAlmostEqual(row, y, delta=0.5)

    def test_the_axis_is_a_log_axis_from_the_first_tick_to_the_last_with_a_row_to_each_band(self) -> None:
        plane = chart_of(strip_page()).plane
        self.assertEqual((True, True), (plane.log, plane.down))
        self.assertEqual((1, 10000, 10), plane.x)
        self.assertEqual((0.5, 3.5, 1), plane.y)

    def test_marks_in_a_row_do_not_cover_each_other(self) -> None:
        chart = chart_of(strip_page())
        left, top, wide, tall = self.inner(chart)
        slot, mark = tall / 3, DEFAULT.spacing.hairline * chart_body.STRIP_MARK
        marks = [(left + wide * math.log10(x) / 4, top + slot * (y - 0.5))
                 for series in chart.series for x, y in zip(series.xs, series.values)]
        for number, (x, y) in enumerate(marks):
            for other_x, other_y in marks[number + 1:]:
                self.assertGreaterEqual(math.hypot(x - other_x, y - other_y), mark * 0.99)

    def test_two_marks_of_the_same_number_are_one_above_the_other(self) -> None:
        chart = chart_of(strip_page())
        twin = [y for x, y in zip(chart.series[0].xs, chart.series[0].values) if x == 15]
        self.assertEqual(2, len(twin))
        self.assertNotEqual(twin[0], twin[1])

    def test_a_row_alone_on_its_band_stays_in_the_middle(self) -> None:
        chart = chart_of(strip_page())
        self.assertEqual(2.0, chart.series[0].values[3])

    def test_the_same_numbers_always_come_out_the_same(self) -> None:
        self.assertEqual(chart_of(strip_page()).series, chart_of(strip_page()).series)

    def test_the_names_of_the_rows_stand_left_of_the_plot_and_the_notes_right_of_it(self) -> None:
        chart = chart_of(strip_page(notes=["1,200 pages", "", "88 pages"]))
        left, top, wide, tall = self.inner(chart)
        names = [callout for callout in chart.callouts if callout.align == "left" and not callout.size]
        notes = [callout for callout in chart.callouts if callout.size]
        self.assertEqual(ROWS, [callout.text for callout in names])
        self.assertEqual(["1,200 pages", "88 pages"], [callout.text for callout in notes])
        for callout in names:
            self.assertEqual(chart.rect.left, callout.words.left)
            self.assertLessEqual(callout.words.right, left)
        for callout, row in zip(notes, (0, 2)):
            self.assertGreaterEqual(callout.words.left, left + wide)
            self.assertAlmostEqual(top + tall / 3 * (row + 0.5), callout.words.top + callout.words.height / 2, delta=1)
            self.assertEqual((DEFAULT.type.caption, DEFAULT.palette.muted), (callout.size, callout.colour))
        for callout, row in zip(names, range(3)):
            self.assertAlmostEqual(top + tall / 3 * (row + 0.5), callout.words.top + callout.words.height / 2, delta=1)
            self.assertEqual(len(ROWS[row].split("\n")) * self.LINE, callout.words.height)

    def test_a_row_with_no_point_keeps_its_name_and_has_no_ring(self) -> None:
        chart = chart_of(strip_page(median=True, series=[{"name": "S", "values": [[3], [], [30, 40]]}]))
        self.assertEqual((1, 3), chart.series[-1].values)
        self.assertEqual(ROWS, [callout.text for callout in chart.callouts if not callout.size])

    def test_the_words_stay_inside_the_chart(self) -> None:
        chart = chart_of(strip_page(notes=["1,200 pages", "340 pages", "88 pages"]))
        for callout in chart.callouts:
            self.assertTrue(chart.rect.contains(callout.words), callout.text)

    def test_one_series_with_no_median_needs_no_legend(self) -> None:
        self.assertFalse(chart_of(strip_page(series=[SMALL])).legend)
        self.assertTrue(chart_of(strip_page(series=[SMALL], median=True)).legend)
        self.assertTrue(chart_of(strip_page(series=[SMALL], median=True, legend=True)).legend)

    def test_the_axis_words_have_a_line_above_the_plot_and_the_legend_a_line_below(self) -> None:
        chart = chart_of(strip_page())
        _left, top, _wide, tall = self.inner(chart)
        self.assertGreaterEqual(top - chart.rect.top, self.LINE)
        self.assertGreaterEqual(chart.rect.bottom - (top + tall), self.LINE)
        self.assertTrue(chart.legend)
        self.assertFalse(chart_of(strip_page(legend=False)).legend)

    def test_a_series_that_stands_out_among_greys_like_every_chart(self) -> None:
        p = DEFAULT.palette
        self.assertEqual([p.accent, p.muted], [series.colour for series in chart_of(strip_page()).series])
        self.assertEqual([p.muted, p.accent],
                         [series.colour for series in chart_of(strip_page(highlight="Large")).series])
        self.assertEqual([p.muted, p.bad],
                         [series.colour for series in chart_of(strip_page(highlight="Large", highlight_tone="bad")).series])
        self.assertEqual(p.bad, chart_of(strip_page(series=[SMALL, {**LARGE, "tone": "bad"}])).series[1].colour)

    def test_the_median_of_a_row_is_a_ring_of_its_own_series_over_every_point_of_the_row(self) -> None:
        chart = chart_of(strip_page(median=True))
        ring = chart.series[-1]
        self.assertEqual(("Median", "", DEFAULT.palette.ink), (ring.name, ring.colour, ring.outline))
        # row 1: 3, 12, 40, 900 -> 26; row 2: 8; row 3: 15, 15, 250, 60, 2000 -> 60
        self.assertEqual((26, 8, 60), ring.xs)
        self.assertEqual(chart_body.STRIP_MARK + chart_body.RING_OVER, ring.mark)   # a ring wider than the marks it rings
        self.assertEqual((1, 2, 3), ring.values)
        self.assertEqual([DEFAULT.palette.accent, DEFAULT.palette.muted], [s.colour for s in chart.series[:2]])

    def test_without_median_there_is_no_ring(self) -> None:
        self.assertEqual(["Small", "Large"], [series.name for series in chart_of(strip_page()).series])

    def test_it_goes_into_a_cell_of_a_compose(self) -> None:
        spec = {"type": "compose", "title": "だい",
                "rows": [{"cells": [{"chart": strip_page()["chart"]}, {"card": ["見出し", "本文"]}]}]}
        self.assertEqual("scatter", chart_of(spec).plot)
        self.assertIsNotNone(chart_of(spec).plane)

    def test_a_row_taller_than_its_band_stops_the_page(self) -> None:
        many = [f"Row {number}\nsecond\nthird" for number in range(1, 13)]
        with self.assertRaises(PageFullError) as stopped:
            chart_of(strip_page(categories=many, series=[{"name": "S", "values": [[5]] * 12}]))
        self.assertIn("name of the tallest", str(stopped.exception))

    def test_names_that_leave_no_room_for_the_plot_stop_the_page(self) -> None:
        with self.assertRaises(PageFullError) as stopped:
            chart_of(strip_page(categories=["x" * 300, "b", "c"]))
        self.assertIn("no room left for its plot", str(stopped.exception))

    def test_written_out_it_is_a_scatter_with_a_log_axis_and_its_numbers_inside(self) -> None:
        xml, _slide = written_out(strip_page(median=True))
        self.assertIn("<c:scatterChart>", xml)
        self.assertEqual(3, len(re.findall(r"<c:ser>", xml)))
        horizontal = re.findall(r"<c:valAx>.*?</c:valAx>", xml, re.S)[0]
        self.assertIn('<c:scaling><c:logBase val="10"/>', horizontal)
        for mark in ('<c:max val="10000.0"/>', '<c:min val="1.0"/>', '<c:majorUnit val="10.0"/>',
                     '<c:numFmt formatCode="#,##0" sourceLinked="0"/>', "<c:majorGridlines>"):
            self.assertIn(mark, horizontal)
        self.assertIn("<c:v>2000</c:v>", xml)

    def test_written_out_the_rows_run_down_from_the_top_with_a_line_between_them(self) -> None:
        xml, _slide = written_out(strip_page())
        vertical = re.findall(r"<c:valAx>.*?</c:valAx>", xml, re.S)[1]
        self.assertIn('<c:orientation val="maxMin"/>', vertical)
        self.assertRegex(vertical, r'<c:delete(/>| val="1"/>)')
        for mark in ('<c:min val="0.5"/>', '<c:max val="3.5"/>', '<c:majorUnit val="1.0"/>', "<c:majorGridlines>"):
            self.assertIn(mark, vertical)
        self.assertNotIn("<c:title>", xml)

    def test_written_out_the_marks_are_the_size_the_points_were_kept_apart_for(self) -> None:
        xml, _slide = written_out(strip_page(median=True))
        self.assertEqual([f'<c:size val="{chart_body.STRIP_MARK}"/>'] * 2
                         + [f'<c:size val="{chart_body.STRIP_MARK + chart_body.RING_OVER}"/>'],
                         re.findall(r"<c:size [^>]*/>", xml))

    def test_written_out_the_median_is_a_ring_in_the_ink_with_no_fill(self) -> None:
        xml, _slide = written_out(strip_page(median=True))
        ring = re.findall(r"<c:ser>.*?</c:ser>", xml, re.S)[-1]
        marker = re.search(r"<c:marker>.*?</c:marker>", ring, re.S).group(0)
        self.assertIn("<a:noFill/>", marker.split("<a:ln")[0])
        self.assertIn(f'<a:ln w="{round(DEFAULT.spacing.hairline * 1.5)}"><a:solidFill><a:srgbClr '
                      f'val="{DEFAULT.palette.ink}"/>', marker)

    def test_written_out_the_words_of_the_rows_and_the_chart_are_one_group(self) -> None:
        _xml, slide = written_out(strip_page(notes=["a", "b", "c"]))
        self.assertIn("<p:grpSp>", slide)
        for words in ("Street scenes", "photographs", "Product shots", "faces blurred"):
            self.assertIn(words, slide)


class AStripIsRefused(unittest.TestCase):
    def test_what_it_does_not_take(self) -> None:
        for key, value in (("unit", "%"), ("labels", True), ("callouts", []), ("x", "a"), ("grid", True),
                           ("data", "x.csv"), ("scale", {})):
            with self.subTest(key=key):
                said = refused_strip(**{key: value})
                self.assertIn(key, said)
                self.assertIn("strip", said)

    def test_the_axis_is_said_and_it_is_a_log_axis(self) -> None:
        for axis in (None, "linear", "Log", True):
            with self.subTest(axis=axis):
                spec = strip_page()
                if axis is None:
                    del spec["chart"]["axis"]
                else:
                    spec["chart"]["axis"] = axis
                with self.assertRaises(PageTypeError) as reason:
                    build(spec).build()
                self.assertIn('`axis = "log"`', str(reason.exception))

    def test_ticks_are_every_power_of_ten_from_the_first_to_the_last(self) -> None:
        for ticks in (None, [], [10], [1, 10, 1000], [1, 5, 10], [1, 5], [2, 20], [10, 1], [0, 10], [-1, 10], ["1", "10"], "1, 10"):
            with self.subTest(ticks=ticks):
                spec = strip_page()
                if ticks is None:
                    del spec["chart"]["ticks"]
                else:
                    spec["chart"]["ticks"] = ticks
                with self.assertRaises(PageTypeError) as reason:
                    build(spec).build()
                self.assertIn("`ticks`", str(reason.exception))
        small = strip_page(ticks=[0.1, 1, 10, 100], series=[{"name": "S", "values": [[0.5], [5], [50]]}])
        self.assertTrue(build(small).build())
        self.assertIn('<c:numFmt formatCode="General" sourceLinked="0"/>', written_out(small)[0])
        self.assertIn('<c:numFmt formatCode="#,##0" sourceLinked="0"/>', written_out(strip_page())[0])

    def test_the_rows_are_named_once_each(self) -> None:
        for rows in (None, [], ["a", ""], ["a", "a", "b"], ["a", 1, "b"]):
            with self.subTest(rows=rows):
                self.assertIn("categories" if rows != ["a", "a", "b"] else "twice",
                              refused_strip(categories=rows, series=[{"name": "S", "values": [[5]] * 3}]))

    def test_the_numbers_are_one_list_for_each_row(self) -> None:
        for values in ([[5], [6]], [[5], [6], 7], "5", [[5], [6], [True]], [[5], [6], [float("nan")]]):
            with self.subTest(values=values):
                self.assertIn("series 1", refused_strip(series=[{"name": "S", "values": values}]))
        self.assertIn("no point at all", refused_strip(series=[{"name": "S", "values": [[], [], []]}]))
        self.assertIn("`series`", refused_strip(series=[]))

    def test_a_point_off_the_axis_is_named_not_cut_off(self) -> None:
        for number in (0.5, 20000, 0, -3):
            with self.subTest(number=number):
                said = refused_strip(series=[{"name": "S", "values": [[5], [number], [7]]}])
                self.assertIn("Product shots", said)
                self.assertIn("outside the axis", said)

    def test_a_name_twice_or_the_name_of_the_medians(self) -> None:
        self.assertIn("twice", refused_strip(series=[SMALL, SMALL]))
        self.assertIn("'Median' is the name of the medians", refused_strip(series=[{**SMALL, "name": "Median"}]))

    def test_a_highlight_and_a_tone_or_a_highlight_that_names_nothing(self) -> None:
        self.assertIn("highlight", refused_strip(highlight="Medium"))
        self.assertIn("tone", refused_strip(highlight="Small", series=[SMALL, {**LARGE, "tone": "good"}]))

    def test_a_fourth_series_needs_a_colour_of_its_own(self) -> None:
        series = [{**SMALL, "name": name} for name in ("A", "B", "C", "D")]
        self.assertIn("series 4", refused_strip(series=series))

    def test_the_switches_are_true_or_false(self) -> None:
        for key in ("median", "legend"):
            with self.subTest(key=key):
                self.assertIn(f"`{key}` is true or false", refused_strip(**{key: "yes"}))

    def test_notes_are_one_line_for_each_row(self) -> None:
        for notes in (["a"], ["a", "b", "c", "d"], "a", [1, 2, 3], ["a\nb", "", ""]):
            with self.subTest(notes=notes):
                self.assertIn("`notes` is one line of words for each of the 3", refused_strip(notes=notes))
