"""A table can name a CSV among the assets instead of listing its rows: `table = { data = "x.csv" }`.

結果の file から機械で埋めた表を、manifest に書き写さずに読む口。1 行目が見出しの行で、マスは字のまま
(= 数を整形しない)。残す列 (= `columns`) と、手で足す注 (= `cells` の `after` と `text`) も、CSV の見出しの字と
1 列目の字で指す。指した先が無い・2 つ以上ある時は、注が黙って消えないように止める。
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))

from pptx_agent_maker import DEFAULT  # noqa: E402
from pptx_agent_maker.__main__ import main  # noqa: E402
from pptx_agent_maker.deck.build import build as bake  # noqa: E402
from pptx_agent_maker.layout import types  # noqa: E402
from pptx_agent_maker.layout.parts.elements import Table  # noqa: E402
from pptx_agent_maker.layout.parts.page import PageFullError  # noqa: E402
from pptx_agent_maker.layout.types import PageTypeError  # noqa: E402
from pptx_agent_maker.layout.types.core.read import read_table  # noqa: E402
from pptx_agent_maker.project import Workspace, create  # noqa: E402
from pptx_agent_maker.project.files.manifest import Manifest, ManifestError  # noqa: E402
from pptx_agent_maker.write import aspect  # noqa: E402

RESULTS = "手法,値,備考\nA,0.50,速い\nB,1.25,遅い\nC,3,普通\n"
#: 見出しの行と、その下の行
HEADING = ["手法", "値", "備考"]
BODY = [["A", "0.50", "速い"], ["B", "1.25", "遅い"], ["C", "3", "普通"]]


class _Assets(unittest.TestCase):
    """A folder of assets the tests write their CSV files into."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def asset(self, name: str) -> Path:
        return self.dir / name

    def write(self, text: str, name: str = "results.csv") -> None:
        (self.dir / name).write_text(text, encoding="utf-8")

    def read(self, table, text: str = RESULTS) -> list[list[str]]:
        self.write(text)
        return read_table(table, "table", self.asset)

    def refused(self, table, text: str = RESULTS) -> str:
        """What the reader says when it stops (= and that it stops)."""
        with self.assertRaises(PageTypeError) as refused:
            self.read(table, text)
        return str(refused.exception)

    def page(self, spec: dict):
        return types.build(spec, self.asset, aspect, DEFAULT)


def table_of(page) -> Table:
    return next(e for e in page.build() if isinstance(e, Table))


class TheWholeFile(_Assets):
    def test_every_row_of_the_file_is_a_row_of_the_table_and_the_first_is_the_heading(self) -> None:
        rows = self.read({"data": "results.csv"})
        self.assertEqual([HEADING, *BODY], rows)
        self.assertTrue(all(type(cell) is str for row in rows for cell in row))

    def test_the_words_stay_as_they_are_written_and_only_the_edges_are_trimmed(self) -> None:
        rows = self.read({"data": "results.csv"},
                         '﻿name , value\n"a, b", 0.50 \n\n  ,  \n00123,1e3\n')
        self.assertEqual([["name", "value"], ["a, b", "0.50"], ["00123", "1e3"]], rows)

    def test_a_table_written_as_rows_is_read_as_it_was(self) -> None:
        rows = read_table([["手法", "値"], {"band": "Group"}, ["A", {"harvey": 3}]], "table", self.asset)
        self.assertEqual(["手法", "値"], rows[0])
        self.assertEqual("Group", str(rows[1][0]))
        self.assertEqual("\u25d5", str(rows[2][1]))


class TheColumnsToKeep(_Assets):
    def test_the_columns_are_kept_in_the_order_they_are_named(self) -> None:
        rows = self.read({"data": "results.csv", "columns": ["備考", "手法"]})
        self.assertEqual([["備考", "手法"], ["速い", "A"], ["遅い", "B"], ["普通", "C"]], rows)

    def test_a_column_left_out_is_not_in_the_table(self) -> None:
        rows = self.read({"data": "results.csv", "columns": ["手法", "値"]})
        self.assertEqual([["手法", "値"], ["A", "0.50"], ["B", "1.25"], ["C", "3"]], rows)

    def test_a_heading_written_twice_in_the_file_is_fine_while_nobody_names_it(self) -> None:
        text = "k,v,v\na,1,2\n"
        self.assertEqual([["k", "v", "v"], ["a", "1", "2"]], self.read({"data": "results.csv"}, text))
        self.assertEqual([["k"], ["a"]], self.read({"data": "results.csv", "columns": ["k"]}, text))


