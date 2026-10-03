"""Grounds a project names for what they mean, and the legend that says so.

見張るのは 4 つ ― 名前を付けた地を、箱・棒・レーンのどこでも `tone` として書けること、地の上の字が
読める方の色になること、その地を使った頁には凡例が宣言の順で出ること、道具の色の役と名前が
ぶつからないこと。
"""

from __future__ import annotations

import io
import shutil
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from test_deck import a_specimen, make_dot  # noqa: E402

from pptx_agent_maker import checks  # noqa: E402
from pptx_agent_maker.__main__ import main  # noqa: E402
from pptx_agent_maker.deck.build import build as build_deck  # noqa: E402
from pptx_agent_maker.layout import types  # noqa: E402
from pptx_agent_maker.layout.page import TONES, Fill, PageFullError, Table, Text  # noqa: E402
from pptx_agent_maker.layout.tokens import DEFAULT, ThemeError, contrast, theme_from  # noqa: E402
from pptx_agent_maker.layout.types import PageTypeError  # noqa: E402
from pptx_agent_maker.project import Workspace, create  # noqa: E402
from pptx_agent_maker.project.manifest import Manifest  # noqa: E402
from pptx_agent_maker.write import add_page, aspect, new_deck, save  # noqa: E402

GROUNDS = {"Inside": "eaf0f8", "Outside": "FFF4E5", "Shared": "E8F3EA", "At risk": "8B1E3F"}
THEME = theme_from({"grounds": GROUNDS})


def build(spec, theme=THEME):
    return types.build({"title": "A page", **spec}, lambda name: Path(name), lambda path: 1.0, theme)


def cards(*tones, **extra):
    return build({"type": "cards", "cards": [{"heading": f"Card {n}", "tone": tone}
                                             for n, tone in enumerate(tones, start=1)], **extra})


def named(built, text):
    return next(e for e in built.build() if getattr(e, "text", None) == text)


def box_of(built, heading):
    head = named(built, heading).rect
    return next(e for e in built.build() if e.kind == "box" and e.rect.contains(head))


def legend(built):
    """The names the legend lists, left to right and line by line."""
    labels = [e for e in built.build() if e.kind == "label"]
    return [e.text for e in sorted(labels, key=lambda e: (e.rect.top, e.rect.left))]


class Declaring(unittest.TestCase):
    """`[theme.grounds]` names a colour for what it means."""

    def test_they_are_read_in_the_order_written(self):
        self.assertEqual(("Inside", "Outside", "Shared", "At risk"), THEME.ground_names())
        self.assertEqual("EAF0F8", dict(THEME.grounds)["Inside"])

    def test_nothing_declared_names_nothing(self):
        self.assertEqual((), DEFAULT.ground_names())

    def test_a_name_the_palette_already_has_is_refused(self):
        for role in TONES:
            with self.subTest(role), self.assertRaises(ThemeError) as raised:
                theme_from({"grounds": {role: "EAF0F8"}})
            self.assertIn("[theme.palette]", str(raised.exception))

    def test_a_colour_is_six_hex_digits(self):
        for value in ("#EAF0F8", "blue", "EAF0F"):
            with self.subTest(value), self.assertRaises(ThemeError):
                theme_from({"grounds": {"Inside": value}})

    def test_they_are_a_table(self):
        with self.assertRaises(ThemeError):
            theme_from({"grounds": ["Inside", "EAF0F8"]})


