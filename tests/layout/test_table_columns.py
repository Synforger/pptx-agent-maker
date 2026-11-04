"""A table's columns can be given a ratio: `table_columns = [1, 2, 2]`, beside the table.

1 つの表を区切りごとに 2 つの表 (= `compose` のマス 2 つ) に割ると、列の幅は表ごとに字の量から決まって、上と下で
ずれる。比を書けば、字の量を見ずにその比で割る。頁の表 (= `board` を含む、どの型にも添える表) とマスの表の
どちらでも効く。書かなければ今までどおり。
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))

from support.pages import asset, build  # noqa: E402

from pptx_agent_maker import DEFAULT  # noqa: E402
from pptx_agent_maker.layout import types  # noqa: E402
from pptx_agent_maker.layout.parts.elements import Table  # noqa: E402
from pptx_agent_maker.layout.parts.page import PageFullError  # noqa: E402
from pptx_agent_maker.layout.types.core.read import read_table, read_table_columns  # noqa: E402
from pptx_agent_maker.layout.types.core.registry import PageTypeError  # noqa: E402
from pptx_agent_maker.write import aspect  # noqa: E402

SHARES = [1, 2, 2]
UPPER = [["Season", "Score", "Note"], ["Spring", "48", "-"], ["Summer", "71", "the longest note of the upper table"]]
LOWER = [["Season", "Score", "Note"], ["Autumn", "9", "short"]]


def tables(built) -> list[Table]:
    return [element for element in built.build() if isinstance(element, Table)]


def split(upper_shares=None, lower_shares=None):
    """One table written as two: the upper in a cell of a compose page, the lower as the table under its body."""
    cell = {"table": UPPER} | ({"table_columns": upper_shares} if upper_shares else {})
    page = {"type": "compose", "title": "A table cut in two", "rows": [{"cells": [cell]}], "table": LOWER}
    if lower_shares:
        page["table_columns"] = lower_shares
    return build(page)


class TheColumnsAreSharedByTheRatioWritten(unittest.TestCase):

    def test_a_table_under_a_body_takes_its_widths_in_the_ratio(self) -> None:
        built = build({"type": "board", "title": "A table", "table": UPPER, "table_columns": SHARES})
        (table,) = tables(built)
        self.assertEqual(sum(table.widths), table.rect.width)
        for width, share in zip(table.widths, SHARES):
            self.assertAlmostEqual(width / table.rect.width, share / sum(SHARES), delta=1e-6)

    def test_a_table_in_a_cell_takes_its_widths_in_the_ratio(self) -> None:
        built = types.build({"type": "compose", "title": "A table", "rows": [
            {"cells": [{"table": UPPER, "table_columns": SHARES}]}]}, asset, aspect)
        (table,) = tables(built)
        self.assertEqual(sum(table.widths), table.rect.width)
        self.assertAlmostEqual(table.widths[0] / table.widths[1], 1 / 2, places=3)
        self.assertEqual(table.widths[1], table.widths[2])

    def test_two_tables_with_different_words_stand_on_the_same_columns(self) -> None:
        """The reason for the key: a table cut in two keeps its columns in line from the upper to the lower."""
        upper, lower = tables(split(SHARES, SHARES))
        self.assertEqual(upper.rect.width, lower.rect.width)
        self.assertEqual(upper.widths, lower.widths)

    def test_without_the_key_two_tables_size_their_columns_by_their_own_words(self) -> None:
        upper, lower = tables(split())
        self.assertNotEqual(upper.widths, lower.widths, "this is what the key is for; if they agree, the test shows nothing")

    def test_the_ratio_is_read_the_way_the_columns_of_a_grid_are(self) -> None:
        """Only the proportion counts: [1, 2, 2] and [0.5, 1, 1] are one ratio."""
        a, _ = tables(split(SHARES, SHARES))
        b, _ = tables(split([0.5, 1, 1], SHARES))
        self.assertEqual(a.widths, b.widths)

    def test_the_height_is_counted_at_the_widths_the_ratio_gives(self) -> None:
        """The table takes the room its rows need at the ratio's widths, not at the widths of its words."""
        narrow = [4, 1, 1]
        rows = read_table(LOWER, "table", asset)
        widths = DEFAULT.shared_widths(narrow, tables(build({"type": "board", "title": "t", "table": LOWER}))[0].rect.width)
        (table,) = tables(build({"type": "board", "title": "t", "table": LOWER, "table_columns": narrow}))
        self.assertEqual(table.rect.height, DEFAULT.table_height(rows, widths))
        self.assertEqual(list(table.widths), widths)

    def test_the_height_of_a_table_in_a_cell_is_counted_at_the_widths_the_ratio_gives(self) -> None:
        """The row is as tall as the table at the ratio's widths (= equal shares fold a note its own words keep whole)."""
        rows = read_table(UPPER, "table", asset)
        cell = {"table": UPPER}

        def table_of(extra: dict) -> Table:
            return tables(types.build({"type": "compose", "title": "t", "rows": [{"cells": [{"text": "words"}, cell | extra]}]},
                                      asset, aspect))[0]

        by_words, equal = table_of({}), table_of({"table_columns": [1, 1, 1]})
        self.assertEqual(equal.rect.height, DEFAULT.table_height(rows, list(equal.widths)))
        self.assertGreater(equal.rect.height, by_words.rect.height, "equal shares fold the long note, and the row is taller")

    def test_a_ratio_that_leaves_a_column_too_narrow_stops_when_the_table_no_longer_fits(self) -> None:
        many = [["Heading", "Words"]] + [[f"row {n}", "a note long enough to fold at a narrow width " * 2] for n in range(14)]
        board = {"type": "board", "title": "t", "table": many}
        tables(build(board))
        with self.assertRaises(PageFullError):
            build(board | {"table_columns": [30, 1]})

    def test_a_table_with_a_band_is_shared_by_the_columns_of_its_cells(self) -> None:
        rows = [["A", "B", "C"], {"band": "Spring"}, ["1", "2", "3"]]
        (table,) = tables(build({"type": "board", "title": "t", "table": rows, "table_columns": [1, 1, 2]}))
        self.assertEqual(len(table.widths), 3)

    def test_a_table_read_from_a_csv_takes_the_ratio_too(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "t.csv").write_text("a,b,c\n1,2,3\n", encoding="utf-8")
            built = types.build({"type": "board", "title": "t", "table": {"data": "t.csv"}, "table_columns": SHARES},
                                lambda name: Path(folder) / name, aspect)
        (table,) = tables(built)
        self.assertEqual(table.widths[1], table.widths[2])
        self.assertAlmostEqual(table.widths[1] / table.widths[0], 2, places=3)

    def test_the_widths_always_add_up_to_the_table(self) -> None:
        for total in (1, 997, 12345678):
            for shares in ([1, 1, 1], [1, 2, 2], [0.3, 0.3, 0.4], [7, 1, 1, 1, 1, 1, 1]):
                self.assertEqual(sum(DEFAULT.shared_widths(shares, total)), total)

    def test_a_page_that_writes_no_ratio_is_laid_out_as_before(self) -> None:
        rows = read_table(UPPER, "table", asset)
        (table,) = tables(build({"type": "board", "title": "t", "table": UPPER}))
        self.assertEqual(list(table.widths), DEFAULT.column_widths(rows, table.rect.width))
        self.assertEqual(DEFAULT.column_widths(rows, 9000000, None), DEFAULT.column_widths(rows, 9000000))


