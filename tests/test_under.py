"""A declared page knows the layout it will sit on.

型で組む頁は白紙に描いてから、テンプレートの 1 枚目のレイアウトへ向け直す。描く側がそのレイアウトを
知らなかった間は、2 つのことが起きた:

* **題がテンプレートの題の見た目にならない** ― レイアウトに題の枠が在るのに、題は自前の文字の枠として
  本文の色で書かれ、テンプレートから複製した頁の題と色が揃わなかった
* **題と札が、レイアウトのロゴに乗る** ― 題の帯は頁の幅いっぱいに取られ、右上のロゴに届いた題と、帯の
  右端に置かれる札が、重なりの検査で止まった (= 字の大きい、映す資料で先に出た)

見た目はテンプレートのもの、頁の割り方は道具のもの、という線は動かさない ― 題の位置と大きさは道具が決め、
色と書体をレイアウトから継ぐ。
"""

from __future__ import annotations

import contextlib
import io
import re
import sys
import tempfile
import unittest
import zipfile
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))

from support.templates import SHIPPED, TITLE_COLOUR, a_template  # noqa: E402

from pptx_agent_maker import DEFAULT, Page, Rect, cm  # noqa: E402
from pptx_agent_maker.__main__ import main  # noqa: E402
from pptx_agent_maker.project import create  # noqa: E402

#: 題の帯の右端に掛かるロゴ (= 頁の右上。帯は上の余白から 1.5cm)
LOGO = Rect(DEFAULT.slide.width - cm(1.2) - cm(2.5), cm(0.7), cm(2.5), cm(1.2))
ONE = "題は結論の文で書く"
#: ロゴが無ければ 1 行に収まり、ロゴの手前で止めると折れる長さ
NEARLY_FULL = "題" * 35


def placed(page: Page, kind: str) -> Rect:
    return next(e for e in page.elements if e.kind == kind).rect


