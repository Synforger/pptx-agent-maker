"""A project sets its own look, and only its look.

⚠ **見た目 (= 書体と色) は案件のもの、頁の割り方はツールのもの。**ここが緩むと、案件ごとに
余白と級数が動いて、同じ役割の頁が週をまたいで別の形になる (= 前の世代が壊れた道)。

もう 1 つ守るのは**色の出どころが 1 つであること**。表だけ PowerPoint 自前のスタイルで
塗られていた間は、`[theme]` で差し色を変えても表が追随しなかった。
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from test_deck import a_specimen, make_dot  # noqa: E402

from pptx_agent_maker.deck.build import build  # noqa: E402
from pptx_agent_maker.layout.base.tokens import DEFAULT, ThemeError, theme_from  # noqa: E402
from pptx_agent_maker.project import Workspace, WorkspaceError  # noqa: E402
from pptx_agent_maker.project.files.manifest import Manifest  # noqa: E402
from pptx_agent_maker.layout.base.tokens import Palette, Theme, Type  # noqa: E402
from pptx_agent_maker.write.pptx import NO_TABLE_STYLE  # noqa: E402

TEMPLATE_SPECIMEN = REPO / "src" / "pptx_agent_maker" / "templates" / "project" / "specimen.pptx"


def _dress(destination, theme):
    """A specimen wearing a given look (= what a project puts down as its own)."""
    spec = importlib.util.spec_from_file_location("baker", REPO / "scripts" / "generate" / "bake-template.py")
    baker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baker)
    shutil.copy(TEMPLATE_SPECIMEN, destination)
    baker.dress(destination, theme)
    return destination

MANIFEST = """
specimen = "specimen.pptx"
out = "built.pptx"

