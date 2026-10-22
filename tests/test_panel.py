"""A panel: a box in a `compose` cell that holds rows of cells of its own.

見張るのは 6 つ ― 見た目が資料の `card_look` に従い、色の決まりがカードと同じ 1 か所 (= `outlined_look` / `look`) を
読むこと、見出しが中の左上に太字で置かれ線が見出しの色で引かれること、中の段が `compose` の段とマスの組み方のまま
(= 入れ子も、頁の高さを使う資料の決まりも) 割られること、高さが見出しと中の段の合計で数えられ収まらなければ縮めずに
止まること、`links` が入れ物の内と外をまたぎ入れ物そのものも端になること、書き方の誤りが止まること。
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))
from support.pages import build  # noqa: E402

from pptx_agent_maker import DEFAULT, checks  # noqa: E402
from pptx_agent_maker.layout.base.tokens import theme_from  # noqa: E402
from pptx_agent_maker.layout.parts.elements import TEXT_INSET_Y  # noqa: E402
from pptx_agent_maker.layout.parts.page import Page, PageFullError  # noqa: E402
from pptx_agent_maker.layout.types.core.registry import PageTypeError  # noqa: E402
from pptx_agent_maker.write import add_page, new_deck, save  # noqa: E402

P, T, S = DEFAULT.palette, DEFAULT.type, DEFAULT.spacing
GROUNDS = {"Deep": "8B1E3F", "Pale": "EAF0F8"}
FILLED = theme_from({"grounds": GROUNDS})
OUTLINED = theme_from({"grounds": GROUNDS, "card_look": "outlined"})
#: 頁の高さを使う資料 (= 入れ物も中のカードも、置かれた高さを使い切る)
FULL = theme_from({"grounds": GROUNDS, "card_look": "outlined", "box_height": "page"})
#: 段とマスの隙間が、矢印のそばの言葉を入れられるだけ広い使い方 (= 頁の高さを使う資料)
AIRY = theme_from({"grounds": GROUNDS, "card_look": "outlined", "box_height": "page",
                   "uses": {"airy": {"like": "read", "spacing": {"gap_m": 2.2}}}}).using("airy")


def row(*cells, **more):
    return {"cells": list(cells), **more}


def panel(*rows, **keys):
    return {"panel": {"rows": list(rows), **keys}}


def card(heading="A card", body="Some words", **keys):
    return {"card": {"heading": heading, "body": body, **keys}}


def compose(rows, theme=FILLED, **extra):
    return build({"type": "compose", "title": "A page", "rows": rows, **extra}, theme)


def kinds(page, kind):
    return [e for e in page.build() if e.kind == kind]


def one(page, kind):
    (found,) = kinds(page, kind)
    return found


def text_of(page, words):
    return next(e for e in page.build() if getattr(e, "text", None) == words)


class TheLookOfAPanelIsTheLookOfTheDeck(unittest.TestCase):
    """The same rule that colours a card colours a panel (= `outlined_look` in an outlined deck, `look` in a filled one)."""

    def test_in_a_filled_deck_a_panel_is_painted_with_the_ground_of_its_tone_and_has_square_corners(self) -> None:
        page = compose([row(panel(row({"text": "Words"}), tone="tint"))])
        box = one(page, "panel")
        fill, _words, edge = Page("p", FILLED).ground("tint")
        self.assertEqual((fill, edge, False), (box.colour, box.outline, box.rounded))

    def test_in_an_outlined_deck_a_colour_is_carried_by_the_edge_and_the_heading_and_the_ground_is_faint(self) -> None:
        page = compose([row(panel(row(card()), tone="accent", heading="Heading"))], OUTLINED)
        box = one(page, "panel")
        built = Page("p", OUTLINED)
        self.assertEqual(P.accent, box.outline)
        self.assertEqual(P.thinned(P.CARD_WASH, P.accent), box.colour)
        self.assertTrue(box.rounded)
        self.assertEqual(built.tone_ink("accent", T.body, False), text_of(page, "Heading").colour)

    def test_a_pale_tone_in_an_outlined_deck_keeps_its_own_ground_and_the_heading_in_the_ink_of_the_body(self) -> None:
        page = compose([row(panel(row(card()), tone="band", heading="Heading"))], OUTLINED)
        box = one(page, "panel")
        fill, _words, edge = Page("p", OUTLINED).ground("band")
        self.assertEqual((fill, edge), (box.colour, box.outline))
        self.assertEqual(P.ink, text_of(page, "Heading").colour)

    def test_in_an_outlined_deck_a_named_ground_of_middle_lightness_is_carried_by_the_edge_as_a_deep_one_is(self) -> None:
        """A bright colour that the body's words can be read on is still no pale ground: it takes the edge, not a fill."""
        theme = theme_from({"grounds": {"Orange": "F79646", "Rust": "D9661F", "Blush": "FDECE3"}, "card_look": "outlined"})
        for tone, edge in (("Orange", "F79646"), ("Rust", "D9661F")):
            with self.subTest(tone=tone):
                box = one(compose([row(panel(row(card()), tone=tone, heading="Heading"))], theme), "panel")
                self.assertEqual((edge, P.thinned(P.CARD_WASH, edge)), (box.outline, box.colour))
        # the heading of the bright one stays readable on the paper: the ink of the body
        page = compose([row(panel(row(card()), tone="Orange", heading="Heading"))], theme)
        self.assertEqual(P.ink, text_of(page, "Heading").colour)
        # a ground as near the paper as the palette's own pale ones keeps its own ground
        fill, _words, edge = Page("p", theme).ground("Blush")
        box = one(compose([row(panel(row({"text": "x"}), tone="Blush", heading="Heading"))], theme), "panel")
        self.assertEqual((fill, edge), (box.colour, box.outline))

    def test_a_panel_takes_the_tones_a_card_takes_and_the_grounds_a_project_named(self) -> None:
        for theme in (FILLED, OUTLINED):
            for tone in ("box", "band", "tint", "accent", "good", "bad", "Deep", "Pale"):
                with self.subTest(tone=tone, look=theme.card_look):
                    inner = card() if tone in ("accent", "good", "bad", "Deep") and theme is FILLED else {"text": "x"}
                    compose([row(panel(row(inner), tone=tone, heading="Heading"))], theme)

    def test_a_tentative_panel_is_the_paper_with_a_line_in_the_ink_and_a_strong_one_has_a_heavy_line(self) -> None:
        page = compose([row(panel(row({"text": "x"}), tentative=True), panel(row({"text": "y"}), strong=True))], OUTLINED)
        loose, firm = kinds(page, "panel")
        self.assertEqual((P.paper, P.ink, False), (loose.colour, loose.outline, loose.heavy))
        self.assertTrue(firm.heavy)
        filled = compose([row(panel(row({"text": "x"}), tentative=True))], FILLED)
        dotted = one(filled, "panel")
        self.assertEqual((P.paper, P.muted, True), (dotted.colour, dotted.outline, dotted.dashed))

    def test_the_tone_of_a_panel_is_the_tone_of_the_card_the_same_words_would_make(self) -> None:
        """One rule, not two copies: a card and a panel of the same tone and look agree on ground and edge."""
        for theme in (FILLED, OUTLINED):
            for tone in ("box", "accent", "bad", "Deep", "Pale"):
                with self.subTest(tone=tone, look=theme.card_look):
                    page = compose([row({"card": {"heading": "C", "body": "b", "tone": tone}},
                                        panel(row(card()), tone=tone))], theme)
                    box, enclosure = one(page, "panel"), kinds(page, "box")[0]
                    self.assertEqual((enclosure.colour, enclosure.outline), (box.colour, box.outline))