class TheNotesOnACell(_Assets):
    def test_after_puts_words_behind_the_value(self) -> None:
        rows = self.read({"data": "results.csv",
                          "cells": [{"row": "B", "column": "値", "after": "（再測定）"}]})
        self.assertEqual(["B", "1.25（再測定）", "遅い"], rows[2])
        self.assertEqual([HEADING, BODY[0], BODY[2]], [rows[0], rows[1], rows[3]])

    def test_after_puts_nothing_between_the_value_and_the_words(self) -> None:
        rows = self.read({"data": "results.csv", "cells": [{"row": "A", "column": "値", "after": " (n=3)"}]})
        self.assertEqual("0.50 (n=3)", rows[1][1])

    def test_text_is_the_whole_cell(self) -> None:
        rows = self.read({"data": "results.csv", "cells": [{"row": "C", "column": "値", "text": "―"}]})
        self.assertEqual(["C", "―", "普通"], rows[3])

    def test_a_row_is_found_by_the_first_cell_of_the_file_even_when_columns_leaves_it_out(self) -> None:
        rows = self.read({"data": "results.csv", "columns": ["値", "備考"],
                          "cells": [{"row": "B", "column": "備考", "after": "（要確認）"}]})
        self.assertEqual([["値", "備考"], ["0.50", "速い"], ["1.25", "遅い（要確認）"], ["3", "普通"]], rows)

    def test_a_cell_is_found_by_the_heading_of_the_file_wherever_columns_puts_it(self) -> None:
        rows = self.read({"data": "results.csv", "columns": ["備考", "値"],
                          "cells": [{"row": "A", "column": "値", "after": "*"}]})
        self.assertEqual(["速い", "0.50*"], rows[1])

    def test_a_cell_filled_by_text_can_stand_where_the_file_has_a_gap(self) -> None:
        rows = self.read({"data": "results.csv", "cells": [{"row": "B", "column": "値", "text": "―"}]},
                         "手法,値\nA,1\nB,\n")
        self.assertEqual(["B", "―"], rows[2])

    def test_several_cells_are_edited_one_by_one(self) -> None:
        rows = self.read({"data": "results.csv",
                          "cells": [{"row": "A", "column": "値", "after": "*"},
                                    {"row": "A", "column": "備考", "text": "最速"},
                                    {"row": "C", "column": "値", "after": "†"}]})
        self.assertEqual([["A", "0.50*", "最速"], ["B", "1.25", "遅い"], ["C", "3†", "普通"]], rows[1:])


class EveryPlaceATableCanBeWritten(_Assets):
    TABLE = {"data": "results.csv", "columns": ["手法", "値", "備考"],
             "cells": [{"row": "B", "column": "値", "after": "（再測定）"}]}
    WANTED = [HEADING, ["A", "0.50", "速い"], ["B", "1.25（再測定）", "遅い"], ["C", "3", "普通"]]

    def test_a_board_a_table_under_a_body_and_a_cell_of_a_compose_read_it_the_same(self) -> None:
        self.write(RESULTS)
        pages = {
            "a board": {"type": "board", "title": "だい", "table": self.TABLE},
            "under a body": {"type": "cards", "title": "だい", "cards": [["見出し", "本文"]], "table": self.TABLE},
            "a cell of a compose": {"type": "compose", "title": "だい",
                                    "rows": [{"cells": [{"table": self.TABLE}]}]},
            "a cell of a panel": {"type": "compose", "title": "だい",
                                  "rows": [{"cells": [{"panel": {"heading": "表", "tone": "box",
                                                                 "rows": [{"cells": [{"table": self.TABLE}]}]}}]}]},
        }
        for where, spec in pages.items():
            with self.subTest(where):
                self.assertEqual([tuple(row) for row in self.WANTED], list(table_of(self.page(spec)).rows))

    def test_the_page_is_the_page_the_same_rows_written_out_would_be(self) -> None:
        self.write(RESULTS)
        written = {"type": "board", "title": "だい", "table": self.WANTED}
        from_file = {"type": "board", "title": "だい", "table": self.TABLE}
        self.assertEqual(self.page(written).build(), self.page(from_file).build())

    def test_a_gap_in_the_file_is_refused_as_an_empty_cell_of_rows_is(self) -> None:
        self.write("手法,値\nA,1\nB,\n")
        with self.assertRaises(ValueError) as refused:
            self.page({"type": "board", "title": "だい", "table": {"data": "results.csv"}}).build()
        self.assertIn("empty cell at row 2, column 1", str(refused.exception))

    def test_a_table_that_does_not_fit_is_refused_as_a_table_of_rows_is(self) -> None:
        self.write("k,v\n" + "".join(f"r{n},{n}\n" for n in range(60)))
        with self.assertRaises(PageFullError) as refused:
            self.page({"type": "board", "title": "だい", "table": {"data": "results.csv"}})
        self.assertIn("this is two pages, not one", str(refused.exception))


