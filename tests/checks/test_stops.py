"""A check that sets `STOPS = False` is told in the report and does not end a `build` or a `check` with 1.

`untoned_cards` and `near_alignment` are for a person to look at: forgetting a colour's name is a matter of
taste, and a small miss is theirs to decide on. Every other check still ends the run with 1.
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))

from pptx_agent_maker.__main__ import main  # noqa: E402
from pptx_agent_maker.checks import CHECKS, DECLARED, Finding, report, stopping  # noqa: E402
from pptx_agent_maker.checks.declared import untoned_cards  # noqa: E402
from pptx_agent_maker.checks.rules import near_alignment  # noqa: E402
from pptx_agent_maker.project import create  # noqa: E402
from support.templates import a_template  # noqa: E402

QUIET = (near_alignment, untoned_cards)
AGENDA = ('[[pages]]\nkind = "declare"\ntype = "agenda"\ntitle = "Agenda"\nlook = "cards"\n'
          'buckets = [["First", ["a"]], ["Second", ["b"]]]\nhighlight = 1\n')
UNTONED = ('[[pages]]\nkind = "declare"\ntype = "cards"\ntitle = "Cards"\nno_figure = "a test of the report"\n'
           'cards = [{ heading = "A", tone = "Deep" }, { heading = "B" }]\n')


class WhichChecksStop(unittest.TestCase):
    def test_the_two_checks_for_a_person_to_look_at_do_not_stop_and_the_rest_do(self) -> None:
        quiet = {check.NAME for check in (*CHECKS, *DECLARED) if not getattr(check, "STOPS", True)}
        self.assertEqual({check.NAME for check in QUIET}, quiet)

    def test_a_hit_of_a_quiet_check_is_not_a_stop_and_any_other_is(self) -> None:
        told = Finding("untoned_cards", 1, "Cards", "1 card with no `tone`")
        for check in ("near_alignment", "long_title", "section_agenda"):
            with self.subTest(check=check):
                hit = Finding(check, 1, "x", "y")
                self.assertEqual([] if check == "near_alignment" else [hit], stopping([hit]))
        self.assertEqual([], stopping([told]))
        self.assertEqual([Finding("overlap", 1, "x", "y")], stopping([told, Finding("overlap", 1, "x", "y")]))

    def test_the_report_marks_a_quiet_hit_as_a_note_and_a_stopping_one_as_a_fail(self) -> None:
        said = report([Finding("near_alignment", 1, "a and b", "their top edges miss by 0.30 mm — line them up"),
                       Finding("long_title", 2, "a title", "too long")], declared=True)
        self.assertIn("a and b  <- their top edges miss by 0.30 mm", said)
        self.assertRegex(said, r"note\s+near_alignment\s+1")
        self.assertRegex(said, r"FAIL\s+long_title\s+1")
        self.assertRegex(report([], declared=True), r"ok\s+near_alignment\s+0")


class TheBuildAndTheCheck(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        create(self.root, specimen=a_template(Path(self.tmp.name) / "t.pptx"))
        settings = self.root / "workspace.toml"
        settings.write_text(settings.read_text(encoding="utf-8") + '\n[theme.grounds]\nDeep = "8B1E3F"\n',
                            encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_main(self, *args: str) -> tuple[int, str]:
        said = io.StringIO()
        with contextlib.redirect_stdout(said), contextlib.redirect_stderr(said):
            code = main(list(args))
        return code, said.getvalue()

    def build(self, pages: str) -> tuple[int, str]:
        (self.root / "deck.toml").write_text(f'specimen = "specimen.pptx"\nout = "deck.pptx"\n{pages}', encoding="utf-8")
        return self.run_main("build", str(self.root), "deck")

    def test_a_deck_whose_only_hit_is_a_card_with_no_tone_builds_with_0_and_says_so(self) -> None:
        code, said = self.build(AGENDA + UNTONED)
        self.assertRegex(said, r"page 2: Cards  <- 1 card with no `tone`")
        self.assertRegex(said, r"note\s+untoned_cards\s+1")
        self.assertNotIn("FAIL", said)
        self.assertEqual(0, code, said)

    def test_a_deck_that_a_stopping_check_hits_still_ends_with_1_beside_a_quiet_hit(self) -> None:
        code, said = self.build(UNTONED)          # no agenda page: `section_agenda` stops it
        self.assertRegex(said, r"note\s+untoned_cards\s+1")
        self.assertRegex(said, r"FAIL\s+section_agenda\s+1")
        self.assertEqual(1, code, said)

    def test_the_check_command_ends_with_0_on_a_deck_that_only_a_quiet_check_hits(self) -> None:
        self.build(AGENDA + UNTONED)
        code, said = self.run_main("check", str(self.root), "deck")
        self.assertEqual(0, code, said)


if __name__ == "__main__":
    unittest.main()
