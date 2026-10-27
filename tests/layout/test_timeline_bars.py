"""What a timeline's bars take beyond their own stretch: line breaks in a name, arrows between bars, and a pale look.

⚠ 見張るのは 3 つ ― 名前の中の改行が行として数えられ、全部の行が同じ揃えで書かれること、棒どうしの
矢印が `id` で結ばれ、結べない書き方は理由つきで止まること、`bar_look = "outlined"` の棒がカードと
同じ色の決まりを読むこと。
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))
from support.pages import build, named  # noqa: E402
from layout.test_timeline import MONTHS, bar, lane, page  # noqa: E402

from pptx_agent_maker import Page, checks  # noqa: E402
from pptx_agent_maker.layout.parts.look import LIGHT, TONES  # noqa: E402
from pptx_agent_maker.layout.tokens import BAR_LOOKS, DEFAULT, ThemeError, theme_from  # noqa: E402
from pptx_agent_maker.layout.types.core.registry import PageTypeError  # noqa: E402
from pptx_agent_maker.write import add_page, new_deck, save  # noqa: E402

THREE_LINES = "名前\n(補足の 1)\n(補足の 2)"


def baked(built) -> str:
    """The slide XML a built page is written as."""
    with tempfile.TemporaryDirectory() as tmp:
        deck = new_deck(built.theme)
        add_page(deck, built.build(), built.theme)
        path = save(deck, Path(tmp) / "timeline.pptx")
        with zipfile.ZipFile(path) as archive:
            return archive.read("ppt/slides/slide1.xml").decode("utf-8")


def shape_of(xml: str, text: str) -> str:
    """The shape whose words contain this text."""
    return next(s for s in re.findall(r"<p:sp>.*?</p:sp>", xml, re.S) if text in s)


def natural(size: float) -> int:
    """One line of a bar at this size, with the room above and below it."""
    return DEFAULT.line_height(size) + 2 * DEFAULT.spacing.bar_pad_y


class ALineBreakInAName(unittest.TestCase):
    """`\\n` in a bar's name is a line of its own: counted for the height, written with the same alignment.

    余った高さは棒の高さに同じだけ足されるので、同じ頁の 2 本の棒の高さの差は、行の数の差ぶんの行の高さになる。
    """

    def lines_more_than_work(self, built, text: str) -> float:
        """How many lines taller than a one-line bar of the same page the bar of this name stands."""
        drawn, work = named(built, text), named(built, "work")
        self.assertEqual(work.size, drawn.size)
        return (drawn.rect.height - work.rect.height) / DEFAULT.line_height(drawn.size)

    def test_every_line_of_a_name_is_a_line_of_the_bar(self):
        built = page([lane("One", [bar(0, 6, "work")]), lane("Two", [bar(0, 3, THREE_LINES)])])
        self.assertEqual(2, self.lines_more_than_work(built, THREE_LINES))

    def test_a_line_that_wraps_counts_besides_the_breaks(self):
        """折り返しと改行は同じ数え方 (= 1 行目が折れれば、改行の 2 行と合わせて 3 行以上)。"""
        text = f"{'語' * 40}\nend"
        built = page([lane("One", [bar(0, 6, "work")]), lane("Two", [bar(0, 3, text)])])
        drawn = named(built, text)
        lines = DEFAULT.wraps(text, drawn.rect.width - 2 * DEFAULT.spacing.bar_pad_x, drawn.size)
        self.assertGreaterEqual(lines, 3)
        self.assertEqual(lines - 1, self.lines_more_than_work(built, text))

    def test_a_name_that_needs_one_more_line_than_it_breaks_into_stays_in_its_bar(self):
        """折り返しが 1 行足されるだけで収まる名前は、隣へ出さず棒の中に置く (= 改行の無い名前の 2 行と同じ決まり)。"""
        text = "a few more words\nsecond"
        built = page([lane("One", [bar(0, 6, "work")]), lane("Two", [bar(0, 1, text)])])
        drawn = named(built, text)
        inner = drawn.rect.width - 2 * DEFAULT.spacing.bar_pad_x
        self.assertGreater(DEFAULT.width(text, drawn.size), inner, "the name fits in one line of its bar")
        self.assertEqual(3, DEFAULT.wraps(text, inner, drawn.size))
        self.assertEqual("bar", drawn.kind)
        self.assertEqual(2, self.lines_more_than_work(built, text))

    def test_a_name_without_breaks_stands_as_tall_as_before(self):
        built = page([lane("One", [bar(0, 6, "work")]), lane("Two", [bar(0, 3, "one line")])])
        self.assertEqual(0, self.lines_more_than_work(built, "one line"))

    def test_a_bar_across_lanes_counts_the_breaks_too(self):
        """またがる棒は、覆うレーンの高さに名前が収まらなければ、出るレーンの段を高くする (= 縮めない)。"""
        text = "\n".join(f"line {number}" for number in range(1, 9))
        built = page([lane("One", [bar(0, 3, text, spans=2)]), lane("Two"), lane("Three", [bar(0, 3, "work")])])
        drawn = named(built, text)
        self.assertGreaterEqual(drawn.rect.height, 8 * DEFAULT.line_height(drawn.size) + 2 * DEFAULT.spacing.bar_pad_y)

    def test_a_name_set_beside_its_bar_keeps_the_room_of_its_lines(self):
        text = "a broad name\nand a second line"
        built = page([lane("One", [bar(0, 6, "work")]), lane("Two", [bar(0, 0.4, text)])])
        label = named(built, text)
        self.assertEqual("label", label.kind)
        self.assertEqual(1, self.lines_more_than_work(built, text))
        beside = next(e for e in built.build() if e.kind == "bar" and e.rect.top == label.rect.top)
        self.assertEqual(beside.rect.height, label.rect.height)

    def test_each_line_is_a_paragraph_with_the_alignment_of_the_first(self):
        xml = baked(page([lane("Core", [bar(0, 3, THREE_LINES)])]))
        shape = shape_of(xml, "名前")
        paragraphs = re.findall(r"<a:p>.*?</a:p>", shape, re.S)
        self.assertEqual(3, len(paragraphs))
        self.assertEqual(1, len({re.search(r'<a:pPr algn="(\w+)"', p).group(1) for p in paragraphs}))
        for paragraph, words in zip(paragraphs, THREE_LINES.split("\n")):
            self.assertIn(f">{words}<", paragraph)
        self.assertNotIn("\n", "".join(re.findall(r"<a:t>(.*?)</a:t>", shape, re.S)))

    def test_a_bar_with_breaks_keeps_the_spare_height_handed_to_the_page(self):
        """余った高さの配り方は改行の無い時と同じ (= 頁の下に空きを残さない)。"""
        lanes = [lane(f"Lane {n}", [bar(0, 6, "work")]) for n in range(5)]
        lanes.append(lane("Lane 5", [bar(0, 3, THREE_LINES)]))
        built = page(lanes)
        bottom = max(e.rect.bottom for e in built.build())
        self.assertLessEqual(built.theme.frame().bottom - bottom, len(lanes))
        heights = {e.rect.height for e in built.build() if e.kind == "bar" and e.text == "work"}
        self.assertEqual(1, len(heights))
        self.assertGreater(heights.pop(), natural(named(built, "work").size))

    def test_the_baked_page_passes_the_checks(self):
        built = page([lane("Core", [bar(0, 3, THREE_LINES), bar(3, 5, "after")]),
                      lane("More", [bar(1, 4, "a\nb")])])
        with tempfile.TemporaryDirectory() as tmp:
            deck = new_deck()
            add_page(deck, built.build())
            self.assertEqual([], checks.run_all(save(deck, Path(tmp) / "breaks.pptx")))


GROUNDS = {"Deep": "8B1E3F", "Pale": "EAF0F8", "Blue": "0092D1"}
FILLED = theme_from({"grounds": GROUNDS})
#: 頼み主の資料と同じ組み合わせ (= カードも棒も `outlined`)
OUTLINED = theme_from({"grounds": GROUNDS, "card_look": "outlined", "bar_look": "outlined"})
#: 色の役 (= 作り付けの 6 つと、案件が名前を付けた地 3 つ)
EVERY_TONE = (*TONES, *GROUNDS)


def timeline(theme, *bars, **extra):
    return build({"type": "timeline", "title": "A plan", "periods": MONTHS,
                  "lanes": [lane("Work", list(bars))], **extra}, theme)


def card_of(theme, tone: str, **extra):
    """A card of this tone in the same theme: its box and its words, to set a bar beside."""
    built = build({"type": "cards", "title": "Cards", "cards": [{"heading": "head", "body": "words", "tone": tone,
                                                                 **extra}]}, theme)
    box = next(e for e in built.build() if e.kind == "box")
    return box, named(built, "words")


class TheLookOfABar(unittest.TestCase):
    """`[theme] bar_look = "outlined"` paints a bar by the rule a card of the same tone is painted by."""

    def test_unsaid_it_is_filled_as_before(self):
        self.assertEqual("filled", DEFAULT.bar_look)
        self.assertEqual("filled", theme_from({"bar_look": "filled"}).bar_look)
        self.assertEqual(("filled", "outlined"), BAR_LOOKS)

    def test_a_name_nobody_knows_is_refused_with_the_key(self):
        with self.assertRaises(ThemeError) as refused:
            theme_from({"bar_look": "pale"})
        self.assertIn("bar_look", str(refused.exception))

    def test_the_look_of_the_bars_and_the_look_of_the_cards_are_chosen_apart(self):
        bars_only, cards_only = theme_from({"bar_look": "outlined"}), theme_from({"card_look": "outlined"})
        accent = DEFAULT.palette.accent
        self.assertEqual(accent, card_of(bars_only, "accent")[0].colour)
        self.assertNotEqual(accent, named(timeline(bars_only, bar(0, 3, "bar", tone="accent")), "bar").fill)
        self.assertNotEqual(accent, card_of(cards_only, "accent")[0].colour)
        self.assertEqual(accent, named(timeline(cards_only, bar(0, 3, "bar", tone="accent")), "bar").fill)

    def test_filled_bars_paint_every_tone_as_they_always_did(self):
        for tone in EVERY_TONE:
            with self.subTest(tone):
                drawn = named(timeline(FILLED, bar(0, 3, "bar", tone=tone)), "bar")
                fill, ink, edge = Page("T", FILLED).ground(tone, drawn.size)
                self.assertEqual((fill, ink, edge), (drawn.fill, drawn.colour, drawn.outline))

    def test_every_tone_is_painted_as_a_card_of_that_tone_is(self):
        for tone in EVERY_TONE:
            with self.subTest(tone):
                box, body = card_of(OUTLINED, tone)
                drawn = named(timeline(OUTLINED, bar(0, 3, "bar", tone=tone)), "bar")
                self.assertEqual((box.colour, box.outline, body.colour), (drawn.fill, drawn.outline, drawn.colour))

    def test_a_tone_that_carries_a_colour_is_a_pale_ground_in_a_line_of_that_colour(self):
        palette = OUTLINED.palette
        for tone in ("accent", "good", "bad", "Deep"):
            with self.subTest(tone):
                drawn = named(timeline(OUTLINED, bar(0, 3, "bar", tone=tone)), "bar")
                colour = Page("T", OUTLINED).ground(tone)[0]
                self.assertEqual(palette.thinned(palette.CARD_WASH, colour), drawn.fill)
                self.assertEqual(colour, drawn.outline)
                self.assertEqual(palette.ink, drawn.colour)

    def test_the_filled_look_of_the_same_bar_is_the_deep_ground(self):
        drawn = named(timeline(FILLED, bar(0, 3, "bar", tone="Deep")), "bar")
        self.assertEqual(Page("T", FILLED).ground("Deep")[0], drawn.fill)
        self.assertNotEqual(named(timeline(OUTLINED, bar(0, 3, "bar", tone="Deep")), "bar").fill, drawn.fill)

    def test_a_pale_ground_is_painted_as_it_was(self):
        for tone in (*LIGHT, "Pale"):
            with self.subTest(tone):
                outlined = named(timeline(OUTLINED, bar(0, 3, "bar", tone=tone)), "bar")
                filled = named(timeline(FILLED, bar(0, 3, "bar", tone=tone)), "bar")
                self.assertEqual((filled.fill, filled.outline, filled.colour),
                                 (outlined.fill, outlined.outline, outlined.colour))

    def test_the_tone_of_a_lane_is_read_the_same_way(self):
        built = build({"type": "timeline", "title": "A plan", "periods": MONTHS,
                       "lanes": [{"name": "Work", "tone": "Deep", "bars": [bar(0, 3, "bar")]}]}, OUTLINED)
        box, _body = card_of(OUTLINED, "Deep")
        self.assertEqual((box.colour, box.outline), (named(built, "bar").fill, named(built, "bar").outline))

    def test_a_tentative_and_a_strong_bar_follow_the_card(self):
        for look in ({"tentative": True}, {"strong": True}, {"tentative": True, "strong": True}):
            with self.subTest(look):
                box, body = card_of(OUTLINED, "Deep", **look)
                drawn = named(timeline(OUTLINED, bar(0, 3, "bar", tone="Deep", **look)), "bar")
                self.assertEqual((box.colour, box.outline, box.dashed, box.heavy, body.colour),
                                 (drawn.fill, drawn.outline, drawn.dashed, drawn.heavy, drawn.colour))

    def test_a_bar_across_lanes_is_painted_by_the_same_rule(self):
        built = build({"type": "timeline", "title": "A plan", "periods": MONTHS,
                       "lanes": [lane("One", [bar(0, 3, "wide", spans=2, tone="Deep")]), lane("Two")]}, OUTLINED)
        box, _body = card_of(OUTLINED, "Deep")
        self.assertEqual((box.colour, box.outline), (named(built, "wide").fill, named(built, "wide").outline))

    def test_a_baked_page_in_the_outlined_look_passes_the_checks(self):
        built = build({"type": "timeline", "title": "A plan", "periods": MONTHS,
                       "lanes": [lane(f"Lane {number}", [bar(0, 3, f"bar {tone}", tone=tone)])
                                 for number, tone in enumerate(EVERY_TONE, start=1)]}, OUTLINED)
        with tempfile.TemporaryDirectory() as tmp:
            deck = new_deck(OUTLINED)
            add_page(deck, built.build(), OUTLINED)
            self.assertEqual([], checks.run_all(save(deck, Path(tmp) / "outlined.pptx")))


def arrows(built):
    return [e for e in built.build() if e.kind == "line"]


def linked(lanes, links, **extra):
    return build({"type": "timeline", "title": "A plan", "periods": MONTHS, "lanes": lanes, "links": links, **extra},
                 DEFAULT)


class AnArrowBetweenBars(unittest.TestCase):
    """`id` on a bar and `links` on the page join two bars with an arrow, read the way `compose` reads its own."""

    def test_bars_one_after_the_other_in_a_lane_are_joined_from_the_end_of_one_to_the_start_of_the_next(self):
        built = linked([lane("Work", [bar(0, 2, "design", id="a"), bar(2, 4, "build", id="b")])],
                       [{"from": "a", "to": "b"}])
        (arrow,) = arrows(built)
        first, second = named(built, "design").rect, named(built, "build").rect
        self.assertTrue(arrow.arrow)
        self.assertEqual(((first.right, first.top + first.height // 2), (second.left, second.top + second.height // 2)),
                         (arrow.start, arrow.end))

    def test_bars_in_two_lanes_that_share_periods_are_joined_from_the_one_above_to_the_one_below(self):
        built = linked([lane("One", [bar(0, 3, "design", id="a")]), lane("Two", [bar(1, 5, "build", id="b")])],
                       [{"from": "a", "to": "b"}])
        (arrow,) = arrows(built)
        above, below = named(built, "design").rect, named(built, "build").rect
        self.assertEqual(arrow.start[0], arrow.end[0])
        self.assertTrue(max(above.left, below.left) <= arrow.start[0] <= min(above.right, below.right))
        self.assertEqual((above.bottom, below.top), (arrow.start[1], arrow.end[1]))

    def test_the_arrow_runs_the_way_it_is_written(self):
        lanes = [lane("One", [bar(0, 3, "design", id="a")]), lane("Two", [bar(1, 5, "build", id="b")])]
        (down,) = arrows(linked(lanes, [{"from": "a", "to": "b"}]))
        (up,) = arrows(linked(lanes, [{"from": "b", "to": "a"}]))
        self.assertEqual((down.start, down.end), (up.end, up.start))

    def test_a_bar_across_lanes_is_joined_by_its_id_like_any_other(self):
        built = linked([lane("One", [bar(0, 3, "shared", spans=2, id="a"), bar(3, 5, "after", id="b")]), lane("Two")],
                       [{"from": "a", "to": "b"}])
        (arrow,) = arrows(built)
        self.assertEqual(named(built, "shared").rect.right, arrow.start[0])
        self.assertEqual(named(built, "after").rect.left, arrow.end[0])

    def test_the_colour_of_the_arrow_is_the_tone_of_the_link(self):
        lanes = [lane("Work", [bar(0, 2, "design", id="a"), bar(2, 4, "build", id="b")])]
        (grey,) = arrows(linked(lanes, [{"from": "a", "to": "b"}]))
        (red,) = arrows(linked(lanes, [{"from": "a", "to": "b", "tone": "bad"}]))
        self.assertEqual(DEFAULT.palette.muted, grey.colour)
        self.assertEqual(Page("T", DEFAULT).tone_ink("bad"), red.colour)

    def test_every_link_is_an_arrow_and_the_bars_are_drawn_under_them(self):
        built = linked([lane("Work", [bar(0, 1, "a", id="a"), bar(1, 2, "b", id="b"), bar(2, 3, "c", id="c")])],
                       [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}])
        elements = built.build()
        drawn = [index for index, e in enumerate(elements) if e.kind == "line"]
        under = [index for index, e in enumerate(elements) if e.kind == "bar"]
        self.assertEqual(2, len(drawn))
        self.assertLess(max(under), min(drawn))

    def test_a_page_without_links_has_no_arrow(self):
        built = page([lane("Work", [bar(0, 2, "design", id="a"), bar(2, 4, "build", id="b")])])
        self.assertEqual([], arrows(built))

    def test_a_baked_page_with_arrows_passes_the_checks(self):
        built = linked([lane("One", [bar(0, 3, "design", id="a"), bar(3, 5, "ship", id="c")]),
                        lane("Two", [bar(1, 5, "build", id="b")])],
                       [{"from": "a", "to": "b"}, {"from": "a", "to": "c"}])
        with tempfile.TemporaryDirectory() as tmp:
            deck = new_deck()
            add_page(deck, built.build())
            self.assertEqual([], checks.run_all(save(deck, Path(tmp) / "arrows.pptx")))


class WhatALinkRefuses(unittest.TestCase):
    """The reasons are the ones `compose` gives, said of bars."""

    def test_an_id_no_bar_has(self):
        with self.assertRaises(PageTypeError) as raised:
            linked([lane("Work", [bar(0, 2, "design", id="a")])], [{"from": "a", "to": "nobody"}])
        self.assertIn("nobody", str(raised.exception))
        self.assertIn("ids on this page: a", str(raised.exception))

    def test_a_link_when_no_bar_has_an_id(self):
        with self.assertRaises(PageTypeError) as raised:
            linked([lane("Work", [bar(0, 2, "design"), bar(2, 4, "build")])], [{"from": "a", "to": "b"}])
        self.assertIn("give the cells an `id`", str(raised.exception))

    def test_two_bars_with_one_id(self):
        with self.assertRaises(PageTypeError) as raised:
            page([lane("One", [bar(0, 2, "design", id="a")]), lane("Two", [bar(0, 2, "build", id="a")])])
        self.assertIn("'a'", str(raised.exception))
        self.assertIn("lane 1, bar 1", str(raised.exception))
        self.assertIn("lane 2, bar 1", str(raised.exception))

    def test_an_id_that_is_not_a_name(self):
        for value in ("", "  ", 3, True):
            with self.subTest(value), self.assertRaises(PageTypeError) as raised:
                page([lane("Work", [bar(0, 2, "design", id=value)])])
            self.assertIn("`id`", str(raised.exception))

    def test_a_bar_standing_between_the_two(self):
        with self.assertRaises(PageTypeError) as raised:
            linked([lane("Work", [bar(0, 2, "a", id="a"), bar(2, 4, "middle"), bar(4, 6, "c", id="c")])],
                   [{"from": "a", "to": "c"}])
        self.assertIn("between", str(raised.exception))

    def test_a_name_set_beside_a_bar_standing_between_the_two(self):
        """棒の隣に出た名前も、矢印が横切れない物 (= 名前を貫くと、どちらの名前か読めない)。"""
        with self.assertRaises(PageTypeError) as raised:
            linked([lane("Work", [bar(0, 0.5, "a name that goes beside its bar", id="a"), bar(3, 4, "b", id="b")])],
                   [{"from": "a", "to": "b"}])
        self.assertIn("between", str(raised.exception))

    def test_a_name_set_to_the_left_of_a_bar_standing_between_the_two(self):
        with self.assertRaises(PageTypeError) as raised:
            linked([lane("Work", [bar(0, 1, "a", id="a"), bar(5.6, 6, "a name that goes to the left", id="b")])],
                   [{"from": "a", "to": "b"}])
        self.assertIn("between", str(raised.exception))

    def test_a_key_a_link_does_not_read(self):
        with self.assertRaises(PageTypeError):
            linked([lane("Work", [bar(0, 2, "a", id="a"), bar(2, 4, "b", id="b")])],
                   [{"from": "a", "to": "b", "colour": "red"}])

    def test_links_in_a_lane_say_where_they_belong(self):
        with self.assertRaises(PageTypeError) as raised:
            page([{"name": "Work", "bars": [bar(0, 2, "a")], "links": []}])
        self.assertIn("`milestones` and `links` belong to the page", str(raised.exception))
        self.assertIn("above the first", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
