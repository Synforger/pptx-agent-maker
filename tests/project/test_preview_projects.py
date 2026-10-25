"""`preview <folder of projects>` finds the projects under it.

⚠ 控え (`_archive` / `_edits`) やツールの状態の中の workspace.toml を案件と読まない。
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pptx_agent_maker.__main__ import _specimens  # noqa: E402
from pptx_agent_maker.project.files.places import projects_under as _projects_under  # noqa: E402
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

    def test_a_project_pointing_at_a_template_is_a_deck_project(self) -> None:
        """テンプレートを写さずに指す案件は自分の specimen を持たない ― 指した先にそろっていれば案件。"""
        create(self.parent / "template")
        project = self.parent / "deck"
        project.mkdir()
        (project / "workspace.toml").write_text('template = "../template"\n', encoding="utf-8")
        found = [p.relative_to(self.parent).as_posix() for p in _projects_under(self.parent)]
        self.assertEqual(found, ["deck", "template"])
        (project / "workspace.toml").write_text('template = "../nowhere"\n', encoding="utf-8")
        found = [p.relative_to(self.parent).as_posix() for p in _projects_under(self.parent)]
        self.assertEqual(found, ["template"])

    def test_another_tools_workspace_is_not_a_deck_project(self) -> None:
        """⚠ `workspace.toml` はほかの道具も使う名前 ― テンプレートの無い folder を案件と読んでいた。"""
        create(self.parent / "one")
        other = self.parent / "handover"
        other.mkdir()
        (other / "workspace.toml").write_text('root = "."\n', encoding="utf-8")
        found = [p.relative_to(self.parent).as_posix() for p in _projects_under(self.parent)]
        self.assertEqual(found, ["one"])

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
        from pptx_agent_maker.project.files.places import discover, load
        create(self.base / "cases" / "client-one")
        (self.base / "old").mkdir()
        (self.base / "old" / "w1.pptx").write_bytes(b"x")
        places = load(self._places(
            f'[[search]]\npath = "{self.base / "cases"}"\n\n'
            f'[[folder]]\nname = "old decks"\npath = "{self.base / "old"}"\n\n'
            f'[labels]\n"{self.base / "cases" / "client-one"}" = "A"\n'))
        found = discover(places, lambda folder: _specimens(Workspace.load(folder)))
        self.assertEqual(sorted(found), ["A", "old decks"])
        self.assertEqual(found["A"][1], ["specimen"], "the project's template is listed as a deck")
        self.assertEqual(found["old decks"][1], [])

    def test_a_project_with_no_label_does_not_show_its_folder_name(self) -> None:
        """⚠ folder 名には先方の名前が入りうる ― 発表中に欄を開くと別の会社の名前が並ぶ。"""
        from pptx_agent_maker.project.files.places import discover, load
        create(self.base / "cases" / "client-one")
        places = load(self._places(f'[[search]]\npath = "{self.base / "cases"}"\n'))
        first = discover(places, lambda f: set())
        (name,) = first
        self.assertNotIn("client", name)
        self.assertTrue(name.startswith("案件 "))
        self.assertEqual(sorted(discover(places, lambda f: set())), [name], "the name moved")

    def test_a_project_that_cannot_be_read_stays_and_says_why(self) -> None:
        """⚠ 読めない案件を黙って飛ばしていた間は、画面を見る人には「デッキが消えた」だった。"""
        from pptx_agent_maker.project.files.places import discover, load
        create(self.base / "cases" / "client-one")
        settings = self.base / "cases" / "client-one" / "workspace.toml"
        settings.write_text(settings.read_text(encoding="utf-8") + "\n[theme]\nnot_a_key = 1\n",
                            encoding="utf-8")
        places = load(self._places(f'[[search]]\npath = "{self.base / "cases"}"\n'))
        (offer,) = discover(places, lambda folder: _specimens(Workspace.load(folder))).values()
        self.assertEqual(offer.folder, self.base / "cases" / "client-one")
        self.assertEqual(offer.skip, ["specimen"], "the usual template is still left out")
        self.assertIn("not_a_key", offer.problem)

    def test_an_unreadable_project_is_told_when_the_toolkit_moved_after_the_start(self) -> None:
        """⚠ 常駐は起動した時の道具のまま走る ― 新しい欄を書いた案件は、起動し直すまで読めない。"""
        from pptx_agent_maker.__main__ import _fingerprint, _offers
        from pptx_agent_maker.project.files.places import load
        create(self.base / "cases" / "good")
        create(self.base / "cases" / "bad")
        settings = self.base / "cases" / "bad" / "workspace.toml"
        settings.write_text(settings.read_text(encoding="utf-8") + "\n[theme]\nnot_a_key = 1\n",
                            encoding="utf-8")
        places = load(self._places(f'[[search]]\npath = "{self.base / "cases"}"\n'))
        same = {o.folder.name: o.problem for o in _offers(places, _fingerprint(), "then").values()}
        self.assertIsNone(same["good"])
        self.assertNotIn("restart", same["bad"], "the toolkit did not change; a restart would not help")
        moved = {o.folder.name: o.problem for o in _offers(places, "older", "then").values()}
        self.assertIsNone(moved["good"])
        self.assertIn("restart the preview", moved["bad"])
        self.assertIn("then", moved["bad"])

    def test_a_folder_that_is_not_there_is_left_out_quietly(self) -> None:
        from pptx_agent_maker.project.files.places import discover, load
        places = load(self._places(f'[[folder]]\nname = "gone"\npath = "{self.base / "gone"}"\n'))
        self.assertEqual(discover(places, lambda f: set()), {})

    def test_a_malformed_places_file_is_said(self) -> None:
        from pptx_agent_maker.project.files.places import PlacesError, load
        for text in ('[[folder]]\npath = "/x"\n', '[[search]]\ndepth = 2\n', '[other]\nx = 1\n'):
            with self.subTest(text):
                with self.assertRaises(PlacesError):
                    load(self._places(text))
        with self.assertRaises(PlacesError):
            load(self.base / "missing.toml")


class StartingWithNothingToShow(unittest.TestCase):
    """⚠ 案件の無い機械の常駐が起動を断り、launchd が 10 秒ごとに起こし直しては落ちた (= 1 日に数千回)。
    置き場の設定が無くても、在って何も見つからなくても、起動して空の画面に理由を出す。"""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        patcher = mock.patch.dict("os.environ", {"AGENT_PLATFORM_ROOT": str(self.root)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _start(self) -> tuple[int, object]:
        """What `preview` returned, and the board it served (= serving itself is stood in for)."""
        from pptx_agent_maker import __main__ as entry
        preview_entry, _state = entry._preview_package()
        with mock.patch.object(preview_entry, "serve", return_value=0) as serve, \
                mock.patch.object(entry, "_watch_the_toolkit"):
            code = entry.main(["preview", "--port", "0", "--no-open"])
        serve.assert_called_once()
        return code, serve.call_args.args[0]

    def test_with_no_places_file_it_starts_and_says_where_the_file_goes(self) -> None:
        code, board = self._start()
        self.assertEqual(0, code)
        self.assertEqual([], board.projects())
        self.assertIn("no places file", board.get(None).problem)

    def test_with_places_that_find_nothing_it_starts_and_waits(self) -> None:
        places = self.root / "config" / "pptx-agent-maker" / "preview.toml"
        places.parent.mkdir(parents=True)
        places.write_text("", encoding="utf-8")
        code, board = self._start()
        self.assertEqual(0, code)
        self.assertIn("nothing to show yet", board.get(None).problem)

    def test_a_places_file_written_later_is_read_without_a_restart(self) -> None:
        code, board = self._start()
        board.REDISCOVER_SECONDS = 0
        cases = self.root / "cases"
        create(cases / "client-one")
        places = self.root / "config" / "pptx-agent-maker" / "preview.toml"
        places.parent.mkdir(parents=True)
        places.write_text(f'[[search]]\npath = "{cases}"\n', encoding="utf-8")
        self.assertEqual(1, len(board.projects()))
        self.assertIsNotNone(board.project)

    def test_a_places_file_named_on_the_command_line_must_be_there(self) -> None:
        from pptx_agent_maker import __main__ as entry
        self.assertEqual(1, entry.main(["preview", "--places", str(self.root / "typo.toml"), "--no-open"]))


class _Stop(Exception):
    """Ends the watching loop from inside a test."""


class StartingAgainWhenTheToolkitMoves(unittest.TestCase):
    """The standing preview starts itself again once the toolkit on disk has changed and settled."""

    def _watch(self, prints: list) -> tuple[mock.Mock, int]:
        """(the stand-in for starting again, how many times the toolkit was looked at)."""
        from pptx_agent_maker import __main__ as entry
        with mock.patch.object(entry.time, "sleep"), \
                mock.patch.object(entry, "_fingerprint", side_effect=prints) as looked, \
                mock.patch.object(entry.os, "execv", side_effect=_Stop) as execv, \
                self.assertRaises(_Stop):
            entry._restart_when_changed("start")
        return execv, looked.call_count

    def test_it_starts_again_with_the_same_arguments_once_the_change_settles(self) -> None:
        execv, looked = self._watch(["writing", "written", "written"])
        execv.assert_called_once_with(sys.executable, sys.orig_argv)
        self.assertEqual(3, looked, "not while the files were still moving")

    def test_it_does_not_start_again_while_nothing_has_changed(self) -> None:
        execv, _looked = self._watch(["start", "start", _Stop()])
        execv.assert_not_called()

    def test_the_preview_s_own_files_count(self) -> None:
        from pptx_agent_maker import __main__ as entry
        with tempfile.TemporaryDirectory() as folder:
            module = Path(folder) / "pptx_live_preview" / "__init__.py"
            module.parent.mkdir()
            module.write_text("", encoding="utf-8")
            spec = mock.Mock(origin=str(module))
            with mock.patch.object(entry.importlib.util, "find_spec", return_value=spec):
                before = entry._fingerprint()
                module.write_text("changed = True\n", encoding="utf-8")
                self.assertNotEqual(before, entry._fingerprint())