class WhatStopsTheTable(_Assets):
    def test_the_file_must_be_a_csv_that_is_named(self) -> None:
        for table in ({"data": "results.txt"}, {"data": "results"}, {"data": 3}, {"columns": ["手法"]}, {}):
            with self.subTest(table=table):
                self.assertIn("`data` is the name of a CSV file", self.refused(table))

    def test_a_key_nobody_reads_is_refused_by_name(self) -> None:
        for key in ("sort", "rows", "mark", "shade", "band", "only"):
            with self.subTest(key=key):
                said = self.refused({"data": "results.csv", key: 1})
                self.assertIn(f"does not take {key}", said)
                self.assertIn("cells, columns, data", said)

    def test_a_file_with_nothing_under_the_heading_row_stops(self) -> None:
        for text in ("", "\n\n", "手法,値\n", "手法,値\n,\n"):
            with self.subTest(text=text):
                self.assertIn("needs a heading row and at least one row under it", self.refused({"data": "results.csv"}, text))

    def test_a_row_with_another_number_of_cells_is_named_by_its_line(self) -> None:
        said = self.refused({"data": "results.csv"}, "手法,値,備考\nA,1,x\n\nB,2\n")
        self.assertIn("results.csv, line 4 has 2 cells and the heading row has 3", said)
        said = self.refused({"data": "results.csv"}, "手法,値\nA,1,x\n")
        self.assertIn("line 2 has 3 cells and the heading row has 2", said)

    def test_a_file_that_is_not_utf8_is_named(self) -> None:
        (self.dir / "results.csv").write_bytes("手法,値\nA,1\n".encode("cp932"))
        with self.assertRaises(PageTypeError) as refused:
            read_table({"data": "results.csv"}, "table", self.asset)
        self.assertIn("results.csv is not UTF-8 text", str(refused.exception))

    def test_a_column_the_file_does_not_have_stops(self) -> None:
        said = self.refused({"data": "results.csv", "columns": ["手法", "速さ"]})
        self.assertIn("'速さ' is not a heading of results.csv", said)
        self.assertIn("'手法', '値', '備考'", said)

    def test_a_column_named_twice_stops(self) -> None:
        self.assertIn("names '値' twice", self.refused({"data": "results.csv", "columns": ["値", "手法", "値"]}))

    def test_columns_that_name_nothing_stop(self) -> None:
        for columns in ([], "手法", 3, [3]):
            with self.subTest(columns=columns):
                self.refused({"data": "results.csv", "columns": columns})

    def test_a_heading_the_file_has_twice_cannot_be_named(self) -> None:
        text = "k,v,v\na,1,2\n"
        for table in ({"data": "results.csv", "columns": ["v"]},
                      {"data": "results.csv", "cells": [{"row": "a", "column": "v", "after": "*"}]}):
            with self.subTest(table=table):
                self.assertIn("has the heading 'v' in columns 2 and 3", self.refused(table, text))

    def test_a_row_the_file_does_not_have_stops(self) -> None:
        said = self.refused({"data": "results.csv", "cells": [{"row": "D", "column": "値", "after": "*"}]})
        self.assertIn("cells, entry 1", said)
        self.assertIn("no row whose first cell is 'D'", said)

    def test_a_row_the_file_has_twice_stops_and_says_where(self) -> None:
        said = self.refused({"data": "results.csv", "cells": [{"row": "A", "column": "値", "after": "*"}]},
                            "手法,値\nA,1\nB,2\nA,3\n")
        self.assertIn("2 rows whose first cell is 'A' (= lines 2 and 4)", said)

    def test_a_column_that_columns_left_out_stops(self) -> None:
        said = self.refused({"data": "results.csv", "columns": ["手法", "値"],
                             "cells": [{"row": "A", "column": "備考", "after": "*"}]})
        self.assertIn("'備考' is not kept by `columns`", said)

    def test_a_column_the_file_does_not_have_stops_in_a_cell_too(self) -> None:
        said = self.refused({"data": "results.csv", "cells": [{"row": "A", "column": "速さ", "after": "*"}]})
        self.assertIn("'速さ' is not a heading of results.csv", said)

    def test_the_heading_row_is_not_edited(self) -> None:
        said = self.refused({"data": "results.csv", "cells": [{"row": "手法", "column": "値", "text": "x"}]})
        self.assertIn("is the heading row of results.csv", said)

    def test_a_cell_takes_after_or_text_and_not_both_or_neither(self) -> None:
        for edit in ({"row": "A", "column": "値", "after": "*", "text": "x"}, {"row": "A", "column": "値"}):
            with self.subTest(edit=edit):
                self.assertIn("`after` (= words put after its value) or `text`",
                              self.refused({"data": "results.csv", "cells": [edit]}))

    def test_an_entry_of_cells_that_is_not_written_whole_stops(self) -> None:
        for edit in ({"row": "A", "after": "*"}, {"column": "値", "after": "*"}, {"row": 1, "column": "値", "after": "*"},
                     {"row": "A", "column": "値", "after": 3}, {"row": "A", "column": "値", "text": None},
                     {"row": "A", "column": "値", "after": "*", "shade": 2}, "A", ["A", "値", "*"]):
            with self.subTest(edit=edit):
                self.refused({"data": "results.csv", "cells": [edit]})

    def test_cells_that_are_not_a_list_stop(self) -> None:
        self.assertIn("`cells` is a list", self.refused({"data": "results.csv", "cells": {"row": "A"}}))

    def test_two_entries_for_one_cell_stop_and_the_second_is_named(self) -> None:
        said = self.refused({"data": "results.csv", "cells": [{"row": "A", "column": "値", "after": "*"},
                                                               {"row": "B", "column": "値", "after": "†"},
                                                               {"row": "A", "column": "値", "text": "x"}]})
        self.assertIn("cells, entry 3", said)
        self.assertIn("already edited by entry 1", said)

    def test_a_table_that_is_neither_rows_nor_a_file_says_both_ways(self) -> None:
        for table in ("results.csv", 3, [], None):
            with self.subTest(table=table):
                self.assertIn('{ data = "x.csv" }', self.refused(table))

    def test_the_place_is_named_inside_a_compose(self) -> None:
        self.write(RESULTS)
        spec = {"type": "compose", "title": "だい",
                "rows": [{"cells": [{"table": {"data": "results.csv", "columns": ["速さ"]}}]}]}
        with self.assertRaises(PageTypeError) as refused:
            self.page(spec).build()
        self.assertIn("table: columns", str(refused.exception))
        self.assertIn("'速さ' is not a heading of results.csv", str(refused.exception))


