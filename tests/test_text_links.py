"""What a text cell and a link may say: the roles of a text, its colour and its alignment, and words beside an arrow.

見張るのは 4 つ ― 文章の役 (= `label` は太字で `stage`、`note` は灰で `caption`) の大きさと色と高さ、`tone` が字の色の役を
運ぶこと (= 色を運ぶ役はその色、意味を持たない薄い地は本文の色)、矢印の `tone` が線と矢じりの色になること、
矢印のそばの言葉が決まった側 (= 上下へ向かう矢印なら右、左右へ向かう矢印なら上) の隙間に収まること (= 収まらなければ縮めずに止まる)。
"""

from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))
from support.pages import build, named  # noqa: E402

from pptx_agent_maker import DEFAULT, Page, checks  # noqa: E402
from pptx_agent_maker.layout.base.tokens import theme_from  # noqa: E402
from pptx_agent_maker.layout.parts.page import PageFullError  # noqa: E402
from pptx_agent_maker.layout.types.core.registry import PageTypeError  # noqa: E402
from pptx_agent_maker.write import add_page, new_deck, save  # noqa: E402

P, T, S = DEFAULT.palette, DEFAULT.type, DEFAULT.spacing
GROUNDS = {"Deep": "8B1E3F", "Pale": "EAF0F8"}
NAMED = theme_from({"grounds": GROUNDS})
#: 段と段、マスとマスの隙間が、矢印のそばの言葉を入れられるだけ広い使い方
AIRY = theme_from({"uses": {"airy": {"like": "read", "spacing": {"gap_m": 2.2}}}}).using("airy")


def row(*cells, **more):
    return {"cells": list(cells), **more}


def compose(rows, theme=DEFAULT, **extra):
    return build({"type": "compose", "title": "A page", "rows": rows, **extra}, theme)


def kinds(page, kind):
    return [e for e in page.build() if e.kind == kind]


def shown(cell, theme=DEFAULT):
    """The one text element a compose of a single text cell places."""
    (text,) = kinds(compose([row(cell)], theme), "display" if cell.get("role") == "display" else "text")
    return text


class OneRuleForTheColourOfATone(unittest.TestCase):
    """The heading of an outlined card, the words of a text and the line of an arrow read one rule: `tone_ink`."""

    #: 濃くも薄くも読める名前付きの地 (= 字の大きさと太さで、墨の字か紙の字かが変わる中ほどの色)
    MIDDLE = theme_from({"grounds": {**GROUNDS, "Middle": "808080"}})

    def test_the_heading_of_an_outlined_card_is_the_colour_the_words_of_its_tone_take(self) -> None:
        from pptx_agent_maker.layout.parts.look import Style
        page = Page("A page", self.MIDDLE)
        tones = ("box", "band", "tint", "accent", "good", "bad", "Deep", "Pale", "Middle")
        for tone in tones:
            for points, bold in ((None, False), (T.heading, True), (T.display, True)):
                with self.subTest(tone=tone, points=points, bold=bold):
                    self.assertEqual(page.tone_ink(tone, points, bold), page.outlined_look(Style(tone), points, bold)[1])

    def test_a_middle_ground_is_deep_for_small_words_and_pale_for_large_bold_ones(self) -> None:
        """Whether a ground the project named is deep depends on the words on it, as it does for the card's own look."""
        page = Page("A page", self.MIDDLE)
        self.assertTrue(page.carries_colour("Middle"))
        self.assertFalse(page.carries_colour("Middle", T.heading, True))

    def test_a_pale_tone_is_not_a_colour_and_a_deep_one_is(self) -> None:
        page = Page("A page", NAMED)
        self.assertEqual([False, False, False, True, True, True, True, False],
                         [page.carries_colour(tone) for tone in ("box", "band", "tint", "accent", "good", "bad", "Deep", "Pale")])