[[pages]]
kind = "declare"
type = "figure"
title = "型で組んだ頁"
figure = "dot.png"
table = [["列", "値"], ["A", "1"]]
"""


class ReadingAThemeTest(unittest.TestCase):
    def test_nothing_declared_means_the_toolkits_own_look(self) -> None:
        self.assertIs(theme_from(None), DEFAULT)
        self.assertIs(theme_from({}), DEFAULT)

    def test_the_typeface_and_the_colours_are_taken(self) -> None:
        theme = theme_from({"font": "Arial", "palette": {"ink": "3f3f3f"}})
        self.assertEqual(theme.type.family, "Arial")
        self.assertEqual(theme.palette.ink, "3F3F3F")

    def test_colours_left_out_keep_their_defaults(self) -> None:
        theme = theme_from({"palette": {"ink": "000000"}})
        self.assertEqual(theme.palette.accent, DEFAULT.palette.accent)

    def test_spacing_and_the_slide_are_not_the_projects_to_set(self) -> None:
        """余白・間隔・紙の大きさは今も受け取らない。文字の大きさだけが案件のものになった
        (= `HowLargeTheTypeIsTest`)。"""
        for settings in ({"spacing": {"margin_x": 1}}, {"slide": "16:9"},
                         {"margin_x": 1}, {"gap_m": 1}):
            with self.subTest(settings=settings), self.assertRaises(ThemeError) as caught:
                theme_from(settings)
            self.assertIn("does not take", str(caught.exception))

    def test_the_edge_of_a_ground_is_the_same_hue_further_from_white(self) -> None:
        palette = Palette()
        for ground in (palette.box, palette.band, palette.tint):
            with self.subTest(ground):
                edge = palette.edge(ground)
                self.assertRegex(edge, r"\A[0-9A-F]{6}\Z")
                pairs = [(int(ground[i:i + 2], 16), int(edge[i:i + 2], 16)) for i in (0, 2, 4)]
                self.assertTrue(all(deep <= light for light, deep in pairs))
                # 白から離れているぶんの順 (= 色あい) は変わらない
                self.assertEqual(sorted(range(3), key=lambda i: pairs[i][0]),
                                 sorted(range(3), key=lambda i: pairs[i][1]))

    def test_the_edge_of_white_is_white_and_no_channel_goes_below_zero(self) -> None:
        self.assertEqual("FFFFFF", Palette().edge("FFFFFF"))
        self.assertEqual("000000", Palette().edge("101010"))

    def test_how_deep_an_edge_is_drawn_is_not_the_projects_to_set(self) -> None:
        with self.assertRaises(ThemeError):
            theme_from({"palette": {"EDGE_DEPTH": "2"}})
        with self.assertRaises(ThemeError):
            theme_from({"palette": {"edge": "000000"}})

    def test_a_misspelled_colour_is_refused_rather_than_dropped(self) -> None:
        with self.assertRaises(ThemeError) as caught:
            theme_from({"palette": {"acccent": "1F5FA9"}})
        self.assertIn("acccent", str(caught.exception))

    def test_a_colour_must_be_six_hex_digits(self) -> None:
        for value in ("#1F5FA9", "blue", "1F5FA", "1F5FA9FF"):
            with self.subTest(value=value), self.assertRaises(ThemeError):
                theme_from({"palette": {"ink": value}})

    def test_an_empty_typeface_is_refused(self) -> None:
        with self.assertRaises(ThemeError):
            theme_from({"font": "   "})


class HowLargeTheTypeIsTest(unittest.TestCase):
    """⚠ **映す資料と読ませる資料は別物。**同じ大きさで両方を組むと、映した時に後ろの席から読めないか、
    配った時に 1 頁に何も載っていないかのどちらかになる。案件は使い方を 1 つ言い、大きさはそこから決まる。
    """

    #: 役ごとの大きさ (= 計画で決めた表。変えるなら `tokens.USES` とここ)
    READ = {"title": 24, "heading": 16, "stage": 14, "body": 12, "caption": 10, "marker": 28, "minimum": 10}
    SHOWN = {"title": 32, "heading": 24, "stage": 20, "body": 18, "caption": 14, "marker": 36, "minimum": 14}

    @staticmethod
    def _sizes(theme) -> dict:
        return {name: getattr(theme.type, name) for name in HowLargeTheTypeIsTest.READ}

    def test_a_deck_is_made_to_be_read_unless_it_says_otherwise(self) -> None:
        self.assertEqual(self.READ, self._sizes(DEFAULT))
        self.assertEqual(self.READ, self._sizes(theme_from({"font": "Arial"})))
        self.assertEqual(self.READ, self._sizes(theme_from({"use": "read"})))
        self.assertEqual((14, 12), DEFAULT.type.plan)

    def test_a_deck_made_to_be_shown_is_set_larger_in_every_role(self) -> None:
        theme = theme_from({"use": "present"})
        self.assertEqual(self.SHOWN, self._sizes(theme))
        self.assertEqual((20, 18), theme.type.plan)

    def test_a_use_nobody_knows_is_refused(self) -> None:
        for use in ("show", "", 3, True):
            with self.subTest(use=use), self.assertRaises(ThemeError) as caught:
                theme_from({"use": use})
            self.assertIn("theme.use", str(caught.exception))

    def test_a_project_may_set_one_role_and_the_rest_stay(self) -> None:
        for use, table in (("read", self.READ), ("present", self.SHOWN)):
            with self.subTest(use=use):
                theme = theme_from({"use": use, "type": {"heading": 21}})
                self.assertEqual({**table, "heading": 21}, self._sizes(theme))

    def test_the_timeline_follows_the_two_sizes_it_is_made_of(self) -> None:
        self.assertEqual((15, 13), theme_from({"type": {"stage": 15, "body": 13}}).type.plan)
        self.assertEqual((13,), theme_from({"type": {"stage": 13, "body": 13}}).type.plan)
        self.assertEqual((16, 12), theme_from({"type": {"stage": 12, "body": 16}}).type.plan)

    def test_a_size_under_the_floor_of_the_use_is_refused(self) -> None:
        for use, floor in (("read", 10), ("present", 14)):
            for role in ("title", "heading", "stage", "body", "caption"):
                with self.subTest(use=use, role=role):
                    self.assertEqual(floor, getattr(theme_from({"use": use, "type": {role: floor}}).type, role))
                    with self.assertRaises(ThemeError) as caught:
                        theme_from({"use": use, "type": {role: floor - 0.5}})
                    self.assertIn(f"{floor}pt floor", str(caught.exception))

    def test_only_the_five_roles_are_the_projects_to_set(self) -> None:
        for role in ("marker", "minimum", "plan", "family", "bodyy"):
            with self.subTest(role=role), self.assertRaises(ThemeError) as caught:
                theme_from({"type": {role: 20}})
            self.assertIn("theme.type does not take", str(caught.exception))

    def test_a_size_is_a_number(self) -> None:
        for value in ("14", True, [14], None):
            with self.subTest(value=value), self.assertRaises(ThemeError):
                theme_from({"type": {"body": value}})
        with self.assertRaises(ThemeError):
            theme_from({"type": [14]})

    def test_the_bands_grow_with_the_type_that_sits_in_them(self) -> None:
        """字だけ大きくして帯をそのままにすると、字が帯からはみ出す。"""
        read, shown = DEFAULT, theme_from({"use": "present"})
        self.assertEqual(read.spacing, theme_from({"use": "read"}).spacing)
        for band, role in (("band_height", "heading"), ("footer_height", "caption")):
            with self.subTest(band=band):
                wanted = getattr(read.spacing, band) * getattr(shown.type, role) / getattr(read.type, role)
                self.assertEqual(round(wanted), getattr(shown.spacing, band))
        self.assertGreaterEqual(shown.spacing.title_height, shown.line_height(shown.type.title))
        self.assertGreaterEqual(shown.spacing.footer_height, shown.line_height(shown.type.caption))
        one = theme_from({"type": {"title": 30}})
        self.assertEqual(read.spacing.band_height, one.spacing.band_height)

    def test_the_title_band_is_two_rows_and_each_grows_with_its_own_type(self) -> None:
        """題の帯は、題の上の小さい字の段と、題の段。題の大きさだけで帯を決めると、小さい字だけを
        大きくした案件で、小さい字の段が足りなくなる。"""
        read = DEFAULT
        for settings in ({"use": "present"}, {"type": {"title": 30}}, {"type": {"caption": 16}},
                         {"use": "present", "type": {"title": 25}}):
            with self.subTest(settings=settings):
                theme = theme_from(settings)
                small = round(read.spacing.kicker_height * theme.type.caption / read.type.caption)
                large = round((read.spacing.title_height - read.spacing.kicker_height)
                              * theme.type.title / read.type.title)
                self.assertEqual(small, theme.spacing.kicker_height)
                self.assertEqual(small + large, theme.spacing.title_height)

    def test_the_margins_and_the_gaps_do_not_move(self) -> None:
        read, shown = DEFAULT.spacing, theme_from({"use": "present", "type": {"body": 22}}).spacing
        moved = {name for name in vars(read) if getattr(read, name) != getattr(shown, name)}
        self.assertEqual({"title_height", "kicker_height", "band_height", "footer_height"}, moved)
        self.assertEqual(DEFAULT.frame(), theme_from({"use": "present"}).frame())

    def test_every_type_builds_a_page_to_be_shown_with_nothing_under_its_floor(self) -> None:
        from test_types import MINIMAL
        from support.pages import build as build_page

        shown = theme_from({"use": "present"})
        for name, data in MINIMAL.items():
            with self.subTest(name):
                page = build_page({"type": name, "title": "だい", "kicker": "01 | しょう", "footer": "でどころ",
                                   **data}, shown)
                sizes = {element.size for element in page.build() if hasattr(element, "size")}
                self.assertTrue(sizes)
                self.assertGreaterEqual(min(sizes), 14)
                self.assertIn(32, sizes, "the title is not set at the size of a deck to be shown")
                for element in page.build():
                    self.assertTrue(shown.frame().contains(element.rect), f"{element.kind} left the frame")

    def test_a_page_that_no_longer_fits_stops_and_is_not_shrunk(self) -> None:
        """映す資料は載る量が減る。読ませる資料で収まっていた頁が収まらなくなったら、縮めずに止まる。"""
        from pptx_agent_maker import PageFullError
        from support.pages import build as build_page

        shown = theme_from({"use": "present"})

        def page(lanes: int) -> dict:
            return {"type": "timeline", "title": "だい", "periods": ["いま", "つぎ"],
                    "lanes": [{"name": f"しごと {index}", "bars": [{"from": 0, "to": 1, "text": "きめる"}]}
                              for index in range(lanes)]}

        def bars(built) -> set:
            return {element.size for element in built.build() if element.kind == "bar"}

        # 8 本は大きい方、9 本は詰まるので小さい方 (= 本文の大きさ)、11 本は読ませる資料でしか載らない
        self.assertEqual({20}, bars(build_page(page(8), shown)))
        self.assertEqual({18}, bars(build_page(page(9), shown)))
        self.assertEqual({14}, bars(build_page(page(11))))
        with self.assertRaises(PageFullError) as stopped:
            build_page(page(11), shown)
        self.assertIn("18pt", str(stopped.exception))


class ThemeThroughTheWorkspaceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        (self.root / "assets").mkdir(parents=True)
        shutil.copy(make_dot(), self.root / "assets" / "dot.png")
        a_specimen(self.root / "specimen.pptx", ["表紙"])
        (self.root / "deck.toml").write_text(MANIFEST, encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _settings(self, body: str) -> Workspace:
        (self.root / "workspace.toml").write_text(f'root = "."\n{body}', encoding="utf-8")
        return Workspace.load(self.root)

    def _built(self, body: str) -> str:
        workspace = self._settings(body)
        built = build(workspace, Manifest.load(workspace.manifest("deck")))
        with zipfile.ZipFile(built) as archive:
            return "".join(
                archive.read(name).decode("utf-8") for name in archive.namelist()
                if name.startswith("ppt/slides/slide") and name.endswith(".xml")
            )

    @staticmethod
    def _table_of(slides: str) -> str:
        """⚠ 落ちたときに頁の XML 全文を出さない (= 読めないものは読まれない)。"""
        found = re.search(r"<a:tbl>.*?</a:tbl>", slides, re.S)
        assert found is not None, "the built deck has no table"
        return found.group(0)

    def test_nothing_declared_means_the_specimens_own_look(self) -> None:
        """⚠ **見た目の真値はテンプレート 1 枚。**書かなければそこから来る。"""
        _dress(self.root / "specimen.pptx",
               Theme(type=Type(family="Arial"), palette=Palette(accent="0092D1")))
        table = self._table_of(self._built(""))
        self.assertIn('typeface="Arial"', table)
        self.assertIn("0092D1", table)
        self.assertNotIn(DEFAULT.palette.accent, table)

    def test_a_declaration_is_laid_over_the_specimen(self) -> None:
        _dress(self.root / "specimen.pptx",
               Theme(type=Type(family="Arial"), palette=Palette(accent="0092D1")))
        table = self._table_of(self._built('[theme.palette]\naccent = "B3261E"\n'))
        self.assertIn("B3261E", table, "the declaration did not win")
        self.assertIn('typeface="Arial"', table, "the specimen's typeface was dropped")

    def test_the_project_look_reaches_the_built_pages(self) -> None:
        slides = self._built('[theme]\nfont = "Arial"\n\n[theme.palette]\naccent = "0092D1"\n')
        self.assertIn('typeface="Arial"', self._table_of(slides))
        self.assertIn("0092D1", self._table_of(slides))
        self.assertNotIn(DEFAULT.palette.accent, self._table_of(slides))

    def test_the_use_of_the_deck_reaches_the_built_pages(self) -> None:
        read = self._built("")
        shown = self._built('[theme]\nuse = "present"\n')
        own = self._built('[theme]\nuse = "present"\n\n[theme.type]\nbody = 20\n')
        title = re.compile(r'<a:rPr[^>]*sz="(\d+)"[^>]*b="1"')
        self.assertIn("2400", title.findall(read))
        self.assertIn("3200", title.findall(shown))
        self.assertIn('sz="1800"', self._table_of(shown))
        self.assertIn('sz="2000"', self._table_of(own))

    def test_a_size_under_the_floor_is_reported_as_a_settings_error(self) -> None:
        with self.assertRaises(WorkspaceError) as caught:
            self._settings('[theme]\nuse = "present"\n\n[theme.type]\nbody = 12\n')
        self.assertIn("workspace.toml", str(caught.exception))
        self.assertIn("14pt floor", str(caught.exception))
        self.assertEqual(12, theme_from(self._settings('[theme.type]\nbody = 12\n').look).type.body)

    def test_the_floor_the_checks_hold_a_deck_to_is_the_floor_of_its_use(self) -> None:
        """⚠ 検査の下限を使い方と別に持つと、映す資料に 10pt の字を持つ複製の頁が通る。"""
        from pptx_agent_maker.__main__ import _checks

        self.assertEqual(10, _checks(self._settings(""))["type_floor"])
        self.assertEqual(14, _checks(self._settings('[theme]\nuse = "present"\n'))["type_floor"])
        own = self._settings('[theme]\nuse = "present"\n\n[checks]\ntype_floor = 12\nstale_words = ["x"]\n')
        self.assertEqual({"type_floor": 12, "stale_words": ["x"]}, _checks(own))

    def test_a_copied_page_set_too_small_for_a_deck_to_be_shown_fails_the_build(self) -> None:
        """見本の頁は読ませる資料の大きさ (= 本文 12pt) で組んである。映す資料に複製すると下限を割る。"""
        import contextlib
        import io
        from pptx_agent_maker.__main__ import main

        (self.root / "deck.toml").write_text(
            'specimen = "specimen.pptx"\nout = "built.pptx"\n\n[[pages]]\nkind = "copy"\npage = 1\n',
            encoding="utf-8")

        def build_with(settings: str) -> tuple[int, str]:
            self._settings(settings)
            (self.root / "built.pptx").unlink(missing_ok=True)
            said = io.StringIO()
            with contextlib.redirect_stdout(said), contextlib.redirect_stderr(said):
                return main(["build", str(self.root), "deck"]), said.getvalue()

        code, said = build_with("")
        self.assertEqual(0, code, said)
        code, said = build_with('[theme]\nuse = "present"\n')
        self.assertEqual(1, code, said)
        self.assertRegex(said, r"FAIL\s+type_floor")
        self.assertIn("14pt floor", said)
        code, said = build_with('[theme]\nuse = "present"\n\n[checks]\ntype_floor = 10\n')
        self.assertEqual(0, code, said)

    def test_a_bad_theme_is_reported_as_a_settings_error(self) -> None:
        with self.assertRaises(WorkspaceError) as caught:
            self._settings('[theme]\nfont = "Arial"\nfonts = "Arial"\n')
        self.assertIn("workspace.toml", str(caught.exception))

    def test_the_table_is_painted_from_the_palette_not_by_powerpoint(self) -> None:
        """⚠ 既定のスタイルは accent1 で見出しを塗る (= 色の真値が 2 つになる)。"""
        table = self._table_of(self._built('[theme.palette]\naccent = "0092D1"\n'))
        self.assertIn(NO_TABLE_STYLE, table)
        self.assertNotIn('firstRow="1"', table)
        self.assertIn("0092D1", table[:table.index("</a:tr>")])


if __name__ == "__main__":
    unittest.main()