class TheHeadingAndTheRule(unittest.TestCase):
    def test_the_heading_stands_in_the_top_left_corner_inside_the_padding_bold_at_the_size_of_a_card_heading(self) -> None:
        page = compose([row(panel(row({"text": "Words"}), heading="A heading"))])
        box, head = one(page, "panel"), text_of(page, "A heading")
        self.assertEqual((box.rect.left + S.pad, box.rect.top + S.pad), (head.rect.left, head.rect.top))
        self.assertEqual(box.rect.width - 2 * S.pad, head.rect.width)
        self.assertEqual((T.heading, True, "left"), (head.size, head.bold, head.align))

    def test_a_panel_without_a_heading_draws_none_and_its_rows_begin_at_the_padding(self) -> None:
        page = compose([row(panel(row({"text": "Words"})))])
        self.assertEqual([], kinds(page, "panel_heading"))
        self.assertEqual(one(page, "panel").rect.top + S.pad, text_of(page, "Words").rect.top)

    def test_the_rule_is_one_hairline_under_the_heading_in_the_colour_of_the_heading(self) -> None:
        page = compose([row(panel(row({"text": "Words"}), heading="A heading", rule=True, tone="accent"))], OUTLINED)
        head = text_of(page, "A heading")
        (line,) = [e for e in kinds(page, "rule") if e.rect.top > head.rect.top]
        self.assertEqual(S.hairline, line.rect.height)
        self.assertEqual(head.colour, line.colour)
        self.assertEqual(head.rect.left, line.rect.left)
        self.assertEqual(head.rect.width, line.rect.width)
        self.assertEqual(head.rect.top + TEXT_INSET_Y + head.rect.height, line.rect.top)

    def test_the_rows_begin_under_the_rule_and_under_the_heading_without_one(self) -> None:
        plain = compose([row(panel(row({"text": "Words"}), heading="A heading"))])
        ruled = compose([row(panel(row({"text": "Words"}), heading="A heading", rule=True))])
        head = text_of(plain, "A heading").rect
        self.assertEqual(head.bottom + S.gap_s, text_of(plain, "Words").rect.top)
        line = [e for e in kinds(ruled, "rule") if e.rect.top > head.top][0].rect
        self.assertEqual(line.bottom + S.gap_s, text_of(ruled, "Words").rect.top)

    def test_the_rule_is_drawn_only_when_asked_for(self) -> None:
        page = compose([row(panel(row({"text": "Words"}), heading="A heading"))])
        head = text_of(page, "A heading")
        self.assertEqual([], [e for e in kinds(page, "rule") if e.rect.top > head.rect.top])

    def test_a_long_heading_folds_and_the_rows_move_down_with_it(self) -> None:
        short = compose([row(panel(row({"text": "Words"}), heading="Short"))])
        long = compose([row(panel(row({"text": "Words"}), heading="A heading long enough to fold over " * 3))])
        self.assertGreater(text_of(long, "Words").rect.top, text_of(short, "Words").rect.top)
        heading = next(e for e in long.build() if e.kind == "panel_heading")
        self.assertGreater(heading.rect.height, text_of(short, "Short").rect.height)


