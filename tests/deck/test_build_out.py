"""`build --out <file>`: a trial build that writes beside nothing the manifest names.

The deck goes to the given path; the manifest's own `out` is neither made nor changed, the pictures are
still found by the manifest's name, and the guards on a deck being open or hand-edited look at the file written.
"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))

from pptx_agent_maker.__main__ import main  # noqa: E402
from pptx_agent_maker.project import create  # noqa: E402
from deck.test_deck import a_specimen, make_dot  # noqa: E402

MANIFEST = ('specimen = "specimen.pptx"\nout = "deck.pptx"\n\n'
            '[[pages]]\nkind = "declare"\ntype = "figure"\ntitle = "A picture"\nfigure = "dot.png"\n')


class TheTrialBuild(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project"
        create(self.root)
        make_dot()
        a_specimen(self.root / "specimen.pptx", ["first"])
        (self.root / "assets" / "deck").mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / "tests" / "data" / "dot.png", self.root / "assets" / "deck" / "dot.png")
        (self.root / "deck.toml").write_text(MANIFEST, encoding="utf-8")

    def build(self, *flags: str) -> tuple[int, str]:
        said = io.StringIO()
        with contextlib.redirect_stdout(said), contextlib.redirect_stderr(said):
            code = main(["build", str(self.root), "deck", *flags])
        return code, said.getvalue()

    def test_it_writes_the_given_file_and_names_it(self) -> None:
        trial = Path(self.tmp.name) / "trial.pptx"
        code, said = self.build("--out", str(trial), "--skip-checks")
        self.assertEqual(0, code, said)
        self.assertTrue(trial.is_file())
        self.assertIn(f"built {trial.resolve()} ", said)

    def test_the_real_deck_is_not_made(self) -> None:
        self.build("--out", str(Path(self.tmp.name) / "trial.pptx"), "--skip-checks")
        self.assertFalse((self.root / "deck.pptx").exists())
        self.assertFalse((self.root / ".pptx-agent-maker").exists())

    def test_the_real_deck_is_not_changed(self) -> None:
        code, said = self.build("--skip-checks")
        self.assertEqual(0, code, said)
        real = self.root / "deck.pptx"
        before = real.read_bytes()
        ledger = {p: p.read_bytes() for p in (self.root / ".pptx-agent-maker").rglob("*") if p.is_file()}
        self.build("--out", str(Path(self.tmp.name) / "trial.pptx"), "--skip-checks")
        self.assertEqual(before, real.read_bytes())
        self.assertEqual(ledger, {p: p.read_bytes() for p in ledger})

    def test_the_pictures_are_found_by_the_manifests_name(self) -> None:
        code, said = self.build("--out", str(Path(self.tmp.name) / "trial.pptx"), "--skip-checks")
        self.assertEqual(0, code, said)
        self.assertNotIn("asset not found", said)

    def test_a_relative_path_is_read_from_the_folder_the_command_runs_in(self) -> None:
        here = Path(self.tmp.name) / "elsewhere"
        here.mkdir()
        before = Path.cwd()
        os.chdir(here)
        self.addCleanup(os.chdir, before)
        code, said = self.build("--out", "trial.pptx", "--skip-checks")
        self.assertEqual(0, code, said)
        self.assertTrue((here / "trial.pptx").is_file())
        self.assertFalse((self.root / "trial.pptx").exists())

    def test_a_name_that_is_not_pptx_is_refused(self) -> None:
        target = Path(self.tmp.name) / "trial.txt"
        code, said = self.build("--out", str(target), "--skip-checks")
        self.assertEqual(1, code)
        self.assertIn(".pptx", said)
        self.assertFalse(target.exists())

    def test_a_deck_open_in_powerpoint_is_not_written(self) -> None:
        trial = Path(self.tmp.name) / "trial.pptx"
        (Path(self.tmp.name) / "~$trial.pptx").write_bytes(b"")
        code, said = self.build("--out", str(trial), "--skip-checks")
        self.assertEqual(1, code)
        self.assertIn("is open in PowerPoint", said)
        self.assertFalse(trial.exists())


if __name__ == "__main__":
    unittest.main()
