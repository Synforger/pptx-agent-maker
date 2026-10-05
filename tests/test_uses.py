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
        self.assertEqual([*USES, "detail"], [name for name, _sizes in theme.scales])

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
            self.assertIn(", ".join(repr(name) for name in (*USES, "detail")), str(refused.exception))

    def test_a_page_built_in_another_use_is_the_page_that_use_would_build(self) -> None:
        shown = theme_from({"use": "present"})
        self.assertEqual(Page("題は結論の文で書く").elements, Page("題は結論の文で書く", shown.using("read")).elements)
        self.assertNotEqual(Page("題は結論の文で書く").elements, Page("題は結論の文で書く", shown).elements)


class _Project(unittest.TestCase):
    """建てる (= 利用者と同じ入口) ための支え: 案件を作り、manifest を書いて建て、頁ごとの字の大きさを読む。"""

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


class BuiltByName(_Project):
    """資料と頁が使い方を名指し、検査の下限がそれに付いて行く。"""

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


SHEET = USES["sheet"]


class APageReadOnOneSheet(unittest.TestCase):
    """紙 1 枚で読ませる頁 (= `sheet`)。字と、字のまわりの余白・間隔が、同じ比で詰まる。

    字だけ小さくできた間は、余白と間隔が手元で読ませる資料の値のまま残り、どの箱も中身の倍の高さを
    取った ― 字を 10pt まで下げても、企画書 1 枚ぶんの中身は 1 頁に収まらなかった。
    """

    def test_its_type_is_three_quarters_of_a_deck_to_be_read_and_its_floor_is_lower(self) -> None:
        self.assertEqual((18, 12, 10, 9, 8), (SHEET.title, SHEET.heading, SHEET.stage, SHEET.body, SHEET.caption))
        self.assertEqual(8, SHEET.minimum)
        self.assertEqual(0.75, SHEET.body / READ.body)

    def test_what_stands_round_the_type_is_tightened_by_the_same_ratio(self) -> None:
        from pptx_agent_maker.layout.base.tokens import TIGHTENED, Spacing

        read, sheet = DEFAULT.spacing, DEFAULT.using("sheet").spacing
        for name in TIGHTENED:
            with self.subTest(name=name):
                self.assertEqual(round(getattr(read, name) * 0.75), getattr(sheet, name))
        for name in ("margin_x", "margin_top", "margin_bottom", "hairline", "strong_line"):
            with self.subTest(name=name):
                self.assertEqual(getattr(read, name), getattr(sheet, name), "the edge of the page and its lines stay")
        self.assertEqual(Spacing(), read)

    def test_a_deck_to_be_read_and_one_to_be_shown_keep_the_spacing_they_had(self) -> None:
        from pptx_agent_maker.layout.base.tokens import TIGHTENED

        read, shown = DEFAULT.spacing, DEFAULT.using("present").spacing
        for name in TIGHTENED:
            self.assertEqual(getattr(read, name), getattr(shown, name), name)

    def test_the_same_page_holds_more(self) -> None:
        """同じ形の頁 (= 3 列の箱、見出しと本文 1 行) に載る枚数: 映す 12 → 読ませる 15 → 紙 1 枚 21。"""
        from pptx_agent_maker.layout import types
        from pptx_agent_maker.layout.parts.page import PageFullError

        def most(theme) -> int:
            held = 0
            for count in range(3, 60, 3):
                cards = [{"heading": f"見出し {i}", "body": "本文の字が 1 行ぶん"} for i in range(count)]
                try:
                    types.build({"type": "cards", "title": "題", "card_columns": 3, "cards": cards},
                                lambda name: None, lambda path: 1.0, theme)
                except PageFullError:
                    break
                held = count
            return held

        self.assertEqual((12, 15, 21), tuple(most(DEFAULT.using(use)) for use in ("present", "read", "sheet")))

    def test_a_row_of_a_table_is_as_tall_as_its_line_and_its_tightened_padding(self) -> None:
        read, sheet = DEFAULT, DEFAULT.using("sheet")
        self.assertEqual(sheet.line_height() + 2 * sheet.spacing.cell_pad_y, sheet.table_row_height())
        self.assertLess(sheet.table_row_height(), read.table_row_height() * 0.8)


