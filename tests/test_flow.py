"""The flow: stages left to right, nodes under each, and how tall a node is for its words.

見張るのは 4 つ ― ノードに色の役を付けられること、段の名前と向きが頁の上で見えること、
同じ順番のノードを横に揃えられること、箱の高さが**実際に折れる行数**で決まること。
"""

from __future__ import annotations

import re
import string
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))
from support.pages import box_of, named  # noqa: E402

from pptx_agent_maker import checks  # noqa: E402
from pptx_agent_maker.layout.base import tokens  # noqa: E402
from pptx_agent_maker.layout import types  # noqa: E402
from pptx_agent_maker.layout.parts.look import LIGHT, TONES  # noqa: E402
from pptx_agent_maker.layout.parts.elements import Fill, Text  # noqa: E402
from pptx_agent_maker.layout.base.tokens import DEFAULT, Theme, Type  # noqa: E402
from pptx_agent_maker.layout.types.core.registry import PageTypeError  # noqa: E402
from pptx_agent_maker.write import add_page, new_deck, save  # noqa: E402

LONG = "a body long enough to run over several lines of a node, so this one stands taller than the rest"


def page(stages, theme: Theme = DEFAULT, **extra):
    return types.build({"type": "flow", "title": "A flow", "stages": stages, **extra},
                       lambda name: Path(name), lambda path: 1.0, theme)


def stage(name, *nodes, **more):
    return {"name": name, "nodes": list(nodes), **more}


class ATone(unittest.TestCase):
    """A node may say which of the palette's roles its ground takes."""

    def test_a_node_written_as_a_pair_keeps_the_plain_ground(self):
        built = page([stage("One", ["Collect", "from the field"]), stage("Two", ["Decide", ""])])
        self.assertEqual(DEFAULT.palette.box, box_of(built, "Collect").colour)
        self.assertEqual(DEFAULT.palette.ink, named(built, "Collect").colour)

    def test_each_tone_takes_its_colour_from_the_palette(self):
        palette = DEFAULT.palette
        for tone in TONES:
            with self.subTest(tone):
                built = page([stage("One", {"heading": "Node", "body": "why", "tone": tone}),
                              stage("Two", ["Other", ""])])
                self.assertEqual(getattr(palette, tone), box_of(built, "Node").colour)

    def test_words_on_a_dark_ground_are_set_in_the_papers_colour(self):
        for tone, ink in (("box", "ink"), ("band", "ink"), ("accent", "paper"), ("good", "paper"),
                          ("bad", "paper")):
            with self.subTest(tone):
                built = page([stage("One", {"heading": "Node", "body": "why", "tone": tone}),
                              stage("Two", ["Other", ""])])
                wanted = getattr(DEFAULT.palette, ink)
                self.assertEqual(wanted, named(built, "Node").colour)
                self.assertEqual(wanted, named(built, "why").colour)

    def test_a_node_on_a_light_ground_has_an_edge_and_one_on_a_dark_ground_has_none(self):
        """薄い地は紙と近い。棒と同じ枠を持つ (= 同じ色の役は、どの型でも同じ見た目)。"""
        palette = DEFAULT.palette
        for tone in TONES:
            with self.subTest(tone):
                built = page([stage("One", {"heading": "Node", "body": "why", "tone": tone}),
                              stage("Two", {"heading": "Other", "tone": "accent"})])
                wanted = palette.edge(getattr(palette, tone)) if tone in LIGHT else ""
                self.assertEqual(wanted, box_of(built, "Node").outline)

    def test_a_tone_changes_one_node_and_leaves_its_neighbours(self):
        built = page([stage("One", ["Plain", ""], {"heading": "Marked", "tone": "bad"}),
                      stage("Two", ["Other", ""])])
        self.assertEqual(DEFAULT.palette.box, box_of(built, "Plain").colour)
        self.assertEqual(DEFAULT.palette.bad, box_of(built, "Marked").colour)

    def test_a_tone_that_is_not_a_role_is_refused_and_lists_the_roles(self):
        with self.assertRaises(PageTypeError) as raised:
            page([stage("One", {"heading": "Node", "tone": "red"}), stage("Two", ["Other", ""])])
        for tone in TONES:
            self.assertIn(tone, str(raised.exception))

    def test_a_node_is_a_pair_or_a_table_of_keys_it_reads(self):
        for node, message in (({"heading": "Node", "colour": "red"}, "does not take colour"),
                              ({"body": "no heading"}, "has no `heading`"),
                              (["one", "two", "three"], "write it as"),
                              ("just words", "write it as")):
            with self.subTest(node=node):
                with self.assertRaises(PageTypeError) as raised:
                    page([stage("One", node), stage("Two", ["Other", ""])])
                self.assertIn(message, str(raised.exception))
                self.assertIn("stage 1, node 1", str(raised.exception))


