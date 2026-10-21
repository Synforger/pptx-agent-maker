"""What a card and a band may be written with: their own sizes, no heading, a tag, a list of bullets.

* `band` and `display` ― the size of the bands over and under a page, and of the big number, each its own
  role in `[theme.type]` and in a use of the project's (= unsaid, the band is the heading and the number is
  twice the title, as they were)
* a card without a heading, or with nothing in it; `align = "center"`; and, in a deck whose cards are
  `outlined`, words in the middle of the box
* `tag = true` ― a one-line label on a pale grey ground, its line and its words in the colour of its tone
* `body = ["…", "…"]` ― one bullet to an item, a wrapped line standing in with the words
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))
from support.pages import box_of, build, named  # noqa: E402

from pptx_agent_maker import DEFAULT, Page, checks  # noqa: E402
from pptx_agent_maker.layout.base.geometry import Rect, pt  # noqa: E402
from pptx_agent_maker.layout.base.tokens import DERIVED, SIZED, ThemeError, theme_from  # noqa: E402
from pptx_agent_maker.layout.parts.elements import bullet_indent  # noqa: E402
from pptx_agent_maker.layout.parts.page import TEXT_PAD_Y, Card, PageFullError, card_text  # noqa: E402
from pptx_agent_maker.layout.types.core.registry import PageTypeError  # noqa: E402
from pptx_agent_maker.write import add_page, new_deck, save  # noqa: E402

P = DEFAULT.palette
T = DEFAULT.type
S = DEFAULT.spacing
OUTLINED = theme_from({"card_look": "outlined"})
OUTLINED_PAGE = theme_from({"card_look": "outlined", "box_height": "page"})


def cards(*items, theme=DEFAULT, **extra):
    return build({"type": "cards", "title": "Cards", "cards": list(items), **extra}, theme)


def elements(built, kind):
    return [e for e in built.build() if e.kind == kind]


def row(*cells, **more):
    return {"cells": list(cells), **more}


class TheBandAndTheBigNumberHaveSizesOfTheirOwn(unittest.TestCase):
    def test_left_unsaid_the_band_is_the_heading_and_the_number_twice_the_title(self) -> None:
        for use in ("read", "present", "sheet"):
            with self.subTest(use=use):
                type = DEFAULT.using(use).type
                self.assertEqual((type.heading, type.title * 2), (type.band, type.display))

    def test_a_project_writes_each_under_theme_type(self) -> None:
        type = theme_from({"type": {"band": 14, "display": 40}}).type
        self.assertEqual((14, 40), (type.band, type.display))
        self.assertEqual((DEFAULT.type.heading, DEFAULT.type.title), (type.heading, type.title))

    def test_the_heading_alone_still_takes_the_band_with_it(self) -> None:
        type = theme_from({"type": {"heading": 12}}).type
        self.assertEqual(12, type.band)

    def test_the_title_alone_still_takes_the_number_with_it(self) -> None:
        self.assertEqual(40, theme_from({"type": {"title": 20}}).type.display)

    def test_a_use_of_the_projects_writes_them_too(self) -> None:
        theme = theme_from({"uses": {"slim": {"like": "read", "heading": 11, "band": 16, "display": 36}}})
        type = theme.using("slim").type
        self.assertEqual((11, 16, 36), (type.heading, type.band, type.display))
        self.assertEqual(DEFAULT.type.band, theme.type.band, "the use it was not written for is as it was")

    def test_the_height_of_a_band_follows_the_band_and_not_the_heading(self) -> None:
        read = DEFAULT.spacing.band_height
        self.assertEqual(round(read * 24 / 16), theme_from({"type": {"band": 24}}).spacing.band_height)
        self.assertEqual(read, theme_from({"type": {"heading": 11, "band": 16}}).spacing.band_height)
        self.assertEqual(round(read * 11 / 16), theme_from({"type": {"heading": 11}}).spacing.band_height)

    def test_a_size_under_the_floor_is_refused_with_the_key_it_was_written_under(self) -> None:
        for key in DERIVED:
            with self.subTest(key=key), self.assertRaises(ThemeError) as refused:
                theme_from({"type": {key: 8}})
            self.assertIn(f"theme.type.{key}", str(refused.exception))

    def test_a_size_that_is_not_a_number_is_refused(self) -> None:
        for key in DERIVED:
            for value in ("big", True, None):
                with self.subTest(key=key, value=value), self.assertRaises(ThemeError):
                    theme_from({"type": {key: value}})

    def test_a_role_nobody_reads_is_still_refused_and_the_two_new_ones_are_listed(self) -> None:
        with self.assertRaises(ThemeError) as refused:
            theme_from({"type": {"bands": 14}})
        for name in (*SIZED, *DERIVED):
            self.assertIn(name, str(refused.exception))

    def test_a_use_of_the_projects_refuses_a_role_nobody_reads_and_lists_the_two_new_ones(self) -> None:
        with self.assertRaises(ThemeError) as refused:
            theme_from({"uses": {"slim": {"like": "read", "bandd": 14}}})
        for name in DERIVED:
            self.assertIn(name, str(refused.exception))

    def test_the_words_of_a_band_are_set_at_the_band_size(self) -> None:
        for look in ("plain", "outlined"):
            theme = theme_from({"band_look": look, "type": {"heading": 12, "band": 18}})
            page = Page("T", theme, condition="If this holds")
            with self.subTest(look=look):
                self.assertEqual(18, next(e for e in page.elements if e.kind == "band_text").size)

    def test_the_conclusion_is_set_at_the_band_size_in_a_plain_band_and_at_the_body_size_in_an_outlined_one(self) -> None:
        sizes = {}
        for look in ("plain", "outlined"):
            page = Page("T", theme_from({"band_look": look, "type": {"band": 18}}), conclusion="Then that follows")
            sizes[look] = next(e for e in page.elements if e.kind == "band_text").size
        self.assertEqual({"plain": 18, "outlined": T.body}, sizes)

    def test_a_card_heading_does_not_follow_the_band(self) -> None:
        built = cards({"heading": "Head", "body": "words"}, theme=theme_from({"type": {"band": 20}}))
        self.assertEqual(T.heading, named(built, "Head").size)

    def test_the_big_number_of_a_compose_is_set_at_the_display_size(self) -> None:
        theme = theme_from({"type": {"display": 40}})
        built = build({"type": "compose", "title": "T", "rows": [row({"text": "76%", "role": "display"})]}, theme)
        self.assertEqual(40, named(built, "76%").size)


class AWordOrTwoOfACardMayBeLeftOut(unittest.TestCase):
    def test_a_card_of_words_only_has_no_heading_and_the_words_take_the_box(self) -> None:
        built = cards({"body": "only the words"})
        self.assertEqual([], elements(built, "box_heading"))
        body, box = named(built, "only the words"), elements(built, "box")[0]
        self.assertEqual((box.rect.left + S.pad, box.rect.top + S.pad), (body.rect.left, body.rect.top))

    def test_a_card_with_nothing_in_it_is_a_box_and_no_words(self) -> None:
        built = cards({"tone": "tint"}, {"heading": "Next", "body": "beside it"})
        self.assertEqual(2, len(elements(built, "box")))
        self.assertEqual(1, len(elements(built, "box_heading")))
        self.assertEqual(1, len(elements(built, "box_body")))

    def test_a_card_of_words_only_is_as_tall_as_its_words_and_no_more(self) -> None:
        one = cards({"heading": "Head", "body": "words"}).build()
        bare = cards({"body": "words"}).build()
        tall = lambda found: next(e for e in found if e.kind == "box").rect.height
        self.assertEqual(tall(one) - DEFAULT.line_height(T.heading) - S.gap_s, tall(bare))

    def test_a_card_with_neither_stands_two_pads_high(self) -> None:
        self.assertEqual(2 * S.pad, elements(cards({}), "box")[0].rect.height)

    def test_a_card_of_a_flow_and_of_a_compose_may_leave_the_heading_out_too(self) -> None:
        stages = [{"name": "S", "nodes": [{"body": "words only"}]}, {"name": "T", "nodes": [["Other", "o"]]}]
        for data in ({"type": "flow", "title": "T", "stages": stages},
                     {"type": "compose", "title": "T", "rows": [row({"card": {"body": "words only"}})]}):
            with self.subTest(type=data["type"]):
                self.assertTrue(named(build(data), "words only"))

    def test_a_key_nobody_reads_is_still_refused_and_the_new_ones_are_listed(self) -> None:
        with self.assertRaises(PageTypeError) as refused:
            cards({"heading": "A", "colour": "red"})
        for key in ("tag", "align", "body", "heading"):
            self.assertIn(key, str(refused.exception))
        self.assertIn("cards: card 1", str(refused.exception))


class AlignmentAndTheMiddleOfTheBox(unittest.TestCase):
    def test_a_card_is_set_to_the_left_unless_it_says_centre(self) -> None:
        left, centre = cards({"heading": "Head", "body": "words"}), cards({"heading": "Head", "body": "words",
                                                                          "align": "center"})
        self.assertEqual(("left", "left"), (named(left, "Head").align, named(left, "words").align))
        self.assertEqual(("center", "center"), (named(centre, "Head").align, named(centre, "words").align))

    def test_an_alignment_nobody_knows_is_refused_with_the_key_and_the_card(self) -> None:
        for value in ("middle", "", 1, True):
            with self.subTest(value=value), self.assertRaises(PageTypeError) as refused:
                cards({"heading": "A", "align": value})
            self.assertIn("`align`", str(refused.exception))
            self.assertIn("cards: card 1", str(refused.exception))

    def centre(self, built, head: str, last: str) -> tuple[float, float]:
        """(the middle of the words as they stand on the page, the middle of the box)."""
        first, end, box = named(built, head).rect, named(built, last).rect, elements(built, "box")[0].rect
        return (first.top + TEXT_PAD_Y + (end.bottom - first.top) / 2, box.top + box.height / 2)

    def test_in_an_outlined_deck_the_words_stand_in_the_middle_of_the_box(self) -> None:
        for items in ({"heading": "Head", "body": "words"}, {"heading": "Head"}, {"body": "words"}):
            built = cards({**items, "tone": "accent"}, theme=OUTLINED_PAGE)
            first = "Head" if "heading" in items else "words"
            last = "words" if "body" in items else "Head"
            with self.subTest(items=items):
                words, box = self.centre(built, first, last)
                self.assertAlmostEqual(box, words, delta=2)

    def test_the_words_of_a_box_that_has_no_room_to_spare_start_at_its_top(self) -> None:
        page = Page("T", OUTLINED)
        box = Rect(page.body.left, page.body.top, page.body.width, DEFAULT.line_height(T.heading) + 2 * S.pad)
        page.boxes(box, [Card("Head", "words that need more room than the box has")])
        head = next(e for e in page.elements if e.kind == "box_heading").rect
        self.assertEqual(box.top + S.pad - TEXT_PAD_Y, head.top)

    def test_a_filled_deck_keeps_the_words_at_the_top(self) -> None:
        built = cards({"heading": "Head", "body": "words"}, theme=theme_from({"box_height": "page"}))
        head, box = named(built, "Head").rect, elements(built, "box")[0].rect
        self.assertEqual(box.top + S.pad, head.top)

    def test_an_outlined_deck_whose_boxes_are_as_tall_as_their_words_keeps_them_apart_as_before(self) -> None:
        was = cards({"heading": "Head", "body": "words"}).build()
        now = cards({"heading": "Head", "body": "words"}, theme=OUTLINED).build()
        self.assertEqual(next(e for e in was if e.kind == "box").rect.height,
                         next(e for e in now if e.kind == "box").rect.height)

    def test_the_heading_and_the_body_do_not_overlap_when_they_are_set_in_the_middle(self) -> None:
        built = cards({"heading": "Head", "body": "words"}, theme=OUTLINED_PAGE)
        self.assertEqual(named(built, "Head").rect.bottom + S.gap_s, named(built, "words").rect.top)


class ATagIsOneLineOnAPaleGround(unittest.TestCase):
    def tag(self, theme=DEFAULT, **more):
        built = cards({"heading": "Stage 1", "tag": True, **more}, theme=theme)
        return elements(built, "box")[0], named(built, "Stage 1"), built

    def test_the_ground_is_pale_grey_and_the_line_and_the_words_are_the_colour_of_the_tone(self) -> None:
        for theme in (DEFAULT, OUTLINED):
            for tone, hue in (("accent", P.accent), ("good", P.good), ("bad", P.bad)):
                with self.subTest(look=theme.card_look, tone=tone):
                    box, words, _built = self.tag(theme, tone=tone)
                    self.assertEqual((P.wash, hue), (box.colour, box.outline))
                    self.assertEqual((hue, True, "center"), (words.colour, words.bold, words.align))

    def test_a_tone_with_no_colour_of_its_own_is_set_in_ink(self) -> None:
        _box, words, _built = self.tag(DEFAULT)
        self.assertEqual(P.ink, words.colour)

    def test_a_tone_a_project_named_gives_its_colour(self) -> None:
        theme = theme_from({"grounds": {"Deep": "8B1E3F"}})
        box, words, _built = self.tag(theme, tone="Deep")
        self.assertEqual(("8B1E3F", "8B1E3F"), (box.outline, words.colour))

    def test_a_tag_is_rounded_where_the_cards_are(self) -> None:
        self.assertEqual((False, True), (self.tag(DEFAULT)[0].rounded, self.tag(OUTLINED)[0].rounded))

    def test_a_strong_tag_draws_a_heavy_line(self) -> None:
        self.assertTrue(self.tag(DEFAULT, strong=True)[0].heavy)
        self.assertFalse(self.tag(DEFAULT)[0].heavy)

    def test_a_tag_is_one_line_high_and_the_words_stand_in_the_middle(self) -> None:
        for theme in (OUTLINED_PAGE, theme_from({"box_height": "page"})):
            box, words, _built = self.tag(theme)
            self.assertAlmostEqual(box.rect.top + box.rect.height / 2,
                                   words.rect.top + TEXT_PAD_Y + words.rect.height / 2, delta=2)
        box, _words, _built = self.tag(DEFAULT)
        self.assertEqual(DEFAULT.line_height(T.heading) + 2 * S.pad, box.rect.height)

    def test_a_tag_that_would_wrap_stops_the_page(self) -> None:
        with self.assertRaises(PageFullError) as stopped:
            cards({"heading": "A stage whose name runs on and on past the end of its box", "tag": True},
                  {"heading": "x"}, {"heading": "y"}, {"heading": "z"}, card_columns=4)
        self.assertIn("tag", str(stopped.exception))

    def test_a_tag_has_a_heading_and_nothing_else(self) -> None:
        for more, word in (({"heading": ""}, "heading"), ({"body": "words"}, "body"), ({"icon": "dot.png"}, "icon")):
            with self.subTest(more=more), self.assertRaises(PageTypeError) as refused:
                cards({"heading": "Stage", "tag": True, **more})
            self.assertIn(word, str(refused.exception))
            self.assertIn("cards: card 1", str(refused.exception))

    def test_a_tag_is_true_or_false(self) -> None:
        for value in ("yes", 1, None):
            with self.subTest(value=value), self.assertRaises(PageTypeError) as refused:
                cards({"heading": "Stage", "tag": value})
            self.assertIn("`tag`", str(refused.exception))

    def test_a_card_that_is_no_tag_is_painted_as_it_was(self) -> None:
        built = cards({"heading": "Head", "body": "words", "tone": "accent", "tag": False})
        self.assertEqual(P.accent, elements(built, "box")[0].colour)

    def test_a_tag_may_stand_in_a_compose_and_in_a_flow(self) -> None:
        stages = [{"name": "S", "nodes": [{"heading": "Stage 1", "tag": True, "tone": "bad"}]},
                  {"name": "T", "nodes": [["Other", "o"]]}]
        for data in ({"type": "flow", "title": "T", "stages": stages},
                     {"type": "compose", "title": "T",
                      "rows": [row({"card": {"heading": "Stage 1", "tag": True, "tone": "bad"}})]}):
            with self.subTest(type=data["type"]):
                self.assertEqual(P.wash, box_of(build(data), "Stage 1").colour)


class ABodyOfBullets(unittest.TestCase):
    ITEMS = ["the first line", "a second line that is long enough to wrap onto another line of the card", "the third"]

    def test_a_list_is_one_bullet_to_an_item(self) -> None:
        body = named(cards({"heading": "Head", "body": self.ITEMS}), "\n".join(self.ITEMS))
        self.assertEqual((True, "box_body"), (body.bullets, body.kind))

    def test_a_string_is_a_paragraph_as_it_was(self) -> None:
        built = cards({"heading": "Head", "body": "one\ntwo"})
        self.assertFalse(named(built, "one\ntwo").bullets)

    def test_a_card_written_as_a_pair_takes_a_list_too(self) -> None:
        body = named(cards(["Head", ["one", "two"]]), "one\ntwo")
        self.assertTrue(body.bullets)

    def test_an_empty_list_an_empty_item_and_a_line_break_are_refused_with_the_line(self) -> None:
        for body, word in (([], "empty list"), (["one", " "], "line 2"), (["one", "two\nthree"], "line 2")):
            with self.subTest(body=body), self.assertRaises(PageTypeError) as refused:
                cards({"heading": "A", "body": body})
            self.assertIn(word, str(refused.exception))
            self.assertIn("cards: card 1", str(refused.exception))

    def test_the_words_of_a_bullet_are_counted_in_the_width_left_after_the_dot(self) -> None:
        """⚠ 点の分だけ内に入るので、字下げの無い数え方では、1 行に収まると数えた物が折れる。"""
        room = 4_000_000
        fits = "あ" * (room // pt(T.body))            # exactly a line, set flush
        flush, bullet = Card("", fits), Card("", fits, bullets=True)
        self.assertEqual(DEFAULT.line_height(T.body), card_text(DEFAULT, flush, room)[1])
        self.assertEqual(2 * DEFAULT.line_height(T.body), card_text(DEFAULT, bullet, room)[1])

    def test_each_item_is_counted_in_its_own_lines(self) -> None:
        room = 4_000_000
        fits = "あ" * (room // pt(T.body) - 1)         # a line, with one em to spare for the dot
        bullets = Card("", "\n".join([fits] * 3), bullets=True)
        self.assertEqual(3 * DEFAULT.line_height(T.body), card_text(DEFAULT, bullets, room)[1])

    def test_a_card_of_bullets_is_as_tall_as_its_bullets(self) -> None:
        flat = cards({"heading": "Head", "body": "\n".join(self.ITEMS)}).build()
        bullets = cards({"heading": "Head", "body": self.ITEMS}).build()
        tall = lambda found: next(e for e in found if e.kind == "box").rect.height
        self.assertGreaterEqual(tall(bullets), tall(flat))

    def test_what_is_written_is_a_bullet_of_the_paragraph_and_not_a_character(self) -> None:
        deck = new_deck()
        add_page(deck, cards({"heading": "Head", "body": self.ITEMS}, {"heading": "Flat", "body": "one\ntwo"}).build(),
                 DEFAULT)
        with tempfile.TemporaryDirectory() as tmp:
            saved = save(deck, Path(tmp) / "bullets.pptx")
            self.assertEqual([], checks.run_all(saved))
            xml = zipfile.ZipFile(saved).read("ppt/slides/slide1.xml").decode("utf-8")
        self.assertEqual(len(self.ITEMS), xml.count('<a:buChar char="•"/>'))
        indent = bullet_indent(T.body)
        self.assertEqual(len(self.ITEMS), len(re.findall(rf'<a:pPr[^>]*marL="{indent}"[^>]*indent="-{indent}"', xml)))
        for item in self.ITEMS:
            self.assertIn(f"<a:t>{item}</a:t>", xml, "the words are the item, with no dot typed in front")
        self.assertEqual(len(self.ITEMS), xml.count("<a:buChar"), "the flat card carries none")

    def test_the_hang_is_as_wide_as_the_size_of_the_words(self) -> None:
        self.assertEqual(pt(T.body), bullet_indent(T.body))


class ADeckInEveryNewWayOpens(unittest.TestCase):
    def test_a_page_with_a_tag_a_list_and_a_card_of_nothing_is_written_and_passes_the_checks(self) -> None:
        theme = theme_from({"card_look": "outlined", "band_look": "outlined", "box_height": "page",
                            "type": {"heading": 12, "band": 16}})
        built = cards({"heading": "Stage 1", "tag": True, "tone": "bad"},
                      {"body": ["first", "second"], "align": "center", "tone": "accent"},
                      {"tone": "tint"}, card_columns=3, theme=theme,
                      condition="Headings are small; the band is not", conclusion="Then that follows")
        deck = new_deck(theme)
        add_page(deck, built.build(), theme)
        with tempfile.TemporaryDirectory() as tmp:
            saved = save(deck, Path(tmp) / "new.pptx")
            self.assertEqual([], checks.run_all(saved))


if __name__ == "__main__":
    unittest.main()