class TheRolesOfAText(unittest.TestCase):
    """`role = "label"` and `role = "note"` stand beside `display`, and `tone` and `align` go with all of them."""

    def test_a_text_with_no_role_is_set_as_it_was(self) -> None:
        text = shown({"text": "Plain"})
        self.assertEqual((T.body, False, P.ink, "left"), (text.size, text.bold, text.colour, text.align))

    def test_a_label_is_bold_at_the_stage_size_in_the_body_colour(self) -> None:
        text = shown({"text": "Column", "role": "label"})
        self.assertEqual((T.stage, True, P.ink), (text.size, text.bold, text.colour))

    def test_a_note_is_small_and_grey_and_not_bold(self) -> None:
        text = shown({"text": "Counted over ten runs", "role": "note"})
        self.assertEqual((T.caption, False, P.muted), (text.size, text.bold, text.colour))

    def test_each_role_is_as_tall_as_its_own_lines(self) -> None:
        """The row takes the height of the words at their own size (= a label wraps as bold type at `stage`)."""
        words = "Words long enough to wrap onto a second line of the cell, and then a third."
        width = Page("A page", DEFAULT).body.width - 2 * S.text_inset
        for role, size, bold in (("label", T.stage, True), ("note", T.caption, False), (None, T.body, False),
                                 ("display", T.display, True)):
            with self.subTest(role=role):
                text = shown({"text": words, "role": role} if role else {"text": words})
                self.assertEqual(DEFAULT.wrapped_height(words, width, size, bold=bold), text.rect.height)

    def test_a_tone_that_carries_a_colour_is_that_colour_in_every_role(self) -> None:
        for role in (None, "label", "note", "display"):
            for tone, colour in (("accent", P.accent), ("good", P.good), ("bad", P.bad)):
                with self.subTest(role=role, tone=tone):
                    cell = {"text": "Words", "tone": tone, **({"role": role} if role else {})}
                    self.assertEqual(colour, shown(cell).colour)

    def test_a_tone_without_a_meaning_leaves_the_words_in_the_body_colour(self) -> None:
        """A pale ground (= `box`, `band`, `tint`) is a ground, not an ink: words on the paper in it would not read."""
        for tone in ("box", "band", "tint"):
            with self.subTest(tone=tone):
                self.assertEqual(P.ink, shown({"text": "Words", "tone": tone}).colour)

    def test_a_tone_wins_over_the_colour_a_role_has_of_its_own(self) -> None:
        self.assertEqual(P.bad, shown({"text": "Aside", "role": "note", "tone": "bad"}).colour)
        self.assertEqual(P.bad, shown({"text": "98%", "role": "display", "tone": "bad"}).colour)
        self.assertEqual(P.accent, shown({"text": "98%", "role": "display"}).colour, "unsaid, the accent as before")

    def test_a_ground_the_project_named_gives_its_colour_when_it_is_deep_and_the_ink_when_it_is_pale(self) -> None:
        self.assertEqual(GROUNDS["Deep"], shown({"text": "Words", "tone": "Deep"}, NAMED).colour)
        self.assertEqual(P.ink, shown({"text": "Words", "tone": "Pale"}, NAMED).colour)

    def test_align_sets_the_words_to_the_middle_of_their_cell(self) -> None:
        self.assertEqual("center", shown({"text": "Heading", "role": "label", "align": "center"}).align)
        self.assertEqual("left", shown({"text": "Heading", "role": "label", "align": "left"}).align)
        self.assertEqual("center", shown({"text": "98%", "role": "display", "align": "center"}).align)

    def test_what_a_text_cannot_say_is_refused_and_says_where(self) -> None:
        refused = (({"text": "A", "tone": "neon"}, "tone 'neon'"), ({"text": "A", "align": "right"}, "`align` is 'left' or 'center'"),
                   ({"text": "A", "align": "middle"}, "not 'middle'"), ({"text": "A", "role": "title"}, "display, label, note, mono"),
                   ({"card": {"heading": "A"}, "tone": "accent"}, "`tone` belongs to a text"),
                   ({"figure": "dot.png", "align": "center"}, "`align` belongs to a text"),
                   ({"text": "x = 1", "role": "mono", "tone": "bad"}, "a mono text"),
                   ({"text": "x = 1", "role": "mono", "align": "center"}, "a mono text"))
        for cell, words in refused:
            with self.subTest(cell=cell), self.assertRaises(PageTypeError) as stopped:
                compose([row({"text": "beside"}, cell)])
            self.assertIn("row 1, cell 2", str(stopped.exception))
            self.assertIn(words, str(stopped.exception))

    def test_written_out_the_roles_keep_their_weight_size_and_colour_and_the_checks_find_nothing(self) -> None:
        page = compose([row({"text": "Column", "role": "label", "tone": "accent", "align": "center"},
                            {"text": "Counted over ten runs", "role": "note"},
                            {"text": "Watch this", "tone": "bad"})])
        with tempfile.TemporaryDirectory() as tmp:
            deck = new_deck(DEFAULT)
            add_page(deck, page.build(), DEFAULT)
            saved = save(deck, Path(tmp) / "roles.pptx")
            self.assertEqual([], checks.run_all(saved))
            with zipfile.ZipFile(saved) as archive:
                xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        self.assertIn(f'sz="{int(T.stage * 100)}" b="1"', xml)
        self.assertIn(f'sz="{int(T.caption * 100)}" b="0"', xml)
        for colour in (P.accent, P.muted, P.bad):
            self.assertIn(f'val="{colour}"', xml)
        self.assertIn('algn="ctr"', xml)