class TheRoomTheHeadingTakes(unittest.TestCase):
    #: 太字で数えると 3 行、太字でなければ 2 行に折れる見出しと、その字が使える幅
    HEADING, ROOM = "Heading of the panel with words", 1780000

    def test_the_heading_is_counted_in_bold_because_it_is_set_in_bold(self) -> None:
        from pptx_agent_maker.layout.parts.page import Panel
        inside = self.ROOM + 2 * S.text_inset
        self.assertEqual(3, DEFAULT.wraps(self.HEADING, self.ROOM, T.heading, bold=True))
        self.assertEqual(2, DEFAULT.wraps(self.HEADING, self.ROOM, T.heading, bold=False))
        built = Page("p", DEFAULT)
        self.assertEqual(3 * built.theme.line_height(T.heading) + S.gap_s, built.panel_head(Panel(self.HEADING), inside))

    def test_a_heading_that_leaves_nothing_inside_stops_the_panel(self) -> None:
        from pptx_agent_maker.layout.base.geometry import Rect
        from pptx_agent_maker.layout.parts.page import Panel
        built = Page("p", DEFAULT)
        with self.assertRaisesRegex(PageFullError, r"its heading takes.*nothing will shrink"):
            built.panel(Rect(0, 0, 5000000, 2 * S.pad + 100000), Panel("A heading"))


class TheRowsInsideArePlacedByTheRulesOfCompose(unittest.TestCase):
    def test_the_cells_of_the_rows_divide_what_is_inside_the_padding_and_never_leave_the_panel(self) -> None:
        page = compose([row(panel(row(card("One"), card("Two")), row(card("Three")), heading="Head"))])
        box = one(page, "panel").rect
        inside = box.inset(S.pad)
        first, second, third = kinds(page, "box")
        self.assertEqual((inside.left, inside.right), (first.rect.left, second.rect.right))
        self.assertEqual((inside.left, inside.right), (third.rect.left, third.rect.right))
        self.assertEqual(first.rect.bottom + S.gap_m, third.rect.top)
        for e in (first, second, third):
            self.assertTrue(box.contains(e.rect))

    def test_cells_beside_each_other_inside_share_the_width_by_weight(self) -> None:
        page = compose([row(panel(row({**card("One"), "weight": 3}, card("Two"))))])
        wide, narrow = kinds(page, "box")
        self.assertAlmostEqual(3, (wide.rect.width) / narrow.rect.width, delta=0.2)

    def test_a_panel_inside_a_panel_is_laid_the_same_way_all_the_way_down(self) -> None:
        inner = panel(row(card("Deep")), heading="Inner")
        page = compose([row(panel(row(inner, inner), heading="Outer"))])
        outer, *little = kinds(page, "panel")
        self.assertEqual(2, len(little))
        for rect in (p.rect for p in little):
            self.assertTrue(outer.rect.inset(S.pad).contains(rect))
        self.assertEqual(little[0].rect.right + S.gap_m, little[1].rect.left)
        self.assertEqual(3, len(kinds(page, "panel_heading")))

    def test_a_panel_holds_a_picture_that_takes_what_height_is_left(self) -> None:
        page = compose([row(panel(row({"text": "Words"}), row({"figure": "dot.png"}), heading="Head"), weight=1)],
                       FILLED)
        box, picture = one(page, "panel").rect, one(page, "figure").rect
        self.assertTrue(box.inset(S.pad).contains(picture))

    def test_a_panel_holds_each_part_a_cell_can_hold(self) -> None:
        cells = [{"text": "Words"}, {"text": "A note", "role": "note"}, {"points": ["one", "two"]},
                 {"table": [["A", "B"], ["1", "2"]]}, {"voices": [{"text": "Said"}]}, card()]
        for cell in cells:
            with self.subTest(part=next(iter(cell))):
                compose([row(panel(row(cell)))], OUTLINED)


