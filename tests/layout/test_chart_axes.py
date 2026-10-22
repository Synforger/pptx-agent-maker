"""The axes of a chart of categories: their names, and where the names of the categories stand below zero.

⚠ **軸が何の数かを言わないグラフは読めない。**横の軸の名前は `x`、縦の軸の名前は `y` (= 点のグラフと同じ鍵と
同じ意味。横棒は値の軸が横)。値の数字を棒に付けて値の軸を隠したグラフでも、名前だけは出る。

⚠ **負の値を持つグラフは、項目の名前を軸の外側の端に置く。**既定の置き場は値の軸の 0 の所で、負の棒と、その先に
付く数字が名前に重なった。
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))

from pptx_agent_maker import DEFAULT, Page, PageFullError, PageTypeError  # noqa: E402
from pptx_agent_maker.layout.geometry import Rect  # noqa: E402
from pptx_agent_maker.layout.parts.elements import Chart  # noqa: E402
from pptx_agent_maker.layout.types.bodies.chart import place_chart  # noqa: E402
from support.pages import build  # noqa: E402
from layout.test_chart import QUARTERS, NORTH, a_chart, written  # noqa: E402

S, LINE = DEFAULT.spacing, DEFAULT.line_height()
#: 頼み主の再現 (= 1 列目が項目、2 列目が差。正と負が混ざる)
DIFFERENCES = {"name": "AP", "values": [0.0013, -0.0063, -0.0008, 0.002]}


def axis(xml: str, tag: str) -> str:
    """One axis of a chart's XML (= `c:catAx` or `c:valAx`)."""
    return re.search(rf"<c:{tag}>.*?</c:{tag}>", xml, re.S).group(0)


def title_of(xml: str, tag: str) -> str | None:
    """The words of an axis's name, or None when it has none."""
    found = re.search(r"<c:title>.*?</c:title>", axis(xml, tag), re.S)
    return "".join(re.findall(r"<a:t>(.*?)</a:t>", found.group(0))) if found else None


def inner(chart: Chart) -> tuple[float, float, float, float]:
    """The plot's area in EMU, from the fractions the chart is pinned to."""
    x, y, w, h = chart.pinned.inner
    frame = chart.frame
    return (frame.left + x * frame.width, frame.top + y * frame.height, w * frame.width, h * frame.height)


class BelowZero(unittest.TestCase):
    def test_the_names_of_the_categories_stand_at_the_outer_end_when_a_value_is_below_zero(self) -> None:
        for kind in ("bar", "column", "line", "stacked"):
            with self.subTest(kind):
                category = axis(written(a_chart(kind, series=(DIFFERENCES,)))[0], "catAx")
                self.assertIn('<c:tickLblPos val="low"/>', category)

    def test_with_no_value_below_zero_the_names_stand_where_they_always_did(self) -> None:
        for kind in ("bar", "column", "line", "stacked"):
            with self.subTest(kind):
                category = axis(written(a_chart(kind))[0], "catAx")
                self.assertNotIn('val="low"', category)

    def test_the_line_at_zero_is_still_drawn_and_the_numbers_stay_at_the_end_of_their_bars(self) -> None:
        xml = written(a_chart("bar", series=(DIFFERENCES,)))[0]
        self.assertIn(f'<a:srgbClr val="{DEFAULT.palette.rule}"/>', axis(xml, "catAx"))
        self.assertIn('<c:dLblPos val="outEnd"/>', xml)

    def test_a_waterfall_that_hangs_below_the_ground_puts_its_names_at_the_foot(self) -> None:
        chart = a_chart("waterfall", series=({"name": "Change", "values": [-5, -3, 2, -6]},), totals=["Q4"])
        self.assertIn('<c:tickLblPos val="low"/>', axis(written(chart)[0], "catAx"))