def two_over(link, theme=DEFAULT, **cells):
    """Two cards, one over the other, and a link from the upper to the lower."""
    return build({"type": "compose", "title": "A page", "links": [{"from": "a", "to": "b", **link}],
                  "rows": [row({"id": "a", "card": {"heading": "Upper"}, **cells}),
                           row({"id": "b", "card": {"heading": "Lower"}})]}, theme)


#: 矢印の上に言葉が立てるだけの高さを持つカード (= 横の矢印の上は、向き合う 2 つのマスの高さの半分まで)
TALL = {"heading": "Card", "body": "one\ntwo\nthree"}


def side_by_side(link, theme=DEFAULT):
    return build({"type": "compose", "title": "A page", "links": [{"from": "a", "to": "b", **link}],
                  "rows": [row({"id": "a", "card": TALL}, {"id": "b", "card": TALL})]}, theme)


class TheColourOfAnArrow(unittest.TestCase):
    """A link's `tone` is the colour of its line and its head; unsaid, the quiet grey it always was."""

    def test_unsaid_the_arrow_is_grey_and_carries_no_words(self) -> None:
        page = two_over({})
        (line,) = kinds(page, "line")
        self.assertEqual(P.muted, line.colour)
        self.assertEqual([], kinds(page, "diagram_text"))

    def test_a_tone_is_the_colour_of_the_line(self) -> None:
        for tone, colour in (("accent", P.accent), ("bad", P.bad), ("good", P.good), ("box", P.ink)):
            with self.subTest(tone=tone):
                (line,) = kinds(two_over({"tone": tone}), "line")
                self.assertEqual(colour, line.colour)
                self.assertTrue(line.arrow)

    def test_a_ground_the_project_named_is_a_tone_of_an_arrow_too(self) -> None:
        (line,) = kinds(two_over({"tone": "Deep"}, NAMED), "line")
        self.assertEqual(GROUNDS["Deep"], line.colour)

    def test_a_tone_that_is_not_one_is_refused_and_says_which_link(self) -> None:
        with self.assertRaises(PageTypeError) as stopped:
            two_over({"tone": "neon"})
        self.assertIn("link 1", str(stopped.exception))
        self.assertIn("tone 'neon'", str(stopped.exception))