class WhatStandsOut(unittest.TestCase):
    """The stage's name and the arrow between stages are meant to be seen."""

    BUILT = staticmethod(lambda: page([stage("Intake", ["a", "b"], ["c", "d"]),
                                       stage("Build", ["e", "f"])]))

    def test_a_stage_name_is_set_larger_than_a_caption_and_bold(self):
        name = named(self.BUILT(), "Intake")
        self.assertEqual("stage", name.kind)
        self.assertEqual(DEFAULT.type.stage, name.size)
        self.assertGreater(name.size, DEFAULT.type.caption)
        self.assertTrue(name.bold)
        self.assertEqual(DEFAULT.palette.ink, name.colour)

    def test_a_long_stage_name_takes_the_lines_it_needs(self):
        short = named(self.BUILT(), "Intake").rect.height
        long_name = "the stage where every request is read sorted and handed to one person"
        built = page([stage(long_name, ["a", "b"]), stage("Build", ["e", "f"])])
        self.assertGreater(named(built, long_name).rect.height, short)
        self.assertGreaterEqual(named(built, "a").rect.top, named(built, long_name).rect.bottom)

    def test_the_arrow_is_dark_bold_and_larger_than_a_heading(self):
        arrow = named(self.BUILT(), "→")
        self.assertEqual(DEFAULT.type.marker, arrow.size)
        self.assertGreater(arrow.size, DEFAULT.type.heading)
        self.assertTrue(arrow.bold)
        self.assertEqual(DEFAULT.palette.ink, arrow.colour)

    def test_the_arrow_stands_beside_the_nodes_not_beside_the_stage_names(self):
        built = self.BUILT()
        arrow = named(built, "→").rect
        first, last = box_of(built, "a").rect, box_of(built, "c").rect
        self.assertEqual(arrow.top, first.top)
        self.assertEqual(arrow.bottom, last.bottom)
        self.assertGreaterEqual(arrow.top, named(built, "Intake").rect.bottom)


class TheSizeOfTheWords(unittest.TestCase):
    """What a flow says is the page's content, set at the body size; the footnote size is not for it."""

    BUILT = staticmethod(lambda: page([stage("Intake", ["Triage", "sort by impact"], settled="one queue"),
                                       stage("Build", ["Code", "small steps"])]))

    def test_a_nodes_body_is_set_at_the_body_size(self):
        self.assertEqual(DEFAULT.type.body, named(self.BUILT(), "sort by impact").size)
        self.assertGreater(DEFAULT.type.body, DEFAULT.type.caption)

    def test_what_is_settled_under_a_stage_is_set_at_the_body_size_too(self):
        settled = named(self.BUILT(), "one queue")
        self.assertEqual(("note", DEFAULT.type.body), (settled.kind, settled.size))

    def test_nothing_on_the_page_is_set_at_the_footnote_size(self):
        sizes = {e.size for e in self.BUILT().build() if isinstance(e, Text)}
        self.assertGreaterEqual(min(sizes), DEFAULT.type.body)

    def test_a_long_line_under_a_stage_takes_the_height_it_needs(self):
        long_line = "what is settled here runs on for long enough that it cannot stay on a single line of the column"
        built = page([stage("Intake", ["Triage", "sort"], settled=long_line), stage("Build", ["Code", "x"])])
        self.assertGreater(named(built, long_line).rect.height, named(self.BUILT(), "one queue").rect.height)


class RowsAcrossStages(unittest.TestCase):
    """`align_rows` lines the nth node of every stage up, for pages where a row means something."""

    STAGES = [stage("Now", ["Core", "short"], ["Apps", LONG], ["Partners", "short"]),
              stage("Next", ["Core", LONG], ["Apps", "short"])]

    def boxes(self, built, heading):
        return sorted((e.rect for e in built.build() if isinstance(e, Fill) and e.kind == "box"
                       and any(isinstance(t, Text) and t.text == heading and e.rect.contains(t.rect)
                               for t in built.build())), key=lambda r: r.left)

    def test_without_it_each_stage_stacks_by_its_own_words(self):
        built = page(self.STAGES)
        left, right = self.boxes(built, "Apps")
        self.assertNotEqual(left.top, right.top)
        self.assertNotEqual(left.height, right.height)

    def test_with_it_the_same_row_shares_its_top_and_its_height(self):
        built = page(self.STAGES, align_rows=True)
        for heading in ("Core", "Apps"):
            with self.subTest(heading):
                left, right = self.boxes(built, heading)
                self.assertEqual(left.top, right.top)
                self.assertEqual(left.height, right.height)

    def test_a_row_is_as_tall_as_its_tallest_node_and_no_taller(self):
        aligned = page(self.STAGES, align_rows=True)
        loose = page(self.STAGES)
        tallest = max(r.height for r in self.boxes(loose, "Core"))
        self.assertEqual(tallest, self.boxes(aligned, "Core")[0].height)

    def test_a_stage_with_fewer_nodes_leaves_the_row_empty(self):
        built = page(self.STAGES, align_rows=True)
        self.assertEqual(1, len(self.boxes(built, "Partners")))

    def test_it_is_true_or_false(self):
        with self.assertRaises(PageTypeError) as raised:
            page(self.STAGES, align_rows="yes")
        self.assertIn("true or false", str(raised.exception))

    def test_only_the_flow_reads_it(self):
        with self.assertRaises(PageTypeError) as raised:
            types.build({"type": "figure", "title": "t", "figure": "a.png", "align_rows": True},
                        lambda name: Path(name), lambda path: 1.0)
        self.assertIn("does not take align_rows", str(raised.exception))


