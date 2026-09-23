"""One manifest, three ways to make a page, one deck.

⚠ 旧世代は「manifest と頁 script のどちらが真値か」が頁の種類で変わり、
「design を変えても動かない」を 2 度踏んだ。**並びの真値は manifest 1 枚**で、
そこに無い頁は組み上がったデッキに存在しない ― それをここで固定する。
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
sys.path.insert(0, str(REPO / "tests"))

from pptx_agent_maker.deck.build import build  # noqa: E402
from pptx_agent_maker.project import Workspace, create  # noqa: E402
from pptx_agent_maker.project.manifest import Manifest, ManifestError  # noqa: E402
from test_deck import a_specimen, make_dot  # noqa: E402

MANIFEST = """
specimen = "specimen.pptx"
out = "built.pptx"

[[pages]]
kind = "copy"
page = 1
replace = [["一枚目", "差し替えた表紙"]]

[[pages]]
kind = "declare"
type = "board"
title = "宣言で組んだ頁"
table = [["列", "値"], ["A", "1"]]

[[pages]]
kind = "import"
deck = "earlier.pptx"
page = 1
"""


class BuildTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        create(self.root)
        make_dot()
        a_specimen(self.root / "specimen.pptx", ["一枚目", "二枚目"])
        a_specimen(self.root / "earlier.pptx", ["前の週の頁"])
        shutil.copy(REPO / "tests" / "data" / "dot.png", self.root / "assets" / "example.png")
        (self.root / "deck.toml").write_text(MANIFEST, encoding="utf-8")
        self.workspace = Workspace.load(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _order(self, deck: Path) -> list[str]:
        with zipfile.ZipFile(deck) as archive:
            presentation = archive.read("ppt/presentation.xml").decode()
            rels = archive.read("ppt/_rels/presentation.xml.rels").decode()
        file_of = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="slides/(slide\d+\.xml)"', rels))
        return [file_of[r] for r in re.findall(r'r:id="(rId\d+)"', presentation) if r in file_of]

    def _text_of(self, deck: Path, index: int) -> str:
        name = self._order(deck)[index]
        with zipfile.ZipFile(deck) as archive:
            return archive.read(f"ppt/slides/{name}").decode()

    def test_all_three_kinds_end_up_in_one_deck(self) -> None:
        built = build(self.workspace, Manifest.load(self.workspace.manifest("deck")))
        self.assertEqual(len(self._order(built)), 3)

    def test_the_pages_read_in_manifest_order(self) -> None:
        built = build(self.workspace, Manifest.load(self.workspace.manifest("deck")))
        self.assertIn("差し替えた表紙", self._text_of(built, 0))
        self.assertIn("宣言で組んだ頁", self._text_of(built, 1))
        self.assertIn("前の週の頁", self._text_of(built, 2))

    def test_the_specimen_pages_are_not_in_the_built_deck(self) -> None:
        built = build(self.workspace, Manifest.load(self.workspace.manifest("deck")))
        joined = "".join(self._text_of(built, i) for i in range(3))
        self.assertNotIn("二枚目", joined, "a page nobody declared came along")

    def test_the_deck_lands_where_the_manifest_says(self) -> None:
        built = build(self.workspace, Manifest.load(self.workspace.manifest("deck")))
        self.assertEqual(built, self.workspace.root / "built.pptx")

    def test_an_unknown_page_type_says_which_ones_exist(self) -> None:
        (self.root / "bad.toml").write_text(
            'specimen = "specimen.pptx"\nout = "x.pptx"\n'
            '[[pages]]\nkind = "declare"\ntype = "not_a_type"\ntitle = "だい"\n',
            encoding="utf-8")
        with self.assertRaises(ManifestError) as caught:
            build(self.workspace, Manifest.load(self.workspace.manifest("bad")))
        self.assertIn("board", str(caught.exception))

    def test_a_missing_specimen_stops_the_build(self) -> None:
        (self.root / "bad.toml").write_text(
            'specimen = "nope.pptx"\nout = "x.pptx"\n'
            '[[pages]]\nkind = "copy"\npage = 1\n', encoding="utf-8")
        with self.assertRaises(ManifestError):
            build(self.workspace, Manifest.load(self.workspace.manifest("bad")))


class ManifestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "m.toml"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _load(self, body: str) -> Manifest:
        self.path.write_text(body, encoding="utf-8")
        return Manifest.load(self.path)

    def test_a_deck_with_no_pages_is_refused(self) -> None:
        with self.assertRaises(ManifestError):
            self._load('specimen = "s.pptx"\nout = "o.pptx"\n')

    def test_an_unknown_kind_is_refused(self) -> None:
        with self.assertRaises(ManifestError) as caught:
            self._load('specimen = "s"\nout = "o"\n[[pages]]\nkind = "invent"\n')
        self.assertIn("kind must be one of", str(caught.exception))

    def test_each_kind_states_what_it_needs(self) -> None:
        for body, missing in [
            ('[[pages]]\nkind = "copy"\n', "page"),
            ('[[pages]]\nkind = "import"\npage = 1\n', "deck"),
            ('[[pages]]\nkind = "declare"\n', "type"),
        ]:
            with self.subTest(missing=missing):
                with self.assertRaises(ManifestError) as caught:
                    self._load(f'specimen = "s"\nout = "o"\n{body}')
                self.assertIn(missing, str(caught.exception))

    def test_replacements_come_through_as_pairs(self) -> None:
        manifest = self._load('specimen = "s"\nout = "o"\n[[pages]]\nkind = "copy"\npage = 1\n'
                              'replace = [["a", "b"], ["c", "d"]]\n')
        self.assertEqual(manifest.entries[0].replace, (("a", "b"), ("c", "d")))


if __name__ == "__main__":
    unittest.main()


class TheNoteStaysANote(unittest.TestCase):
    """`why` says why the page is here — not what happened to it.

    ⚠ 前の世代では 1 つのキーに日付つきの改訂が積まれ、頁の一覧を読む前に必ずそこを
    通ることになった。長さも日付も機械が判定できるので、書いた時点で止める。
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _load(self, why: str) -> Manifest:
        path = self.root / "m.toml"
        path.write_text('specimen = "s"\nout = "o"\n[[pages]]\nkind = "copy"\npage = 1\n'
                        f'why = "{why}"\n', encoding="utf-8")
        return Manifest.load(path)

    def test_a_short_reason_is_kept(self) -> None:
        self.assertEqual("型見本から複製して文言だけ差し替える",
                         self._load("型見本から複製して文言だけ差し替える").entries[0].why)

    def test_a_note_that_grew_into_a_history_is_refused(self) -> None:
        with self.assertRaises(ManifestError) as caught:
            self._load("この頁の経緯。" * 40)
        self.assertIn("history", str(caught.exception))

    def test_a_dated_line_is_refused(self) -> None:
        for dated in ("2026-08-24: 結果頁を足した", "2026/8/24 に差し替え"):
            with self.subTest(dated):
                with self.assertRaises(ManifestError) as caught:
                    self._load(dated)
                self.assertIn("date", str(caught.exception))

    def test_a_number_that_is_not_a_date_passes(self) -> None:
        """版や枚数は覚え書きに書いてよい (= 止めたいのは日付の並びだけ)。"""
        self.assertIn("3 型", self._load("3 型そろった run から引いている").entries[0].why)