class WordsBesideAnArrow(unittest.TestCase):
    """`text` of a link: to the right of a downward arrow, above a sideways one, in the body's size, weight and colour."""

    def test_the_words_of_a_downward_arrow_stand_to_its_right_in_the_gap_between_the_cells(self) -> None:
        page = two_over({"text": "Then"}, AIRY)
        upper, lower = (e.rect for e in kinds(page, "box"))
        (line,) = kinds(page, "line")
        words = named(page, "Then")
        self.assertEqual("diagram_text", words.kind)
        self.assertEqual(line.start[0] + AIRY.spacing.gap_s, words.rect.left)
        self.assertGreaterEqual(words.rect.top, upper.bottom)
        self.assertLessEqual(words.rect.bottom, lower.top)
        self.assertEqual(lower.top - words.rect.bottom, words.rect.top - upper.bottom, "in the middle of the gap")
        self.assertEqual(Page("A page", AIRY).body.right, words.rect.right, "as far right as the cells go")
        self.assertEqual((AIRY.type.body, True, "left"), (words.size, words.bold, words.align))

    def test_the_words_are_in_the_body_colour_whatever_the_colour_of_the_arrow(self) -> None:
        """The tone is the arrow's: an orange line carries words as dark as any others."""
        for link in ({}, {"tone": "bad"}, {"tone": "accent"}):
            with self.subTest(link=link):
                self.assertEqual(P.ink, named(two_over({"text": "Then", **link}, AIRY), "Then").colour)

    def test_the_words_of_a_downward_arrow_stop_short_of_a_cell_in_their_way(self) -> None:
        """A tall card to the right stands in the gap's whole height: the words are set between it and the arrow."""
        page = build({"type": "compose", "title": "A page", "links": [{"from": "a", "to": "b", "text": "Then"}],
                      "rows": [row({"rows": [row({"id": "a", "card": {"heading": "Upper"}}),
                                             row({"id": "b", "card": {"heading": "Lower"}})]},
                                   {"card": {"heading": "Tall"}})]}, AIRY)
        tall = max((e.rect for e in kinds(page, "box")), key=lambda rect: rect.height)
        words = named(page, "Then")
        self.assertEqual(tall.left - AIRY.spacing.gap_s, words.rect.right)

    def test_the_words_of_a_sideways_arrow_stand_above_it_across_the_gap(self) -> None:
        page = side_by_side({"text": "Next"}, AIRY)
        left, right = (e.rect for e in kinds(page, "box"))
        (line,) = kinds(page, "line")
        words = named(page, "Next")
        self.assertEqual((left.right, right.left), (words.rect.left, words.rect.right))
        self.assertLess(words.rect.bottom, line.start[1])
        self.assertGreaterEqual(words.rect.top, left.top)
        self.assertEqual("center", words.align)

    def test_the_words_of_a_backward_arrow_stand_over_the_same_gap(self) -> None:
        page = build({"type": "compose", "title": "A page", "links": [{"from": "b", "to": "a", "text": "Back"}],
                      "rows": [row({"id": "a", "card": TALL}, {"id": "b", "card": TALL})]}, AIRY)
        left, right = (e.rect for e in kinds(page, "box"))
        self.assertEqual((left.right, right.left), (named(page, "Back").rect.left, named(page, "Back").rect.right))

    def test_words_that_rise_above_the_cells_beside_a_sideways_arrow_stop(self) -> None:
        """Above the arrow there is the height of the cells, and no more: the words are not set over the page's bands."""
        with self.assertRaises(PageFullError) as stopped:
            side_by_side({"text": "Words that wrap onto many lines in a narrow gap"}, AIRY)
        self.assertIn("link 1", str(stopped.exception))
        self.assertIn("of height above the arrow", str(stopped.exception))

    def test_words_that_do_not_fit_the_gap_stop_and_say_which_link_and_what_to_widen(self) -> None:
        with self.assertRaises(PageFullError) as above:
            side_by_side({"text": "Words that are longer than the gap between two cells"})
        self.assertIn("link 1", str(above.exception))
        self.assertIn("`gap_m`", str(above.exception))
        with self.assertRaises(PageFullError) as beside:
            two_over({"text": "Words long enough to need two lines beside the arrow " * 4})
        self.assertIn("link 1", str(beside.exception))
        self.assertIn("nothing will shrink", str(beside.exception))
        with self.assertRaises(PageFullError) as tight:
            two_over({"text": "Then"})
        self.assertIn("`gap_m`", str(tight.exception), "one line of body type is taller than the gap a page has unsaid")

    def test_a_downward_arrow_with_no_room_on_its_right_stops(self) -> None:
        """A column narrower than the distance the words keep from the arrow and from the cell beside it."""
        loose = theme_from({"uses": {"loose": {"like": "read", "spacing": {"gap_m": 1.6, "gap_s": 1.0}}}}).using("loose")
        with self.assertRaises(PageFullError) as stopped:
            build({"type": "compose", "title": "A page", "links": [{"from": "a", "to": "b", "text": "Then"}],
                   "rows": [row({"rows": [row({"id": "a", "card": {}}), row({"id": "b", "card": {}})], "weight": 0.05},
                                {"card": {"heading": "Tall"}, "weight": 1})]}, loose)
        self.assertIn("link 1", str(stopped.exception))
        self.assertIn("not even one character", str(stopped.exception))
        self.assertIn("to the right of the arrow", str(stopped.exception))

    def test_an_arrow_crosses_an_empty_cell_and_its_words_stand_over_the_whole_span(self) -> None:
        """A cell of `text = ""` is space: two cells with one between them are joined across it, words on the line."""
        page = build({"type": "compose", "title": "A page", "links": [{"from": "a", "to": "b", "text": "Then"}],
                      "rows": [row({"id": "a", "card": TALL}, {"text": "", "weight": 2}, {"id": "b", "card": TALL})]})
        left, right = (e.rect for e in kinds(page, "box"))
        (line,) = kinds(page, "line")
        words = named(page, "Then")
        self.assertEqual((left.right, right.left), (line.start[0], line.end[0]))
        self.assertEqual((left.right, right.left), (words.rect.left, words.rect.right))

    def test_a_cell_with_something_in_it_still_stops_the_arrow(self) -> None:
        for between in ({"text": "x"}, {"text": "", "role": "mono"}, {"card": {}}):
            with self.subTest(between=between), self.assertRaises(PageTypeError) as stopped:
                build({"type": "compose", "title": "A page", "links": [{"from": "a", "to": "b"}],
                       "rows": [row({"id": "a", "card": {"heading": "Left"}}, between,
                                    {"id": "b", "card": {"heading": "Right"}})]})
            self.assertIn("stands between", str(stopped.exception))

    def test_an_empty_cell_beside_a_downward_arrow_does_not_stop_its_words(self) -> None:
        page = build({"type": "compose", "title": "A page", "links": [{"from": "a", "to": "b", "text": "Then"}],
                      "rows": [row({"rows": [row({"id": "a", "card": {"heading": "Upper"}}),
                                             row({"id": "b", "card": {"heading": "Lower"}})]}, {"text": ""})]}, AIRY)
        self.assertEqual(Page("A page", AIRY).body.right, named(page, "Then").rect.right)

    def test_words_that_are_not_words_are_refused(self) -> None:
        for said in ("", "  ", 3, ["Then"]):
            with self.subTest(said=said), self.assertRaises(PageTypeError) as stopped:
                two_over({"text": said}, AIRY)
            self.assertIn("link 1", str(stopped.exception))
            self.assertIn("`text`", str(stopped.exception))

    def test_a_link_still_refuses_a_key_it_does_not_read(self) -> None:
        with self.assertRaises(PageTypeError) as stopped:
            two_over({"label": "Then"})
        self.assertIn("label", str(stopped.exception))

    def test_written_out_the_arrow_keeps_its_colour_and_its_words_their_weight_and_the_checks_find_nothing(self) -> None:
        page = two_over({"text": "Then", "tone": "accent"}, AIRY)
        with tempfile.TemporaryDirectory() as tmp:
            deck = new_deck(AIRY)
            add_page(deck, page.build(), AIRY)
            saved = save(deck, Path(tmp) / "links.pptx")
            self.assertEqual([], checks.run_all(saved))
            with zipfile.ZipFile(saved) as archive:
                xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        self.assertIn("<a:t>Then</a:t>", xml)
        self.assertEqual(1, xml.count(f'val="{P.accent}"'), "the line only: its words are in the body colour")
        self.assertIn(f'sz="{int(AIRY.type.body * 100)}" b="1"', xml)


if __name__ == "__main__":
    unittest.main()