class BakedFromTheAssetsOfAProject(unittest.TestCase):
    """A CSV among the assets of a project becomes the cells of a table in the built deck."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = create(Path(self.tmp.name) / "project")
        (self.root / "assets" / "results.csv").write_text(RESULTS, encoding="utf-8")
        self.workspace = Workspace.load(self.root)

    def bake(self, table: str) -> str:
        """The text of every slide of the deck a board with this table builds."""
        (self.root / "deck.toml").write_text(
            'specimen = "specimen.pptx"\nout = "deck.pptx"\n'
            f'[[pages]]\nkind = "declare"\ntype = "board"\ntitle = "結果"\nfooter = "出所: 計測"\ntable = {table}\n',
            encoding="utf-8")
        built = bake(self.workspace, Manifest.load(self.workspace.manifest("deck")))
        with zipfile.ZipFile(built) as archive:
            return "".join(archive.read(name).decode("utf-8") for name in archive.namelist()
                           if name.startswith("ppt/slides/slide") and name.endswith(".xml"))

    def test_the_cells_of_the_file_are_the_cells_of_the_table(self) -> None:
        slide = self.bake('{ data = "results.csv" }')
        for words in ("手法", "備考", "0.50", "1.25", "速い", "遅い", "普通"):
            self.assertIn(f"<a:t>{words}</a:t>", slide)

    def test_the_columns_and_the_notes_reach_the_deck(self) -> None:
        slide = self.bake('{ data = "results.csv", columns = ["手法", "値"], '
                          'cells = [{ row = "B", column = "値", after = "（再測定）" }] }')
        self.assertIn("<a:t>1.25（再測定）</a:t>", slide)
        self.assertNotIn("備考", slide)
        self.assertNotIn("速い", slide)

    def test_the_checks_of_a_build_let_a_table_from_a_file_through(self) -> None:
        self.bake('{ data = "results.csv", cells = [{ row = "B", column = "値", after = "（再測定）" }] }')
        said = io.StringIO()
        with contextlib.redirect_stdout(said), contextlib.redirect_stderr(said):
            code = main(["build", str(self.root), "deck"])
        self.assertEqual(0, code, said.getvalue())

    def test_a_file_that_is_not_among_the_assets_says_so_and_which_page(self) -> None:
        with self.assertRaises(ManifestError) as raised:
            self.bake('{ data = "missing.csv" }')
        self.assertIn("page 1 of the manifest:", str(raised.exception))
        self.assertIn("asset not found: missing.csv", str(raised.exception))

    def test_a_refusal_of_the_reader_says_which_page(self) -> None:
        with self.assertRaises(ManifestError) as raised:
            self.bake('{ data = "results.csv", columns = ["速さ"] }')
        self.assertIn("page 1 of the manifest:", str(raised.exception))
        self.assertIn("'速さ' is not a heading of results.csv", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