class NamedAxes(unittest.TestCase):
    def test_x_names_the_axis_across_and_y_the_axis_up(self) -> None:
        column = written(a_chart("column", x="Quarter", y="Sales (units)"))[0]
        self.assertEqual(("Quarter", "Sales (units)"), (title_of(column, "catAx"), title_of(column, "valAx")))
        bar = written(a_chart("bar", x="Sales (units)", y="Quarter"))[0]
        self.assertEqual(("Quarter", "Sales (units)"), (title_of(bar, "catAx"), title_of(bar, "valAx")),
                         "on a bar chart the value axis runs across")

    def test_left_unsaid_an_axis_has_no_name(self) -> None:
        xml = written(a_chart())[0]
        self.assertIsNone(title_of(xml, "catAx"))
        self.assertIsNone(title_of(xml, "valAx"))

    def test_with_the_numbers_on_the_bars_the_value_axis_stays_for_its_name_and_prints_no_number(self) -> None:
        value = axis(written(a_chart(y="Sales (units)"))[0], "valAx")
        self.assertIn('<c:delete val="0"/>', value)
        self.assertIn('<c:tickLblPos val="none"/>', value)
        self.assertRegex(axis(written(a_chart(x="Quarter"))[0], "valAx"), r'<c:delete(/>| val="1"/>)',
                         "a name on the other axis does not bring the value axis back")

    def test_with_the_numbers_on_the_axis_it_prints_them_beside_its_name(self) -> None:
        value = axis(written(a_chart(y="Sales (units)", labels=False))[0], "valAx")
        self.assertIn('<c:delete val="0"/>', value)
        self.assertNotIn('<c:tickLblPos val="none"/>', value)

    def test_the_name_is_set_like_the_other_words_of_the_chart(self) -> None:
        name = re.search(r"<c:title>.*?</c:title>", axis(written(a_chart(y="Sales"))[0], "valAx"), re.S).group(0)
        for said in (f'sz="{round(DEFAULT.type.body * 100)}"', 'b="0"', f'<a:srgbClr val="{DEFAULT.palette.ink}"/>',
                     f'typeface="{DEFAULT.type.family}"'):
            self.assertIn(said, name, said)

    def test_a_name_that_says_nothing_is_refused(self) -> None:
        for name in ("", "  ", 3, True):
            with self.subTest(name=name), self.assertRaises(PageTypeError) as refused:
                build({"type": "chart", "title": "t",
                       "chart": {"kind": "column", "categories": QUARTERS, "series": [NORTH], "y": name}})
            self.assertIn("`y` is the name of the vertical axis", str(refused.exception))


class RoomForTheNames(unittest.TestCase):
    """A chart whose plot the toolkit holds (= callouts, notes) keeps a line under it and a line beside it for the names."""

    CALLOUT = [{"at": "Q3", "text": "the new product"}]

    def test_the_name_across_takes_a_line_under_the_plot(self) -> None:
        plain, named = (a_chart(callouts=self.CALLOUT, **keys) for keys in ({}, {"x": "Quarter"}))
        self.assertAlmostEqual(inner(plain)[1] + inner(plain)[3] - LINE - S.gap_s, inner(named)[1] + inner(named)[3],
                               delta=1)

    def test_the_name_up_takes_a_line_beside_the_plot(self) -> None:
        plain, named = (a_chart(callouts=self.CALLOUT, **keys) for keys in ({}, {"y": "Sales"}))
        self.assertAlmostEqual(inner(plain)[0] + LINE + S.gap_s, inner(named)[0], delta=1)

    def test_on_a_bar_chart_the_name_up_stands_left_of_the_names_of_the_bars(self) -> None:
        notes = {"notes": ["one", "", "three", ""]}
        plain, named = (a_chart("bar", **notes, **keys) for keys in ({}, {"y": "Quarter"}))
        self.assertAlmostEqual(inner(plain)[0] + LINE + S.gap_s, inner(named)[0], delta=1)
        below = a_chart("bar", **notes, x="Sales")
        self.assertAlmostEqual(inner(plain)[1] + inner(plain)[3] - LINE - S.gap_s, inner(below)[1] + inner(below)[3],
                               delta=1)

    def test_a_bar_chart_counts_the_name_across_when_it_asks_whether_its_bars_are_tall_enough(self) -> None:
        """名前の 1 行を数えずに、帯が名前の 1 行ちょうどの横棒が通ると、PowerPoint の側で名前どうしが重なる。"""
        page = Page("t", DEFAULT, needs_figure=False)
        body = page.body
        just = Rect(body.left, body.top, body.width, 2 * S.gap_s + len(QUARTERS) * LINE)
        chart = {"kind": "bar", "categories": QUARTERS, "series": [NORTH]}
        place_chart(page, None, chart, just, "chart")
        with self.assertRaises(PageFullError) as stopped:
            place_chart(page, None, {**chart, "x": "Sales"}, just, "chart")
        self.assertIn("its name needs", str(stopped.exception))


if __name__ == "__main__":
    unittest.main()
