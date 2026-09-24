"""A deck project lives outside the toolkit, and the toolkit will not pretend otherwise.

⚠ ここが緩むと、案件のデータが repo に入り、push に入る。境界は 2 つで守る ―
**repo の中を指す workspace を拒む**ことと、**無い path を黙って返さない**こと。
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from pptx_agent_maker.project import Workspace, WorkspaceError, create  # noqa: E402


class ProjectTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "a-deck-project"
        create(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_the_skeleton_is_laid_down_with_its_settings(self) -> None:
        self.assertTrue((self.root / "workspace.toml").is_file())
        for folder in ("assets",):
            self.assertTrue((self.root / folder).is_dir(), folder)

    def test_the_project_name_reaches_the_settings(self) -> None:
        self.assertIn("a-deck-project", (self.root / "workspace.toml").read_text())

    def test_a_project_can_be_given_its_look_as_it_is_created(self) -> None:
        """⚠ **建てる 1 手で決める** ― あとから手で上書きすると、忘れた回だけ顔が変わる。"""
        elsewhere = Path(self.tmp.name) / "brand.pptx"
        shutil.copy(REPO / "src" / "pptx_agent_maker" / "templates" / "project" / "specimen.pptx",
                    elsewhere)
        elsewhere.write_bytes(elsewhere.read_bytes())  # 別の 1 枚として置く
        root = Path(self.tmp.name) / "with-a-look"
        create(root, specimen=elsewhere)
        self.assertEqual((root / "specimen.pptx").read_bytes(), elsewhere.read_bytes())

    def test_a_folder_hands_over_the_look_and_the_table_that_reads_it(self) -> None:
        """⚠ pptx のテーマ色は意味を持たない枠で、ツールは意味で色を使う。**その 2 つを
        繋ぐ表はテンプレートの中に書けない**ので、対で渡せる。
        """
        shelf = Path(self.tmp.name) / "house-style"
        shelf.mkdir()
        shutil.copy(REPO / "src" / "pptx_agent_maker" / "templates" / "project" / "specimen.pptx",
                    shelf / "specimen.pptx")
        (shelf / "workspace.toml").write_text(
            'root = "."\n\n[theme]\nfont = "Arial"\n', encoding="utf-8")

        root = Path(self.tmp.name) / "from-a-shelf"
        create(root, specimen=shelf)
        self.assertEqual((root / "specimen.pptx").read_bytes(),
                         (shelf / "specimen.pptx").read_bytes())
        self.assertIn('font = "Arial"', (root / "workspace.toml").read_text(encoding="utf-8"))

    def test_a_folder_without_a_specimen_is_said_plainly(self) -> None:
        shelf = Path(self.tmp.name) / "empty-shelf"
        shelf.mkdir()
        root = Path(self.tmp.name) / "never-from-here"
        with self.assertRaises(FileNotFoundError) as caught:
            create(root, specimen=shelf)
        self.assertIn("specimen.pptx", str(caught.exception))
        self.assertFalse(root.exists())

    def test_a_folder_may_hold_only_the_specimen(self) -> None:
        shelf = Path(self.tmp.name) / "look-only"
        shelf.mkdir()
        shutil.copy(REPO / "src" / "pptx_agent_maker" / "templates" / "project" / "specimen.pptx",
                    shelf / "specimen.pptx")
        root = Path(self.tmp.name) / "look-only-project"
        create(root, name="look-only-project", specimen=shelf)
        self.assertIn("look-only-project", (root / "workspace.toml").read_text(encoding="utf-8"))

    def test_a_specimen_that_is_not_there_is_said_before_anything_is_written(self) -> None:
        root = Path(self.tmp.name) / "never-built"
        with self.assertRaises(FileNotFoundError):
            create(root, specimen=Path(self.tmp.name) / "nope.pptx")
        self.assertFalse(root.exists(), "半分だけできた folder が残っている")

    def test_a_specimen_that_is_not_a_pptx_is_refused(self) -> None:
        plain = Path(self.tmp.name) / "notes.txt"
        plain.write_text("not a deck", encoding="utf-8")
        root = Path(self.tmp.name) / "never-built-either"
        with self.assertRaises(ValueError):
            create(root, specimen=plain)
        self.assertFalse(root.exists())

    def test_an_existing_folder_is_not_overwritten(self) -> None:
        with self.assertRaises(FileExistsError):
            create(self.root)

    def test_loading_resolves_every_folder(self) -> None:
        workspace = Workspace.load(self.root)
        self.assertEqual(workspace.root, self.root.resolve())
        self.assertEqual(workspace.assets, self.root.resolve() / "assets")

    def test_a_workspace_inside_the_repository_is_refused(self) -> None:
        """Data in the repo is data in the push."""
        settings = Path(self.tmp.name) / "workspace.toml"
        settings.write_text(f'root = "{REPO / "output"}"\n')
        with self.assertRaises(WorkspaceError) as caught:
            Workspace.load(settings)
        self.assertIn("inside this repository", str(caught.exception))

    def test_a_missing_asset_stops_instead_of_returning_a_path(self) -> None:
        workspace = Workspace.load(self.root)
        with self.assertRaises(WorkspaceError):
            workspace.asset("not-there.png")

    def test_a_present_asset_comes_back(self) -> None:
        workspace = Workspace.load(self.root)
        (workspace.assets / "there.png").write_bytes(b"x")
        self.assertTrue(workspace.asset("there.png").is_file())

    def test_a_built_deck_lands_beside_its_manifest(self) -> None:
        """焼いたデッキは、それを組んだマニフェストの隣に出る。"""
        workspace = Workspace.load(self.root)
        self.assertEqual(workspace.root / "w1.pptx", workspace.out("w1.pptx"))

    def test_the_workspaces_own_file_is_not_a_manifest(self) -> None:
        workspace = Workspace.load(self.root)
        with self.assertRaises(WorkspaceError):
            workspace.manifest("workspace.toml")

    def test_the_manifests_are_listed_without_the_settings(self) -> None:
        workspace = Workspace.load(self.root)
        (self.root / "w1.toml").write_text("", encoding="utf-8")
        (self.root / "w2.toml").write_text("", encoding="utf-8")
        self.assertEqual(["example.toml", "w1.toml", "w2.toml"],
                         [p.name for p in workspace.manifests()])

    def test_a_missing_settings_file_says_so(self) -> None:
        with self.assertRaises(WorkspaceError):
            Workspace.load(Path(self.tmp.name) / "nowhere")


if __name__ == "__main__":
    unittest.main()


class TheCommandLineReachesTheProject(unittest.TestCase):
    """The CLI is walked, not just imported.

    ⚠ **走らせない口は緑でも赤でもない。**置き方を変えたとき、test はすべて通ったのに
    `show` と `check` と `preview` は消えた folder を指したままだった ― CLI を通す
    test が 1 つも無かったため。
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        create(self.root)
        self.addCleanup(self.tmp.cleanup)

    def _run(self, *argv: str) -> tuple[int, str]:
        import contextlib
        import io
        from pptx_agent_maker.__main__ import main
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = main(list(argv))
        return code, out.getvalue()

    def test_show_names_every_folder_the_workspace_has(self) -> None:
        from pptx_agent_maker.project.workspace import FOLDERS
        code, printed = self._run("show", str(self.root))
        self.assertEqual(0, code)
        for folder in FOLDERS:
            self.assertIn(folder, printed)

    def test_show_points_at_folders_that_are_really_there(self) -> None:
        _code, printed = self._run("show", str(self.root))
        for line in printed.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1].startswith("/"):
                self.assertTrue(Path(parts[1]).exists(), f"{parts[0]} points nowhere")
