"""Handing an existing project what a newer toolkit carries.

⚠ `init` の時点で写した task と手順書は、ツールを更新しても案件に届かない。ここは
ツールが持つ file だけが最新になり、案件の file は 1 バイトも変わらないことを見る。
"""

from __future__ import annotations

import hashlib
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pptx_agent_maker.__main__ import main  # noqa: E402
from pptx_agent_maker.project import create  # noqa: E402
from pptx_agent_maker.project.scaffold import TEMPLATE  # noqa: E402


class Refreshing(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = create(Path(self.tmp.name) / "project")
        (self.root / "w1.toml").write_text("# the project's own", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self) -> str:
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["refresh", str(self.root)]), 0)
        return out.getvalue()

    def _project_files(self) -> dict[str, str]:
        owned = {"Taskfile.yml", "_README.md"}
        return {p.relative_to(self.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob("*") if p.is_file()
                and p.relative_to(self.root).as_posix() not in owned
                and not p.relative_to(self.root).as_posix().startswith((".claude/", ".pptx-agent-maker/"))}

    def test_a_project_made_by_an_older_toolkit_gets_the_new_tasks_and_skill(self) -> None:
        taskfile = self.root / "Taskfile.yml"
        taskfile.write_text("version: '3'\ntasks: {}\n", encoding="utf-8")  # 古いツールの口
        (self.root / ".claude/skills/deck/reference.md").unlink()
        before = self._project_files()
        said = self._run()
        self.assertEqual(taskfile.read_bytes(), (TEMPLATE / "Taskfile.yml").read_bytes())
        self.assertTrue((self.root / ".claude/skills/deck/reference.md").is_file())
        self.assertIn("refreshed Taskfile.yml", said)
        self.assertEqual(self._project_files(), before, "a file of the project was touched")

    def test_what_it_replaced_is_kept(self) -> None:
        (self.root / "Taskfile.yml").write_text("# changed in this project", encoding="utf-8")
        self._run()
        kept = list((self.root / ".pptx-agent-maker" / "replaced").rglob("Taskfile.yml"))
        self.assertEqual([p.read_text(encoding="utf-8") for p in kept], ["# changed in this project"])

    def test_an_up_to_date_project_is_left_alone(self) -> None:
        self.assertIn("already up to date", self._run())
        self.assertFalse((self.root / ".pptx-agent-maker" / "replaced").exists())


if __name__ == "__main__":
    unittest.main()
