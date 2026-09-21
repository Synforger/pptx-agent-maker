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
specimen = "base/specimen.pptx"
out = "built.pptx"

[[pages]]
kind = "copy"
page = 1
replace = [["一枚目", "差し替えた表紙"]]

[[pages]]
kind = "declare"
module = "example_page"

[[pages]]
kind = "import"
deck = "base/earlier.pptx"
page = 1
"""


class BuildTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        create(self.root)
        make_dot()
        a_specimen(self.root / "base" / "specimen.pptx", ["一枚目", "二枚目"])
        a_specimen(self.root / "base" / "earlier.pptx", ["前の週の頁"])
        shutil.copy(REPO / "tests" / "data" / "dot.png", self.root / "assets" / "example.png")
        (self.root / "manifests" / "deck.toml").write_text(MANIFEST, encoding="utf-8")
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
        self.assertIn("見本の頁", self._text_of(built, 1))
        self.assertIn("前の週の頁", self._text_of(built, 2))

    def test_the_specimen_pages_are_not_in_the_built_deck(self) -> None:
        built = build(self.workspace, Manifest.load(self.workspace.manifest("deck")))
        joined = "".join(self._text_of(built, i) for i in range(3))
        self.assertNotIn("二枚目", joined, "a page nobody declared came along")

    def test_the_deck_lands_where_the_manifest_says(self) -> None:
        built = build(self.workspace, Manifest.load(self.workspace.manifest("deck")))
        self.assertEqual(built, self.workspace.output / "built.pptx")

    def test_a_missing_page_recipe_says_which_file(self) -> None:
        (self.root / "manifests" / "bad.toml").write_text(
            'specimen = "base/specimen.pptx"\nout = "x.pptx"\n'
            '[[pages]]\nkind = "declare"\nmodule = "not_there"\n', encoding="utf-8")
        with self.assertRaises(ManifestError) as caught:
            build(self.workspace, Manifest.load(self.workspace.manifest("bad")))
        self.assertIn("not_there.py", str(caught.exception))

    def test_a_missing_specimen_stops_the_build(self) -> None:
        (self.root / "manifests" / "bad.toml").write_text(
            'specimen = "base/nope.pptx"\nout = "x.pptx"\n'
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
            ('[[pages]]\nkind = "declare"\n', "module"),
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
