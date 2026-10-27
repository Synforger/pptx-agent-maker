"""What a tentative box, bar or arrowhead is painted in: grey, or the colour of its tone (= `[theme] tentative_look`).

⚠ 見張るのは 3 つ ― 書かなければ今までの灰の点線のままであること、`toned` なら点線のまま枠と字が色の役の色に
なること (= 読めない色の役は本文の色に倒れ、明暗差の検査は緩まない)、`card_look = "outlined"` の資料では
枠と見出しだけが色になること。
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))
from support.pages import named  # noqa: E402

from pptx_agent_maker import checks  # noqa: E402
from pptx_agent_maker.layout import types  # noqa: E402
from pptx_agent_maker.layout.parts.elements import Bar, Fill  # noqa: E402
from pptx_agent_maker.layout.parts.look import Style  # noqa: E402
from pptx_agent_maker.layout.parts.page import Page  # noqa: E402
from pptx_agent_maker.layout.tokens import (DEFAULT, TENTATIVE_LOOKS, ThemeError, contrast,  # noqa: E402
                                            reading_floor, theme_from)
from pptx_agent_maker.write import add_page, aspect, new_deck, save  # noqa: E402

DATA = REPO / "tests" / "data"
GROUNDS = {"Inside": "EAF0F8", "Deep": "1F3A5F", "Yellow": "FFE066"}
MUTED = theme_from({"grounds": GROUNDS})
TONED = theme_from({"grounds": GROUNDS, "tentative_look": "toned"})
TONED_OUTLINED = theme_from({"grounds": GROUNDS, "tentative_look": "toned", "card_look": "outlined",
                             "bar_look": "outlined"})
P = DEFAULT.palette
#: 色を運ぶ役 (= 名前, 枠と字の色)。`Deep` は案件が名前を付けた濃い地
CARRYING = (("accent", P.accent), ("good", P.good), ("bad", P.bad), ("Deep", "1F3A5F"))
#: 色を運ばない役。薄い地と、本文の色の字が読める明るい地
PALE = ("box", "band", "tint", "Inside", "Yellow")


def build(spec, theme):
    return types.build({"title": "A page", **spec}, lambda name: DATA / name, aspect, theme)


def shape_of(built, text):
    found = named(built, text)
    if isinstance(found, Bar):
        return found
    return next(e for e in built.build() if e.kind == "box" and e.rect.contains(found.rect))


def card(theme, look):
    return build({"type": "cards", "cards": [{"heading": "It", "tentative": True, **look}]}, theme)


def node(theme, look):
    return build({"type": "flow", "stages": [{"name": "A", "nodes": [{"heading": "It", "tentative": True, **look}]},
                                             {"name": "B", "nodes": [["Other", ""]]}]}, theme)


def bar(theme, look):
    return build({"type": "timeline", "periods": ["a", "b", "c"],
                  "lanes": [{"name": "L", "bars": [{"from": 0, "to": 3, "text": "It", "tentative": True, **look}]}]},
                 theme)


def stage(theme, look):
    return build({"type": "roadmap", "stages": [{"name": "It", "nodes": [["n", ""]], "tentative": True, **look},
                                                {"name": "Next", "nodes": [["m", ""]]}]}, theme)


PARTS = {"card": card, "flow node": node, "timeline bar": bar, "roadmap stage": stage}


class WhereTheProjectSaysIt(unittest.TestCase):
    def test_left_unsaid_it_is_the_grey_it_always_was(self):
        self.assertEqual("muted", DEFAULT.tentative_look)
        self.assertEqual("muted", theme_from({"font": "Meiryo"}).tentative_look)
        self.assertEqual(("muted", "toned"), TENTATIVE_LOOKS)

    def test_toned_is_read_from_the_theme(self):
        self.assertEqual("toned", TONED.tentative_look)

    def test_a_look_nobody_knows_is_refused(self):
        with self.assertRaises(ThemeError) as refused:
            theme_from({"tentative_look": "tinted"})
        self.assertIn("tentative_look", str(refused.exception))


class GreyUnlessAskedOtherwise(unittest.TestCase):
    def test_a_tentative_part_with_a_tone_is_grey_and_dashed(self):
        for name, part in PARTS.items():
            for tone, _colour in CARRYING:
                with self.subTest(name, tone=tone):
                    built = part(MUTED, {"tone": tone})
                    shape = shape_of(built, "It")
                    self.assertEqual((P.paper, P.muted, True), (shape.fill if isinstance(shape, Bar) else shape.colour,
                                                                shape.outline, shape.dashed))
                    self.assertEqual(P.muted, named(built, "It").colour)


class ColouredByItsTone(unittest.TestCase):
    """A tentative part keeps the meaning of its colour: a dotted line and its words in the colour of the tone."""

    def test_the_line_and_the_words_take_the_colour_of_the_tone_and_the_ground_is_the_paper(self):
        for name, part in PARTS.items():
            for tone, colour in CARRYING:
                with self.subTest(name, tone=tone):
                    built = part(TONED, {"tone": tone})
                    shape = shape_of(built, "It")
                    self.assertEqual((P.paper, colour, True), (shape.fill if isinstance(shape, Bar) else shape.colour,
                                                               shape.outline, shape.dashed))
                    self.assertEqual(colour, named(built, "It").colour)

    def test_a_tone_that_carries_no_colour_falls_to_the_ink_as_it_does_everywhere(self):
        for name, part in PARTS.items():
            for tone in PALE:
                with self.subTest(name, tone=tone):
                    built = part(TONED, {"tone": tone})
                    shape = shape_of(built, "It")
                    self.assertEqual((P.ink, True), (shape.outline, shape.dashed))
                    self.assertEqual(P.ink, named(built, "It").colour)

    def test_a_strong_one_is_a_heavy_dotted_line_in_the_colour(self):
        for name, part in PARTS.items():
            with self.subTest(name):
                shape = shape_of(part(TONED, {"tone": "accent", "strong": True}), "It")
                self.assertEqual((P.accent, True, True), (shape.outline, shape.dashed, shape.heavy))

    def test_the_ground_stays_the_paper_and_the_words_reach_the_floor_the_checks_hold_them_to(self):
        page = Page("t", TONED)
        for tone in [tone for tone, _colour in CARRYING] + list(PALE):
            with self.subTest(tone=tone):
                look = page.look(Style(tone=tone, tentative=True), DEFAULT.type.body)
                self.assertEqual(P.paper, look.fill)
                self.assertEqual(look.ink, look.outline)
                self.assertGreaterEqual(contrast(look.ink, P.paper), reading_floor(DEFAULT.type.body))


class InADeckOfOutlinedCards(unittest.TestCase):
    def test_a_tentative_card_is_a_dotted_line_in_the_colour_with_its_heading_in_it(self):
        built = card(TONED_OUTLINED, {"tone": "accent"})
        box = shape_of(built, "It")
        self.assertEqual((P.paper, P.accent, True), (box.colour, box.outline, box.dashed))
        self.assertEqual(P.accent, named(built, "It").colour)

    def test_a_tentative_bar_keeps_the_words_in_the_ink_as_a_bar_of_this_look_does(self):
        built = bar(TONED_OUTLINED, {"tone": "accent"})
        drawn = named(built, "It")
        self.assertEqual((P.paper, P.accent, True, P.ink), (drawn.fill, drawn.outline, drawn.dashed, drawn.colour))

    def test_a_tone_without_colour_is_the_ink(self):
        box = shape_of(card(TONED_OUTLINED, {"tone": "tint"}), "It")
        self.assertEqual((P.ink, True), (box.outline, box.dashed))

    def test_left_to_grey_the_card_is_drawn_in_ink_and_not_dashed(self):
        outlined = theme_from({"grounds": GROUNDS, "card_look": "outlined"})
        box = shape_of(card(outlined, {"tone": "accent"}), "It")
        self.assertEqual((P.paper, P.ink, False), (box.colour, box.outline, box.dashed))


class OnceBaked(unittest.TestCase):
    def test_the_checks_find_nothing(self):
        for theme in (TONED, TONED_OUTLINED):
            built = build({"type": "compose", "rows": [
                {"cells": [{"card": {"heading": "Open", "body": "not yet", "tentative": True, "tone": tone}}
                           for tone, _colour in CARRYING]},
                {"weight": 1, "cells": [{"timeline": {"periods": ["a", "b"], "lanes": [{"name": "L", "bars": [
                    {"from": 0, "to": 1, "text": "Maybe", "tentative": True, "tone": tone}
                    for tone in ("accent", "Yellow")] + [{"from": 1, "to": 2, "text": "Surely"}]}]}}]}]},
                theme)
            with tempfile.TemporaryDirectory() as tmp:
                deck = new_deck(theme)
                add_page(deck, built.build(), theme)
                path = save(deck, Path(tmp) / "tentative.pptx")
                with self.subTest(card_look=theme.card_look):
                    self.assertEqual([], checks.run_all(path))


if __name__ == "__main__":
    unittest.main()