class WhatTheLayoutHas(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_the_shipped_specimen_offers_no_title_and_prints_nothing(self) -> None:
        """同梱の見本の 1 枚目は表紙 (= 真ん中の題)。そこへ本文の頁の題を書かない。"""
        from pptx_agent_maker.deck.base.under import under_of
        from pptx_agent_maker.layout.base.tokens import Under

        self.assertEqual(Under(), under_of(SHIPPED))

    def test_a_content_layout_offers_its_title_and_says_what_it_prints(self) -> None:
        from pptx_agent_maker.deck.base.under import under_of

        under = under_of(a_template(self.dir / "t.pptx", logo=LOGO))
        self.assertTrue(under.title)
        self.assertIn(LOGO, under.prints)

    def test_a_layout_with_a_logo_and_no_title_placeholder_says_only_the_logo(self) -> None:
        from pptx_agent_maker.deck.base.under import under_of

        under = under_of(a_template(self.dir / "t.pptx", title=False, logo=LOGO))
        self.assertFalse(under.title)
        self.assertIn(LOGO, under.prints)

    def test_a_file_that_cannot_be_read_says_nothing(self) -> None:
        from pptx_agent_maker.deck.base.under import under_of
        from pptx_agent_maker.layout.base.tokens import Under

        self.assertEqual(Under(), under_of(self.dir / "not-there.pptx"))


class TheTitleBandKeepsOffWhatTheLayoutPrints(unittest.TestCase):
    @staticmethod
    def over(*prints: Rect):
        from pptx_agent_maker.layout.base.tokens import Under
        return replace(DEFAULT, under=Under(prints=tuple(prints)))

    def test_with_nothing_printed_the_band_is_the_frame(self) -> None:
        frame = DEFAULT.frame()
        self.assertEqual((1, frame.left, frame.right), DEFAULT.title_band(ONE))
        self.assertEqual(Page(ONE).elements, Page(ONE, self.over()).elements)

    def test_the_title_stops_short_of_a_logo_at_the_right(self) -> None:
        theme = self.over(LOGO)
        lines, left, right = theme.title_band(ONE)
        self.assertEqual((1, DEFAULT.frame().left, LOGO.left - DEFAULT.spacing.gap_s), (lines, left, right))
        self.assertEqual(right, placed(Page(ONE, theme), "title").right)

    def test_a_title_that_reached_the_logo_folds_before_it(self) -> None:
        self.assertEqual(1, DEFAULT.title_lines(NEARLY_FULL))
        theme = self.over(LOGO)
        self.assertEqual(2, theme.title_lines(NEARLY_FULL))
        page = Page(NEARLY_FULL, theme)
        self.assertEqual(Page("題" * 60).body, page.body, "the body starts under a band of two lines")

    def test_a_sticker_sits_before_the_logo(self) -> None:
        theme = self.over(LOGO)
        for kicker in ("", "01 | 背景"):
            with self.subTest(kicker=kicker):
                page = Page(ONE, theme, kicker=kicker, sticker="暫定")
                sticker, words = placed(page, "sticker"), placed(page, "title")
                self.assertEqual(LOGO.left - DEFAULT.spacing.gap_s, sticker.right)
                self.assertFalse(sticker.overlaps(LOGO))
                self.assertLess(words.right, sticker.left)

    def test_a_logo_at_the_left_moves_the_start_of_the_band(self) -> None:
        logo = Rect(DEFAULT.frame().left, cm(0.7), cm(2.5), cm(1.2))
        theme = self.over(logo)
        self.assertEqual(logo.right + DEFAULT.spacing.gap_s, theme.title_band(ONE)[1])
        page = Page(ONE, theme, kicker="01 | 背景")
        self.assertEqual(logo.right + DEFAULT.spacing.gap_s, placed(page, "title").left)
        self.assertEqual(logo.right + DEFAULT.spacing.gap_s, placed(page, "kicker").left)

    def test_what_is_printed_elsewhere_changes_nothing(self) -> None:
        frame = DEFAULT.frame()
        below = Rect(LOGO.left, frame.top + DEFAULT.spacing.title_height + cm(3), LOGO.width, LOGO.height)
        across = Rect(0, cm(0.7), DEFAULT.slide.width, cm(0.3))
        for name, thing in (("below the band", below), ("across the whole page", across)):
            with self.subTest(name):
                self.assertEqual(Page(ONE).elements, Page(ONE, self.over(thing)).elements)

    def test_a_logo_only_a_folded_title_reaches_is_kept_off_too(self) -> None:
        """帯は題が折れるぶん下へ伸びる。伸びた先に在る物も避ける (= 避けるとさらに折れることがある)。"""
        frame = DEFAULT.frame()
        lower = Rect(LOGO.left, frame.top + DEFAULT.spacing.title_height + cm(0.2), LOGO.width, cm(0.5))
        theme = self.over(lower)
        self.assertEqual(frame.right, theme.title_band(ONE)[2], "a title on one line never reaches it")
        folded = "題" * 60
        self.assertEqual(lower.left - DEFAULT.spacing.gap_s, theme.title_band(folded)[2])

    def test_the_line_under_the_band_stops_before_what_it_would_cross(self) -> None:
        frame = DEFAULT.frame()
        tall = Rect(LOGO.left, cm(0.7), LOGO.width, frame.top + DEFAULT.spacing.title_height)
        rule = placed(Page(ONE, self.over(tall)), "rule")
        self.assertFalse(rule.overlaps(tall))
        self.assertEqual(placed(Page(ONE), "rule"), placed(Page(ONE, self.over(LOGO)), "rule"))


class ALineAcrossThePage(unittest.TestCase):
    """⚠ **レイアウトが頁を横切って描く線** (= 題の下の罫線) **は、幅を詰めても避けられない。**題の帯は題が
    折れるぶん下へ伸びるが、レイアウトの線は動かない。2 行に折れた題の 2 行目が、その線の上に乗った
    (= 字の大きい、映す資料で出た。重なりの検査は細い線を数えない)。折れて増えた行が線に掛かる題は、
    縮めずに止める ― 直せるのは題の長さだけ。"""

    #: 1 行の題の下、2 行に折れた題の 2 行目が来る高さ
    @staticmethod
    def under_one_line(theme=DEFAULT) -> Rect:
        frame, row = theme.frame(), theme.line_height(theme.type.title)
        one = frame.top + (theme.spacing.title_height - row) // 2 + row
        return Rect(0, one + row // 2, theme.slide.width, 12700)

    @staticmethod
    def over(*prints: Rect, theme=DEFAULT):
        from pptx_agent_maker.layout.base.tokens import Under
        return replace(theme, under=Under(prints=tuple(prints)))

    FOLDED = "題" * 60

    def test_a_title_on_one_line_is_built_as_it_always_was(self) -> None:
        for kicker in ("", "01 | 背景"):
            with self.subTest(kicker=kicker):
                self.assertEqual(Page(ONE, kicker=kicker).elements,
                                 Page(ONE, self.over(self.under_one_line()), kicker=kicker).elements)

    def test_a_title_on_one_line_is_never_stopped_whatever_runs_under_it(self) -> None:
        """題を短くしても直らない頁を、ここで止めない。1 行の題の字のすぐ下から太い物が頁を横切っていても、
        止まるのは折れた題だけ。"""
        from pptx_agent_maker import PageFullError

        frame, row = DEFAULT.frame(), DEFAULT.line_height(DEFAULT.type.title)
        end = frame.top + (DEFAULT.spacing.title_height - row) // 2 + row     # 1 行の題の字の下端
        thick = Rect(0, end - row // 4, DEFAULT.slide.width, row)
        self.assertTrue(Page(ONE, self.over(thick)).elements)
        with self.assertRaises(PageFullError):
            Page(self.FOLDED, self.over(thick))

    def test_a_title_that_folds_onto_the_line_stops_and_says_what_to_do(self) -> None:
        from pptx_agent_maker import PageFullError

        with self.assertRaises(PageFullError) as stopped:
            Page(self.FOLDED, self.over(self.under_one_line()))
        said = str(stopped.exception)
        self.assertIn("2 lines", said)
        self.assertIn("shorter", said)

    def test_it_stops_wherever_the_small_words_stand(self) -> None:
        from pptx_agent_maker import PageFullError
        from pptx_agent_maker.layout.base.tokens import theme_from

        for settings in ({}, {"kicker": "beside"}, {"use": "present", "kicker": "beside", "type": {"title": 25}}):
            theme = theme_from(settings) if settings else DEFAULT
            with self.subTest(settings=settings):
                page = Page(ONE, self.over(self.under_one_line(theme), theme=theme), kicker="01 | 背景")
                self.assertTrue(page.elements)
                if theme.kicker == "above":
                    continue   # 上に小さい字を置く頁は、題が下の段に寄るので別の高さで確かめる
                with self.assertRaises(PageFullError):
                    Page(self.FOLDED, self.over(self.under_one_line(theme), theme=theme), kicker="01 | 背景")

    def test_a_line_under_everything_the_title_folds_to_changes_nothing(self) -> None:
        frame = DEFAULT.frame()
        low = Rect(0, frame.top + DEFAULT.spacing.title_height + 3 * DEFAULT.line_height(DEFAULT.type.title),
                   DEFAULT.slide.width, 12700)
        self.assertEqual(Page(self.FOLDED).elements, Page(self.FOLDED, self.over(low)).elements)

    def test_a_short_line_at_one_side_is_kept_off_like_a_logo_and_does_not_stop_the_page(self) -> None:
        across = self.under_one_line()
        short = Rect(LOGO.left, across.top, LOGO.width, across.height)
        page = Page(self.FOLDED, self.over(short))
        self.assertLessEqual(placed(page, "title").right, short.left)

    def test_the_layouts_lines_are_read_however_they_are_written(self) -> None:
        from pptx_agent_maker.deck.base.under import under_of

        across = Rect(DEFAULT.frame().left, self.under_one_line().top, DEFAULT.frame().width, 12700)
        with tempfile.TemporaryDirectory() as tmp:
            for how in ("connector", "flat"):
                with self.subTest(how=how):
                    prints = under_of(a_template(Path(tmp) / f"{how}.pptx", line=across, line_as=how)).prints
                    self.assertEqual(1, len(prints), prints)
                    line = prints[0]
                    self.assertEqual((across.left, across.width), (line.left, line.width))
                    self.assertTrue(line.top <= across.top <= line.bottom)
                    self.assertGreater(line.height, 0)
            self.assertEqual((), under_of(a_template(Path(tmp) / "unseen.pptx", line=across, line_as="unseen")).prints,
                             "a shape that draws no line prints nothing")


class TheTitleIsTheLayoutsTitle(unittest.TestCase):
    """題は、レイアウトに題の枠が在れば、その枠として書く (= 色と書体を継ぐ。位置と大きさは道具が書く)。"""

    @staticmethod
    def baked(theme) -> list[str]:
        from pptx_agent_maker.write import add_page, new_deck, save

        with tempfile.TemporaryDirectory() as tmp:
            deck = new_deck(theme)
            page = Page(ONE, theme, kicker="01 | 背景", needs_figure=False)
            add_page(deck, page.build(), theme)
            with zipfile.ZipFile(save(deck, Path(tmp) / "one.pptx")) as archive:
                xml = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        return re.findall(r"<p:sp>.*?</p:sp>", xml, re.S)

    def test_the_title_is_a_title_placeholder_that_says_where_and_how_large(self) -> None:
        from pptx_agent_maker.layout.base.tokens import Under

        shapes = self.baked(replace(DEFAULT, under=Under(title=True)))
        titles = [s for s in shapes if '<p:ph type="title"/>' in s]
        self.assertEqual(1, len(titles))
        title = titles[0]
        self.assertIn(f">{ONE}<", title)
        self.assertRegex(title, r'<a:off x="\d+" y="\d+"/>')
        self.assertIn(f'sz="{int(DEFAULT.type.title * 100)}"', title)
        self.assertIn("<a:noAutofit/>", title)
        self.assertIn('anchor="ctr"', title)
        self.assertRegex(title, r'lIns="\d+"')
        self.assertIn('algn="l"', title)
        self.assertNotIn('txBox="1"', title)

    def test_it_writes_no_colour_no_typeface_and_no_weight_of_its_own(self) -> None:
        from pptx_agent_maker.layout.base.tokens import Under

        title = next(s for s in self.baked(replace(DEFAULT, under=Under(title=True))) if "<p:ph" in s)
        for own in ("<a:solidFill>", "<a:latin", ' b="', "<a:noFill/>"):
            self.assertNotIn(own, title, own)

    def test_only_the_title_becomes_a_placeholder(self) -> None:
        from pptx_agent_maker.layout.base.tokens import Under

        shapes = self.baked(replace(DEFAULT, under=Under(title=True)))
        self.assertEqual(1, sum("<p:ph" in s for s in shapes))
        kicker = next(s for s in shapes if ">01 | 背景<" in s)
        self.assertIn("<a:solidFill>", kicker)

    def test_without_a_title_in_the_layout_the_title_is_written_as_it_always_was(self) -> None:
        shapes = self.baked(DEFAULT)
        self.assertFalse(any("<p:ph" in s for s in shapes))
        title = next(s for s in shapes if f">{ONE}<" in s)
        self.assertIn(f'<a:srgbClr val="{DEFAULT.palette.ink}"/>', title)
        self.assertIn(' b="1"', title)


class BuiltOnATemplateOfItsOwn(unittest.TestCase):
    """建てて焼く (= 利用者と同じ入口)。題はテンプレートの題の枠に乗り、題も札もロゴに掛からない。"""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def build(self, look: str, **template) -> tuple[int, str, Path]:
        root = self.dir / f"project-{len(list(self.dir.iterdir()))}"
        create(root, specimen=a_template(self.dir / f"{root.name}.pptx", **template))
        settings = root / "workspace.toml"
        settings.write_text(settings.read_text(encoding="utf-8") + "\n" + look, encoding="utf-8")
        (root / "deck.toml").write_text(
            'specimen = "specimen.pptx"\nout = "deck.pptx"\n\n'
            '[[pages]]\nkind = "declare"\ntype = "figure"\nkicker = "01 | 背景"\nsticker = "暫定"\n'
            f'title = "{"題は結論の文で書くので長い" * 2}"\n'
            'figure = "example.png"\nfooter = "出所 (= 見本)"\n', encoding="utf-8")
        (root / "assets" / "deck").mkdir(parents=True)
        (root / "assets" / "deck" / "example.png").write_bytes(
            (root / "assets" / "example" / "example.png").read_bytes())
        said = io.StringIO()
        with contextlib.redirect_stdout(said), contextlib.redirect_stderr(said):
            code = main(["build", str(root), "deck"])
        return code, said.getvalue(), root / "deck.pptx"

    def test_a_long_title_and_a_sticker_keep_off_the_logo_whatever_the_deck_is_for(self) -> None:
        for look in ('[theme]\nuse = "read"\n', '[theme]\nuse = "present"\n'):
            with self.subTest(look=look):
                code, said, _deck = self.build(look, logo=LOGO)
                self.assertEqual(0, code, said)
                self.assertNotIn("FAIL", said)

    def test_the_title_takes_the_colour_of_the_templates_title(self) -> None:
        code, said, deck = self.build("", logo=LOGO)
        self.assertEqual(0, code, said)
        with zipfile.ZipFile(deck) as archive:
            slide = archive.read("ppt/slides/slide2.xml").decode("utf-8")
            rels = archive.read("ppt/slides/_rels/slide2.xml.rels").decode("utf-8")
            layout = archive.read("ppt/slideLayouts/slideLayout1.xml").decode("utf-8")
        self.assertIn("slideLayout1.xml", rels)
        self.assertIn(TITLE_COLOUR, layout)
        title = next(s for s in re.findall(r"<p:sp>.*?</p:sp>", slide, re.S) if '<p:ph type="title"/>' in s)
        self.assertIn("題は結論の文で書くので長い", title)
        self.assertNotIn("<a:solidFill>", title)

    def test_a_title_folded_onto_the_layouts_line_stops_the_build_and_says_which_page(self) -> None:
        line = ALineAcrossThePage.under_one_line()
        across = Rect(DEFAULT.frame().left, line.top, DEFAULT.frame().width, 12700)
        def built(title: str, how: str) -> tuple[int, str]:
            root = self.dir / f"line-{how}-{len(title)}"
            create(root, specimen=a_template(self.dir / f"{root.name}.pptx", line=across, line_as=how))
            (root / "deck.toml").write_text(
                'specimen = "specimen.pptx"\nout = "deck.pptx"\n\n'
                f'[[pages]]\nkind = "declare"\ntype = "figure"\ntitle = "{title}"\n'
                'figure = "example.png"\nfooter = "出所 (= 見本)"\n', encoding="utf-8")
            (root / "assets" / "deck").mkdir(parents=True)
            (root / "assets" / "deck" / "example.png").write_bytes(
                (root / "assets" / "example" / "example.png").read_bytes())
            said = io.StringIO()
            with contextlib.redirect_stdout(said), contextlib.redirect_stderr(said):
                code = main(["build", str(root), "deck"])
            return code, said.getvalue()

        for how in ("connector", "flat"):
            with self.subTest(how=how):
                code, said = built("題" * 60, how)
                self.assertNotEqual(0, code)
                self.assertIn("page 1", said)
                self.assertIn("shorter", said)
                code, said = built(ONE, how)
                self.assertEqual(0, code, said)
                self.assertNotIn("FAIL", said)

    def test_a_title_past_two_lines_is_said_once(self) -> None:
        """題の枠に書いた題は、焼いた deck の側の検査にも題として見える。宣言の頁の題を数えるのは宣言の
        側の 1 か所 (= 帯の高さを取るのと同じ数) で、同じ頁を 2 度言わない。"""
        root = self.dir / "three-lines"
        create(root, specimen=a_template(self.dir / "three-lines.pptx", logo=LOGO))
        (root / "deck.toml").write_text(
            'specimen = "specimen.pptx"\nout = "deck.pptx"\n\n'
            '[[pages]]\nkind = "declare"\ntype = "figure"\n'
            f'title = "{"題は結論の文で書くので長くなりやすい。" * 5}"\n'
            'figure = "example.png"\nfooter = "出所 (= 見本)"\n', encoding="utf-8")
        (root / "assets" / "deck").mkdir(parents=True)
        (root / "assets" / "deck" / "example.png").write_bytes(
            (root / "assets" / "example" / "example.png").read_bytes())
        said = io.StringIO()
        with contextlib.redirect_stdout(said), contextlib.redirect_stderr(said):
            main(["build", str(root), "deck"])
        self.assertRegex(said.getvalue(), r"FAIL\s+long_title\s+1\b", said.getvalue())


if __name__ == "__main__":
    unittest.main()
