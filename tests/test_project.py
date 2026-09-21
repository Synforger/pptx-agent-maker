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
        for folder in ("base", "manifests", "pages", "assets", "output"):
            self.assertTrue((self.root / folder).is_dir(), folder)

    def test_the_project_name_reaches_the_settings(self) -> None:
        self.assertIn("a-deck-project", (self.root / "workspace.toml").read_text())

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

    def test_the_output_folder_is_made_on_demand(self) -> None:
        workspace = Workspace.load(self.root)
        shutil.rmtree(workspace.output)
        target = workspace.out("deck.pptx")
        self.assertTrue(target.parent.is_dir())

    def test_a_missing_settings_file_says_so(self) -> None:
        with self.assertRaises(WorkspaceError):
            Workspace.load(Path(self.tmp.name) / "nowhere")


if __name__ == "__main__":
    unittest.main()
