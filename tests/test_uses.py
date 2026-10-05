"""The size of the type is picked by name: by the project, by a deck, and by a page.

字の大きさは「資料の使い方」(= `use`) でまとめて決まる。案件が 1 つ選ぶだけだった間は、映して話す資料の
途中に、情報を詰めた 1 枚 (= 手元で読ませる大きさの頁) を挟めなかった ― 資料を丸ごと小さい字にするか、
その 1 枚を諦めるかの 2 択だった。

* **選ぶ所は 3 段** ― 案件 (= `[theme] use`) → 資料 (= manifest の `use`) → 頁 (= `[[pages]]` の `use`)。
  内側が勝つ
* **選べるのは使い方の名前だけ** ― 頁に大きさそのものは書けない。同じ使い方の頁どうしは必ず揃う
* **案件は自分の使い方を名前付きで足せる** (= `[theme.uses.<名前>]`。道具の使い方のどれに倣うかと、
  変える役の大きさ)
* **検査の字の下限は、その頁の使い方のもの**
"""

from __future__ import annotations

import contextlib
import io
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))

from pptx_agent_maker import DEFAULT, Page  # noqa: E402
from pptx_agent_maker.__main__ import main  # noqa: E402
from pptx_agent_maker.layout.base.tokens import USES, ThemeError, Under, theme_from  # noqa: E402
from pptx_agent_maker.project import create  # noqa: E402

READ, PRESENT = USES["read"], USES["present"]
DETAIL = '[theme.uses.detail]\nlike = "read"\nheading = 14\nbody = 11\n'


def sizes(theme) -> tuple[float, ...]:
    return (theme.type.title, theme.type.heading, theme.type.stage, theme.type.body, theme.type.caption)


class AProjectNamesUsesOfItsOwn(unittest.TestCase):
    def test_a_named_use_starts_from_the_one_it_is_like_and_changes_what_it_says(self) -> None:
        theme = theme_from({"uses": {"detail": {"like": "read", "heading": 14, "body": 11}}})
        detail = dict(theme.scales)["detail"]
        self.assertEqual((READ.title, 14, READ.stage, 11, READ.caption),
                         (detail.title, detail.heading, detail.stage, detail.body, detail.caption))
        self.assertEqual(READ.minimum, detail.minimum, "the floor is the one of the use it is like")
        self.assertEqual(["read", "present", "detail"], [name for name, _sizes in theme.scales])

    def test_the_project_may_make_its_own_use_one_it_named(self) -> None:
        theme = theme_from({"use": "detail", "uses": {"detail": {"like": "present", "body": 16}}})
        self.assertEqual("detail", theme.use)
        self.assertEqual((PRESENT.title, 16), (theme.type.title, theme.type.body))

    def test_what_theme_type_says_is_laid_over_the_projects_own_use_and_no_other(self) -> None:
        theme = theme_from({"use": "present", "type": {"body": 20}})
        self.assertEqual(20, theme.type.body)
        self.assertEqual(READ.body, theme.using("read").type.body)
        self.assertEqual(20, theme.using("read").using("present").type.body, "and it is there on the way back")

    def test_a_use_cannot_take_a_name_the_toolkit_uses(self) -> None:
        for name in USES:
            with self.subTest(name=name), self.assertRaises(ThemeError) as refused:
                theme_from({"uses": {name: {"like": "read"}}})
            self.assertIn("toolkit's own", str(refused.exception))

    def test_a_use_says_which_of_the_toolkits_it_is_like(self) -> None:
        for said in ({}, {"like": "detail"}, {"like": 3}, {"body": 11}):
            with self.subTest(said=said), self.assertRaises(ThemeError) as refused:
                theme_from({"uses": {"detail": said}})
            self.assertIn("theme.uses.detail.like", str(refused.exception))

    def test_a_size_below_the_floor_of_what_it_is_like_is_refused(self) -> None:
        with self.assertRaises(ThemeError) as refused:
            theme_from({"uses": {"tiny": {"like": "read", "body": 9}}})
        self.assertIn("theme.uses.tiny.body is 9pt, below the 10pt floor", str(refused.exception))
        with self.assertRaises(ThemeError) as refused:
            theme_from({"uses": {"shown": {"like": "present", "body": 12}}})
        self.assertIn("below the 14pt floor", str(refused.exception))
        self.assertEqual(14, dict(theme_from({"uses": {"shown": {"like": "present", "body": 14}}}).scales)["shown"].body)

    def test_a_role_nobody_sets_and_a_shape_that_is_not_a_table_are_refused(self) -> None:
        for uses, said in (({"detail": {"like": "read", "marker": 20}}, "theme.uses.detail does not take marker"),
                           ({"detail": "read"}, "theme.uses.detail is a table"),
                           ("detail", "theme.uses is a table"),
                           ({"detail": {"like": "read", "body": "small"}}, "theme.uses.detail.body is 'small'")):
            with self.subTest(uses=uses), self.assertRaises(ThemeError) as refused:
                theme_from({"uses": uses})
            self.assertIn(said, str(refused.exception))

    def test_a_project_that_names_a_use_it_does_not_know_is_refused(self) -> None:
        with self.assertRaises(ThemeError) as refused:
            theme_from({"use": "detail"})
        self.assertIn("theme.use is 'detail'", str(refused.exception))


