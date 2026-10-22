"""How a table's width is shared out among its columns, and how tall its rows are counted.

⚠ **要る幅は字の数ではなく描かれる幅で測る。**字の数の比で配った間は、全角の名前の列が数字の列と同じ割合で
しか広がらず、1 行に収まる名前が折れて、表が倍の高さに数えられた (= 入る表が「入らない」で止まった)。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pptx_agent_maker import DEFAULT  # noqa: E402
from pptx_agent_maker.layout.geometry import cm  # noqa: E402
from pptx_agent_maker.layout.types.core.read import read_table  # noqa: E402

HEAD = ["項目", "列 1", "列 2", "列 3", "列 4", "列 5", "列 6"]


def shaded(names: int = 12) -> list[list[str]]:
    """Names in the first column, the other six cells one word each on a ground as deep as its value."""
    return read_table([HEAD] + [[f"学習データの名前 {n}"] + [{"text": "多", "shade": 4}] * 6
                                for n in range(1, names + 1)], "table")


class TheWidthOfAColumn(unittest.TestCase):

    def test_a_table_whose_words_fit_on_one_line_is_counted_one_line_a_row(self) -> None:
        rows = shaded()
        widths = DEFAULT.column_widths(rows, cm(14))
        self.assertEqual(DEFAULT.table_height(rows, widths), len(rows) * DEFAULT.table_row_height())

    def test_every_column_gets_at_least_what_its_longest_cell_needs_on_one_line(self) -> None:
        rows = shaded()
        widths = DEFAULT.column_widths(rows, cm(14))
        pad = 2 * DEFAULT.spacing.cell_pad_x
        for index, width in enumerate(widths):
            longest = max(DEFAULT.width(str(row[index]), bold=row is rows[0]) for row in rows)
            self.assertGreaterEqual(width, longest + pad, f"column {index + 1} folds its longest cell")

    def test_a_shaded_cell_is_measured_by_its_words(self) -> None:
        plain = read_table([HEAD] + [[f"学習データの名前 {n}"] + ["多"] * 6 for n in range(1, 13)], "table")
        self.assertEqual(DEFAULT.column_widths(shaded(), cm(14)), DEFAULT.column_widths(plain, cm(14)))

    def test_the_widths_add_up_to_the_table(self) -> None:
        for total in (cm(8), cm(14), cm(30)):
            self.assertEqual(sum(DEFAULT.column_widths(shaded(), total)), total)

    def test_a_heading_is_measured_bold(self) -> None:
        rows = read_table([["A heading wider than its cells", "B"], ["x", "y"]], "table")
        widths = DEFAULT.column_widths(rows, cm(30))
        self.assertGreaterEqual(widths[0], DEFAULT.width(rows[0][0], bold=True) + 2 * DEFAULT.spacing.cell_pad_x)

    def test_a_table_exactly_as_wide_as_its_words_gives_each_column_what_it_needs(self) -> None:
        rows = read_table([["A heading longer than its cells", "Year"], ["x", "2020"], ["y", "2021"]], "table")
        pad = 2 * DEFAULT.spacing.cell_pad_x
        needs = [DEFAULT.width(rows[0][0], bold=True) + pad,
                 max(DEFAULT.width("Year", bold=True), DEFAULT.width("2020"), DEFAULT.width("2021")) + pad]
        self.assertEqual(DEFAULT.column_widths(rows, sum(needs)), needs,
                         "each column is its longest cell on one line (the heading set bold) and its padding")

    def test_a_long_line_of_half_width_letters_that_fits_is_one_line(self) -> None:
        """全角 1 字ぶんで数えると、欧文の長い 1 行は倍に数えられて 2 行になる。"""
        rows = read_table([["Method", "Note"], ["B", "slower, and the label of this row is long enough to wrap"]],
                          "table")
        widths = DEFAULT.column_widths(rows, cm(30))
        self.assertEqual(DEFAULT.table_height(rows, widths), len(rows) * DEFAULT.table_row_height())

    def test_a_table_too_narrow_for_its_words_still_gives_every_column_a_floor(self) -> None:
        rows = shaded()
        total = cm(8)
        widths = DEFAULT.column_widths(rows, total)
        self.assertGreaterEqual(min(widths), total // (len(HEAD) * 3))
        self.assertGreater(DEFAULT.table_height(rows, widths), len(rows) * DEFAULT.table_row_height(),
                           "a table this narrow folds its names, and its height says so")


if __name__ == "__main__":
    unittest.main()
