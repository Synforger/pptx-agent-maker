"""A compose page laid out on a grid (cells at a row and a column, backdrops under them), and the legend a cell may hold.

見張るのは 6 つ ― 列と行が本体を比で分け合い (= 間は `gap_x` と `gap_y`)、マスと背景が覆う範囲いっぱいの枠に置かれること、
箱は範囲を使い切り文章は自分の高さのまま上に寄ること、背景がマスより下の層に敷かれること、格子の頁の書き方の誤りが
止まること (= 重なったマスは、どのマスとどのマスかを言う)、マスの `legend = true` が頁で使った地の名前を縦に並べて
頁の下の凡例を出さないこと、格子のマスどうしを矢印で結べること (= 向き合わなければ曲がる線)。
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))
from support.pages import asset, box_of, build  # noqa: E402

from pptx_agent_maker import DEFAULT, checks  # noqa: E402
from pptx_agent_maker.layout.geometry import Rect  # noqa: E402
from pptx_agent_maker.layout.parts.page import Page, PageFullError  # noqa: E402
from pptx_agent_maker.layout.tokens import theme_from  # noqa: E402
from pptx_agent_maker.layout.types.bodies.compose import GRID_INSET  # noqa: E402
from pptx_agent_maker.layout.types.core.frame import legend_cells  # noqa: E402
from pptx_agent_maker.layout.types.core.read import Spec  # noqa: E402
from pptx_agent_maker.layout.types.core.registry import PageTypeError  # noqa: E402
from pptx_agent_maker.write import add_page, aspect, new_deck, save  # noqa: E402

S, T = DEFAULT.spacing, DEFAULT.type
#: how far in from the squares it covers what stands in a cell is kept (= half of `gap_m`, on each of the four sides)
INSET = round(S.gap_m * GRID_INSET)
GROUNDS = {"Deep": "8B1E3F", "Pale": "EAF0F8"}
FILLED = theme_from({"grounds": GROUNDS})


def card(heading="A card", body="Some words", *, tone=None, **cell):
    """A cell holding a card (= `tone` is the card's; any other key is the cell's: `at`, `span`, `id`)."""
    return {"card": {"heading": heading, "body": body, **({"tone": tone} if tone else {})}, **cell}


def grid_page(cells, columns=(1, 1, 1), rows=(1, 1), backdrops=None, theme=FILLED, **extra):
    data = {"type": "compose", "title": "A page", "grid": {"columns": list(columns), "rows": list(rows)},
            "cells": cells, **extra}
    if backdrops is not None:
        data["backdrops"] = backdrops
    return build(data, theme)


def kinds(page, kind):
    return [e for e in page.build() if e.kind == kind]


def squares(page, columns=(1, 1, 1), rows=(1, 1)):
    """The rects the grid is divided in (= what the page's body is shared out as): (columns, rows)."""
    body = page.body
    return body.columns(list(columns), gap=S.gap_x), body.rows(list(rows), gap=S.gap_y)


def area(page, first, last, columns=(1, 1, 1), rows=(1, 1)):
    """From the top left of square `first` to the bottom right of square `last` (= (row, column) from 0)."""
    across, down = squares(page, columns, rows)
    return (across[first[1]].left, down[first[0]].top, across[last[1]].right - across[first[1]].left,
            down[last[0]].bottom - down[first[0]].top)


def tuple_of(rect):
    return rect.left, rect.top, rect.width, rect.height


def kept(page, first, last, columns=(1, 1, 1), rows=(1, 1)):
    """What `area` is, taken in by the room a cell keeps on each side."""
    return tuple_of(Rect(*area(page, first, last, columns, rows)).inset(INSET))


class TheGridSharesOutTheBody(unittest.TestCase):
    def test_a_cell_stands_on_its_square_and_a_box_uses_all_of_it_but_the_room_kept_round_it(self) -> None:
        page = grid_page([card("One", at=[1, 1]), card("Two", at=[2, 3])])
        self.assertEqual(kept(page, (0, 0), (0, 0)), tuple_of(box_of(page, "One").rect))
        self.assertEqual(kept(page, (1, 2), (1, 2)), tuple_of(box_of(page, "Two").rect))

    def test_the_room_kept_is_the_same_on_all_four_sides_and_half_of_the_gap_between_boxes(self) -> None:
        page = grid_page([card("One", at=[1, 1])])
        whole = Rect(*area(page, (0, 0), (0, 0)))
        box = box_of(page, "One").rect
        self.assertEqual({INSET}, {box.left - whole.left, box.top - whole.top, whole.right - box.right,
                                   whole.bottom - box.bottom})
        self.assertEqual(round(S.gap_m / 2), INSET)

    def test_boxes_side_by_side_are_two_rooms_and_a_gap_apart_so_an_arrow_between_them_has_a_length_to_read(self) -> None:
        page = grid_page([card("One", at=[1, 1], id="a"), card("Two", at=[1, 2], id="b")],
                         links=[{"from": "a", "to": "b"}])
        one, two = box_of(page, "One").rect, box_of(page, "Two").rect
        self.assertEqual(S.gap_x + 2 * INSET, two.left - one.right)
        (arrow,) = kinds(page, "line")
        self.assertEqual(S.gap_x + 2 * INSET, abs(arrow.end[0] - arrow.start[0]))

    def test_a_text_a_table_and_a_legend_keep_the_same_room(self) -> None:
        cells = [{"text": "Words", "at": [1, 1]}, {"table": [["k", "v"], ["a", "1"]], "at": [1, 2]},
                 {"legend": True, "at": [1, 3]}, card("Deep", tone="Deep", at=[2, 1]), card("Pale", tone="Pale", at=[2, 2])]
        page = grid_page(cells)
        across, down = squares(page)
        words = next(e for e in page.build() if getattr(e, "text", None) == "Words")
        self.assertEqual((across[0].left + INSET, down[0].top + INSET), (words.rect.left, words.rect.top))
        table = kinds(page, "table")[0]
        self.assertEqual((across[1].left + INSET, down[0].top + INSET), (table.rect.left, table.rect.top))
        self.assertEqual(across[2].left + INSET, self.legend_left(page))

    def legend_left(self, page):
        return kinds(page, "swatch")[0].rect.left

    def test_squares_too_small_to_keep_the_room_stop_the_page(self) -> None:
        with self.assertRaisesRegex(PageFullError, r"cell 1: the squares it covers are too small to keep \d+ EMU"):
            grid_page([card("A", at=[1, 1])], rows=(0.001, 1))

    def test_the_columns_and_the_rows_share_the_body_by_their_weights_with_the_gaps_between(self) -> None:
        page = grid_page([card("Wide", at=[1, 1]), card("Narrow", at=[1, 2]), card("Low", at=[2, 1])],
                         columns=(3, 1), rows=(1, 2))
        wide, narrow, low = (box_of(page, n).rect for n in ("Wide", "Narrow", "Low"))
        self.assertEqual(wide.right + S.gap_x + 2 * INSET, narrow.left)
        self.assertLessEqual(abs((wide.width + 2 * INSET) - 3 * (narrow.width + 2 * INSET)), 3)
        self.assertEqual(wide.bottom + S.gap_y + 2 * INSET, low.top)
        self.assertLessEqual(abs((low.height + 2 * INSET) - 2 * (wide.height + 2 * INSET)), 3)
        self.assertEqual(page.body.bottom, low.bottom + INSET)
        self.assertEqual(page.body.right, narrow.right + INSET)

    def test_a_cell_that_spans_covers_the_squares_and_the_gaps_between_them(self) -> None:
        page = grid_page([card("Tall", at=[1, 2], span=[2, 1]), card("Wide", at=[1, 1], span=[1, 1])])
        self.assertEqual(kept(page, (0, 1), (1, 1)), tuple_of(box_of(page, "Tall").rect))
        wide = grid_page([card("Across", at=[2, 1], span=[1, 3])])
        self.assertEqual(kept(wide, (1, 0), (1, 2)), tuple_of(box_of(wide, "Across").rect))

    def test_the_gap_across_and_the_gap_down_are_the_two_gaps_of_a_use_that_sets_them_apart(self) -> None:
        theme = theme_from({"uses": {"gapped": {"like": "read", "spacing": {"gap_x": 2.0, "gap_y": 0.5}}}}).using("gapped")
        page = grid_page([card("A", at=[1, 1]), card("B", at=[1, 2]), card("C", at=[2, 1])], theme=theme)
        a, b, c = (box_of(page, name).rect for name in "ABC")
        self.assertEqual(theme.spacing.gap_x + 2 * INSET, b.left - a.right)
        self.assertEqual(theme.spacing.gap_y + 2 * INSET, c.top - a.bottom)
        self.assertNotEqual(theme.spacing.gap_x, theme.spacing.gap_y)

    def test_a_span_left_out_is_one_square(self) -> None:
        plain = grid_page([card("A", at=[1, 1])])
        said = grid_page([card("A", at=[1, 1], span=[1, 1])])
        self.assertEqual(box_of(plain, "A").rect, box_of(said, "A").rect)

    def test_a_text_keeps_its_own_height_at_the_top_of_its_squares_and_a_panel_uses_all_of_them(self) -> None:
        page = grid_page([{"text": "Users", "at": [1, 1]},
                          {"panel": {"rows": [{"cells": [{"text": "In"}]}]}, "at": [2, 1], "span": [1, 2]}])
        square = squares(page)[1][0]
        words = next(e for e in page.build() if getattr(e, "text", None) == "Users")
        self.assertEqual(square.top + INSET, words.rect.top)
        self.assertLess(words.rect.height, square.height)
        self.assertEqual(kept(page, (1, 0), (1, 1)), tuple_of(kinds(page, "panel")[0].rect))

    def test_a_cell_that_is_a_nested_set_of_rows_stands_on_its_squares_like_any_other_part(self) -> None:
        page = grid_page([{"rows": [{"cells": [card("Nested")]}], "at": [2, 2]}])
        across, down = squares(page)
        square = Rect(across[1].left, down[1].top, across[1].width, down[1].height)
        self.assertTrue(square.contains(box_of(page, "Nested").rect))

    def test_a_cell_of_no_words_is_a_space_that_a_link_may_cross(self) -> None:
        page = grid_page([card("A", at=[1, 1], id="a"), {"text": "", "at": [1, 2]}, card("B", at=[1, 3], id="b")],
                         links=[{"from": "a", "to": "b"}])
        (arrow,) = kinds(page, "line")
        self.assertEqual((), arrow.corners)


class BackdropsLieUnderTheBoxes(unittest.TestCase):
    BANDS = [{"at": [1, 1], "span": [1, 3], "tone": "band"}, {"at": [2, 1], "span": [1, 3], "tone": "tint"}]

    def test_a_backdrop_is_a_ground_over_the_squares_it_covers_and_nothing_more(self) -> None:
        page = grid_page([card("A", at=[1, 2])], backdrops=self.BANDS)
        first, second = (e.rect for e in kinds(page, "backdrop"))
        self.assertEqual(area(page, (0, 0), (0, 2)), tuple_of(first))
        self.assertEqual(area(page, (1, 0), (1, 2)), tuple_of(second))
        self.assertEqual(first.bottom + S.gap_y, second.top)

    def test_the_ground_of_a_backdrop_is_the_ground_of_its_tone_and_a_tone_a_project_named_is_read_too(self) -> None:
        page = grid_page([card("A", at=[1, 1])], backdrops=[{"at": [1, 1], "tone": "tint"},
                                                           {"at": [2, 1], "tone": "Deep"}])
        first, second = kinds(page, "backdrop")
        fill, _ink, edge = Page("p", FILLED).ground("tint")
        self.assertEqual((fill, edge), (first.colour, first.outline))
        self.assertEqual(GROUNDS["Deep"], second.colour)

    def test_a_backdrop_that_says_no_tone_is_a_pale_ground_that_says_nothing(self) -> None:
        page = grid_page([card("A", at=[1, 1])], backdrops=[{"at": [1, 1]}])
        self.assertEqual(DEFAULT.palette.band, kinds(page, "backdrop")[0].colour)

    def test_the_backdrops_are_laid_before_any_box_so_the_boxes_stand_over_them(self) -> None:
        page = grid_page([card("A", at=[1, 1]), card("B", at=[2, 2])], backdrops=self.BANDS)
        order = [e.kind for e in page.build()]
        self.assertLess(max(i for i, kind in enumerate(order) if kind == "backdrop"),
                        min(i for i, kind in enumerate(order) if kind == "box"))

    def test_a_name_set_in_a_cell_over_a_backdrop_is_a_text_like_any_other(self) -> None:
        page = grid_page([{"text": "Users", "role": "label", "at": [1, 1]}], backdrops=self.BANDS)
        words = next(e for e in page.build() if getattr(e, "text", None) == "Users")
        self.assertTrue(kinds(page, "backdrop")[0].rect.contains(words.rect))

    def test_two_backdrops_may_not_cover_the_same_square(self) -> None:
        with self.assertRaisesRegex(PageTypeError, "backdrop 2 and backdrop 1 both cover row 1, column 2"):
            grid_page([card("A", at=[1, 1])], backdrops=[{"at": [1, 1], "span": [1, 2]}, {"at": [1, 2]}])

    def test_a_backdrop_may_be_under_a_cell_and_under_a_cell_that_spans(self) -> None:
        page = grid_page([card("Tall", at=[1, 1], span=[2, 1])], backdrops=self.BANDS)
        self.assertTrue(kinds(page, "backdrop")[0].rect.overlaps(box_of(page, "Tall").rect))

    def test_a_backdrop_is_an_area_a_tone_and_nothing_else(self) -> None:
        with self.assertRaisesRegex(PageTypeError, "backdrop 1 does not take colour"):
            grid_page([card("A", at=[1, 1])], backdrops=[{"at": [1, 1], "colour": "red"}])
        with self.assertRaisesRegex(PageTypeError, "backdrop 1 has no `at`"):
            grid_page([card("A", at=[1, 1])], backdrops=[{"tone": "band"}])
        with self.assertRaisesRegex(PageTypeError, "backdrop 1 has tone 'blue'"):
            grid_page([card("A", at=[1, 1])], backdrops=[{"at": [1, 1], "tone": "blue"}])
        with self.assertRaisesRegex(PageTypeError, "backdrop 1: covers column 4, and the grid has 3 columns"):
            grid_page([card("A", at=[1, 1])], backdrops=[{"at": [1, 1], "span": [1, 4]}])


class WhatMayBeWritten(unittest.TestCase):
    def refused(self, cells, pattern, **keys):
        with self.assertRaisesRegex(PageTypeError, pattern):
            grid_page(cells, **keys)

    def test_rows_and_a_grid_are_two_ways_to_lay_out_the_body_and_a_page_writes_one(self) -> None:
        with self.assertRaisesRegex(PageTypeError, "`rows` and `grid` are two ways"):
            build({"type": "compose", "title": "T", "grid": {"columns": [1], "rows": [1]},
                   "cells": [card(at=[1, 1])], "rows": [{"cells": [card()]}]}, FILLED)

    def test_cells_and_backdrops_need_a_grid_and_a_grid_needs_cells_and_a_page_needs_one_way_or_the_other(self) -> None:
        with self.assertRaisesRegex(PageTypeError, "`cells` are placed on a grid"):
            build({"type": "compose", "title": "T", "cells": [card(at=[1, 1])]}, FILLED)
        with self.assertRaisesRegex(PageTypeError, "`backdrops` are placed on a grid"):
            build({"type": "compose", "title": "T", "backdrops": [{"at": [1, 1]}]}, FILLED)
        with self.assertRaisesRegex(PageTypeError, "`grid` is filled by `cells`"):
            build({"type": "compose", "title": "T", "grid": {"columns": [1], "rows": [1]}}, FILLED)
        with self.assertRaisesRegex(PageTypeError, "missing rows"):
            build({"type": "compose", "title": "T"}, FILLED)
        self.refused([], "`cells` is empty")

    def test_a_grid_is_a_list_of_column_shares_and_a_list_of_row_shares(self) -> None:
        for grid, pattern in (({"columns": [1]}, "`rows` is a list of shares"),
                              ({"rows": [1]}, "`columns` is a list of shares"),
                              ({"columns": [], "rows": [1]}, "`columns` is a list of shares"),
                              ({"columns": [1], "rows": [1], "gap": 1}, "grid does not take gap"),
                              ({"columns": [1, 0], "rows": [1]}, "`weight` is a number above 0"),
                              ({"columns": [1], "rows": ["a"]}, "`weight` is a number above 0")):
            with self.subTest(grid=grid):
                with self.assertRaisesRegex(PageTypeError, pattern):
                    build({"type": "compose", "title": "T", "grid": grid, "cells": [card(at=[1, 1])]}, FILLED)

    def test_at_is_a_row_and_a_column_from_1_and_span_a_number_of_rows_and_a_number_of_columns(self) -> None:
        self.refused([card()], "cell 1 has no `at`")
        for at in ([0, 1], [1], [1, 2, 3], "1,1", [1.5, 1], [True, 1], [-1, 1]):
            with self.subTest(at=at):
                self.refused([card(at=at)], r"cell 1: `at` is the row and the column of its top left corner")
        for span in ([0, 1], [1], [2, 2, 2], "2", [True, 1]):
            with self.subTest(span=span):
                self.refused([card(at=[1, 1], span=span)], r"cell 1: `span` is how many rows and how many columns")

    def test_a_cell_that_reaches_out_of_the_grid_is_refused_and_the_error_says_where(self) -> None:
        self.refused([card(at=[3, 1])], r"cell 1: covers row 3, and the grid has 2 rows")
        self.refused([card(at=[1, 4])], r"cell 1: covers column 4, and the grid has 3 columns")
        self.refused([card(at=[2, 3], span=[1, 2])], r"cell 1: covers column 4, and the grid has 3 columns")
        self.refused([card(at=[1, 1], span=[3, 1])], r"cell 1: covers row 3, and the grid has 2 rows")

    def test_cells_that_cover_the_same_square_are_refused_and_the_error_says_which_two(self) -> None:
        self.refused([card("A", at=[1, 1], span=[2, 1]), card("B", at=[1, 2]), card("C", at=[2, 1])],
                     r"cell 3 and cell 1 both cover row 2, column 1")
        self.refused([card("A", at=[1, 1], span=[1, 2]), card("B", at=[1, 2])],
                     r"cell 2 and cell 1 both cover row 1, column 2")

    def test_a_cell_reads_the_keys_of_a_cell_of_a_row_except_weight_and_with_at_and_span(self) -> None:
        self.refused([card(at=[1, 1], weight=2)], "cell 1 does not take weight")
        self.refused([card(at=[1, 1], colour="red")], "cell 1 does not take colour")
        self.refused([{"at": [1, 1]}], "cell 1 holds nothing")
        self.refused([{"at": [1, 1], "card": {}, "text": "x"}], "one part per cell")

    def test_a_cell_in_a_row_may_not_write_at_or_span(self) -> None:
        with self.assertRaisesRegex(PageTypeError, "does not take at"):
            build({"type": "compose", "title": "T", "rows": [{"cells": [card(at=[1, 1])]}]}, FILLED)

    def test_a_grid_with_more_columns_than_the_gaps_between_them_leave_width_for_stops_the_page(self) -> None:
        with self.assertRaisesRegex(PageFullError, "the gaps between them are wider"):
            grid_page([card(at=[1, 1])], columns=[1] * 60, rows=[1])

    def test_a_cell_taller_than_its_squares_stops_the_page_with_the_words_a_row_uses(self) -> None:
        with self.assertRaisesRegex(PageFullError, r"cell 1: this card needs \d+ EMU of height and its row has \d+ — "
                                                    r"give the row a larger `weight`, or take something off the page; "
                                                    r"nothing will shrink"):
            grid_page([card("Tall", "word " * 400, at=[1, 1])])

    def test_two_cells_may_not_share_an_id(self) -> None:
        self.refused([card(at=[1, 1], id="x"), card(at=[1, 2], id="x")], "two cells have the id 'x'")


class LinksOnAGrid(unittest.TestCase):
    CELLS = [card("Hub", at=[1, 1], span=[2, 1], id="hub"), card("Upper", at=[1, 2], id="up"),
             card("Lower", at=[2, 2], id="down"), card("Late", at=[2, 3], id="late")]

    def test_boxes_that_face_each_other_are_joined_straight_and_a_box_over_two_rows_faces_both(self) -> None:
        page = grid_page(self.CELLS, links=[{"from": "hub", "to": "up"}, {"from": "hub", "to": "down"}])
        straight_up, straight_down = kinds(page, "line")
        self.assertEqual(((), ()), (straight_up.corners, straight_down.corners))
        self.assertEqual(straight_up.start[1], straight_up.end[1])
        self.assertEqual(box_of(page, "Hub").rect.right, straight_up.start[0])

    def test_boxes_that_do_not_face_each_other_are_joined_by_a_line_that_bends_once(self) -> None:
        page = grid_page(self.CELLS[:2] + [card("Far", at=[2, 3], id="far")], links=[{"from": "up", "to": "far"}])
        (line,) = kinds(page, "line")
        up, far = box_of(page, "Upper").rect, box_of(page, "Far").rect
        self.assertEqual(1, len(line.corners))
        self.assertEqual((up.right, up.top + up.height // 2), line.start)
        self.assertEqual((far.left + far.width // 2, far.top), line.end)

    def test_a_line_whose_short_way_is_shut_goes_round_by_the_gap_between_the_boxes(self) -> None:
        page = grid_page(self.CELLS + [card("Between", at=[1, 3], id="between")], links=[{"from": "up", "to": "late"}])
        (line,) = kinds(page, "line")
        between = box_of(page, "Between").rect
        self.assertGreater(len(line.corners), 1)
        self.assertFalse(any(between.left < max(x1, x2) and min(x1, x2) < between.right
                             and between.top < max(y1, y2) and min(y1, y2) < between.bottom
                             for (x1, y1), (x2, y2) in zip(line.points(), line.points()[1:])))


class TheDottedLineInTheLegend(unittest.TestCase):
    """`dotted_legend` says what a dotted line means: a sample of it and the words, last in the legend."""

    WORDS = "Flow to come"
    CELLS = [card("Upper", tone="Deep", at=[1, 1], id="up"), card("Lower", tone="Pale", at=[1, 2], id="down")]
    DOTTED = [{"from": "up", "to": "down", "tentative": True}]

    def page(self, cells=None, **extra):
        return grid_page(self.CELLS if cells is None else cells, columns=(1, 1), rows=(1,), **extra)

    def test_a_dotted_line_with_words_ends_the_legend_with_its_sample_and_the_words(self) -> None:
        page = self.page(links=self.DOTTED, dotted_legend=self.WORDS, legend=True)
        labels = sorted(kinds(page, "label"), key=lambda e: e.rect.left)
        self.assertEqual(["Deep", "Pale", self.WORDS], [label.text for label in labels])
        arrow, sample = kinds(page, "line")
        swatch = kinds(page, "swatch")[0]
        self.assertTrue(sample.dashed)
        self.assertEqual(arrow.colour, sample.colour)
        self.assertEqual(sample.start[1], sample.end[1])
        self.assertEqual(swatch.rect.top + swatch.rect.height // 2, sample.start[1])
        self.assertEqual(S.swatch, sample.end[0] - sample.start[0])
        self.assertEqual(sample.start[0] + S.swatch + S.gap_s, labels[2].rect.left)

    def test_the_sample_takes_the_colour_of_the_arrow_it_stands_for(self) -> None:
        tinted = [{"from": "up", "to": "down", "tentative": True, "tone": "Deep"}]
        arrow = kinds(self.page(links=tinted, dotted_legend=self.WORDS, legend=True), "line")[0]
        plain = kinds(self.page(links=self.DOTTED, dotted_legend=self.WORDS, legend=True), "line")[0]
        self.assertEqual(FILLED.palette.muted, plain.colour)
        self.assertNotEqual(arrow.colour, plain.colour)

    def test_a_page_that_does_not_write_it_lists_the_names_alone_as_before(self) -> None:
        page = self.page(links=self.DOTTED, legend=True)
        self.assertEqual(["Deep", "Pale"], sorted(label.text for label in kinds(page, "label")))
        self.assertEqual(1, len(kinds(page, "line")))

    def test_a_legend_cell_lists_the_sample_under_the_names(self) -> None:
        cells = [*self.CELLS, {"legend": True, "at": [2, 1], "id": "key"}]
        page = grid_page(cells, columns=(1, 1), rows=(1, 1), links=self.DOTTED, dotted_legend=self.WORDS)
        labels = kinds(page, "label")
        self.assertEqual(["Deep", "Pale", self.WORDS], [label.text for label in labels])
        sample, _arrow = kinds(page, "line")          # a legend cell is set with the cells, the arrows after them
        self.assertEqual(kinds(page, "swatch")[0].rect.left, sample.start[0])
        self.assertEqual(labels[1].rect.top + DEFAULT.line_height(T.body), labels[2].rect.top)
        self.assertEqual(labels[2].rect.top + DEFAULT.line_height(T.body) // 2, sample.start[1])

    def test_a_legend_cell_stands_for_the_legend_even_when_the_page_would_show_none_under_it(self) -> None:
        one_name = [card("Upper", tone="Deep", at=[1, 1], id="up"), card("Lower", at=[1, 2], id="down"),
                    {"legend": True, "at": [2, 1]}]
        page = grid_page(one_name, columns=(1, 1), rows=(1, 1), links=self.DOTTED, dotted_legend=self.WORDS)
        self.assertEqual(["Deep", self.WORDS], [label.text for label in kinds(page, "label")])

    def test_a_legend_cell_narrower_than_the_words_of_the_dotted_line_stops_the_page(self) -> None:
        cells = [{"legend": True, "at": [1, 1]}, card("Upper", tone="Deep", at=[1, 2], id="up"),
                 card("Lower", tone="Pale", at=[2, 2], id="down")]
        words = " ".join(["words"] * 12)
        with self.assertRaisesRegex(PageFullError, "the legend needs"):
            grid_page(cells, columns=(1, 2), rows=(1, 1), links=self.DOTTED, dotted_legend=words)
        grid_page(cells, columns=(1, 2), rows=(1, 1), links=self.DOTTED, dotted_legend="Short")

    def test_the_legend_under_the_page_keeps_room_for_the_sample(self) -> None:
        page = self.page(links=self.DOTTED, dotted_legend=" ".join(["a long line of words"] * 8), legend=True)
        labels = kinds(page, "label")
        self.assertGreater(len({label.rect.top for label in labels}), 1)
        self.assertLess(max(label.rect.bottom for label in labels), page.theme.frame().bottom + 1)
        self.assertLessEqual(box_of(page, "Upper").rect.bottom, min(label.rect.top for label in labels))

    def test_a_dotted_card_is_as_good_as_a_dotted_arrow(self) -> None:
        cells = [card("Upper", tone="Deep", at=[1, 1]), {**card("Lower", tone="Pale", at=[1, 2]), "card": {
            "heading": "Lower", "tone": "Pale", "tentative": True}}]
        page = self.page(cells, dotted_legend=self.WORDS)
        self.assertEqual(self.WORDS, kinds(page, "label")[-1].text)

    def test_the_words_with_no_dotted_line_on_the_page_stop_it(self) -> None:
        with self.assertRaisesRegex(PageTypeError, "this page has none"):
            self.page(links=[{"from": "up", "to": "down"}], dotted_legend=self.WORDS)
        with self.assertRaisesRegex(PageTypeError, "this page has none"):
            self.page(links=[{"from": "up", "to": "down", "tentative": False}], dotted_legend=self.WORDS)

    def test_the_words_with_no_legend_on_the_page_stop_it(self) -> None:
        with self.assertRaisesRegex(PageTypeError, "this page shows none"):
            self.page(links=self.DOTTED, dotted_legend=self.WORDS, legend=False)
        one_name = [card("Upper", tone="Deep", at=[1, 1], id="up"), card("Lower", at=[1, 2], id="down")]
        with self.assertRaisesRegex(PageTypeError, "this page shows none"):
            self.page(one_name, links=self.DOTTED, dotted_legend=self.WORDS)
        self.assertEqual(self.WORDS, kinds(self.page(one_name, links=self.DOTTED, dotted_legend=self.WORDS, legend=True),
                                          "label")[-1].text)

    def test_the_words_are_a_line_of_words(self) -> None:
        for words in ("", "  ", 3, True):
            with self.subTest(words=words), self.assertRaisesRegex(PageTypeError, "`dotted_legend` is the words"):
                self.page(links=self.DOTTED, dotted_legend=words, legend=True)

    def test_only_a_compose_page_reads_it(self) -> None:
        with self.assertRaisesRegex(PageTypeError, "dotted_legend"):
            build({"type": "cards", "title": "A page", "cards": [{"heading": "A", "tentative": True}],
                   "dotted_legend": self.WORDS})


class TheDeckOfAGridIsPassedByTheChecks(unittest.TestCase):
    def test_a_page_with_backdrops_names_boxes_over_two_rows_and_bent_arrows_is_read_clean(self) -> None:
        cells = [{"text": "Users", "role": "label", "at": [1, 1]}, {"text": "Developers", "role": "label", "at": [2, 1]},
                 card("Hub", at=[1, 2], span=[2, 1], id="hub"), card("Use", at=[1, 3], id="use"),
                 card("Build", at=[2, 3], id="build"), card("Late", at=[2, 4], id="late")]
        backdrops = [{"at": [1, 1], "span": [1, 4], "tone": "band"}, {"at": [2, 1], "span": [1, 4], "tone": "tint"}]
        page = grid_page(cells, columns=(1, 3, 3, 3), backdrops=backdrops,
                         links=[{"from": "hub", "to": "use"}, {"from": "hub", "to": "build"}, {"from": "use", "to": "late"}])
        deck = new_deck(FILLED)
        add_page(deck, page.build(), FILLED)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual([], checks.run_all(save(deck, Path(tmp) / "grid.pptx")))


def legend_rows(*cells):
    return [{"cells": [card("In", "words", tone="Pale"), card("Out", "words", tone="Deep"), *cells]}]


def compose(rows, theme=FILLED, **extra):
    return build({"type": "compose", "title": "A page", "rows": rows, **extra}, theme)


class TheLegendInACell(unittest.TestCase):
    def swatches(self, page):
        return kinds(page, "swatch")

    def test_a_cell_with_legend_lists_the_grounds_the_page_uses_one_to_a_line_under_one_another(self) -> None:
        page = compose(legend_rows({"legend": True}))
        swatches, labels = self.swatches(page), kinds(page, "label")
        self.assertEqual(["Deep", "Pale"], [label.text for label in labels])
        self.assertEqual(1, len({swatch.rect.left for swatch in swatches}))
        line = DEFAULT.line_height(T.body)
        self.assertEqual(line, swatches[1].rect.top - swatches[0].rect.top)
        self.assertEqual([GROUNDS["Deep"], GROUNDS["Pale"]], [swatch.colour for swatch in swatches])

    def test_a_row_that_holds_the_legend_alone_is_as_tall_as_the_legend_is_drawn(self) -> None:
        rows = [{"cells": [{"legend": True}, {"text": ""}]},
                {"cells": [card("In", "words", tone="Pale"), card("Out", "words", tone="Deep")]}]
        page = compose(rows)
        row_bottom = box_of(page, "In").rect.top - S.gap_y
        self.assertGreaterEqual(row_bottom, max(swatch.rect.bottom for swatch in self.swatches(page)))

    def test_a_page_with_that_cell_leaves_the_legend_under_the_page_out(self) -> None:
        with_cell = compose(legend_rows({"legend": True}))
        without = compose(legend_rows())
        self.assertEqual(2, len(self.swatches(with_cell)))
        self.assertEqual(2, len(self.swatches(without)))
        self.assertEqual(1, len({swatch.rect.top for swatch in self.swatches(without)}))
        self.assertGreater(self.swatches(without)[0].rect.top, box_of(without, "In").rect.bottom)
        self.assertLess(max(swatch.rect.bottom for swatch in self.swatches(with_cell)),
                        box_of(with_cell, "In").rect.bottom + 1)

    def test_a_cell_with_legend_stands_in_an_empty_square_of_a_grid_and_lists_the_grounds_of_the_cells(self) -> None:
        cells = [{"legend": True, "at": [1, 1]}, card("Below", tone="Deep", at=[2, 1]), card("Beside", tone="Pale", at=[1, 2], span=[2, 1])]
        page = grid_page(cells, columns=(1, 1), rows=(1, 1))
        labels = kinds(page, "label")
        self.assertEqual(["Deep", "Pale"], [label.text for label in labels])
        square = squares(page, (1, 1), (1, 1))
        self.assertTrue(square[0][0].contains(self.swatches(page)[0].rect))
        self.assertEqual(2, len(self.swatches(page)))

    def test_the_cell_holds_nothing_else_and_says_true(self) -> None:
        with self.assertRaisesRegex(PageTypeError, "holds card, legend — one part per cell"):
            compose(legend_rows({"legend": True, "card": {"heading": "x"}}))
        with self.assertRaisesRegex(PageTypeError, "`legend` is true"):
            compose(legend_rows({"legend": False}))

    def test_a_page_has_one_cell_with_legend_even_when_one_of_them_is_in_a_panel_or_a_grid(self) -> None:
        with self.assertRaisesRegex(PageTypeError, "two cells hold the legend"):
            compose(legend_rows({"legend": True}, {"legend": True}))
        panel = {"panel": {"rows": [{"cells": [{"legend": True}]}]}}
        with self.assertRaisesRegex(PageTypeError, "two cells hold the legend"):
            compose(legend_rows({"legend": True}, panel))
        with self.assertRaisesRegex(PageTypeError, "two cells hold the legend"):
            grid_page([{"legend": True, "at": [1, 1]}, {"legend": True, "at": [1, 2]}, card("A", tone="Deep", at=[2, 1])])

    def test_a_page_that_uses_no_named_ground_has_nothing_for_the_cell_to_list(self) -> None:
        with self.assertRaisesRegex(PageTypeError, "this page uses none"):
            compose([{"cells": [card("Plain"), {"legend": True}]}])

    def test_a_cell_narrower_than_its_longest_name_stops_the_page_and_one_as_wide_as_it_is_not(self) -> None:
        short, long = "Short", ("A name that is long enough that no narrow cell holds it " * 3).strip()
        theme = theme_from({"grounds": {short: "EAF0F8", long: "8B1E3F"}})
        rows = [{"cells": [card("One", tone=short), card("Two", tone=long), {"legend": True}]}]
        with self.assertRaisesRegex(PageFullError, "the legend needs"):
            compose(rows, theme)
        # as wide as the longest name needs: it stands (= the widest entry sets the width, not the narrowest)
        need = Page("p", theme).legend_width([short, long])
        self.assertLess(Page("p", theme).legend_width([short]), need)
        fits = theme_from({"grounds": {short: "EAF0F8", "A longer name": "8B1E3F"}})
        page = compose([{"cells": [card("One", tone=short), card("Two", tone="A longer name"), {"legend": True}]}], fits)
        self.assertEqual(2, len(self.swatches(page)))

    def test_a_legend_taller_than_its_squares_stops_the_page(self) -> None:
        cells = [card("One", tone="Deep", at=[2, 1]), card("Two", tone="Pale", at=[2, 2]), {"legend": True, "at": [1, 3]}]
        with self.assertRaisesRegex(PageFullError, "cell 3: this legend needs \\d+ EMU of height and its row has \\d+"):
            grid_page(cells, rows=(0.12, 1))

    def test_a_chart_that_writes_legend_does_not_count_as_a_cell_with_legend(self) -> None:
        rows = [{"cells": [{"chart": {"kind": "strip", "legend": True}}, {"legend": True}]}]
        self.assertEqual(1, legend_cells(Spec({"rows": rows}, asset, aspect)))
        cells = [{"legend": True, "at": [1, 1]}, {"chart": {"legend": True}, "at": [1, 2]}]
        self.assertEqual(1, legend_cells(Spec({"cells": cells}, asset, aspect)))
        self.assertEqual(0, legend_cells(Spec({"cells": [{"chart": {"legend": True}, "at": [1, 1]}]}, asset, aspect)))

    def test_a_cell_in_a_deep_panel_would_set_dark_words_on_a_dark_ground_and_is_refused(self) -> None:
        panel = {"panel": {"tone": "Deep", "rows": [{"cells": [{"legend": True}]}]}}
        with self.assertRaisesRegex(PageTypeError, "stands straight on the ground of this panel"):
            compose(legend_rows(panel))


if __name__ == "__main__":
    unittest.main()


class CardsStartingOnOneRowLineUp(unittest.TestCase):
    """⚠ 色の枠のカード (= `card_look = "outlined"`) は字を箱の縦の中央に置くので、同じ行から始まって
    2 行をまたぐカードと 1 行のカードで、見出しの上端がずれた (= 揃いの検査 `near_alignment` が赤にした)。
    格子のカードは、字を箱の上端から置く。"""

    def test_a_card_over_two_rows_and_a_card_on_one_put_their_headings_at_one_height(self) -> None:
        outlined = theme_from({"grounds": GROUNDS, "card_look": "outlined"})
        page = grid_page([card("One row", tone="Deep", at=[1, 1]),
                          card("Two rows", "1\n2\n3\n4", tone="Deep", at=[1, 2], span=[2, 1])],
                         columns=(1, 1), rows=(1, 1), theme=outlined)
        tops = {e.text: e.rect.top for e in page.build() if getattr(e, "text", None) in ("One row", "Two rows")}
        self.assertEqual(tops["One row"], tops["Two rows"])
