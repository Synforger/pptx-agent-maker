"""A project sets its own look, and only its look.

⚠ **意匠 (= 書体と色) は案件のもの、版面の割り方は道具のもの。**ここが緩むと、案件ごとに
余白と級数が動いて、同じ役割の頁が週をまたいで別の形になる (= 前の世代が壊れた道)。

もう 1 つ守るのは**色の出どころが 1 つであること**。表だけ PowerPoint 自前のスタイルで
塗られていた間は、`[theme]` で差し色を変えても表が追随しなかった。
"""

from __future__ import annotations

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
from pptx_agent_maker.layout.tokens import DEFAULT, ThemeError, theme_from  # noqa: E402
from pptx_agent_maker.project import Workspace, WorkspaceError  # noqa: E402
from pptx_agent_maker.project.manifest import Manifest  # noqa: E402
from pptx_agent_maker.write.pptx import NO_TABLE_STYLE  # noqa: E402

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

    def test_sizes_and_spacing_are_not_the_projects_to_set(self) -> None:
        for settings in ({"spacing": {"margin_x": 1}}, {"type": {"body": 20}},
                         {"slide": "16:9"}):
            with self.subTest(settings=settings), self.assertRaises(ThemeError) as caught:
                theme_from(settings)
            self.assertIn("does not take", str(caught.exception))

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

    def test_no_theme_means_the_default(self) -> None:
        self.assertIs(self._settings("").theme, DEFAULT)

    def test_the_project_look_reaches_the_built_pages(self) -> None:
        slides = self._built('[theme]\nfont = "Arial"\n\n[theme.palette]\naccent = "0092D1"\n')
        self.assertIn('typeface="Arial"', self._table_of(slides))
        self.assertIn("0092D1", self._table_of(slides))
        self.assertNotIn(DEFAULT.palette.accent, self._table_of(slides))

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
