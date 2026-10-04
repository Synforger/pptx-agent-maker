"""Reading a deck as a story: its titles in order, a title that runs too long, data with no source.

⚠ **頁を 1 枚ずつ良くしても、並べて話が通るとは限らない。**ここの 3 つは、頁の割り方ではなく
話の側を見る ― 題だけを順に読む口と、題が長すぎる頁、出所を書いていないデータの頁。

後ろの 2 つは `build` を赤にする検査なので、**案件ごとに外せる**ことも一緒に見張る (= 外せない検査は、
道具を上げた日に既存の案件を止める)。
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))

from pptx_agent_maker.__main__ import main  # noqa: E402
from pptx_agent_maker.checks import declared, report, run_declared  # noqa: E402
from pptx_agent_maker.layout.base.tokens import DEFAULT  # noqa: E402
from pptx_agent_maker.project import create  # noqa: E402
from pptx_agent_maker.project.files.manifest import Manifest  # noqa: E402
from test_deck import make_dot  # noqa: E402

HEAD = 'specimen = "specimen.pptx"\nout = "deck.pptx"\n'
COVER = '[[pages]]\nkind = "copy"\npage = 1\nreplace = [["案件名", "The plan for the year"], ["第 N 回 進捗報告", "Round 3"]]\n'
#: 24pt で 1 行に入るのは全角 36 字ほど
ONE_LINE = "題は結論の文で書く"
TWO_LINES = "題は結論の文で書くので長くなりやすい。" * 3
THREE_LINES = "題は結論の文で書くので長くなりやすい。" * 5


def toml(value) -> str:
    """A value the way a manifest writes it (= tables inline, so a page stays one block)."""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{key} = {toml(item)}" for key, item in value.items()) + " }"
    if isinstance(value, list):
        return "[" + ", ".join(toml(item) for item in value) + "]"
    return json.dumps(value, ensure_ascii=False)


def page(**keys) -> str:
    return '[[pages]]\nkind = "declare"\n' + "".join(f"{key} = {toml(value)}\n" for key, value in keys.items())


class _Project(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project"
        create(self.root)
        shutil.copy(make_dot(), self.root / "assets" / "dot.png")

    def write(self, *pages: str, checks: str = "") -> Manifest:
        (self.root / "deck.toml").write_text(HEAD + "\n".join(pages), encoding="utf-8")
        settings = self.root / "workspace.toml"
        text = settings.read_text(encoding="utf-8")
        settings.write_text(text[:text.index("[checks]")] + "[checks]\nstale_words = [\"案件名\"]\n" + checks,
                            encoding="utf-8")
        return Manifest.load(self.root / "deck.toml")

    def run_cli(self, *argv: str) -> tuple[int, str]:
        said = io.StringIO()
        with contextlib.redirect_stdout(said), contextlib.redirect_stderr(said):
            code = main([argv[0], str(self.root), *argv[1:]])
        return code, said.getvalue()

    def found(self, manifest: Manifest, config: dict | None = None) -> list[tuple[str, int]]:
        return [(finding.check, finding.page) for finding in run_declared(manifest, DEFAULT, config or {})]


class TheTitlesInOrder(_Project):
    def setUp(self) -> None:
        super().setUp()
        self.write(COVER,
                   page(type="cards", kicker="01 | Where we are", title="Sales grew in every region",
                        cards=[["North", "up"]]),
                   page(type="cards", title="<to be worded>", cards=[["One", "a"]],
                        replace=[["<to be worded>", "The plan rests on two things"]]))

    def test_one_line_per_page_with_its_number_and_the_words_above_the_title(self) -> None:
        self.assertEqual(0, self.run_cli("build", "deck")[0])
        code, said = self.run_cli("titles", "deck")
        self.assertEqual(0, code)
        self.assertEqual(["  1  The plan for the year",
                          "  2  [01 | Where we are]  Sales grew in every region",
                          "  3  The plan rests on two things"], said.splitlines())

    def test_declared_pages_are_listed_before_anything_is_built(self) -> None:
        """宣言で組む頁の題は manifest に在る。複製した頁の題は、焼くまで読めないと言う。"""
        code, said = self.run_cli("titles", "deck")
        self.assertEqual(0, code)
        lines = said.splitlines()
        self.assertIn("build the deck", lines[0])
        self.assertEqual("  2  [01 | Where we are]  Sales grew in every region", lines[1])


class ATitleThatRunsTooLong(_Project):
    def test_three_lines_are_reported_with_the_page_and_two_are_not(self) -> None:
        manifest = self.write(page(type="cards", title=ONE_LINE, cards=[["a", "b"]]),
                              page(type="cards", title=TWO_LINES, cards=[["a", "b"]]),
                              page(type="cards", title=THREE_LINES, cards=[["a", "b"]]))
        self.assertEqual([("long_title", 3)], self.found(manifest))

    def test_the_lines_are_counted_at_the_size_the_title_is_set_in(self) -> None:
        """題の大きさが変われば、同じ文が折れる行も変わる (= 数え方を頁の組み方と別に持たない)。"""
        manifest = self.write(page(type="cards", title=TWO_LINES, cards=[["a", "b"]]))
        room = DEFAULT.frame().width - 2 * DEFAULT.spacing.text_inset
        self.assertEqual(2, DEFAULT.wraps(TWO_LINES, room, DEFAULT.type.title, bold=True),
                         "the sentence chosen does not sit on the boundary this test is about")
        self.assertEqual([], declared.long_title.run(manifest, DEFAULT, {}))

    def test_a_copied_page_is_left_to_the_check_of_the_built_deck(self) -> None:
        manifest = self.write(COVER.replace("The plan for the year", THREE_LINES))
        self.assertEqual([], self.found(manifest))

    def test_the_build_fails_and_names_the_check(self) -> None:
        self.write(page(type="cards", title=THREE_LINES, cards=[["a", "b"]]))
        code, said = self.run_cli("build", "deck")
        self.assertEqual(1, code)
        self.assertIn("page 1:", said)
        self.assertRegex(said, r"FAIL\s+long_title\s+1")

    def test_a_project_can_switch_it_off(self) -> None:
        self.write(page(type="cards", title=THREE_LINES, cards=[["a", "b"]]), checks="long_title = false\n")
        code, said = self.run_cli("build", "deck")
        self.assertEqual(0, code, said)


class DataWithNoSource(_Project):
    def test_a_picture_or_a_table_without_a_footer_is_reported(self) -> None:
        manifest = self.write(
            page(type="figure", title="A", figure="dot.png"),
            page(type="figure", title="B", figure="dot.png", footer="Source: the survey"),
            page(type="board", title="C", table=[["k", "v"], ["a", "1"]]),
            page(type="figures", title="D", figures=["dot.png", "dot.png"]),
            page(type="cards", title="E", cards=[["a", "b"]], table=[["k", "v"], ["a", "1"]]))
        self.assertEqual([("unsourced", 1), ("unsourced", 3), ("unsourced", 4), ("unsourced", 5)],
                         self.found(manifest))

    def test_a_page_that_shows_no_data_is_not_asked_for_a_source(self) -> None:
        """カードと図解 (= 流れ図・道のり・線表) は、どこかから持ってきた数字を見せていない。"""
        manifest = self.write(
            page(type="cards", title="A", cards=[{"heading": "a", "icon": "dot.png"}]),
            page(type="flow", title="B", stages=[{"name": "x", "nodes": [["a", "b"]]},
                                                 {"name": "y", "nodes": [["c", "d"]]}]),
            page(type="timeline", title="C", periods=["a", "b"],
                 lanes=[{"name": "L", "bars": [{"from": 0, "to": 1, "text": "t"}]}]),
            page(type="agenda", title="D", buckets=[["one", ["a"]]]))
        self.assertEqual([], self.found(manifest))

    def test_a_table_deep_inside_a_compose_is_found(self) -> None:
        cells = [{"cells": [{"card": ["a", "b"]}, {"rows": [{"cells": [{"table": [["k", "v"], ["a", "1"]]}]}]}]}]
        manifest = self.write(page(type="compose", title="A", rows=cells),
                              page(type="compose", title="B", rows=[{"cells": [{"card": ["a", "b"]}]}]))
        self.assertEqual([("unsourced", 1)], self.found(manifest))

    def test_a_copied_page_is_not_asked(self) -> None:
        self.assertEqual([], self.found(self.write(COVER)))

    def test_switching_it_off_leaves_the_other_check_on(self) -> None:
        pages = (page(type="figure", title=THREE_LINES, figure="dot.png"),)
        self.write(*pages)
        code, said = self.run_cli("build", "deck")
        self.assertEqual(1, code)
        self.assertRegex(said, r"FAIL\s+long_title\s+1")
        self.assertRegex(said, r"FAIL\s+unsourced\s+1")

        self.write(*pages, checks="unsourced = false\n")
        code, said = self.run_cli("build", "deck")
        self.assertEqual(1, code, "the title is still too long")
        self.assertRegex(said, r"FAIL\s+long_title\s+1")
        self.assertRegex(said, r"ok\s+unsourced\s+0")

    def test_a_built_deck_checked_alone_does_not_claim_what_it_cannot_see(self) -> None:
        """⚠ 焼いた deck だけを渡された `check` は、manifest を読む検査を回せない。回していない検査を
        「ok」と言うと、出所の無い頁が在っても緑に見える。"""
        self.write(page(type="figure", title="A", figure="dot.png", footer="Source: the survey"))
        self.assertEqual(0, self.run_cli("build", "deck")[0])
        code, said = self.run_cli("check", "deck")
        self.assertEqual(0, code)
        self.assertNotIn("unsourced", said)
        self.assertIn("long_title", said, "the half of this check that reads a built deck did run")
        self.assertIn("unsourced", report([], declared=True))

    def test_the_template_a_project_starts_from_passes_both(self) -> None:
        """`init` した直後の見本が、新しい検査で止まらない。"""
        code, said = self.run_cli("build", "example")
        self.assertEqual(0, code, said)


if __name__ == "__main__":
    unittest.main()