class AWrongRatioStopsAndSaysWhere(unittest.TestCase):

    def stops(self, shares, *, in_cell: bool = False) -> str:
        with self.assertRaises(PageTypeError) as refused:
            if in_cell:
                types.build({"type": "compose", "title": "t", "rows": [
                    {"cells": [{"text": "words"}, {"table": UPPER, "table_columns": shares}]}]}, asset, aspect)
            else:
                build({"type": "board", "title": "t", "table": UPPER, "table_columns": shares})
        return str(refused.exception)

    def test_a_ratio_with_the_wrong_number_of_shares_says_how_many_each_has(self) -> None:
        for shares in ([1, 2], [1, 2, 2, 3]):
            said = self.stops(shares)
            self.assertIn(f"{len(shares)} shares", said)
            self.assertIn("3 columns", said)

    def test_a_cell_names_where_it_stands(self) -> None:
        said = self.stops([1, 2], in_cell=True)
        self.assertIn("row 1, cell 2", said)
        self.assertIn("table_columns", said)

    def test_a_share_that_is_not_above_zero_says_which_column(self) -> None:
        for bad in (0, -1, True, "wide", float("nan")):
            said = self.stops([1, bad, 1])
            self.assertIn("column 2", said, f"{bad!r}")

    def test_the_ratio_is_a_list(self) -> None:
        for bad in ([], 3, "1 2 2", {"a": 1}):
            self.assertIn("a list of shares", self.stops(bad))

    def test_a_ratio_with_no_table_to_share_is_refused(self) -> None:
        with self.assertRaises(PageTypeError) as refused:
            build({"type": "cards", "title": "t", "cards": [["a", "b"]], "table_columns": SHARES})
        self.assertIn("no `table`", str(refused.exception))

    def test_a_cell_that_holds_no_table_refuses_the_ratio(self) -> None:
        with self.assertRaises(PageTypeError) as refused:
            types.build({"type": "compose", "title": "t", "rows": [
                {"cells": [{"text": "words", "table_columns": SHARES}]}]}, asset, aspect)
        self.assertIn("belongs to a table", str(refused.exception))

    def test_a_table_that_names_its_kept_columns_by_name_is_not_a_ratio(self) -> None:
        """`columns` inside `table = { data = … }` keeps the CSV's columns by their headings; it stays that."""
        rows = [["a", "b", "c"], ["1", "2", "3"]]
        self.assertIsNone(read_table_columns(None, rows, "table"))
        self.assertEqual(read_table_columns([1, 2, 3], rows, "table"), (1.0, 2.0, 3.0))


if __name__ == "__main__":
    unittest.main()
