"""`preview <folder of projects>` finds the projects under it.

⚠ 控え (`_archive` / `_edits`) やツールの状態の中の workspace.toml を案件と読まない。
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pptx_agent_maker.__main__ import _specimens  # noqa: E402
from pptx_agent_maker.project.places import projects_under as _projects_under  # noqa: E402
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


class ReadingThePlaces(unittest.TestCase):
    """What the standing preview offers comes from one file on the machine."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _places(self, text: str) -> Path:
        path = self.base / "preview.toml"
        path.write_text(text, encoding="utf-8")
        return path

    def test_projects_and_plain_folders_are_both_offered(self) -> None:
        from pptx_agent_maker.project.places import discover, load
        create(self.base / "cases" / "one")
        (self.base / "old").mkdir()
        (self.base / "old" / "w1.pptx").write_bytes(b"x")
        places = load(self._places(
            f'[[search]]\npath = "{self.base / "cases"}"\n\n'
            f'[[folder]]\nname = "old decks"\npath = "{self.base / "old"}"\n'))
        found = discover(places, lambda folder: _specimens(Workspace.load(folder)))
        self.assertEqual(sorted(found), ["old decks", "one"])
        self.assertEqual(found["one"][1], ["specimen"], "the project's template is listed as a deck")
        self.assertEqual(found["old decks"][1], [])

    def test_a_folder_that_is_not_there_is_left_out_quietly(self) -> None:
        from pptx_agent_maker.project.places import discover, load
        places = load(self._places(f'[[folder]]\nname = "gone"\npath = "{self.base / "gone"}"\n'))
        self.assertEqual(discover(places, lambda f: set()), {})

    def test_a_malformed_places_file_is_said(self) -> None:
        from pptx_agent_maker.project.places import PlacesError, load
        for text in ('[[folder]]\npath = "/x"\n', '[[search]]\ndepth = 2\n', '[other]\nx = 1\n'):
            with self.subTest(text):
                with self.assertRaises(PlacesError):
                    load(self._places(text))
        with self.assertRaises(PlacesError):
            load(self.base / "missing.toml")
