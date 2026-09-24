"""`preview <folder of projects>` finds the projects under it.

⚠ 控え (`_archive` / `_edits`) やツールの状態の中の workspace.toml を案件と読まない。
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pptx_agent_maker.__main__ import _projects_under, _specimens  # noqa: E402
from pptx_agent_maker.project import Workspace, create  # noqa: E402


class FindingProjects(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.parent = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_projects_are_found_and_copies_are_not(self) -> None:
        create(self.parent / "one")
        create(self.parent / "client-b" / "deck")
        create(self.parent / "_archive" / "old")
        create(self.parent / "one" / "_edits" / "stray")
        found = [p.relative_to(self.parent).as_posix() for p in _projects_under(self.parent)]
        self.assertEqual(found, ["client-b/deck", "one"])

    def test_too_deep_is_not_searched(self) -> None:
        create(self.parent / "a" / "b" / "c" / "d")
        self.assertEqual(_projects_under(self.parent), [])

    def test_each_project_leaves_its_own_template_out_of_the_list(self) -> None:
        create(self.parent / "one")
        self.assertEqual(_specimens(Workspace.load(self.parent / "one")), {"specimen"})


if __name__ == "__main__":
    unittest.main()