class TheHeightOfAPanel(unittest.TestCase):
    def test_the_rows_are_measured_at_the_width_inside_the_padding_so_what_wraps_there_fits(self) -> None:
        width = one(compose([row(panel(row({"text": "x"})))]), "panel").rect.width
        room, inside = width - 2 * S.text_inset, width - 2 * S.pad - 2 * S.text_inset
        words = next(" ".join(["word"] * n) for n in range(1, 200)
                     if DEFAULT.wrapped_height(" ".join(["word"] * n), room)
                     != DEFAULT.wrapped_height(" ".join(["word"] * n), inside))
        page = compose([row(panel(row({"text": words})))])
        box, text = one(page, "panel").rect, next(e for e in page.build() if e.kind == "text")
        self.assertTrue(box.inset(S.pad).contains(text.rect))

    def test_it_is_the_padding_the_heading_and_the_rows_inside_it(self) -> None:
        page = compose([row(panel(row(card("One")), row(card("Two")), heading="Head"))])
        box, first, second = one(page, "panel").rect, *[e.rect for e in kinds(page, "box")]
        head = text_of(page, "Head").rect.height + S.gap_s
        self.assertEqual(2 * S.pad + head + first.height + S.gap_m + second.height, box.height)

    def test_panels_in_one_row_stand_as_tall_as_the_tallest(self) -> None:
        page = compose([row(panel(row(card("One", "short"))), panel(row(card("Two", "a much longer body " * 8))))])
        short, long = [e.rect.height for e in kinds(page, "panel")]
        self.assertEqual(short, long)

    def test_the_cards_inside_a_deck_of_text_height_stay_the_height_of_their_words(self) -> None:
        page = compose([row(panel(row(card("One", "short")), row(card("Two", "short"))))], OUTLINED)
        box, first, _second = one(page, "panel").rect, *[e.rect for e in kinds(page, "box")]
        self.assertEqual(box.top + S.pad, first.top)

    def test_in_a_row_that_shares_what_is_left_a_panel_stands_at_the_height_of_its_words_at_the_top(self) -> None:
        page = compose([row({"figure": "dot.png"}, panel(row(card("One", "short")))), row(card("Under"))])
        box, picture = one(page, "panel").rect, one(page, "figure").rect
        self.assertEqual(picture.top, box.top)
        self.assertEqual(2 * S.pad + kinds(page, "box")[0].rect.height, box.height)

    def test_a_row_too_low_for_a_panel_stops_the_page_and_says_where(self) -> None:
        tall = panel(*[row(card(f"Card {n}", "words " * 40)) for n in range(5)])
        with self.assertRaisesRegex(PageFullError, r"row 1, cell 2: this panel needs \d+ EMU.*nothing will shrink"):
            compose([row({"figure": "dot.png"}, tall, weight=1), row(card("Under"))])

    def test_rows_that_do_not_fit_in_a_panel_name_the_row_inside_it(self) -> None:
        tall = panel(row({"figure": "dot.png"}), row({"figure": "dot.png"}), row({"figure": "dot.png"}),
                     row({"figure": "dot.png"}), row(card("Fixed", "words " * 200)))
        with self.assertRaisesRegex(PageFullError, r"row 1, cell 1, panel"):
            compose([row(tall), row(card("Under", "words " * 200))])

    def test_a_panel_that_holds_a_panel_with_a_picture_takes_what_is_left_as_the_inner_one_would_alone(self) -> None:
        inner = panel(row({"figure": "dot.png"}), heading="Inner")
        lead = row({"text": "lead " * 200})
        nested = compose([lead, row(panel(row(inner, weight=1), heading="Outer"), weight=1)])
        alone = compose([lead, row(inner, weight=1)])
        outer, little = kinds(nested, "panel")
        self.assertEqual(one(alone, "panel").rect, outer.rect)
        self.assertEqual(outer.rect.inset(S.pad).inset(top=text_of(nested, "Outer").rect.height + S.gap_s), little.rect)

    def test_a_panel_left_too_low_by_the_rows_beside_it_names_the_panel_and_what_the_other_rows_take(self) -> None:
        inner = panel(row({"figure": "dot.png"}), heading="Inner")
        with self.assertRaisesRegex(
                PageFullError,
                r"row 2, cell 1, panel: row 1, cell 1: a panel has \d+ EMU of height inside and its heading takes \d+"
                r".*compose: row 2 shares the \d+ EMU the other rows leave of \d+, and they take \d+"):
            compose([row({"text": "lead " * 500}), row(panel(row(inner, weight=1), heading="Outer"), weight=1)])

    def test_a_panel_too_low_with_nothing_beside_it_says_no_more_than_before(self) -> None:
        with self.assertRaises(PageFullError) as stopped:
            compose([row(panel(row({"figure": "dot.png"}), heading="Head " * 400), weight=1)])
        self.assertNotIn("shares the", str(stopped.exception))


