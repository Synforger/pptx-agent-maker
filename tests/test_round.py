"""Starting the next round from the one before.

手で複製すると、出力の名前を書き換え忘れて前の回のデッキを上書きする。ここはそれが
起きないこと、素材が黙って引き継がれないことを見る。
"""

from __future__ import annotations

import io
import sys
import tempfile
import tomllib
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pptx_agent_maker.__main__ import main  # noqa: E402
from pptx_agent_maker.project import create  # noqa: E402
from pptx_agent_maker.project.manifest import Manifest  # noqa: E402

W1 = """# 第 1 回
specimen = "specimen.pptx"
out = "w1.pptx"

[[pages]]
kind = "copy"
page = 1
replace = [["案件名", "見本"]]
why = "表紙"
"""


class StartingARound(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = create(Path(self.tmp.name) / "project")
        (self.root / "w1.toml").write_text(W1, encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self, *argv: str) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue() + err.getvalue()

    def test_the_new_round_builds_its_own_deck_from_the_same_pages(self) -> None:
        code, said = self._run("round", str(self.root), "w2", "--from", "w1")
        self.assertEqual(code, 0, said)
        new, old = Manifest.load(self.root / "w2.toml"), Manifest.load(self.root / "w1.toml")
        self.assertEqual(new.out, "w2.pptx", "the new round would overwrite the last one's deck")
        self.assertEqual(new.assets, "w2")
        self.assertEqual(new.entries, old.entries)
        self.assertTrue((self.root / "assets" / "w2").is_dir())
        self.assertIn("# 第 1 回", (self.root / "w2.toml").read_text(encoding="utf-8"))

    def test_the_material_is_not_carried_over(self) -> None:
        (self.root / "assets" / "w1").mkdir()
        (self.root / "assets" / "w1" / "old.png").write_bytes(b"x")
        self._run("round", str(self.root), "w2", "--from", "w1")
        self.assertEqual(list((self.root / "assets" / "w2").iterdir()), [])

    def test_missing_material_names_the_page_and_where_it_looked(self) -> None:
        """新しい回で最初に必ず見る止まり方 ― 何頁目の、どこを探したかを言う。"""
        (self.root / "w1.toml").write_text(W1 + """
[[pages]]
kind = "declare"
type = "figure"
title = "結果"
figure = "front.png"
""", encoding="utf-8")
        self._run("round", str(self.root), "w2", "--from", "w1")
        code, said = self._run("build", str(self.root), "w2")
        self.assertEqual(code, 1)
        self.assertIn("page 2", said)
        self.assertIn("assets/w2/", said)

    def test_a_named_material_folder_follows_the_round(self) -> None:
        (self.root / "w1.toml").write_text(W1.replace('out = "w1.pptx"',
                                                      'out = "w1.pptx"\nassets = "w1"'),
                                           encoding="utf-8")
        self._run("round", str(self.root), "w2", "--from", "w1")
        data = tomllib.loads((self.root / "w2.toml").read_text(encoding="utf-8"))
        self.assertEqual(data["assets"], "w2")

    def test_a_round_that_exists_is_not_overwritten(self) -> None:
        (self.root / "w2.toml").write_text("# mine", encoding="utf-8")
        code, said = self._run("round", str(self.root), "w2", "--from", "w1")
        self.assertEqual(code, 1)
        self.assertEqual((self.root / "w2.toml").read_text(encoding="utf-8"), "# mine")

    def test_a_missing_previous_round_is_said(self) -> None:
        code, said = self._run("round", str(self.root), "w2", "--from", "w0")
        self.assertEqual(code, 1)
        self.assertIn("no manifest", said)


if __name__ == "__main__":
    unittest.main()