class WordsOnThem(unittest.TestCase):
    """Words on a named ground take whichever of ink and paper reads better; light grounds take an edge."""

    def test_the_contrast_runs_from_one_to_twenty_one(self):
        self.assertAlmostEqual(21.0, contrast("FFFFFF", "000000"), places=3)
        self.assertAlmostEqual(1.0, contrast("8B1E3F", "8B1E3F"), places=3)

    def test_a_light_ground_takes_ink_and_an_edge(self):
        built = cards("Inside")
        box, words = box_of(built, "Card 1"), named(built, "Card 1")
        self.assertEqual("EAF0F8", box.colour)
        self.assertEqual(DEFAULT.palette.ink, words.colour)
        self.assertEqual(DEFAULT.palette.edge("EAF0F8"), box.outline)

    def test_a_dark_ground_takes_paper_and_no_edge(self):
        built = cards("At risk")
        self.assertEqual(DEFAULT.palette.paper, named(built, "Card 1").colour)
        self.assertEqual("", box_of(built, "Card 1").outline)

    def test_the_colour_that_reads_better_wins_at_any_lightness(self):
        palette = DEFAULT.palette
        for ground in ("0092D1", "777777", "5A9E3A", "FFD400", "1A1A1A", "F3F3F3"):
            with self.subTest(ground):
                built = build({"type": "cards", "cards": [{"heading": "Card", "tone": "Here"}]},
                              theme_from({"grounds": {"Here": ground}}))
                wanted = max((palette.ink, palette.paper), key=lambda words: contrast(ground, words))
                self.assertEqual(wanted, named(built, "Card").colour)

    def test_the_palettes_own_roles_keep_their_words(self):
        """道具の色の役の字は変えない (= 既に書いてある頁の見た目を動かさない)。"""
        built = cards(*TONES)
        for number, tone in enumerate(TONES, start=1):
            light = tone in ("box", "band", "tint")
            wanted = DEFAULT.palette.ink if light else DEFAULT.palette.paper
            self.assertEqual(wanted, named(built, f"Card {number}").colour, tone)


class WhereTheyAreWritten(unittest.TestCase):
    """A named ground is a tone like any other: on a card, a node, a lane, a card in a cell."""

    def test_a_node(self):
        built = build({"type": "flow", "stages": [
            {"name": "One", "nodes": [{"heading": "Node", "tone": "Outside"}]}, {"name": "Two", "nodes": [["B", ""]]}]})
        self.assertEqual("FFF4E5", box_of(built, "Node").colour)

    def test_a_lane(self):
        built = build({"type": "timeline", "periods": ["a", "b"],
                       "lanes": [{"name": "L", "tone": "Shared", "bars": [{"from": 0, "to": 2, "text": "work"}]}]})
        self.assertEqual("E8F3EA", named(built, "work").fill)

    def test_a_roadmap_node_and_a_card_in_a_cell(self):
        road = build({"type": "roadmap", "stages": [{"name": "A", "nodes": [{"heading": "Node", "tone": "Inside"}]},
                                                    {"name": "B", "nodes": [["m", ""]]}]})
        cell = build({"type": "compose", "rows": [{"cells": [{"card": {"heading": "Cell", "tone": "Inside"}}]}]})
        self.assertEqual("EAF0F8", box_of(road, "Node").colour)
        self.assertEqual("EAF0F8", box_of(cell, "Cell").colour)

    def test_a_name_nobody_declared_is_refused_and_the_declared_ones_are_listed(self):
        with self.assertRaises(PageTypeError) as raised:
            cards("Elsewhere")
        said = str(raised.exception)
        for name in ("Elsewhere", "Inside", "At risk", "[theme.grounds]", "box"):
            self.assertIn(name, said)

    def test_without_a_declaration_the_message_says_where_one_goes(self):
        with self.assertRaises(PageTypeError) as raised:
            build({"type": "cards", "cards": [{"heading": "Card", "tone": "Inside"}]}, DEFAULT)
        self.assertIn("a project may name its own in [theme.grounds]", str(raised.exception))