class AUseSetsItsOwnFloorAndSpacing(unittest.TestCase):
    """案件が名前を付けた使い方は、字の下限と、余白と間隔を自分で決められる。

    ⚠ **道具は幅を持たせ、使い方は道具が配る skill が縛る。**動かせる口は名前を付けた使い方にだけ在り、頁と
    資料は名前で選ぶだけ ― 同じ名前の頁は、どの資料でも同じ形になる。
    """

    @staticmethod
    def use(**said):
        return theme_from({"uses": {"proposal": {"like": "sheet", **said}}}).using("proposal")

    def refused(self, **said) -> str:
        with self.assertRaises(ThemeError) as stopped:
            self.use(**said)
        return str(stopped.exception)

    def test_a_floor_of_its_own_lets_its_type_go_under_the_one_it_is_like(self) -> None:
        proposal = self.use(floor=7, body=8, caption=7)
        self.assertEqual((7, 8, 7), (proposal.type.minimum, proposal.type.body, proposal.type.caption))
        self.assertIn("theme.uses.proposal.body is 7pt, below the 8pt floor of the use 'proposal'", self.refused(body=7))
        self.assertIn("below the 7pt floor", self.refused(floor=7, body=6.5))

    def test_a_floor_may_be_raised_and_everything_left_alone_must_clear_it(self) -> None:
        self.assertEqual(9, self.use(floor=9, caption=9).type.minimum)
        said = self.refused(floor=9)
        self.assertIn("theme.uses.proposal leaves caption at 8pt, below the 9pt floor", said)

    def test_a_floor_is_a_size_above_zero(self) -> None:
        for floor in (0, -1, "8", True):
            with self.subTest(floor=floor):
                self.assertIn("theme.uses.proposal.floor", self.refused(floor=floor))

    def test_scale_tightens_everything_together_from_a_deck_to_be_read(self) -> None:
        from pptx_agent_maker.layout.base.tokens import TIGHTENED

        read, half = DEFAULT.spacing, self.use(spacing={"scale": 0.5}).spacing
        for name in TIGHTENED:
            self.assertEqual(round(getattr(read, name) * 0.5), getattr(half, name), name)
        self.assertEqual(read.margin_x, half.margin_x)
        self.assertEqual(DEFAULT.using("sheet").spacing.pad, self.use().spacing.pad, "unsaid, that of the use it is like")
        self.assertEqual(read.pad, self.use(spacing={"scale": 1}).spacing.pad)

    def test_a_distance_written_by_itself_wins_over_the_scale(self) -> None:
        from pptx_agent_maker import cm

        proposal = self.use(spacing={"scale": 0.5, "pad": 0.1, "gap_m": 0.25, "margin_x": 0.8, "cell_pad_y": 0}).spacing
        self.assertEqual((cm(0.1), cm(0.25), cm(0.8), 0), (proposal.pad, proposal.gap_m, proposal.margin_x, proposal.cell_pad_y))
        self.assertEqual(round(DEFAULT.spacing.gap_s * 0.5), proposal.gap_s, "the others follow the scale")
        kept = self.use(spacing={"pad": 0.1}).spacing
        self.assertEqual(DEFAULT.using("sheet").spacing.gap_m, kept.gap_m, "with no scale said, that of the use it is like")

    def test_the_bands_still_follow_the_type(self) -> None:
        loose, tight = self.use().spacing, self.use(spacing={"scale": 0.4}).spacing
        self.assertEqual((loose.title_height, loose.band_height, loose.footer_height),
                         (tight.title_height, tight.band_height, tight.footer_height))

    def test_what_cannot_be_read_as_spacing_is_refused(self) -> None:
        for spacing, said in (({"padding": 0.1}, "theme.uses.proposal.spacing does not take padding"),
                              ({"title_height": 1}, "does not take title_height"),
                              ({"hairline": 0.1}, "does not take hairline"),
                              ({"pad": -0.1}, "theme.uses.proposal.spacing.pad is -0.1cm"),
                              ({"pad": "small"}, "theme.uses.proposal.spacing.pad is 'small'"),
                              ({"scale": 0}, "theme.uses.proposal.spacing.scale is 0"),
                              ({"scale": True}, "theme.uses.proposal.spacing.scale is True"),
                              (0.5, "theme.uses.proposal.spacing is a table")):
            with self.subTest(spacing=spacing):
                self.assertIn(said, self.refused(spacing=spacing))

    def test_the_projects_own_table_of_sizes_takes_neither(self) -> None:
        for key in ("floor", "spacing"):
            with self.subTest(key=key), self.assertRaises(ThemeError) as stopped:
                theme_from({"type": {key: 8}})
            self.assertIn(f"theme.type does not take {key}", str(stopped.exception))

    def test_a_use_may_be_like_the_sheet(self) -> None:
        self.assertEqual("proposal", self.use().use)
        self.assertEqual(SHEET.body, self.use().type.body)


