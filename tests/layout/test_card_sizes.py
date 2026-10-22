"""The size of a tag, the look of a table a use picks, and the single words of a card standing in the middle of their frame.

* `tag` under `[theme.type]` and `[theme.uses.<name>]` ― the size of the words of a tag, apart from the headings of
  the cards beside it (= unsaid, the size of a heading, as it was)
* `table_look` under `[theme.uses.<name>]` ― a use may pick the look of its tables, apart from the deck (= unsaid,
  the look the deck sets)
* a card that holds one set of words (= a tag, a card of a body only, a card of a heading only) in a deck whose
  cards are `outlined` ― the frame of the words is the whole inside of the box and the words stand in its middle,
  so two boxes side by side set in different sizes still line up
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
from support.pages import build  # noqa: E402

from pptx_agent_maker import DEFAULT  # noqa: E402
from pptx_agent_maker.checks.rules import near_alignment  # noqa: E402
from pptx_agent_maker.layout.tokens import TABLE_LOOKS, ThemeError, theme_from  # noqa: E402
from pptx_agent_maker.layout.parts.elements import TEXT_INSET_Y, Text  # noqa: E402
from pptx_agent_maker.layout.parts.page import Card, PageFullError, card_text  # noqa: E402
from pptx_agent_maker.write import add_page, new_deck, save  # noqa: E402

P = DEFAULT.palette
S = DEFAULT.spacing
OUTLINED = theme_from({"card_look": "outlined"})
OUTLINED_PAGE = theme_from({"card_look": "outlined", "box_height": "page"})


def cards(*items, theme=DEFAULT, **extra):
    return build({"type": "cards", "title": "Cards", "cards": list(items), **extra}, theme)


def of_kind(built, kind):
    return [e for e in built.build() if e.kind == kind]


def words_of(built, text: str) -> Text:
    return next(e for e in built.build() if getattr(e, "text", None) == text)


class ATagHasASizeOfItsOwn(unittest.TestCase):
    def test_left_unsaid_a_tag_is_the_size_of_a_heading(self) -> None:
        for settings in ({}, {"type": {"heading": 11}}, {"use": "present"}, {"use": "sheet"}):
            with self.subTest(settings=settings):
                type = theme_from(settings).type
                self.assertEqual(type.heading, type.tag)
        self.assertEqual(DEFAULT.type.heading, DEFAULT.type.tag)

    def test_a_project_writes_it_under_theme_type_and_the_heading_stays_as_it_was(self) -> None:
        type = theme_from({"type": {"heading": 11, "tag": 14}}).type
        self.assertEqual((11, 14), (type.heading, type.tag))

    def test_a_use_of_the_project_writes_it_for_itself_only(self) -> None:
        theme = theme_from({"uses": {"slim": {"like": "read", "heading": 11, "tag": 14}}})
        type = theme.using("slim").type
        self.assertEqual((11, 14), (type.heading, type.tag))
        self.assertEqual(DEFAULT.type.tag, theme.type.tag, "the use it was not written for is as it was")

    def test_a_tag_is_set_at_its_size_and_the_heading_beside_it_at_its_own(self) -> None:
        theme_type = {"heading": 10.5, "tag": 14}
        for look in ("filled", "outlined"):
            with self.subTest(look=look):
                built = cards({"heading": "Stage 1", "tag": True}, {"heading": "Method", "body": "words"},
                              theme=theme_from({"card_look": look, "type": theme_type}), card_columns=2)
                self.assertEqual(14, words_of(built, "Stage 1").size)
                self.assertEqual(10.5, words_of(built, "Method").size)

    def test_a_tag_is_as_tall_as_one_line_of_its_size(self) -> None:
        theme = theme_from({"type": {"heading": 10.5, "tag": 16}})
        built = cards({"heading": "Stage 1", "tag": True}, theme=theme)
        self.assertEqual(theme.line_height(16) + 2 * theme.spacing.pad, of_kind(built, "box")[0].rect.height)
        self.assertEqual((theme.line_height(16), 0), card_text(theme, Card("Stage 1", tag=True), 10 ** 7))

    def test_a_tag_is_kept_to_one_line_at_its_own_size(self) -> None:
        """A name that fits on a line at a heading's size may not at a larger tag's: that stops the page."""
        heading, big = theme_from({"type": {"heading": 12}}), theme_from({"type": {"heading": 12, "tag": 24}})
        room = heading.width("Stage name", 12, bold=True) + 1000
        self.assertEqual((heading.line_height(12), 0), card_text(heading, Card("Stage name", tag=True), room))
        with self.assertRaises(PageFullError):
            card_text(big, Card("Stage name", tag=True), room)

    def test_the_words_of_a_card_that_is_not_a_tag_do_not_follow_the_tag(self) -> None:
        theme = theme_from({"type": {"heading": 10.5, "tag": 16}})
        built = cards({"heading": "Method"}, theme=theme)
        self.assertEqual(10.5, words_of(built, "Method").size)
        self.assertEqual(theme.line_height(10.5) + 2 * theme.spacing.pad, of_kind(built, "box")[0].rect.height)


class ATableLookIsPickedByAUse(unittest.TestCase):
    GREY = {"uses": {"grey": {"like": "read", "table_look": "plain"}}}

    def test_a_use_that_names_a_look_has_it_and_the_deck_keeps_its_own(self) -> None:
        theme = theme_from(self.GREY)
        self.assertEqual("accent", theme.table_look)
        self.assertEqual("plain", theme.using("grey").table_look)

    def test_a_use_that_says_nothing_takes_the_look_of_the_deck(self) -> None:
        for look in TABLE_LOOKS:
            theme = theme_from({"table_look": look, "uses": {"quiet": {"like": "read"}}})
            for use in ("read", "present", "sheet", "quiet"):
                with self.subTest(deck=look, use=use):
                    self.assertEqual(look, theme.using(use).table_look)

    def test_a_use_may_pick_the_look_the_deck_does_not(self) -> None:
        for deck, use in (("plain", "accent"), ("accent", "plain")):
            with self.subTest(deck=deck):
                theme = theme_from({"table_look": deck, "uses": {"said": {"like": "read", "table_look": use}}})
                self.assertEqual((use, deck), (theme.using("said").table_look, theme.using("read").table_look))
                self.assertEqual(use, theme.using("said").using("said").table_look)

    def test_a_deck_made_in_a_use_of_its_own_has_the_look_of_that_use(self) -> None:
        theme = theme_from({**self.GREY, "use": "grey"})
        self.assertEqual("plain", theme.table_look)
        self.assertEqual("accent", theme.using("read").table_look, "a page in another use goes back to the deck's look")

    def test_a_look_nobody_pictured_is_refused_with_the_key_it_was_written_under(self) -> None:
        for look in ("outlined", "filled", "", 3, True, None):
            with self.subTest(look=look), self.assertRaises(ThemeError) as refused:
                theme_from({"uses": {"said": {"like": "read", "table_look": look}}})
            self.assertIn("theme.uses.said.table_look", str(refused.exception))
            self.assertIn("'plain'", str(refused.exception))

    def test_a_deck_cannot_pick_it_under_theme_type(self) -> None:
        with self.assertRaises(ThemeError) as refused:
            theme_from({"type": {"table_look": "plain"}})
        self.assertIn("table_look", str(refused.exception))

    def test_a_use_that_is_not_the_projects_own_cannot_be_given_a_look_by_the_deck(self) -> None:
        theme = theme_from({"table_look": "plain"})
        self.assertEqual({"plain"}, {theme.using(use).table_look for use in ("read", "present", "sheet")})

    def heading_ground(self, theme, **page) -> str:
        """The ground of the heading cell of a table as it is written (= the page reads the look of its own use)."""
        built = build({"type": "board", "title": "T", "table": [["A", "B"], ["1", "2"]], **page}, theme)
        deck = new_deck(theme)
        add_page(deck, built.build(), built.theme)
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(save(deck, Path(tmp) / "t.pptx")) as archive:
                xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        first = re.findall(r"<a:tc>.*?</a:tc>", xml, re.S)[0]
        return re.findall(r'srgbClr val="(\w+)"', re.findall(r"<a:tcPr.*?</a:tcPr>", first, re.S)[0])[-1]

    def test_a_page_in_the_use_has_tables_in_that_look_and_the_next_page_in_the_decks(self) -> None:
        theme = theme_from(self.GREY)
        self.assertEqual(P.accent, self.heading_ground(theme))
        self.assertEqual(P.wash, self.heading_ground(theme, use="grey"))
        self.assertEqual(P.accent, self.heading_ground(theme, use="read"))

    def test_a_deck_whose_tables_are_plain_has_one_page_with_the_accent(self) -> None:
        theme = theme_from({"table_look": "plain", "uses": {"blue": {"like": "read", "table_look": "accent"}}})
        self.assertEqual(P.wash, self.heading_ground(theme))
        self.assertEqual(P.accent, self.heading_ground(theme, use="blue"))

    def test_a_row_that_divides_a_table_is_painted_in_the_look_of_the_use(self) -> None:
        rows = [["A", "B"], {"band": "Group", "tone": "accent"}, ["1", "2"]]
        theme = theme_from(self.GREY)
        painted = {}
        for use in ("read", "grey"):
            table = next(e for e in build({"type": "board", "title": "T", "table": rows, "use": use}, theme).build()
                         if e.kind == "table")
            painted[use] = table.bands[1]
        self.assertEqual(P.accent, painted["read"][0])
        self.assertNotEqual(P.accent, painted["grey"][0], "in the plain look the colour goes to the words")
        self.assertEqual(P.accent, painted["grey"][1])


class TheSingleWordsOfACardStandInTheMiddleOfTheirFrame(unittest.TestCase):
    ONE = ({"heading": "Stage 1", "tag": True}, {"heading": "Heading only"}, {"body": "Words only"})

    def test_the_frame_is_the_whole_inside_of_the_box_and_the_words_stand_in_its_middle(self) -> None:
        for look in (OUTLINED, OUTLINED_PAGE):
            for item in self.ONE:
                with self.subTest(item=item, boxes=look.box_height):
                    built = cards(item, {"heading": "Other", "body": "words"}, theme=look, card_columns=2)
                    box = of_kind(built, "box")[0].rect
                    words = words_of(built, item.get("heading") or item["body"])
                    self.assertTrue(words.middle)
                    self.assertEqual(box.inset(S.pad), words.rect)

    def test_a_tag_is_set_that_way_in_a_deck_of_filled_cards_too(self) -> None:
        built = cards({"heading": "Stage 1", "tag": True}, theme=DEFAULT)
        words = words_of(built, "Stage 1")
        self.assertTrue(words.middle)
        self.assertEqual(of_kind(built, "box")[0].rect.inset(S.pad), words.rect)

    def test_a_filled_card_that_is_not_a_tag_keeps_its_words_at_the_top(self) -> None:
        for item in self.ONE[1:]:
            with self.subTest(item=item):
                built = cards(item, theme=theme_from({"box_height": "page"}))
                self.assertFalse(words_of(built, item.get("heading") or item["body"]).middle)

    def test_a_card_of_a_heading_and_a_body_is_worked_out_from_the_height_of_both(self) -> None:
        built = cards({"heading": "Head", "body": "words"}, theme=OUTLINED_PAGE)
        head, body, box = words_of(built, "Head"), words_of(built, "words"), of_kind(built, "box")[0].rect
        self.assertEqual((False, False), (head.middle, body.middle))
        block = head.rect.height + S.gap_s + body.rect.height
        self.assertAlmostEqual(box.top + box.height / 2,
                               head.rect.top + TEXT_INSET_Y + block / 2, delta=2)

    def test_two_boxes_side_by_side_set_in_different_sizes_line_up_when_written(self) -> None:
        """A tag and a card of a body only, in sizes that do not halve alike: the frames missed by 0.13 mm."""
        theme = theme_from({"card_look": "outlined", "box_height": "page", "type": {"heading": 10.5, "body": 11}})
        built = cards({"heading": "Stage 1", "tag": True}, {"body": "A description"}, theme=theme, card_columns=2)
        deck = new_deck(theme)
        add_page(deck, built.build(), built.theme)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual([], near_alignment.run(save(deck, Path(tmp) / "pair.pptx"), {}))

    def test_the_frame_is_written_with_its_words_in_the_middle(self) -> None:
        built = cards({"heading": "Stage 1", "tag": True}, {"heading": "Head", "body": "words"}, theme=OUTLINED_PAGE,
                      card_columns=2)
        deck = new_deck(OUTLINED_PAGE)
        add_page(deck, built.build(), built.theme)
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(save(deck, Path(tmp) / "mid.pptx")) as archive:
                xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        shapes = re.findall(r"<p:sp>.*?</p:sp>", xml, re.S)
        anchor = {name: re.search(r'<a:bodyPr[^>]*anchor="(\w+)"', shape).group(1)
                  for name in ("Stage 1", "Head", "words") for shape in shapes if f"<a:t>{name}</a:t>" in shape}
        self.assertEqual({"Stage 1": "ctr", "Head": "t", "words": "t"}, anchor)


if __name__ == "__main__":
    unittest.main()