class ALookInAnotherUse(unittest.TestCase):
    def test_it_takes_the_sizes_and_the_bands_of_that_use_and_keeps_the_rest(self) -> None:
        under = Under(title=True)
        from dataclasses import replace
        shown = replace(theme_from({"use": "present", "font": "Arial", "palette": {"accent": "112233"}}), under=under)
        read = shown.using("read")
        self.assertEqual(sizes(DEFAULT), sizes(read))
        self.assertEqual(DEFAULT.spacing, read.spacing, "the bands are as tall as the type that sits in them")
        self.assertLess(read.spacing.title_height, shown.spacing.title_height)
        self.assertEqual(("read", "Arial", "112233", under), (read.use, read.type.family, read.palette.accent, read.under))
        self.assertEqual(shown.scales, read.scales, "it still knows every use, to turn back")
        self.assertEqual(shown, read.using("present"))

    def test_naming_its_own_use_or_none_changes_nothing(self) -> None:
        theme = theme_from({"use": "present"})
        self.assertIs(theme, theme.using(None))
        self.assertIs(theme, theme.using("present"))
        self.assertIs(DEFAULT, DEFAULT.using("read"))

    def test_a_use_the_project_does_not_know_is_refused_with_the_ones_it_knows(self) -> None:
        theme = theme_from({"uses": {"detail": {"like": "read"}}})
        for use in ("dense", "", 12, "Read"):
            with self.subTest(use=use), self.assertRaises(ThemeError) as refused:
                theme.using(use)
            self.assertIn("'read', 'present', 'detail'", str(refused.exception))

    def test_a_page_built_in_another_use_is_the_page_that_use_would_build(self) -> None:
        shown = theme_from({"use": "present"})
        self.assertEqual(Page("題は結論の文で書く").elements, Page("題は結論の文で書く", shown.using("read")).elements)
        self.assertNotEqual(Page("題は結論の文で書く").elements, Page("題は結論の文で書く", shown).elements)


