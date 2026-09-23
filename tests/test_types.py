"""The page types: what they build, and what they refuse.

型が「用意されただけ」にならないことを、ここで機械が見張る ― 座標を書く口が
型の中にも無いこと、宣言に縦横比を書けないこと、綴り違いが黙って落ちないこと。
"""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from pptx_agent_maker.layout import types
from pptx_agent_maker.layout.page import Figure, Table, Text
from pptx_agent_maker.layout.types import PageTypeError
from pptx_agent_maker.project.manifest import Manifest, ManifestError
from pptx_agent_maker.write import aspect

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "tests" / "data"
SQUARE = "dot.png"      # 8 x 8
WIDE = "wide.png"       # 16 x 4


def asset(name: str) -> Path:
    return DATA / name


def build(data: dict):
    return types.build(data, asset, aspect)


#: 7 型それぞれの、本体に最小限そろった宣言
MINIMAL = {
    "figure": {"figure": SQUARE},
    "figures": {"figures": [SQUARE, WIDE]},
    "figure_grid": {"figures": [SQUARE, WIDE, SQUARE, WIDE]},
    "flow": {"stages": [{"name": "にゅうりょく", "nodes": [["A", "ほそく"]], "settled": "じょうけん"},
                        {"name": "せいせい", "nodes": [["B", "ほそく"]]}]},
    # 絵を持たなくてよい型 (= デッキの骨格)
    "agenda": {"buckets": [["しょう 1", ["こうもく"]], ["しょう 2", ["こうもく"]]],
               "highlight": 1},
    "board": {"table": [["列", "値"], ["A", "1"]]},
    "cards": {"cards": [["\u2460", "さいしょ"], ["\u2461", "つぎ"]]},
}

#: 絵を持たなくてよい型 (= デッキの骨格)
SKELETON = {"agenda", "board", "cards"}

#: 本体に添えられるもの (= どの型でも同じように効く)
EXTRAS = {"table": [["列", "値"], ["A", "1"]],
          "points": ["ひとつ", "ふたつ"],
          "note": "読み方を 1 行",
          "cards": [["\u2460", "さいしょ"], ["\u2461", "つぎ"]]}


class EveryTypeBuilds(unittest.TestCase):
    """Each of the eight makes a page, and every page has something to look at."""

    def test_every_type_is_covered_here(self):
        self.assertEqual(sorted(MINIMAL), types.names())

    def test_only_the_scaffolding_may_skip_the_figure(self):
        self.assertEqual(sorted(SKELETON), types.skeleton())

    def test_each_type_builds_a_page_inside_its_frame(self):
        for name, data in MINIMAL.items():
            with self.subTest(name):
                page = build({"type": name, "title": "だい", **data})
                elements = page.build()
                figures = [e for e in elements if isinstance(e, Figure)]
                if "figure" in data or "figures" in data:
                    self.assertTrue(figures, f"{name} produced no figure")
                frame = page.theme.frame()
                for element in elements:
                    self.assertTrue(frame.contains(element.rect),
                                    f"{name}: {element.kind} landed outside the frame")

    def test_siblings_never_overlap(self):
        for name, data in MINIMAL.items():
            with self.subTest(name):
                placed = [e for e in build({"type": name, "title": "だい", **data}).build()
                          if isinstance(e, (Figure, Table))]
                for i, a in enumerate(placed):
                    for b in placed[i + 1:]:
                        self.assertFalse(a.rect.overlaps(b.rect),
                                         f"{name}: {a.kind} and {b.kind} overlap")

    def test_the_bands_are_optional_and_appear_when_asked(self):
        plain = build({"type": "figure", "title": "だい", "figure": SQUARE}).build()
        dressed = build({"type": "figure", "title": "だい", "figure": SQUARE,
                         "kicker": "01 | しるし", "condition": "じょうけん",
                         "conclusion": "けつろん", "footer": "でどころ"}).build()
        kinds = {e.kind for e in dressed} - {e.kind for e in plain}
        self.assertEqual({"kicker", "band", "band_text", "footer"}, kinds)