class TheHeightOfANode(unittest.TestCase):
    """A box is as tall as its words actually run, not as tall as a cautious count says."""

    def height(self, heading, body="why", theme: Theme = DEFAULT):
        built = page([stage("One", [heading, body]), stage("Two", ["x", "y"]),
                      stage("Three", ["x", "y"])], theme)
        return box_of(built, heading).rect.height

    def test_a_heading_of_letters_digits_and_signs_that_fits_takes_one_line(self):
        """全角 1 文字ぶんで数えていた間は 2 行と数えられ、箱の中に 1 行ぶんの空白ができた。"""
        self.assertEqual(self.height("Code"), self.height("Code + tests (CI v2)"))

    def test_a_heading_that_does_not_fit_still_takes_two(self):
        self.assertGreater(self.height("Triage of every request by impact and by owner"),
                           self.height("Code"))

    def test_full_width_text_is_counted_at_full_width(self):
        self.assertEqual(self.height("確認"), self.height("設計の確認をする"))
        self.assertGreater(self.height("設計の確認をして、結果を全員に知らせる段"), self.height("確認"))

    def test_a_body_is_counted_the_same_way(self):
        self.assertEqual(self.height("Code", "why"),
                         self.height("Code", "two readers, one page (v2)"))
        self.assertGreater(self.height("Code", LONG), self.height("Code", "why"))

    def test_a_narrower_typeface_needs_no_more_room_than_a_wide_one(self):
        arial = Theme(type=Type(family="Arial"))
        heading = "Triage (P1/P2) by impact"
        self.assertLess(self.height(heading, theme=arial), self.height(heading))

    def test_the_box_and_the_words_inside_it_agree_on_the_headings_height(self):
        """箱の高さを出す側と、見出しの枠を取る側が別々に数えると、本文が見出しに乗る。"""
        for heading in ("Code + tests (CI v2)", "Triage of every request by impact and by owner"):
            with self.subTest(heading):
                built = page([stage("One", [heading, "why"]), stage("Two", ["x", "y"]),
                              stage("Three", ["x", "y"])])
                box, head, body = box_of(built, heading).rect, named(built, heading).rect, \
                    named(built, "why").rect
                self.assertGreaterEqual(body.top, head.bottom)
                self.assertLessEqual(body.bottom, box.bottom)
                self.assertGreaterEqual(body.height, DEFAULT.line_height(DEFAULT.type.body),
                                        "the heading took the room the body was counted to have")


class HowALineBreaks(unittest.TestCase):
    """`wraps` breaks where a text box breaks: at spaces, and between full-width characters."""

    EM = tokens.pt(10)

    def test_words_are_kept_whole(self):
        self.assertEqual(1, DEFAULT.wraps("aaaa bbbb", self.EM * 8, 10))
        self.assertEqual(2, DEFAULT.wraps("aaaa bbbb", self.EM * 4, 10))
        self.assertEqual(3, DEFAULT.wraps("aaaa bbbb cccc", self.EM * 4, 10))
        # 文字の途中で折れば 2 行に収まる長さ。語を割らないので 3 行になる
        self.assertEqual(3, DEFAULT.wraps("nnni nnni nnni", self.EM * 4, 10))

    def test_a_word_longer_than_the_line_breaks_inside_itself(self):
        self.assertGreaterEqual(DEFAULT.wraps("m" * 30, self.EM * 10, 10), 3)

    def test_full_width_characters_break_anywhere(self):
        self.assertEqual(2, DEFAULT.wraps("全" * 15, self.EM * 10, 10))
        self.assertEqual(1, DEFAULT.wraps("全" * 10, self.EM * 10, 10))

    def test_each_paragraph_starts_a_line(self):
        self.assertEqual(3, DEFAULT.wraps("a\nb\nc", self.EM * 10, 10))

    def test_nothing_takes_one_line(self):
        self.assertEqual(1, DEFAULT.wraps("", self.EM * 10, 10))

    def test_bold_can_tip_a_line_over(self):
        text = "nnnnnnnnnnnnnnn"
        width = DEFAULT.width(text, 10)
        self.assertEqual(1, DEFAULT.wraps(text, width, 10))
        self.assertEqual(2, DEFAULT.wraps(text, width, 10, bold=True))

    def test_the_longest_unbreakable_run_is_a_word_or_one_full_width_character(self):
        self.assertEqual(DEFAULT.width("longest", 10), DEFAULT.unbreakable("a longest word", 10))
        self.assertEqual(self.EM, DEFAULT.unbreakable("全角の文", 10))