class InADeckThatUsesThePageHeight(unittest.TestCase):
    """`box_height = "page"` reaches inside a panel unchanged: the panel fills its cell and the cards fill their rows in it."""

    def test_the_panel_fills_the_row_and_the_card_in_it_fills_the_panel(self) -> None:
        page = compose([row(panel(row(card("One")), heading="Head"), card("Beside"))], FULL)
        box, inner, beside = one(page, "panel").rect, kinds(page, "box")[0].rect, kinds(page, "box")[1].rect
        self.assertEqual(box.height, beside.height)
        self.assertEqual(box.bottom - S.pad, inner.bottom)
        self.assertGreater(box.height, 0)

    def test_the_extra_height_goes_to_the_rows_inside_in_equal_shares(self) -> None:
        page = compose([row(panel(row(card("One", "a")), row(card("Two", "a")), row(card("Three", "a")))),
                        row({"figure": "dot.png"}, weight=1)], FULL)
        heights = [e.rect.height for e in kinds(page, "box")]
        self.assertEqual(1, len(set(heights)))

    def test_a_panel_of_words_alone_is_taller_than_its_words_and_shares_what_is_left_with_a_card_row(self) -> None:
        rows = [row(panel(row({"text": "Words"}))), row(card("Under"))]
        full, short = compose(rows, FULL), compose(rows, OUTLINED)
        self.assertGreater(one(full, "panel").rect.height, one(short, "panel").rect.height)
        self.assertEqual(one(full, "panel").rect.height - one(short, "panel").rect.height,
                         kinds(full, "box")[0].rect.height - kinds(short, "box")[0].rect.height)

    def test_a_panel_beside_a_taller_card_is_as_tall_and_still_fills_its_cards_row_by_row(self) -> None:
        page = compose([row(panel(row(card("One", "x")), row(card("Two", "x"))), card("Tall", "words " * 60))], FULL)
        box = one(page, "panel").rect
        first, second, tall = [e.rect for e in kinds(page, "box")]
        self.assertEqual(box.height, tall.height)
        self.assertEqual(box.bottom - S.pad, second.bottom)
        self.assertEqual(first.height, second.height)

    def test_a_panel_without_a_card_fills_its_cell_too_and_its_words_stay_on_top(self) -> None:
        page = compose([row(panel(row({"text": "Words"}), heading="Head"), card("Beside", "words " * 40))], FULL)
        box = one(page, "panel").rect
        self.assertEqual(kinds(page, "box")[0].rect.height, box.height)
        self.assertEqual(box.top + S.pad + text_of(page, "Head").rect.height + S.gap_s, text_of(page, "Words").rect.top)


class InADeckThatCentresItsBody(unittest.TestCase):
    """`box_height = "middle"` moves what the body placed as one piece, a panel and everything in it with it."""

    MIDDLE = theme_from({"grounds": GROUNDS, "card_look": "outlined", "box_height": "middle"})

    def test_the_panel_and_what_it_holds_move_down_together_and_keep_their_places_in_it(self) -> None:
        rows = [row({**panel(row(card("One")), row({"text": "Words"}), heading="Head", rule=True), "id": "p"},
                    {**card("Beside"), "id": "b"})]
        text, middle = compose(rows, OUTLINED, links=[{"from": "p", "to": "b"}]), compose(rows, self.MIDDLE,
                                                                                         links=[{"from": "p", "to": "b"}])
        moved = one(middle, "panel").rect.top - one(text, "panel").rect.top
        self.assertGreater(moved, 0)
        for kind in ("panel_heading", "box", "line"):
            self.assertEqual([e.rect.top + moved for e in kinds(text, kind)], [e.rect.top for e in kinds(middle, kind)])
        self.assertEqual(text_of(text, "Words").rect.top + moved, text_of(middle, "Words").rect.top)