class TheExtrasWorkOnEveryType(unittest.TestCase):
    """Cards, a table and the reading are the same on every type.

    ⚠ **付属の有無で型を分けない。**分けていた間は、実物の頁が持っているものを
    受け取れる型が 1 つも無く、ほとんどの頁で何かが落ちた (= 表を持つ型は
    カードを受け取れず、カードを持つ型は表を受け取れなかった)。
    """

    def test_every_type_accepts_every_extra(self):
        for name, data in MINIMAL.items():
            with self.subTest(name):
                spec = {"type": name, "title": "だい", **data, **EXTRAS}
                if name == "cards":
                    spec.pop("cards", None)
                    spec["cards"] = EXTRAS["cards"]
                page = build(spec)
                kinds = {e.kind for e in page.build()}
                self.assertIn("table", kinds, f"{name} dropped the table")
                self.assertIn("points", kinds, f"{name} dropped the points")
                self.assertIn("note", kinds, f"{name} dropped the reading")
                self.assertIn("box", kinds, f"{name} dropped the cards")

    def test_the_extras_stay_inside_the_frame(self):
        for name, data in MINIMAL.items():
            with self.subTest(name):
                page = build({"type": name, "title": "だい", **data, **EXTRAS})
                frame = page.theme.frame()
                for element in page.build():
                    self.assertTrue(frame.contains(element.rect),
                                    f"{name}: {element.kind} landed outside the frame")

    def test_the_order_of_the_frame_never_changes(self):
        """並びは 1 つしかない ― カードは本体の上、表と読み方は本体の下。"""
        page = build({"type": "figure", "title": "だい", "figure": SQUARE, **EXTRAS})
        placed = {e.kind: e.rect for e in page.build()}
        self.assertLess(placed["box"].top, placed["figure"].top)
        self.assertLess(placed["figure"].bottom, placed["table"].top)
        self.assertLess(placed["table"].bottom, placed["points"].top)
        self.assertLess(placed["points"].bottom, placed["note"].top)


class OnlyTheTypeThatReadsAKeyAcceptsIt(unittest.TestCase):
    """⚠ **読まない型に書けるままだと、書いたつもりで頁には無い。**

    `caption` は「どの型にも添えられる」一覧に入っていたが、絵を並べる型は頁全体の
    caption を読まない (= 絵ごとの説明は `figures` の中に書く)。黙って落ちていた。
    """

    @staticmethod
    def _build(data):
        return types.build(data, lambda name: Path(name), lambda path: 1.0)

    def test_one_image_takes_a_caption(self) -> None:
        self._build({"type": "figure", "title": "t", "figure": "a.png", "caption": "読み方"})

    def test_images_side_by_side_do_not(self) -> None:
        with self.assertRaises(types.PageTypeError) as caught:
            self._build({"type": "figures", "title": "t",
                         "figures": ["a.png", "b.png"], "caption": "落ちていた"})
        self.assertIn("does not take caption", str(caught.exception))

    def test_a_grid_takes_its_column_count(self) -> None:
        self._build({"type": "figure_grid", "title": "t",
                     "figures": ["a.png", "b.png"], "columns": 2})

    def test_one_image_does_not_take_a_column_count(self) -> None:
        with self.assertRaises(types.PageTypeError):
            self._build({"type": "figure", "title": "t", "figure": "a.png", "columns": 2})


class WhatTheTypesRefuse(unittest.TestCase):
    """A declaration nobody can build must stop here, not later."""

    def test_an_unknown_type_is_refused_and_lists_what_exists(self):
        with self.assertRaises(PageTypeError) as raised:
            build({"type": "figure_and_vibes", "title": "だい", "figure": SQUARE})
        self.assertIn("figure_grid", str(raised.exception))

    def test_a_missing_required_key_is_refused(self):
        with self.assertRaises(PageTypeError) as raised:
            build({"type": "board", "title": "だい"})
        self.assertIn("table", str(raised.exception))

    def test_a_key_nobody_reads_is_refused(self):
        """⚠ 綴り違いを捨てると、書いた人は書いたつもりで、頁にはそれが無い。"""
        with self.assertRaises(PageTypeError) as raised:
            build({"type": "figure", "title": "だい", "figure": SQUARE, "captoin": "typo"})
        self.assertIn("captoin", str(raised.exception))

    def test_a_page_without_a_title_is_refused(self):
        with self.assertRaises(PageTypeError):
            build({"type": "figure", "figure": SQUARE})

    def test_a_flow_needs_more_than_one_stage(self):
        with self.assertRaises(PageTypeError):
            build({"type": "flow", "title": "だい",
                   "stages": [{"name": "ひとつ", "nodes": [["A", "b"]]}]})

    def test_an_agenda_cannot_highlight_a_chapter_that_is_not_there(self):
        with self.assertRaises(PageTypeError):
            build({"type": "agenda", "title": "だい", "highlight": 9,
                   "buckets": [["しょう", ["こうもく"]]]})

    def test_figures_needs_more_than_one(self):
        with self.assertRaises(PageTypeError):
            build({"type": "figures", "title": "だい", "figures": [SQUARE]})

    def test_an_empty_points_block_is_refused(self):
        with self.assertRaises(ValueError):
            build({"type": "figure", "title": "だい", "figure": SQUARE,
                   "points": ["", "  "]})

    def test_a_table_with_an_empty_cell_is_refused(self):
        with self.assertRaises(ValueError):
            build({"type": "figure", "title": "だい", "figure": SQUARE,
                   "table": [["列", "値"], ["A", ""]]})