class TheLegend(unittest.TestCase):
    """A page using a named ground says what it means, in the order the project declared them."""

    def test_it_lists_the_names_used_in_the_order_declared_not_the_order_used(self):
        self.assertEqual(["Inside", "Outside", "At risk"], legend(cards("At risk", "Outside", "Inside", "Outside")))

    def test_the_palettes_own_roles_bring_no_legend(self):
        self.assertEqual([], legend(cards("box", "accent")))

    def test_each_name_has_a_swatch_of_its_ground_with_its_edge(self):
        built = cards("Inside", "At risk")
        swatches = sorted((e for e in built.build() if e.kind == "swatch"), key=lambda e: e.rect.left)
        self.assertEqual(["EAF0F8", "8B1E3F"], [s.colour for s in swatches])
        self.assertEqual([DEFAULT.palette.edge("EAF0F8"), ""], [s.outline for s in swatches])
        for swatch in swatches:
            self.assertEqual((DEFAULT.spacing.swatch, DEFAULT.spacing.swatch), (swatch.rect.width, swatch.rect.height))

    def test_it_sits_just_under_the_body_and_above_the_table(self):
        built = cards("Inside", table=[["a", "b"], ["1", "2"]])
        label = named(built, "Inside" if legend(built) else "missing")
        labels = [e for e in built.build() if e.kind == "label"]
        table = next(e for e in built.build() if isinstance(e, Table))
        self.assertEqual(box_of(built, "Card 1").rect.bottom + DEFAULT.spacing.gap_s, label.rect.top)
        self.assertLess(max(l.rect.bottom for l in labels), table.rect.top)

    def test_a_body_that_fills_the_page_leaves_it_room(self):
        built = build({"type": "timeline", "periods": ["a", "b"], "lanes": [
            {"name": f"L{n}", "tone": "Inside", "bars": [{"from": 0, "to": 2, "text": f"w{n}"}]} for n in range(8)]})
        label = next(e for e in built.build() if e.kind == "label" and e.text == "Inside")
        self.assertLess(named(built, "w7").rect.bottom, label.rect.top)
        self.assertLessEqual(label.rect.bottom, built.theme.frame().bottom)

    def test_many_names_run_on_to_a_second_line(self):
        names = {f"A ground with a long name number {n}": "EAF0F8" for n in range(12)}
        theme = theme_from({"grounds": names})
        built = build({"type": "cards", "cards": [{"heading": f"C{n}", "tone": name}
                                                  for n, name in enumerate(names)]}, theme)
        tops = {e.rect.top for e in built.build() if e.kind == "label"}
        self.assertGreater(len(tops), 1)
        width = built.theme.frame().right
        self.assertTrue(all(e.rect.right <= width for e in built.build() if e.kind == "label"))

    def test_legend_false_leaves_it_out(self):
        self.assertEqual([], legend(cards("Inside", legend=False)))

    def test_legend_is_true_or_false(self):
        with self.assertRaises(PageTypeError) as raised:
            cards("Inside", legend="no")
        self.assertIn("`legend` is true or false", str(raised.exception))

    def test_a_name_inside_a_cell_of_a_type_inside_a_cell_is_found(self):
        built = build({"type": "compose", "rows": [{"cells": [{"rows": [{"cells": [{"flow": {"stages": [
            {"name": "A", "nodes": [{"heading": "Deep", "tone": "Shared"}]}, {"name": "B", "nodes": [["m", ""]]}]}}]}]}]}]})
        self.assertEqual(["Shared"], legend(built))

    def test_once_baked_the_checks_find_nothing(self):
        built = cards("Inside", "Outside", "At risk", table=[["a", "b"], ["1", "2"]])
        with tempfile.TemporaryDirectory() as tmp:
            deck = new_deck(THEME)
            add_page(deck, built.build(), THEME)
            self.assertEqual([], checks.run_all(save(deck, Path(tmp) / "grounds.pptx")))


class ThroughTheProject(unittest.TestCase):
    """Declared in `workspace.toml`, read by `build` and listed by `types`."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_a_deck_built_from_a_manifest_paints_the_named_ground(self):
        root = Path(self.tmp.name) / "project"
        (root / "assets").mkdir(parents=True)
        shutil.copy(make_dot(), root / "assets" / "dot.png")
        a_specimen(root / "specimen.pptx", ["表紙"])
        (root / "workspace.toml").write_text('root = "."\n[theme.grounds]\n"内部向け" = "EAF0F8"\n', encoding="utf-8")
        (root / "deck.toml").write_text(
            'specimen = "specimen.pptx"\nout = "built.pptx"\n\n[[pages]]\nkind = "declare"\ntype = "cards"\n'
            'title = "カード"\ncards = [{ heading = "内側", body = "ひとつ", tone = "内部向け" }]\n', encoding="utf-8")
        workspace = Workspace.load(root)
        built = build_deck(workspace, Manifest.load(workspace.manifest("deck")))
        with zipfile.ZipFile(built) as archive:
            slides = "".join(archive.read(n).decode("utf-8") for n in archive.namelist()
                             if n.startswith("ppt/slides/slide") and n.endswith(".xml"))
        self.assertIn('val="EAF0F8"', slides)
        self.assertIn(">内部向け<", slides)

    def test_types_lists_the_names_a_tone_may_take(self):
        root = create(Path(self.tmp.name) / "project")
        (root / "workspace.toml").write_text(
            (root / "workspace.toml").read_text(encoding="utf-8") + '\n[theme.grounds]\n"内部向け" = "EAF0F8"\n',
            encoding="utf-8")
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(0, main(["types", str(root)]))
        said = out.getvalue()
        self.assertIn("tone", said)
        self.assertIn("内部向け", said)
        for role in TONES:
            self.assertIn(role, said)


if __name__ == "__main__":
    unittest.main()
