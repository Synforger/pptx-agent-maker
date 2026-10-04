"""One set of looks for everything shaped like a box: a tone, an icon, a dashed line, a strong edge.

**属性を部品ごとに 1 つずつ足していた間は、同じ問い (= 箱に何を持たせられるか) に部品の数だけ
答えていた。**ここで見張るのは、カード・ノード・線表の棒・道のりの段の全部が、同じ 4 つのキーを
同じ意味で読むこと ― 1 つでも欠けた部品が出れば、表のマスがまた 1 つずつ埋まり始める。
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

from pptx_agent_maker import checks  # noqa: E402
from pptx_agent_maker.layout import types  # noqa: E402
from pptx_agent_maker.layout.parts.elements import Bar, Figure, Fill, Text  # noqa: E402
from pptx_agent_maker.layout.parts.page import PageFullError  # noqa: E402
from pptx_agent_maker.layout.base.tokens import DEFAULT, theme_from  # noqa: E402
from pptx_agent_maker.layout.types.core.read import LOOK_KEYS  # noqa: E402
from pptx_agent_maker.layout.types.core.registry import PageTypeError  # noqa: E402
from pptx_agent_maker.write import add_page, aspect, new_deck, save  # noqa: E402

DATA = REPO / "tests" / "data"
SQUARE = "dot.png"
THEME = theme_from({"grounds": {"Inside": "EAF0F8"}})
P, S = DEFAULT.palette, DEFAULT.spacing


def build(spec):
    return types.build({"title": "A page", **spec}, lambda name: DATA / name, aspect, THEME)


def named(built, text):
    return next(e for e in built.build() if getattr(e, "text", None) == text)


def shape_of(built, text):
    """The painted shape a name belongs to: the bar itself, or the box its heading sits in."""
    found = named(built, text)
    if isinstance(found, Bar):
        return found
    return next(e for e in built.build() if e.kind == "box" and e.rect.contains(found.rect))


# 箱の形をした部品の全部 (= 名前, 見た目のキーを渡すと 1 頁を組む関数)
def card(look):
    return build({"type": "cards", "cards": [{"heading": "It", **look}]})


def node(look):
    return build({"type": "flow", "stages": [{"name": "A", "nodes": [{"heading": "It", **look}]},
                                             {"name": "B", "nodes": [["Other", ""]]}]})


def cell(look):
    return build({"type": "compose", "rows": [{"cells": [{"card": {"heading": "It", **look}}]}]})


def bar(look):
    return build({"type": "timeline", "periods": ["a", "b", "c"],
                  "lanes": [{"name": "L", "bars": [{"from": 0, "to": 3, "text": "It", **look}]}]})


def spanning(look):
    return build({"type": "timeline", "periods": ["a", "b", "c"],
                  "lanes": [{"name": "L", "bars": [{"from": 0, "to": 3, "text": "It", "spans": 2, **look}]},
                            {"name": "M"}]})


def stage(look):
    return build({"type": "roadmap", "stages": [{"name": "It", "nodes": [["n", ""]], **look},
                                                {"name": "Next", "nodes": [["m", ""]]}]})


def notched(look):
    """A stage after the first: its arrowhead is notched on the left."""
    return build({"type": "roadmap", "stages": [{"name": "First", "nodes": [["n", ""]]},
                                                {"name": "It", "nodes": [["m", ""]], **look}]})


PARTS = {"card": card, "flow node": node, "card in a cell": cell, "timeline bar": bar,
         "spanning bar": spanning, "first roadmap stage": stage, "later roadmap stage": notched}


def outline_of(shape):
    return shape.outline


def fill_of(shape):
    return shape.fill if isinstance(shape, Bar) else shape.colour


class EveryPartReadsEveryLook(unittest.TestCase):
    """The same four keys, the same meaning, on every part shaped like a box."""

    def test_a_tone_paints_the_ground(self):
        for name, part in PARTS.items():
            for tone, wanted in (("Inside", "EAF0F8"), ("tint", P.tint), ("bad", P.bad)):
                with self.subTest(name, tone=tone):
                    self.assertEqual(wanted, fill_of(shape_of(part({"tone": tone}), "It")))

    def test_tentative_is_a_grey_dashed_line_on_paper(self):
        for name, part in PARTS.items():
            with self.subTest(name):
                built = part({"tentative": True, "tone": "Inside"})
                shape = shape_of(built, "It")
                self.assertEqual((P.paper, P.muted, True), (fill_of(shape), outline_of(shape), shape.dashed))
                self.assertEqual(P.muted, named(built, "It").colour)

    def test_strong_is_a_heavy_edge_in_the_ink_and_keeps_the_ground(self):
        for name, part in PARTS.items():
            with self.subTest(name):
                shape = shape_of(part({"strong": True, "tone": "tint"}), "It")
                self.assertEqual((P.tint, P.ink, True), (fill_of(shape), outline_of(shape), shape.heavy))

    def test_tentative_and_strong_together_are_a_heavy_grey_dashed_line(self):
        for name, part in PARTS.items():
            with self.subTest(name):
                shape = shape_of(part({"strong": True, "tentative": True}), "It")
                self.assertEqual((P.muted, True, True), (outline_of(shape), shape.dashed, shape.heavy))

    def test_unsaid_nothing_is_dashed_or_heavy(self):
        for name, part in PARTS.items():
            with self.subTest(name):
                shape = shape_of(part({}), "It")
                self.assertEqual((False, False), (shape.dashed, shape.heavy))

    def test_an_icon_sits_inside_the_part_before_its_name(self):
        for name, part in PARTS.items():
            with self.subTest(name):
                built = part({"icon": SQUARE})
                icon = next(e for e in built.build() if isinstance(e, Figure))
                shape = shape_of(built, "It")
                self.assertTrue(shape.rect.contains(icon.rect))
                if isinstance(shape, Bar):
                    self.assertEqual(icon.rect.right + S.gap_s - shape.rect.left - S.bar_pad_x
                                     - (S.chevron_point if shape.shape == "chevron" else 0), shape.lead)

    def test_each_flag_is_true_or_false(self):
        for name, part in PARTS.items():
            for key in ("tentative", "strong"):
                with self.subTest(name, key=key), self.assertRaises(PageTypeError) as raised:
                    part({key: "yes"})
                self.assertIn(f"`{key}` is true or false", str(raised.exception))

    def test_the_four_keys_are_the_same_four_everywhere(self):
        self.assertEqual(("tone", "icon", "tentative", "strong"), LOOK_KEYS)


class OnABar(unittest.TestCase):

    def lanes(self, *bars, tone="Inside"):
        return build({"type": "timeline", "periods": ["a", "b", "c", "d"],
                      "lanes": [{"name": "L", "tone": tone, "bars": list(bars)}]})

    def test_a_bar_takes_its_lanes_tone_unless_it_names_its_own(self):
        built = self.lanes({"from": 0, "to": 2, "text": "lanes"}, {"from": 2, "to": 4, "text": "own", "tone": "bad"})
        self.assertEqual("EAF0F8", named(built, "lanes").fill)
        self.assertEqual(P.bad, named(built, "own").fill)

    def test_a_named_tone_on_a_bar_brings_the_legend(self):
        built = build({"type": "timeline", "periods": ["a", "b"],
                       "lanes": [{"name": "L", "bars": [{"from": 0, "to": 2, "text": "x", "tone": "Inside"}]}]})
        self.assertIn("Inside", [e.text for e in built.build() if e.kind == "label"])

    def test_a_name_that_fits_alone_may_go_beside_once_an_icon_takes_its_room(self):
        size, line = DEFAULT.type.plan[0], DEFAULT.line_height(DEFAULT.type.plan[0])
        # 前提: アイコン無しでは中に 1 行で収まり、アイコンのぶん狭いと収まらない名前を選ぶ
        built = self.lanes({"from": 0, "to": 1, "text": "x"})
        inner = named(built, "x").rect.width - 2 * S.bar_pad_x
        text = "w"
        while DEFAULT.width(text + "w", size) <= inner:
            text += "w"
        self.assertGreater(DEFAULT.width(text, size), inner - line - S.gap_s)
        plain = self.lanes({"from": 0, "to": 1, "text": text})
        iconic = self.lanes({"from": 0, "to": 1, "text": text, "icon": SQUARE})
        self.assertIsInstance(named(plain, text), Bar)
        self.assertNotIsInstance(named(iconic, text), Bar)

    def test_a_bar_too_short_for_its_icon_stops_the_page(self):
        with self.assertRaises(PageFullError) as raised:
            build({"type": "timeline", "periods": [str(n) for n in range(12)],
                   "lanes": [{"name": "L", "bars": [{"from": 0, "to": 0.1, "text": "x", "icon": SQUARE}]}]})
        self.assertIn("too short for its icon", str(raised.exception))


class OnAStage(unittest.TestCase):

    def test_the_goal_stays_dark_unless_it_names_a_tone(self):
        goal = build({"type": "roadmap", "stages": [{"name": "A", "nodes": [["n", ""]]},
                                                    {"name": "B", "nodes": [["m", ""]], "goal": True}]})
        toned = build({"type": "roadmap", "stages": [{"name": "A", "nodes": [["n", ""]]},
                                                     {"name": "B", "nodes": [["m", ""]], "goal": True, "tone": "good"}]})
        self.assertEqual(P.accent, named(goal, "B").fill)
        self.assertEqual(P.good, named(toned, "B").fill)

    def test_an_icon_leaves_the_name_less_room(self):
        def road(name, **look):
            return build({"type": "roadmap", "stages": [{"name": name, "nodes": [["n", ""]], **look},
                                                        {"name": "B", "nodes": [["m", ""]]},
                                                        {"name": "C", "nodes": [["o", ""]]}]})
        size, line = DEFAULT.type.stage, DEFAULT.line_height(DEFAULT.type.stage)
        room = named(road("x"), "x").rect.width - S.chevron_point // 2 - 2 * S.bar_pad_x
        # 前提: アイコンのぶん狭い幅で 1 行多く折れる名前を、語を 1 つずつ足して探す
        text = "word"
        while (DEFAULT.wraps(text, room - line - S.gap_s, size, bold=True)
               == DEFAULT.wraps(text, room, size, bold=True)):
            text += " word"
        self.assertGreater(named(road(text, icon=SQUARE), text).rect.height, named(road(text), text).rect.height)


class OnceBaked(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        built = build({"type": "compose", "rows": [
            {"cells": [{"card": {"heading": "Dashed card", "tentative": True}},
                       {"card": {"heading": "Strong card", "strong": True}}]},
            {"weight": 1, "cells": [{"timeline": {"periods": ["a", "b"], "lanes": [
                {"name": "L", "bars": [{"from": 0, "to": 1, "text": "Strong bar", "strong": True},
                                       {"from": 1, "to": 2, "text": "Icon bar", "icon": SQUARE}]}]}}]}]})
        deck = new_deck(THEME)
        add_page(deck, built.build(), THEME)
        cls.deck = save(deck, Path(cls.tmp.name) / "look.pptx")
        with zipfile.ZipFile(cls.deck) as archive:
            cls.xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        cls.shapes = re.findall(r"<p:sp>.*?</p:sp>", cls.xml, re.S)
        cls.built = built

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def shape(self, text):
        return next(s for s in self.shapes if f">{text}<" in s)

    def painted(self, heading):
        """The filled box a card's heading sits in, as written to the file."""
        box = shape_of(self.built, heading).rect
        return next(s for s in self.shapes
                    if f'<a:off x="{box.left}" y="{box.top}"/>' in s and "<a:solidFill>" in s.split("<p:txBody>")[0])

    def test_a_strong_shape_is_written_with_the_heavy_line(self):
        for written in (self.shape("Strong bar"), self.painted("Strong card")):
            self.assertRegex(written, rf'<a:ln w="{S.strong_line}">')

    def test_a_dashed_card_is_written_dashed(self):
        self.assertIn('<a:prstDash val="dash"/>', self.painted("Dashed card"))

    def test_the_words_of_a_bar_with_an_icon_start_after_it(self):
        lead = named(self.built, "Icon bar").lead
        self.assertGreater(lead, 0)
        self.assertIn(f'lIns="{S.bar_pad_x + lead}"', self.shape("Icon bar"))

    def test_the_checks_find_nothing(self):
        self.assertEqual([], checks.run_all(self.deck))


if __name__ == "__main__":
    unittest.main()