class CoordinatesCannotBeDeclared(unittest.TestCase):
    """The whole point: neither the declaration nor the types hold numbers."""

    def test_the_aspect_ratio_comes_from_the_file(self):
        square = [e for e in build({"type": "figure", "title": "だい", "figure": SQUARE}).build()
                  if isinstance(e, Figure)][0]
        wide = [e for e in build({"type": "figure", "title": "だい", "figure": WIDE}).build()
                if isinstance(e, Figure)][0]
        self.assertAlmostEqual(square.rect.width / square.rect.height, 1.0, places=1)
        self.assertAlmostEqual(wide.rect.width / wide.rect.height, 4.0, places=1)

    def test_the_aspect_ratio_cannot_be_declared(self):
        """比を宣言に書けると、絵を差し替えた日に古い比が残って潰れた絵が焼ける。"""
        with self.assertRaises(PageTypeError):
            build({"type": "figure", "title": "だい", "figure": WIDE, "aspect": 1.0})

    def test_the_types_module_holds_no_coordinates(self):
        """型の中にも座標を書かせない (= 割り方は比、寸法は token が持つ)。"""
        source = (REPO / "src/pptx_agent_maker/layout/types.py").read_text(encoding="utf-8")
        code = "\n".join(line.split("#")[0] for line in source.splitlines())
        code = re.sub(r'""".*?"""', "", code, flags=re.S)
        offenders = re.findall(r"(?<![\w.])\d{4,}(?![\w.])", code)
        self.assertEqual([], offenders,
                         f"a page type wrote a raw dimension: {offenders}")

    def test_a_body_type_must_show_something(self):
        """本文の型が図解を落とせるなら、表と文章だけの頁が戻ってくる。

        絵を持つか、図形で組んだ図解を持つか (= `flow`) のどちらかでなければ組めない。
        """
        for name, data in MINIMAL.items():
            if name in SKELETON:
                continue
            with self.subTest(name):
                shows = {"figure", "figures", "stages"} & data.keys()
                self.assertTrue(shows, f"{name} can be built without anything to look at")

    def test_the_scaffolding_stays_small(self):
        """例外の型は増やさない (= 増えた分だけ「表だけの頁」の逃げ道になる)。"""
        self.assertLessEqual(len(types.skeleton()), 3)


class ManifestCarriesTheType(unittest.TestCase):
    """A declared page picks a type or a script — one way, never both."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def write(self, body: str) -> Path:
        path = self.root / "deck.toml"
        path.write_text('specimen = "base/s.pptx"\nout = "d.pptx"\n' + body, encoding="utf-8")
        return path

    def test_a_typed_page_keeps_its_fields_and_drops_the_plumbing(self):
        manifest = Manifest.load(self.write(
            '[[pages]]\nkind = "declare"\ntype = "figure"\ntitle = "だい"\n'
            'figure = "a.png"\nwhy = "おぼえがき"\n'))
        entry = manifest.entries[0]
        self.assertEqual("figure", entry.type)
        self.assertEqual("おぼえがき", entry.why)
        self.assertEqual({"type", "title", "figure"}, set(entry.data))

    def test_a_declared_page_without_a_type_is_refused(self):
        """型に収まらない頁は、型を足してから作る (= 手で図形を置く道は無い)。"""
        with self.assertRaises(ManifestError) as raised:
            Manifest.load(self.write('[[pages]]\nkind = "declare"\n'))
        self.assertIn("type", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