class TheWidthOfACharacter(unittest.TestCase):
    """Widths come from the typefaces themselves (= `scripts/generate/measure-advance.py`)."""

    ASCII = string.ascii_letters + string.digits + " " + string.punctuation

    def test_every_printable_ascii_character_was_measured_in_every_table(self):
        for group, table in tokens._ADVANCE_OF.items():
            with self.subTest(group):
                self.assertEqual([], [c for c in self.ASCII if c not in table])

    def test_no_character_is_in_a_table_twice(self):
        for group, table in tokens._ADVANCE.items():
            with self.subTest(group):
                listed = "".join(table.values())
                self.assertEqual(len(listed), len(set(listed)))

    def test_characters_differ_by_a_factor_of_three(self):
        self.assertGreater(tokens.advance("m"), 3 * tokens.advance("i"))
        self.assertEqual(1.0, tokens.advance("全"))

    def test_a_typeface_nobody_measured_takes_the_wide_table(self):
        for character in "aMi 0(":
            self.assertEqual(tokens.advance(character), tokens.advance(character, family="Unknown Sans"))

    def test_arial_and_helvetica_share_a_narrower_table(self):
        text = "The quick brown fox, 0123456789"
        wide = sum(tokens.advance(c) for c in text)
        arial = sum(tokens.advance(c, family="Arial") for c in text)
        self.assertLess(arial, wide)
        self.assertEqual(arial, sum(tokens.advance(c, family="Helvetica Neue") for c in text))
        self.assertEqual(arial, sum(tokens.advance(c, family="arial") for c in text))

    def test_the_wide_table_is_never_narrower_than_what_the_overlap_check_assumes(self):
        """検査は半角を 0.5 文字ぶんと見る。平均でそれより狭く数えると、収まると言った物が検査で重なる。"""
        text = string.ascii_lowercase
        self.assertGreater(sum(tokens.advance(c) for c in text) / len(text), 0.5)


class OnceBaked(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        built = page([stage("Intake", {"heading": "Marked", "body": "why", "tone": "bad"}),
                      stage("Build", ["Plain", "how"])], align_rows=True)
        deck = new_deck()
        add_page(deck, built.build())
        cls.deck = save(deck, Path(cls.tmp.name) / "flow.pptx")
        with zipfile.ZipFile(cls.deck) as archive:
            xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        cls.shapes = re.findall(r"<p:sp>.*?</p:sp>", xml, re.S)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def shape(self, text):
        return next(s for s in self.shapes if f">{text}<" in s)

    def test_the_arrow_is_one_unwrapped_character_centred_in_its_column(self):
        arrow = self.shape("→")
        self.assertIn('wrap="none"', arrow)
        self.assertNotIn("spAutoFit", arrow)
        self.assertIn('anchor="ctr"', arrow)
        self.assertIn('lIns="0"', arrow)
        self.assertIn('sz="2800"', arrow)

    def test_the_stage_name_is_bold_at_its_own_size(self):
        self.assertRegex(self.shape("Intake"), r'sz="1400" b="1"')

    def test_words_on_a_dark_ground_are_written_in_the_papers_colour(self):
        self.assertIn(f'val="{DEFAULT.palette.paper}"', self.shape("Marked"))
        self.assertIn(f'val="{DEFAULT.palette.ink}"', self.shape("Plain"))

    def box(self, colour):
        """The shape painted in that colour (= a node's ground carries no words of its own)."""
        return next(s for s in self.shapes
                    if f'<a:srgbClr val="{colour}"/>' in s.split("<a:ln")[0])

    def test_a_light_node_is_written_with_a_solid_edge_and_a_dark_one_with_none(self):
        palette = DEFAULT.palette
        self.assertRegex(self.box(palette.box),
                         rf'<a:ln w="{DEFAULT.spacing.hairline}">\s*<a:solidFill>\s*'
                         rf'<a:srgbClr val="{palette.edge(palette.box)}"/>')
        self.assertRegex(self.box(palette.bad), r"<a:ln[^>]*>\s*<a:noFill/>")

    def test_the_checks_find_nothing(self):
        self.assertEqual([], checks.run_all(self.deck))


if __name__ == "__main__":
    unittest.main()