class WordsStraightOnADeepGround(unittest.TestCase):
    """In a filled deck a panel of a deep tone is painted deep, and the ink of the body does not read on it."""

    def test_words_set_straight_on_it_stop_the_page_and_say_which_part(self) -> None:
        for part in ({"text": "Words"}, {"points": ["one"]}, {"table": [["A"], ["1"]]}, {"voices": [{"text": "Said"}]},
                     {"chart": {"kind": "bar", "categories": ["a"], "series": [{"name": "s", "values": [1]}]}},
                     {"ring": [["A", "a"], ["B", "b"], ["C", "c"]]}, {"overlap": {"sets": ["A", "B"]}}):
            with self.subTest(part=next(iter(part))):
                with self.assertRaisesRegex(PageTypeError, rf"panel: a {next(iter(part))} stands straight on the ground"):
                    compose([row(panel(row(part), tone="accent"))], FILLED)

    def test_a_picture_with_a_name_or_marks_stops_it_and_one_without_is_let_through(self) -> None:
        for words in ({"caption": "A name"}, {"marks": [{"at": [0.5, 0.5], "text": "A point"}]}):
            with self.subTest(words=next(iter(words))):
                with self.assertRaisesRegex(PageTypeError, "a figure with its words stands straight"):
                    compose([row(panel(row({"figure": "dot.png", **words}), tone="Deep"))], FILLED)

    def test_the_same_words_in_a_nested_row_of_the_panel_stop_it_too(self) -> None:
        with self.assertRaisesRegex(PageTypeError, "a text stands straight"):
            compose([row(panel(row({"rows": [row({"text": "Words"})]}), tone="Deep"))], FILLED)

    def test_what_keeps_its_own_ground_is_let_through(self) -> None:
        mono = {"text": "x = 1", "role": "mono"}
        for part in (card(), mono, panel(row({"text": "Words"}), tone="tint"), {"figure": "dot.png"}):
            with self.subTest(part=next(iter(part))):
                compose([row(panel(row(part), tone="accent"))], FILLED)

    def test_a_pale_tone_a_tentative_panel_and_an_outlined_deck_have_no_such_limit(self) -> None:
        compose([row(panel(row({"text": "Words"}), tone="tint"))], FILLED)
        compose([row(panel(row({"text": "Words"}), tone="accent", tentative=True))], FILLED)
        for tone in ("accent", "bad", "Deep"):
            compose([row(panel(row({"text": "Words"}, {"points": ["one"]}), tone=tone))], OUTLINED)

    def test_the_ink_of_the_body_reads_on_a_panel_exactly_when_the_page_says_it_does(self) -> None:
        from pptx_agent_maker.layout.parts.look import Style
        built = Page("p", FILLED)
        self.assertEqual([True, True, True, False, False, False, False],
                         [built.reads_ink(Style(tone)) for tone in ("box", "band", "tint", "accent", "good", "bad", "Deep")])
        self.assertTrue(built.reads_ink(Style("accent", tentative=True)))
        self.assertTrue(Page("p", OUTLINED).reads_ink(Style("accent")))


