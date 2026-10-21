"""How tall the bands are, and how tall the boxes of one use are: written by a use, not by the type of the text.

* `band_height` and `conclusion_height` under `[theme.uses.<name>.spacing]` ― the band over a page and the band
  under it each have a height of their own, which does not follow the size of the type that sits in them
* `box_height` under `[theme.uses.<name>]` ― a use may pick how tall its boxes stand, apart from the deck
* `box_height = "middle"` ― boxes are as tall as their words, and what the body holds stands in its middle
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))
from support.pages import box_of, build, named  # noqa: E402

from pptx_agent_maker import DEFAULT, Page, cm  # noqa: E402
from pptx_agent_maker.layout.base.geometry import Rect  # noqa: E402
from pptx_agent_maker.layout.base.tokens import BOX_HEIGHTS, ThemeError, theme_from  # noqa: E402
from pptx_agent_maker.layout.parts.elements import Callout, Chart, Fill, Line  # noqa: E402
from pptx_agent_maker.layout.types.core.frame import centre_body  # noqa: E402

BAND_AND_CONCLUSION = {"type": {"band": 16}, "uses": {"tall": {
    "like": "read", "spacing": {"band_height": 1.6, "conclusion_height": 1.3}}}}
CARDS = [["One", "first"], ["Two", "second"], ["Three", "third"]]


def theme_with(**use):
    """A deck whose one named use says what `use` says."""
    return theme_from({"uses": {"said": {"like": "read", **use}}}).using("said")


def of_kind(built, kind):
    return [e for e in built.build() if e.kind == kind]


def cards_page(theme, **more):
    return build({"type": "cards", "title": "T", "cards": CARDS, "card_columns": 1, **more}, theme)


class ABandHasAHeightOfItsOwn(unittest.TestCase):
    def test_left_unsaid_the_bands_are_as_tall_as_their_type_and_both_the_same(self) -> None:
        for settings in ({}, {"type": {"band": 24}}, {"use": "present"}, {"type": {"heading": 11}}):
            with self.subTest(settings=settings):
                spacing = theme_from(settings).spacing
                self.assertEqual(spacing.band_height, spacing.conclusion_height)
        self.assertEqual(DEFAULT.spacing.band_height, DEFAULT.spacing.conclusion_height)

    def test_a_height_a_use_writes_is_kept_whatever_the_type_in_it(self) -> None:
        for body, band in ((12, 16), (12, 24), (14, 11)):
            with self.subTest(band=band):
                spacing = theme_from({"uses": {"said": {
                    "like": "read", "band": band, "heading": min(band, 14), "body": body,
                    "spacing": {"band_height": 1.6, "conclusion_height": 1.3}}}}).using("said").spacing
                self.assertEqual((cm(1.6), cm(1.3)), (spacing.band_height, spacing.conclusion_height))

    def test_the_band_over_the_page_alone_leaves_the_one_under_it_as_tall(self) -> None:
        spacing = theme_with(spacing={"band_height": 1.6}).spacing
        self.assertEqual((cm(1.6), cm(1.6)), (spacing.band_height, spacing.conclusion_height))

    def test_the_band_under_the_page_alone_leaves_the_one_over_it_following_its_type(self) -> None:
        spacing = theme_with(band=24, spacing={"conclusion_height": 0.9}).spacing
        self.assertEqual(round(DEFAULT.spacing.band_height * 24 / 16), spacing.band_height)
        self.assertEqual(cm(0.9), spacing.conclusion_height)

    def test_the_page_takes_the_band_over_it_and_the_band_under_it_at_their_own_heights(self) -> None:
        theme = theme_from(BAND_AND_CONCLUSION).using("tall")
        bands = {e.rect.top: e for e in of_kind(build(
            {"type": "cards", "title": "T", "cards": CARDS, "condition": "c", "conclusion": "d"}, theme), "band")}
        over, under = sorted(bands.values(), key=lambda e: e.rect.top)
        self.assertEqual((cm(1.6), cm(1.3)), (over.rect.height, under.rect.height))

    def test_the_body_between_them_is_what_the_two_heights_leave(self) -> None:
        theme = theme_from(BAND_AND_CONCLUSION).using("tall")
        plain = Page("T", theme).body
        both = Page("T", theme, condition="c", conclusion="d").body
        gap = theme.spacing.gap_m
        self.assertEqual(plain.height - (cm(1.6) + gap) - (cm(1.3) + gap), both.height)

    def test_a_distance_below_zero_or_not_a_number_is_refused_under_its_own_name(self) -> None:
        for name in ("band_height", "conclusion_height"):
            for value, said in ((-1, "is -1cm"), ("tall", "is 'tall'"), (True, "is True")):
                with self.subTest(name=name, value=value), self.assertRaises(ThemeError) as refused:
                    theme_from({"uses": {"said": {"like": "read", "spacing": {name: value}}}})
                self.assertIn(f"theme.uses.said.spacing.{name} {said}", str(refused.exception))

    def test_the_deck_cannot_write_them_apart_from_a_use(self) -> None:
        """余白と間隔は案件の名前付きの使い方の中にだけ在る (= `[theme]` の直下では拒まれる)。"""
        for name in ("band_height", "conclusion_height"):
            with self.subTest(name=name), self.assertRaises(ThemeError):
                theme_from({name: 1.6})

    def test_a_page_in_a_use_with_no_height_of_its_own_is_back_to_the_type(self) -> None:
        theme = theme_from({"uses": {"tall": {"like": "read", "spacing": {"band_height": 1.6}}}})
        self.assertEqual(DEFAULT.spacing, theme.using("tall").using("read").spacing)


class AUseMayPickHowTallItsBoxesStand(unittest.TestCase):
    def test_a_use_that_says_nothing_has_the_height_of_the_deck(self) -> None:
        for deck in BOX_HEIGHTS:
            theme = theme_from({"box_height": deck, "uses": {"plain": {"like": "read"}}})
            with self.subTest(deck=deck):
                self.assertEqual(deck, theme.box_height)
                self.assertEqual(deck, theme.using("plain").box_height)
                self.assertEqual(deck, theme.using("present").box_height)

    def test_a_use_that_says_its_own_wins_over_the_deck(self) -> None:
        for deck in BOX_HEIGHTS:
            for own in BOX_HEIGHTS:
                with self.subTest(deck=deck, own=own):
                    theme = theme_from({"box_height": deck, "uses": {"said": {"like": "read", "box_height": own}}})
                    self.assertEqual(own, theme.using("said").box_height)
                    self.assertEqual(deck, theme.box_height, "the deck's own use is the deck's")

    def test_a_deck_made_in_such_a_use_has_its_height(self) -> None:
        theme = theme_from({"box_height": "page", "use": "said",
                            "uses": {"said": {"like": "read", "box_height": "middle"}}})
        self.assertEqual("middle", theme.box_height)

    def test_a_page_in_a_use_without_one_goes_back_to_the_height_of_the_deck(self) -> None:
        """資料が使い方 (= 箱の高さを書いた) で組まれていても、書いていない使い方を名指した頁は資料の値に戻る。"""
        theme = theme_from({"box_height": "page", "use": "said", "uses": {
            "said": {"like": "read", "box_height": "middle"}, "plain": {"like": "read"}}})
        self.assertEqual("page", theme.using("plain").box_height)
        self.assertEqual("page", theme.using("plain").using("present").box_height)
        self.assertEqual("middle", theme.using("plain").using("said").box_height)

    def test_the_sizes_a_deck_writes_for_its_own_use_keep_the_height_of_that_use(self) -> None:
        theme = theme_from({"use": "said", "type": {"body": 13},
                            "uses": {"said": {"like": "read", "box_height": "page"}}})
        self.assertEqual(("page", 13), (theme.box_height, theme.type.body))

    def test_a_name_nobody_knows_is_refused_under_the_use_it_was_written_in(self) -> None:
        for value in ("wide", "", 1, True, ["page"]):
            with self.subTest(value=value), self.assertRaises(ThemeError) as refused:
                theme_from({"uses": {"said": {"like": "read", "box_height": value}}})
            self.assertIn("theme.uses.said.box_height", str(refused.exception))

    def test_a_page_in_a_use_of_boxes_as_tall_as_the_page_fills_it_in_a_deck_that_does_not(self) -> None:
        theme = theme_from({"uses": {"full": {"like": "read", "box_height": "page"}}})
        full = theme.using("full")
        data = {"type": "cards", "title": "T", "cards": CARDS, "card_columns": 1}
        body = Page("T", full).body
        self.assertEqual(body.bottom, max(e.rect.bottom for e in of_kind(build(data, full), "box")))
        self.assertLess(max(e.rect.bottom for e in of_kind(build(data, theme), "box")), body.bottom - 1)

    def test_a_page_naming_a_use_reads_it_at_build_time(self) -> None:
        theme = theme_from({"uses": {"full": {"like": "read", "box_height": "page"}}})
        body = Page("T", theme).body
        built = build({"type": "cards", "title": "T", "cards": CARDS, "card_columns": 1, "use": "full"}, theme)
        self.assertEqual(body.bottom, max(e.rect.bottom for e in of_kind(built, "box")))


class TheBodyStandsInTheMiddle(unittest.TestCase):
    MIDDLE = theme_from({"box_height": "middle"})

    def test_it_is_one_of_the_heights_a_deck_may_pick(self) -> None:
        self.assertIn("middle", BOX_HEIGHTS)
        self.assertEqual("middle", self.MIDDLE.box_height)

    def test_the_boxes_are_as_tall_as_their_words_and_a_gap_apart_as_they_were(self) -> None:
        text, middle = of_kind(cards_page(DEFAULT), "box"), of_kind(cards_page(self.MIDDLE), "box")
        self.assertEqual([e.rect.height for e in text], [e.rect.height for e in middle])
        self.assertEqual([b.rect.top - a.rect.bottom for a, b in zip(text, text[1:])],
                         [b.rect.top - a.rect.bottom for a, b in zip(middle, middle[1:])])

    def test_what_is_left_of_the_body_is_shared_by_the_top_and_the_bottom(self) -> None:
        body = Page("T", self.MIDDLE).body
        boxes = of_kind(cards_page(self.MIDDLE), "box")
        above, below = boxes[0].rect.top - body.top, body.bottom - boxes[-1].rect.bottom
        self.assertGreater(above, 0)
        self.assertLessEqual(abs(above - below), 1)

    def test_everything_the_body_placed_moves_together_by_the_same_distance(self) -> None:
        text, middle = cards_page(DEFAULT).build(), cards_page(self.MIDDLE).build()
        moved = {(m.rect.top - t.rect.top) for t, m in zip(text, middle) if t.kind in ("box", "box_heading", "box_body")}
        self.assertEqual(1, len(moved))
        self.assertGreater(moved.pop(), 0)

    def test_the_title_the_bands_and_the_foot_stay_where_they_are(self) -> None:
        data = {"condition": "c", "conclusion": "d", "footer": "f", "kicker": "k"}
        text, middle = cards_page(DEFAULT, **data).build(), cards_page(self.MIDDLE, **data).build()
        self.assertEqual(len(text), len(middle))
        still = [t for t, m in zip(text, middle) if t.kind not in ("box", "box_heading", "box_body")]
        self.assertEqual(still, [m for t, m in zip(text, middle) if t.kind not in ("box", "box_heading", "box_body")])
        self.assertTrue({"title", "band", "band_text", "footer"} <= {e.kind for e in still})

    def test_the_bands_of_their_own_heights_are_the_edges_of_the_middle(self) -> None:
        theme = replace(theme_from({"box_height": "middle", **BAND_AND_CONCLUSION}).using("tall"))
        built = cards_page(theme, condition="c", conclusion="d")
        body = Page("T", theme, condition="c", conclusion="d").body
        boxes = of_kind(built, "box")
        self.assertLessEqual(abs((boxes[0].rect.top - body.top) - (body.bottom - boxes[-1].rect.bottom)), 1)

    def test_a_legend_a_table_and_a_reading_stand_with_the_cards_as_one(self) -> None:
        data = {"table": [["列", "値"], ["A", "1"]], "note": "How to read this", "card_columns": 3}
        body = Page("T", self.MIDDLE).body
        built = cards_page(self.MIDDLE, **data)
        placed = [e for e in built.build() if e.rect.top >= body.top]
        top = min(e.rect.top for e in placed)
        bottom = max(e.rect.bottom for e in placed)
        self.assertGreater(top, body.top)
        self.assertLessEqual(abs((top - body.top) - (body.bottom - bottom)), 1)
        text = cards_page(DEFAULT, **data)
        # 間隔は動かない: 表と読み方の並びは、字の高さの資料と同じ
        self.assertEqual(of_kind(text, "table")[0].rect.top - of_kind(text, "box")[0].rect.top,
                         of_kind(built, "table")[0].rect.top - of_kind(built, "box")[0].rect.top)
        self.assertEqual(of_kind(text, "note")[0].rect.top - of_kind(text, "table")[0].rect.top,
                         of_kind(built, "note")[0].rect.top - of_kind(built, "table")[0].rect.top)

    def test_a_body_that_fills_the_page_is_not_moved(self) -> None:
        data = {"type": "figure", "title": "T", "figure": "dot.png"}
        self.assertEqual(build(data).build(), build(data, self.MIDDLE).build())

    def test_every_page_that_is_not_in_the_middle_is_built_as_it_was(self) -> None:
        for data in (
            {"type": "cards", "title": "T", "cards": CARDS, "card_columns": 3, "condition": "c"},
            {"type": "flow", "title": "T", "stages": [{"name": "s", "nodes": [["A", "a"]]},
                                                       {"name": "t", "nodes": [["B", "b"]]}]},
            {"type": "compose", "title": "T", "rows": [{"cells": [{"card": {"heading": "Goal", "body": "one"}}]}]},
        ):
            with self.subTest(type=data["type"]):
                text = build(data).build()
                middle = build(data, self.MIDDLE).build()
                self.assertEqual([e.rect.height for e in text], [e.rect.height for e in middle])
                self.assertEqual([e.rect.width for e in text], [e.rect.width for e in middle])

    def test_the_pages_of_a_deck_not_in_the_middle_are_not_moved_by_a_use_that_is(self) -> None:
        theme = theme_from({"uses": {"centred": {"like": "read", "box_height": "middle"}}})
        data = {"type": "cards", "title": "T", "cards": CARDS, "card_columns": 1}
        self.assertEqual(build(data, DEFAULT).build(), build(data, theme).build())
        self.assertEqual(build(data, self.MIDDLE).build(), build({**data, "use": "centred"}, theme).build())

    def test_a_card_of_a_body_with_a_reading_below_it_is_not_pushed_out_of_the_body(self) -> None:
        body = Page("T", self.MIDDLE, conclusion="d").body
        built = cards_page(self.MIDDLE, conclusion="d", note="How to read this")
        for e in built.build():
            if e.kind in ("box", "note"):
                self.assertTrue(body.contains(e.rect), (e.kind, e.rect, body))

    def test_a_cell_of_a_compose_that_holds_a_figure_stands_as_a_whole(self) -> None:
        """図を持つ本体は枠を使い切る (= 動かす余りが無い)。"""
        data = {"type": "compose", "title": "T", "rows": [{"cells": [{"figure": "dot.png"}]}]}
        self.assertEqual(build(data).build(), build(data, self.MIDDLE).build())

    def test_named_words_stay_with_their_box(self) -> None:
        built = cards_page(self.MIDDLE)
        for heading in ("One", "Two", "Three"):
            self.assertTrue(box_of(built, heading).rect.contains(named(built, heading).rect))

    def test_the_arrow_between_two_cells_moves_with_them(self) -> None:
        data = {"type": "compose", "title": "T",
                "rows": [{"cells": [{"id": "a", "card": {"heading": "A"}}]},
                         {"cells": [{"id": "b", "card": {"heading": "B"}}]}],
                "links": [{"from": "a", "to": "b"}]}
        built = build(data, self.MIDDLE)
        upper, lower = box_of(built, "A").rect, box_of(built, "B").rect
        line = of_kind(built, "line")[0]
        self.assertTrue(upper.bottom <= line.start[1] <= line.end[1] <= lower.top, (upper, line, lower))
        self.assertTrue(line.rect.top <= line.start[1] and line.end[1] <= line.rect.bottom)


class CentringWhatTheBodyPlaced(unittest.TestCase):
    """`centre_body` on a page with things put on it by hand, so every kind of thing it may meet is moved."""

    AREA = Rect(0, 1000, 4000, 6000)

    def page(self, *placed):
        """A page with its title on it, and these put on it after (= `first` is where they start)."""
        page = Page("T")
        self.first = len(page.elements)
        page.elements.extend(placed)
        return page

    def test_a_line_is_moved_by_its_two_ends_and_by_the_box_round_them(self) -> None:
        line = Line("arrow", Rect(100, 1000, 500, 800), (100, 1000), (600, 1800), "000000", arrow=True)
        page = self.page(line)
        centre_body(page, self.AREA, self.first)
        moved = page.elements[self.first]
        self.assertEqual((Rect(100, 3600, 500, 800), (100, 3600), (600, 4400)), (moved.rect, moved.start, moved.end))
        self.assertTrue(moved.arrow)

    def test_a_chart_is_moved_with_its_frame_and_the_words_it_points_with(self) -> None:
        callout = Callout("peak", Rect(200, 1100, 300, 100), line=Rect(250, 1200, 10, 200))
        chart = Chart("chart", Rect(0, 1000, 1000, 800), frame=Rect(0, 1100, 1000, 700), callouts=(callout,))
        page = self.page(chart)
        centre_body(page, self.AREA, self.first)
        moved = page.elements[self.first]
        self.assertEqual((Rect(0, 3600, 1000, 800), Rect(0, 3700, 1000, 700)), (moved.rect, moved.frame))
        self.assertEqual((Rect(200, 3700, 300, 100), Rect(250, 3800, 10, 200)),
                         (moved.callouts[0].words, moved.callouts[0].line))

    def test_what_stands_before_the_first_one_asked_for_is_left_alone(self) -> None:
        page = self.page(Fill("box", Rect(0, 1000, 100, 100), "000000"))
        before = page.elements[:self.first]
        centre_body(page, self.AREA, self.first)
        self.assertEqual(before, page.elements[:self.first])
        self.assertEqual(Rect(0, 3950, 100, 100), page.elements[self.first].rect)

    def test_a_block_taller_than_the_area_is_never_moved_up(self) -> None:
        box = Fill("box", Rect(0, 1000, 100, 7000), "000000")
        page = self.page(box)
        centre_body(page, self.AREA, self.first)
        self.assertEqual(box, page.elements[self.first])

    def test_nothing_placed_moves_nothing(self) -> None:
        page = self.page()
        before = list(page.elements)
        centre_body(page, self.AREA, self.first)
        self.assertEqual(before, page.elements)


if __name__ == "__main__":
    unittest.main()