class TightPagesBuilt(_Project):
    """建てる。紙 1 枚の頁が映す資料の途中に立ち、検査の下限がその頁の使い方に付いて行く。"""

    PROPOSAL = ('[theme.uses.proposal]\nlike = "sheet"\nfloor = 7\nbody = 8\ncaption = 7\n\n'
                '[theme.uses.proposal.spacing]\nscale = 0.5\npad = 0.1\n')

    def test_a_sheet_stands_in_the_middle_of_a_deck_made_to_be_shown(self) -> None:
        code, said, root = self.build('[theme]\nuse = "present"\n', self.page("映す頁") + self.page("紙 1 枚の頁", "sheet"))
        self.assertEqual(0, code, said)
        self.assertEqual([self.SHOWN, [SHEET.body, SHEET.heading, SHEET.title]], self.type_of(root))
        self.assertNotIn("FAIL", said, "the sheet is held to its own floor of 8pt")

    def test_a_page_in_a_use_with_a_floor_of_its_own_is_held_to_that_floor(self) -> None:
        from pptx_agent_maker.__main__ import _checks
        from pptx_agent_maker.deck.build import theme_of
        from pptx_agent_maker.project.files.manifest import Manifest
        from pptx_agent_maker.project.files.workspace import Workspace

        code, said, root = self.build('[theme]\nuse = "present"\n\n' + self.PROPOSAL,
                                      self.page("映す頁") + self.page("詰めた頁", "proposal"))
        self.assertEqual(0, code, said)
        self.assertEqual([self.SHOWN, [8, SHEET.heading, SHEET.title]], self.type_of(root))
        self.assertNotIn("FAIL", said)
        workspace, manifest = Workspace.load(root / "workspace.toml"), Manifest.load(root / "deck.toml")
        self.assertEqual({2: 7}, _checks(workspace, manifest, theme_of(workspace, manifest))["type_floor_of"])

    def test_the_words_of_a_tight_page_get_the_room_the_layout_counted(self) -> None:
        """詰めた使い方の頁は、文字の枠の左右の余白を数えたとおりに書く (= 書かなければ pptx の既定のままで、
        字の入る幅が数えたより狭く、狭い箱で見積もりより 1 行多く折れた)。読ませる頁は今までどおり何も書かない。"""
        code, said, root = self.build('[theme]\nuse = "present"\n\n' + self.PROPOSAL,
                                      self.page("読ませる頁", "read") + self.page("紙 1 枚の頁", "sheet")
                                      + self.page("詰めた頁", "proposal"))
        self.assertEqual(0, code, said)
        with zipfile.ZipFile(root / "deck.pptx") as archive:
            presentation = archive.read("ppt/presentation.xml").decode("utf-8")
            rels = archive.read("ppt/_rels/presentation.xml.rels").decode("utf-8")
            part = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="(slides/slide\d+\.xml)"', rels))
            pages = [archive.read(f"ppt/{part[rid]}").decode("utf-8")
                     for rid in re.findall(r'<p:sldId[^>]*r:id="(rId\d+)"', presentation)]

        def insets(page: str) -> set[tuple[str, str]]:
            boxes = [box for box in re.findall(r"<p:sp>.*?</p:sp>", page, re.S) if 'txBox="1"' in box]
            self.assertGreater(len(boxes), 3)
            return {(re.search(r'<a:bodyPr[^>]*?\blIns="(\d+)"', box) or [None, ""])[1]
                    + "/" + (re.search(r'<a:bodyPr[^>]*?\brIns="(\d+)"', box) or [None, ""])[1] for box in boxes}

        sheet = DEFAULT.using("sheet").spacing.text_inset
        tight = round(DEFAULT.spacing.text_inset * 0.5)
        self.assertEqual({"/"}, insets(pages[0]), "a page to be read writes none: the default is its own")
        self.assertEqual({f"{sheet}/{sheet}"}, insets(pages[1]))
        self.assertEqual({f"{tight}/{tight}"}, insets(pages[2]))

    def test_the_sheet_is_the_page_a_project_made_of_sheets_would_hold(self) -> None:
        def second_page(look: str, use: str | None) -> str:
            code, said, root = self.build(look, self.page("一枚目") + self.page("紙 1 枚の頁", use))
            self.assertEqual(0, code, said)
            with zipfile.ZipFile(root / "deck.pptx") as archive:
                presentation = archive.read("ppt/presentation.xml").decode("utf-8")
                rels = archive.read("ppt/_rels/presentation.xml.rels").decode("utf-8")
                part = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="(slides/slide\d+\.xml)"', rels))
                return archive.read(f"ppt/{part[re.findall(r'<p:sldId[^>]*r:id="(rId\d+)"', presentation)[1]]}").decode("utf-8")

        self.assertEqual(second_page('[theme]\nuse = "sheet"\n', None), second_page('[theme]\nuse = "present"\n', "sheet"))
        self.assertNotEqual(second_page("", None), second_page('[theme]\nuse = "present"\n', "sheet"))


if __name__ == "__main__":
    unittest.main()