class BuiltByName(unittest.TestCase):
    """建てる (= 利用者と同じ入口)。資料と頁が使い方を名指し、検査の下限がそれに付いて行く。"""

    CARDS = ('card_columns = 2\ncards = [\n  { heading = "見出し", body = "本文の字" },\n'
             '  { heading = "二つめ", body = "本文の字" },\n]\n\n')

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def page(self, title: str, use: str | None = None) -> str:
        said = f'use = "{use}"\n' if use else ""
        return f'[[pages]]\nkind = "declare"\ntype = "cards"\n{said}title = "{title}"\n' + self.CARDS

    def project(self, look: str, checks: str = "") -> Path:
        """A project whose `workspace.toml` says `look`, with `checks` added to the checks it already asks for."""
        root = self.dir / f"project-{len(list(self.dir.iterdir()))}"
        create(root)
        settings = root / "workspace.toml"
        text = settings.read_text(encoding="utf-8")
        self.assertEqual(1, text.count("\n[checks]\n"))
        settings.write_text(text.replace("\n[checks]\n", "\n[checks]\n" + checks) + "\n" + look, encoding="utf-8")
        return root

    def run_in(self, root: Path, *argv: str) -> tuple[int, str]:
        said = io.StringIO()
        with contextlib.redirect_stdout(said), contextlib.redirect_stderr(said):
            code = main([argv[0], str(root), *argv[1:]])
        return code, said.getvalue()

    def build(self, look: str, pages: str, head: str = "", checks: str = "") -> tuple[int, str, Path]:
        root = self.project(look, checks)
        (root / "deck.toml").write_text(f'specimen = "specimen.pptx"\nout = "deck.pptx"\n{head}\n' + pages,
                                        encoding="utf-8")
        code, said = self.run_in(root, "build", "deck")
        return code, said, root

    @staticmethod
    def type_of(root: Path) -> list[list[float]]:
        """The sizes of the type on each page of the built deck, in reading order."""
        with zipfile.ZipFile(root / "deck.pptx") as archive:
            presentation = archive.read("ppt/presentation.xml").decode("utf-8")
            rels = archive.read("ppt/_rels/presentation.xml.rels").decode("utf-8")
            part = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="(slides/slide\d+\.xml)"', rels))
            return [sorted({int(size) / 100 for size in re.findall(
                        r'<a:rPr[^>]*\bsz="(\d+)"', archive.read(f"ppt/{part[rid]}").decode("utf-8"))})
                    for rid in re.findall(r'<p:sldId[^>]*r:id="(rId\d+)"', presentation)]

    SHOWN = [PRESENT.body, PRESENT.heading, PRESENT.title]
    TO_READ = [READ.body, READ.heading, READ.title]

    def test_a_page_to_be_read_stands_in_the_middle_of_a_deck_made_to_be_shown(self) -> None:
        code, said, root = self.build('[theme]\nuse = "present"\n',
                                      self.page("映す頁") + self.page("詰めた 1 枚", "read") + self.page("映す頁に戻る"))
        self.assertEqual(0, code, said)
        self.assertEqual([self.SHOWN, self.TO_READ, self.SHOWN], self.type_of(root))
        self.assertNotIn("FAIL", said, "the page to be read is held to its own floor, not the deck's")

    def test_the_page_is_the_one_a_deck_to_be_read_would_hold(self) -> None:
        """挟んだ頁は、読ませる資料で組んだ同じ頁と 1 字も違わない (= 表の行の高さも箱の余白も、その頁の
        大きさから出る)。資料の側の大きさが 1 つでも混ざれば、ここで食い違う。"""
        table = ('[[pages]]\nkind = "declare"\ntype = "cards"\n__USE__title = "表を持つ頁"\n' + self.CARDS.rstrip("\n")
                 + '\ntable = [["手法", "値"], ["A", "1"], ["B", "2"]]\nnote = "読み方の 1 行"\nfooter = "出所 (= 見本)"\n\n')

        def second_page(look: str, use: str) -> str:
            code, said, root = self.build(look, self.page("一枚目") + table.replace("__USE__", use))
            self.assertEqual(0, code, said)
            with zipfile.ZipFile(root / "deck.pptx") as archive:
                presentation = archive.read("ppt/presentation.xml").decode("utf-8")
                rels = archive.read("ppt/_rels/presentation.xml.rels").decode("utf-8")
                part = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="(slides/slide\d+\.xml)"', rels))
                rid = re.findall(r'<p:sldId[^>]*r:id="(rId\d+)"', presentation)[1]
                return archive.read(f"ppt/{part[rid]}").decode("utf-8")

        inside_a_shown_deck = second_page('[theme]\nuse = "present"\n', 'use = "read"\n')
        in_a_deck_to_be_read = second_page("", "")
        self.assertIn("<a:tbl>", in_a_deck_to_be_read)
        self.assertEqual(in_a_deck_to_be_read, inside_a_shown_deck)
        self.assertNotEqual(in_a_deck_to_be_read, second_page('[theme]\nuse = "present"\n', ""))

    def test_a_page_may_name_a_use_the_project_named(self) -> None:
        code, said, root = self.build('[theme]\nuse = "present"\n\n' + DETAIL,
                                      self.page("映す頁") + self.page("案件の大きさの頁", "detail"))
        self.assertEqual(0, code, said)
        self.assertEqual([self.SHOWN, [11, 14, READ.title]], self.type_of(root))
        self.assertNotIn("FAIL", said)

    def test_a_deck_names_its_use_and_a_page_inside_it_another(self) -> None:
        """案件は読ませる資料。この資料だけ映す (= サブデッキ)。その中の 1 枚がまた読ませる頁。"""
        code, said, root = self.build("", self.page("映す頁") + self.page("詰めた 1 枚", "read"), 'use = "present"\n')
        self.assertEqual(0, code, said)
        self.assertEqual([self.SHOWN, self.TO_READ], self.type_of(root))
        self.assertNotIn("FAIL", said)

    def test_a_deck_that_names_nothing_is_set_in_the_projects_use(self) -> None:
        code, said, root = self.build('[theme]\nuse = "present"\n', self.page("映す頁"))
        self.assertEqual(0, code, said)
        self.assertEqual([self.SHOWN], self.type_of(root))

    def test_a_use_nobody_named_stops_the_build_and_says_where(self) -> None:
        code, said, _root = self.build("", self.page("一枚目") + self.page("二枚目", "dense"))
        self.assertNotEqual(0, code)
        self.assertIn("page 2", said)
        self.assertIn("`use` is 'dense'", said)
        code, said, _root = self.build("", self.page("一枚目"), 'use = "dense"\n')
        self.assertNotEqual(0, code)
        self.assertIn("deck.toml", said)
        self.assertIn("`use` is 'dense'", said)
        code, said, _root = self.build("", self.page("一枚目"), "use = 12\n")
        self.assertNotEqual(0, code)
        self.assertIn("names its use in words", said)

    def test_a_page_cannot_say_a_size_only_the_name_of_a_use(self) -> None:
        code, said, _root = self.build("", '[[pages]]\nkind = "declare"\ntype = "cards"\nbody = 10\ntitle = "題"\n'
                                       + self.CARDS)
        self.assertNotEqual(0, code)
        self.assertIn("does not take body", said)

    def test_a_copied_page_is_not_set_in_type_so_it_names_no_use(self) -> None:
        code, said, _root = self.build("", '[[pages]]\nkind = "copy"\npage = 1\nuse = "read"\n')
        self.assertNotEqual(0, code)
        self.assertIn("does not take use", said)

    def test_the_other_pages_of_a_shown_deck_are_still_held_to_its_floor(self) -> None:
        from pptx_agent_maker.checks.rules import type_floor

        code, said, root = self.build('[theme]\nuse = "present"\n', self.page("映す頁") + self.page("詰めた 1 枚", "read"))
        self.assertEqual(0, code, said)
        deck = root / "deck.pptx"
        self.assertEqual([], type_floor.run(deck, {"type_floor": 14, "type_floor_of": {2: 10}}))
        everywhere = type_floor.run(deck, {"type_floor": 14})
        self.assertEqual({2}, {finding.page for finding in everywhere}, "without its own floor the page is small")
        self.assertEqual({1, 2}, {finding.page for finding in type_floor.run(deck, {"type_floor": 30})} - {0})
        self.assertEqual({1}, {finding.page for finding in type_floor.run(deck, {"type_floor": 14, "type_floor_of": {1: 30, 2: 10}})})

    def test_only_the_pages_that_name_a_use_are_held_to_a_floor_of_their_own(self) -> None:
        """使い方を名指さない頁は資料の下限のまま (= 頁ごとの下限を持つのは、名指した頁だけ)。資料が自分の
        使い方を名指していれば、資料の下限はその使い方のもの。"""
        from pptx_agent_maker.__main__ import _checks
        from pptx_agent_maker.deck.build import theme_of
        from pptx_agent_maker.project.files.manifest import Manifest
        from pptx_agent_maker.project.files.workspace import Workspace

        _code, _said, root = self.build("", self.page("映す頁") + self.page("詰めた 1 枚", "read") + self.page("映す頁"),
                                        'use = "present"\n')
        workspace = Workspace.load(root / "workspace.toml")
        manifest = Manifest.load(root / "deck.toml")
        config = _checks(workspace, manifest, theme_of(workspace, manifest))
        self.assertEqual(PRESENT.minimum, config["type_floor"], "the deck's floor is that of the use it names")
        self.assertEqual({2: READ.minimum}, config["type_floor_of"])
        self.assertEqual(READ.minimum, _checks(workspace)["type_floor"], "with no deck named, the project's")

    def test_checking_a_built_deck_later_holds_each_page_to_the_same_floor(self) -> None:
        _code, _said, root = self.build('[theme]\nuse = "present"\n', self.page("映す頁") + self.page("詰めた 1 枚", "read"))
        code, said = self.run_in(root, "check", "deck")
        self.assertRegex(said, r"ok\s+type_floor\s+0", said)
        self.assertNotRegex(said, r"FAIL\s+type_floor")
        self.assertIsNotNone(code)

    def test_a_floor_the_project_writes_for_itself_holds_every_page(self) -> None:
        code, said, _root = self.build('[theme]\nuse = "present"\n', self.page("映す頁") + self.page("詰めた 1 枚", "read"),
                                       checks="type_floor = 14\n")
        self.assertRegex(said, r"FAIL\s+type_floor", said)
        self.assertNotEqual(0, code)

    def test_a_long_title_is_counted_in_the_size_of_its_own_page(self) -> None:
        """題の行は、その頁の題の大きさで数える (= 映す大きさで 3 行になる題が、読ませる頁では 2 行)。"""
        long = "題は結論の文で書くので長くなりやすい。" * 3 + "ここまで"
        shown = theme_from({"use": "present"})
        self.assertEqual((3, 2), (shown.title_lines(long), shown.using("read").title_lines(long)))
        code, said, _root = self.build('[theme]\nuse = "present"\n', self.page(long, "read"))
        self.assertNotRegex(said, r"FAIL\s+long_title", said)
        code, said, _root = self.build('[theme]\nuse = "present"\n', self.page(long))
        self.assertRegex(said, r"FAIL\s+long_title\s+1\b", said)


if __name__ == "__main__":
    unittest.main()