class LinksAcrossAPanel(unittest.TestCase):
    def arrows(self, page):
        return kinds(page, "line")

    def test_an_arrow_joins_a_cell_inside_a_panel_to_one_outside_it(self) -> None:
        page = compose([row(panel(row({**card("In"), "id": "in"})), {**card("Out"), "id": "out"})], OUTLINED,
                       links=[{"from": "in", "to": "out"}])
        (arrow,) = self.arrows(page)
        inner = next(e for e in kinds(page, "box") if e.rect.contains(text_of(page, "In").rect)).rect
        outer = next(e for e in kinds(page, "box") if e.rect.contains(text_of(page, "Out").rect)).rect
        self.assertEqual((inner.right, outer.left), (arrow.start[0], arrow.end[0]))
        self.assertTrue(arrow.arrow)

    def test_the_panel_itself_can_be_the_end_of_an_arrow(self) -> None:
        enclosure = {"panel": {"rows": [row(card("In"))], "heading": "Head"}, "id": "p"}
        page = compose([row(enclosure, {**card("Out"), "id": "out"})], OUTLINED, links=[{"from": "p", "to": "out"}])
        (arrow,) = self.arrows(page)
        self.assertEqual(one(page, "panel").rect.right, arrow.start[0])

    def test_two_panels_are_joined_across_the_gap_between_them(self) -> None:
        a = {"panel": {"rows": [row(card("A"))]}, "id": "a"}
        b = {"panel": {"rows": [row(card("B"))]}, "id": "b"}
        page = compose([row(a, b)], AIRY, links=[{"from": "a", "to": "b", "text": "then", "tone": "accent"}])
        first, second = [e.rect for e in kinds(page, "panel")]
        (arrow,) = self.arrows(page)
        self.assertEqual((first.right, second.left), (arrow.start[0], arrow.end[0]))
        self.assertEqual(P.accent, arrow.colour)
        self.assertIsNotNone(text_of(page, "then"))

    def test_an_arrow_starts_at_the_panel_as_it_is_drawn_when_it_stands_shorter_than_its_cell(self) -> None:
        """A panel in a row that shares what is left keeps the height of its words, and the arrow leaves its foot."""
        enclosure = {"panel": {"rows": [row(card("In", "short"))]}, "id": "p"}
        page = compose([row({"figure": "dot.png", "id": "pic"}, enclosure), row({**card("Under"), "id": "u"})],
                       FILLED, links=[{"from": "p", "to": "u"}])
        box = one(page, "panel").rect
        (arrow,) = self.arrows(page)
        self.assertEqual(box.bottom, arrow.start[1])

    def test_a_cell_between_the_two_ends_inside_the_panel_stops_the_link(self) -> None:
        a, c = {**card("A"), "id": "a"}, {**card("C"), "id": "c"}
        with self.assertRaisesRegex(PageTypeError, "another cell stands between"):
            compose([row(panel(row(a), row(card("Middle")), row(c)))], OUTLINED, links=[{"from": "a", "to": "c"}])

    def test_a_panel_standing_between_two_cells_stops_the_link(self) -> None:
        a, c = {**card("A"), "id": "a"}, {**card("C"), "id": "c"}
        with self.assertRaisesRegex(PageTypeError, "another cell stands between"):
            compose([row(a, panel(row(card("Middle"))), c)], OUTLINED, links=[{"from": "a", "to": "c"}])

    def test_a_panel_is_not_joined_to_what_stands_inside_it(self) -> None:
        enclosure = {"panel": {"rows": [row({**card("In"), "id": "in"})]}, "id": "p"}
        with self.assertRaisesRegex(PageTypeError, "'p' holds 'in'"):
            compose([row(enclosure)], OUTLINED, links=[{"from": "p", "to": "in"}])
        with self.assertRaisesRegex(PageTypeError, "'p' holds 'in'"):
            compose([row(enclosure)], OUTLINED, links=[{"from": "in", "to": "p"}])

    def test_two_cells_may_not_share_an_id_even_when_one_is_inside_a_panel(self) -> None:
        with self.assertRaisesRegex(PageTypeError, "two cells have the id"):
            compose([row(panel(row({**card("In"), "id": "x"})), {**card("Out"), "id": "x"})], OUTLINED)


class WhatMayBeWritten(unittest.TestCase):
    def refused(self, cell, pattern, theme=OUTLINED):
        with self.assertRaisesRegex(PageTypeError, pattern):
            compose([row(cell)], theme)

    def test_a_key_nobody_reads_is_refused(self) -> None:
        self.refused({"panel": {"rows": [row(card())], "colour": "red"}}, r"panel does not take colour")

    def test_an_icon_is_not_a_key_of_a_panel(self) -> None:
        self.refused({"panel": {"rows": [row(card())], "icon": "dot.png"}}, r"does not take icon")

    def test_rows_are_needed_and_cannot_be_empty(self) -> None:
        self.refused({"panel": {"heading": "Head"}}, r"a panel holds rows")
        self.refused({"panel": {"rows": []}}, r"a panel holds rows")
        self.refused({"panel": {"rows": "text"}}, r"a panel holds rows")

    def test_a_panel_is_a_table_and_not_a_word(self) -> None:
        self.refused({"panel": "Words"}, r"panel is 'Words'")

    def test_an_unknown_tone_is_refused_naming_the_roles_and_the_grounds_of_the_project(self) -> None:
        self.refused({"panel": {"rows": [row(card())], "tone": "mauve"}}, r"tone 'mauve'.*Deep", FILLED)

    def test_the_flags_are_true_or_false(self) -> None:
        for key in ("tentative", "strong", "rule"):
            self.refused({"panel": {"rows": [row(card())], "heading": "H", key: "yes"}}, rf"`{key}` is true or false")

    def test_a_rule_needs_a_heading_to_stand_under(self) -> None:
        self.refused({"panel": {"rows": [row(card())], "rule": True}}, r"no heading")
        self.refused({"panel": {"rows": [row(card())], "rule": True, "heading": "  "}}, r"no heading")

    def test_a_heading_is_words(self) -> None:
        self.refused({"panel": {"rows": [row(card())], "heading": 3}}, r"`heading` is the words")

    def test_a_panel_shares_a_cell_with_no_other_part(self) -> None:
        self.refused({**panel(row(card())), "card": {"heading": "x"}}, r"holds card, panel|holds panel, card")

    def test_a_panel_takes_no_caption_role_or_look_of_a_text(self) -> None:
        self.refused({**panel(row(card())), "caption": "x"}, r"`caption` belongs to a figure")
        self.refused({**panel(row(card())), "role": "label"}, r"`role` belongs to a text")
        self.refused({**panel(row(card())), "tone": "accent"}, r"`tone` belongs to a text")

    def test_an_error_inside_a_panel_says_which_row_and_cell_of_which_panel(self) -> None:
        self.refused(panel(row(card()), row({"text": "x", "role": "huge"})), r"row 1, cell 1, panel: row 2, cell 1.*role")


class ACardBesideAPanel(unittest.TestCase):
    """A card in a row with a panel sets its words from the top, as the panel sets its heading, in every look."""

    LOOKS = {"filled": FILLED, "outlined": OUTLINED, "page": FULL}

    def test_the_heading_of_the_card_stands_at_the_height_of_the_heading_of_the_panel(self) -> None:
        for name, theme in self.LOOKS.items():
            for beside in (card("B", "Some words"), card("B", ""), card("B", "words " * 30)):
                with self.subTest(look=name, body=beside["card"]["body"][:10]):
                    page = compose([row(panel(row({"figure": "dot.png"}), heading="A", tone="accent"), beside)], theme)
                    self.assertEqual(text_of(page, "A").rect.top, text_of(page, "B").rect.top)
                    self.assertFalse(text_of(page, "B").middle)

    def test_the_same_inside_a_panel(self) -> None:
        inside = row(panel(row({"figure": "dot.png"}), heading="A"), card("B", "Some words"), weight=1)
        page = compose([row(panel(inside, heading="Outer"), weight=1)], FULL)
        self.assertEqual(text_of(page, "A").rect.top, text_of(page, "B").rect.top)

    def test_a_card_in_a_row_without_a_panel_still_stands_in_the_middle_of_its_box(self) -> None:
        page = compose([row({"figure": "dot.png"}, card("B", "Some words"), weight=1)], FULL)
        box = one(page, "box").rect
        self.assertGreater(text_of(page, "B").rect.top, box.top + S.pad)

    def test_a_tag_beside_a_panel_keeps_its_word_in_the_middle(self) -> None:
        page = compose([row(panel(row({"figure": "dot.png"}), heading="A"), card("Tag", "", tag=True))], FULL)
        tag = text_of(page, "Tag")
        self.assertTrue(tag.middle)

    def test_written_out_the_checks_find_nothing_wrong(self) -> None:
        for name, theme in self.LOOKS.items():
            with self.subTest(look=name):
                rows = [row(panel(row({"figure": "dot.png"}), heading="A", tone="accent"), card("B", "Some words"))]
                page = compose(rows, theme)
                with tempfile.TemporaryDirectory() as tmp:
                    deck = new_deck(theme)
                    add_page(deck, page.build(), theme)
                    found = checks.run_all(save(deck, Path(tmp) / "beside.pptx"))
                self.assertEqual([], [f for f in found if f.check == "near_alignment"])


class WrittenOutTheChecksFindNothingWrong(unittest.TestCase):
    """The checks read the file that is written, and a box that holds boxes must not look like a fault to them."""

    def written(self, rows, theme, **extra):
        page = compose(rows, theme, **extra)
        with tempfile.TemporaryDirectory() as tmp:
            deck = new_deck(theme)
            add_page(deck, page.build(), theme)
            return checks.run_all(save(deck, Path(tmp) / "panels.pptx"))

    def test_nested_panels_with_headings_rules_and_arrows_in_the_outlined_look(self) -> None:
        little = panel(row(card("Name", "A line of words")), heading="Little", rule=True, tone="good")
        rows = [row({**panel(row({"text": "Words", "role": "note"}), row(little, little), heading="Big", rule=True,
                             tone="accent"), "id": "big"},
                    {**panel(row(card("One", "Words", tone="bad")), heading="Side", tone="bad"), "id": "side"})]
        self.assertEqual([], self.written(rows, AIRY, links=[{"from": "big", "to": "side", "text": "next"}]))

    def test_the_same_in_a_filled_deck(self) -> None:
        rows = [row(panel(row(card("One", "Words", tone="accent")), row({"text": "Words"}), heading="Big", rule=True,
                          tone="tint"),
                    panel(row(card("Two", "Words")), heading="Side", tone="Pale"))]
        self.assertEqual([], self.written(rows, FILLED))


if __name__ == "__main__":
    unittest.main()
