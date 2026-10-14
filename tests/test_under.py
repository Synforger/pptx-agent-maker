"""A declared page knows the layout it will sit on.

型で組む頁は白紙に描いてから、テンプレートの 1 枚目のレイアウトへ向け直す。描く側がそのレイアウトを
知らなかった間は、2 つのことが起きた:

* **題がテンプレートの題の見た目にならない** ― レイアウトに題の枠が在るのに、題は自前の文字の枠として
  本文の色で書かれ、テンプレートから複製した頁の題と色が揃わなかった
* **題と札が、レイアウトのロゴに乗る** ― 題の帯は頁の幅いっぱいに取られ、右上のロゴに届いた題と、帯の
  右端に置かれる札が、重なりの検査で止まった (= 字の大きい、映す資料で先に出た)
* **型の頁にだけ頁番号が出ない** ― 頁に番号を振る資料で、テンプレートから複製した頁には番号が出て、
  型の頁には出なかった (= 道具が頁番号の枠を 1 つも置いていなかった)

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

from support.templates import NUMBER_IDX, SHIPPED, TITLE_COLOUR, a_template, with_a_cover  # noqa: E402

from pptx_agent_maker import DEFAULT, Page, Rect, cm  # noqa: E402
from pptx_agent_maker.__main__ import main  # noqa: E402
from pptx_agent_maker.project import create  # noqa: E402

#: 題の帯の右端に掛かるロゴ (= 頁の右上。帯は上の余白から 1.5cm)
LOGO = Rect(DEFAULT.slide.width - cm(1.2) - cm(2.5), cm(0.7), cm(2.5), cm(1.2))
ONE = "題は結論の文で書く"
#: ロゴが無ければ 1 行に収まり、ロゴの手前で止めると折れる長さ
NEARLY_FULL = "題" * 35
#: 同梱の見本のレイアウトが、頁番号の枠に付けている名乗り
NUMBER = (("type", "sldNum"), ("sz", "quarter"), ("idx", str(NUMBER_IDX)))


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

    def test_a_title_on_one_line_is_placed_as_it_always_was(self) -> None:
        """題と、題の上の小さい字は、線が在っても同じ所に置く。変わるのは線から下 (= `TheRestGoesOnUnderTheLine`)。"""
        for kicker in ("", "01 | 背景"):
            with self.subTest(kicker=kicker):
                plain, ruled = Page(ONE, kicker=kicker), Page(ONE, self.over(self.under_one_line()), kicker=kicker)
                for kind in ("title", "kicker") if kicker else ("title",):
                    self.assertEqual(placed(plain, kind), placed(ruled, kind), kind)

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

    def test_a_line_under_everything_the_title_folds_to_stops_nothing(self) -> None:
        frame = DEFAULT.frame()
        low = Rect(0, frame.top + DEFAULT.spacing.title_height + 3 * DEFAULT.line_height(DEFAULT.type.title),
                   DEFAULT.slide.width, 12700)
        self.assertEqual(placed(Page(self.FOLDED), "title"), placed(Page(self.FOLDED, self.over(low)), "title"))

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


class TheRestGoesOnUnderTheLine(unittest.TestCase):
    """題の帯の下に、レイアウトが頁を横切って描く線が残っていれば、頁はその下から続く。

    題の帯の高さは使い方で変わるが、レイアウトの線は動かない。字の小さい使い方の頁 (= 紙 1 枚の頁) は帯が低く、
    本文がテンプレートの罫線より上から始まって、箱が罫線に乗った (= 検査は細い線を数えない)。
    """

    @staticmethod
    def over(*prints: Rect, theme=DEFAULT):
        from pptx_agent_maker.layout.base.tokens import Under
        return replace(theme, under=Under(prints=tuple(prints)))

    @staticmethod
    def line(below_the_frame_top: int, theme=DEFAULT) -> Rect:
        return Rect(0, theme.frame().top + below_the_frame_top, theme.slide.width, 12700)

    def test_the_body_starts_under_a_line_left_below_the_band(self) -> None:
        line = self.line(DEFAULT.spacing.title_height + cm(0.4))
        page = Page(ONE, self.over(line))
        self.assertEqual(line.bottom + DEFAULT.spacing.gap_s, page.body.top)
        self.assertEqual(Page(ONE).body.bottom, page.body.bottom, "only the top of what is left moves")
        self.assertFalse(any(e.kind == "rule" for e in page.elements), "the line under the title is the layout's")

    def test_a_page_set_in_smaller_type_clears_a_line_drawn_for_a_larger_title(self) -> None:
        """実際に出た形: 映す資料のテンプレートの罫線は、映す大きさの題の帯のすぐ下に在る。そこへ紙 1 枚の
        頁を挟むと帯が低く、本文が罫線の上から始まった。"""
        shown = DEFAULT.using("present")
        line = self.line(shown.spacing.title_height)          # 映す資料の題の帯の下端に引かれた線
        for use in ("read", "sheet"):
            with self.subTest(use=use):
                page = Page(ONE, self.over(line, theme=shown.using(use)))
                self.assertGreaterEqual(page.body.top, line.bottom)
                self.assertFalse(any(e.rect.overlaps(line) for e in page.elements if e.kind != "title"))
        in_its_own_use = Page(ONE, self.over(line, theme=shown))
        self.assertEqual(Page(ONE, shown).elements, in_its_own_use.elements, "a line at the foot of the band moves nothing")

    def test_a_line_inside_the_band_or_above_it_changes_nothing(self) -> None:
        for name, line in (("inside the band", self.line(DEFAULT.spacing.title_height - cm(0.2))),
                           ("at the foot of the band", self.line(DEFAULT.spacing.title_height)),
                           ("in the gap under the band, with room to spare", self.line(DEFAULT.spacing.title_height + cm(0.1))),
                           ("at the top of the page", Rect(0, cm(0.3), DEFAULT.slide.width, 12700))):
            with self.subTest(name):
                self.assertEqual(Page(ONE).elements, Page(ONE, self.over(line)).elements)

    def test_what_reaches_the_lower_half_of_the_page_changes_nothing(self) -> None:
        low = Rect(0, DEFAULT.slide.height - cm(1.2), DEFAULT.slide.width, 12700)          # 出所の上の罫線
        ground = Rect(0, 0, DEFAULT.slide.width, DEFAULT.slide.height)                     # 頁を丸ごと覆う地
        tall = Rect(0, DEFAULT.frame().top + DEFAULT.spacing.title_height + cm(0.2), DEFAULT.slide.width,
                    DEFAULT.slide.height // 2)                                             # 上半分から下半分へ届く物
        for name, thing in (("a rule above the source", low), ("a ground over the page", ground), ("tall", tall)):
            with self.subTest(name):
                self.assertEqual(Page(ONE).body, Page(ONE, self.over(thing)).body)

    def test_a_short_line_at_one_side_changes_nothing_below(self) -> None:
        short = Rect(LOGO.left, DEFAULT.frame().top + DEFAULT.spacing.title_height + cm(0.4), LOGO.width, 12700)
        self.assertEqual(Page(ONE).body, Page(ONE, self.over(short)).body)

    def test_a_block_over_the_title_that_ends_under_the_band_is_cleared_too(self) -> None:
        block = Rect(0, 0, DEFAULT.slide.width, DEFAULT.frame().top + DEFAULT.spacing.title_height + cm(0.8))
        self.assertEqual(block.bottom + DEFAULT.spacing.gap_s, Page(ONE, self.over(block)).body.top)

    def test_the_lowest_of_several_lines_decides(self) -> None:
        first, second = self.line(DEFAULT.spacing.title_height + cm(0.3)), self.line(DEFAULT.spacing.title_height + cm(0.8))
        self.assertEqual(second.bottom + DEFAULT.spacing.gap_s, Page(ONE, self.over(first, second)).body.top)

    def test_a_folded_title_that_clears_the_line_goes_on_under_it(self) -> None:
        folded = "題" * 60
        band = DEFAULT.spacing.title_height + DEFAULT.line_height(DEFAULT.type.title)
        line = self.line(band + cm(0.3))
        self.assertEqual(line.bottom + DEFAULT.spacing.gap_s, Page(folded, self.over(line)).body.top)


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


class ADeckThatNumbersItsPages(unittest.TestCase):
    """頁に番号を振る資料 (= 見本の頁が頁番号の枠を持つ) では、型の頁も、レイアウトの頁番号の枠を持つ。

    ⚠ **レイアウトに枠が在るだけでは振らない。**PowerPoint のレイアウトはほとんどが頁番号の枠を持ち、
    番号が出るのは、頁の側がその枠を持つ時だけ。見本の頁が持たない資料で型の頁にだけ置くと、複製した
    頁には番号が無く、型の頁にだけ出る。
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def under(self, **template):
        from pptx_agent_maker.deck.base.under import under_of
        return under_of(a_template(self.dir / f"t{len(list(self.dir.iterdir()))}.pptx", **template))

    def test_a_specimen_whose_pages_carry_a_number_hands_on_the_layouts_frame(self) -> None:
        self.assertEqual(NUMBER, self.under(numbered=True).number)

    def test_a_layout_that_only_offers_the_frame_numbers_nothing(self) -> None:
        from pptx_agent_maker.deck.base.under import under_of

        self.assertEqual((), self.under().number)
        self.assertEqual((), under_of(SHIPPED).number)

    def test_with_no_frame_in_the_layout_there_is_nothing_to_carry(self) -> None:
        self.assertEqual((), self.under(numbered=True, number_frame=None).number)

    def test_the_frame_is_named_the_way_the_layout_names_it(self) -> None:
        self.assertEqual((("type", "sldNum"), ("sz", "quarter"), ("idx", "21")),
                         self.under(numbered=True, number_frame=21).number)

    def test_reading_the_number_changes_nothing_else_that_is_read(self) -> None:
        plain, numbered = self.under(logo=LOGO), self.under(logo=LOGO, numbered=True)
        self.assertEqual((plain.title, plain.prints), (numbered.title, numbered.prints))


class TheNumberIsTheLayoutsFrame(unittest.TestCase):
    """頁番号は、レイアウトの枠を頁が持つ形で書く。位置も見た目も書かない (= 全部レイアウトから継ぐ)。"""

    @staticmethod
    def baked(**under) -> list[str]:
        from pptx_agent_maker.layout.base.tokens import Under
        return TheTitleIsTheLayoutsTitle.baked(replace(DEFAULT, under=Under(**under)))

    def test_the_page_holds_the_frame_under_the_layouts_name_and_a_field_for_the_number(self) -> None:
        frames = [s for s in self.baked(number=NUMBER) if 'type="sldNum"' in s]
        self.assertEqual(1, len(frames))
        frame = frames[0]
        self.assertIn(f'<p:ph type="sldNum" sz="quarter" idx="{NUMBER_IDX}"/>', frame)
        self.assertRegex(frame, r'<a:fld id="\{[0-9A-F-]{36}\}" type="slidenum">')
        self.assertIn('<a:spLocks noGrp="1"/>', frame)

    def test_it_says_nothing_of_where_it_stands_or_how_it_looks(self) -> None:
        frame = next(s for s in self.baked(number=NUMBER) if 'type="sldNum"' in s)
        self.assertIn("<p:spPr/>", frame)
        for own in ("<a:off", "<a:ext", "<a:solidFill>", "<a:latin", ' sz="1', ' b="', "<a:prstGeom"):
            self.assertNotIn(own, frame, own)

    def test_the_frame_takes_the_name_it_is_handed(self) -> None:
        named = (("type", "sldNum"), ("idx", "21"))
        frame = next(s for s in self.baked(number=named) if 'type="sldNum"' in s)
        self.assertIn('<p:ph type="sldNum" idx="21"/>', frame)

    def test_no_two_shapes_on_the_page_share_an_id(self) -> None:
        ids = [found for s in self.baked(title=True, number=NUMBER)
               for found in re.findall(r'<p:cNvPr id="(\d+)"', s)]
        self.assertGreater(len(ids), 2)
        self.assertEqual(len(ids), len(set(ids)), ids)

    def test_the_title_and_the_number_are_the_only_placeholders(self) -> None:
        shapes = self.baked(title=True, number=NUMBER)
        self.assertEqual(2, sum("<p:ph" in s for s in shapes))

    def test_a_deck_that_numbers_nothing_gets_no_frame(self) -> None:
        self.assertFalse(any("<p:ph" in s or "slidenum" in s for s in self.baked()))


class NumberedOnATemplateOfItsOwn(unittest.TestCase):
    """建てる (= 利用者と同じ入口)。複製した頁と型の頁が、同じ枠で番号を持つ。"""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def pages(self, **template) -> tuple[str, list[str], str]:
        """(what the build said, the pages of the deck in part order, the layout declared pages sit on)."""
        root = self.dir / f"project-{len(list(self.dir.iterdir()))}"
        create(root, specimen=a_template(self.dir / f"{root.name}.pptx", **template))
        (root / "deck.toml").write_text(
            'specimen = "specimen.pptx"\nout = "deck.pptx"\n\n'
            '[[pages]]\nkind = "copy"\npage = 1\n'
            'replace = [["案件名", "見本の案件"], ["第 N 回 進捗報告", "第 1 回 進捗報告"]]\n\n'
            '[[pages]]\nkind = "declare"\ntype = "figure"\n'
            f'title = "{ONE}"\nfigure = "example.png"\nfooter = "出所 (= 見本)"\n\n'
            '[[pages]]\nkind = "declare"\ntype = "figure"\n'
            f'title = "{ONE}"\nfigure = "example.png"\nfooter = "出所 (= 見本)"\n', encoding="utf-8")
        (root / "assets" / "deck").mkdir(parents=True)
        (root / "assets" / "deck" / "example.png").write_bytes(
            (root / "assets" / "example" / "example.png").read_bytes())
        said = io.StringIO()
        with contextlib.redirect_stdout(said), contextlib.redirect_stderr(said):
            code = main(["build", str(root), "deck"])
        self.assertEqual(0, code, said.getvalue())
        with zipfile.ZipFile(root / "deck.pptx") as archive:
            names = sorted(n for n in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n))
            return (said.getvalue(), [archive.read(n).decode("utf-8") for n in names],
                    archive.read("ppt/slideLayouts/slideLayout1.xml").decode("utf-8"))

    def test_every_page_of_a_numbered_deck_carries_one_number(self) -> None:
        said, pages, _layout = self.pages(numbered=True)
        self.assertEqual(3, len(pages))
        self.assertEqual([1, 1, 1], [page.count('type="sldNum"') for page in pages])
        self.assertEqual([1, 1, 1], [page.count('type="slidenum"') for page in pages])
        self.assertNotIn("FAIL", said)

    def test_the_declared_pages_frame_is_the_one_the_layout_keeps(self) -> None:
        _said, pages, layout = self.pages(numbered=True, number_frame=21)
        self.assertIn('<p:ph type="sldNum" sz="quarter" idx="21"/>', layout)
        declared = [page for page in pages if ONE in page]
        self.assertEqual(2, len(declared))
        for page in declared:
            self.assertIn('<p:ph type="sldNum" sz="quarter" idx="21"/>', page)

    def test_a_deck_that_numbers_nothing_stays_without_numbers(self) -> None:
        said, pages, layout = self.pages()
        self.assertIn('type="sldNum"', layout, "the layout offers the frame all the same")
        self.assertEqual([0, 0, 0], [page.count("sldNum") + page.count("slidenum") for page in pages])
        self.assertNotIn("FAIL", said)


class TheCountStartsAfterTheCover(unittest.TestCase):
    """表紙 (= 番号を持たない 1 枚目) は数えない。番号の出る最初の頁が 1 になる。

    数え始めが 1 のままだと、表紙が 1 頁目に数えられ、表紙の次の頁に「2」が出た。資料は「1 枚目の番号」を
    1 つだけ持てる (= PowerPoint の「スライド開始番号」)。表紙が番号を持たない資料では、そこに 0 を書く。
    """

    COVER = '[[pages]]\nkind = "copy"\npage = 1\n\n'
    BODY = ('[[pages]]\nkind = "declare"\ntype = "figure"\n'
            f'title = "{ONE}"\nfigure = "example.png"\nfooter = "出所 (= 見本)"\n\n')

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def built(self, pages: str, template: Path) -> tuple[str, list[int]]:
        """(the tag at the root of the built deck, how many number frames each page carries in reading order)."""
        root = self.dir / f"project-{len(list(self.dir.iterdir()))}"
        create(root, specimen=template)
        (root / "deck.toml").write_text('specimen = "specimen.pptx"\nout = "deck.pptx"\n\n' + pages,
                                        encoding="utf-8")
        (root / "assets" / "deck").mkdir(parents=True)
        (root / "assets" / "deck" / "example.png").write_bytes(
            (root / "assets" / "example" / "example.png").read_bytes())
        said = io.StringIO()
        with contextlib.redirect_stdout(said), contextlib.redirect_stderr(said):
            code = main(["build", str(root), "deck"])
        self.assertEqual(0, code, said.getvalue())
        self.assertNotIn("FAIL", said.getvalue())
        with zipfile.ZipFile(root / "deck.pptx") as archive:
            presentation = archive.read("ppt/presentation.xml").decode("utf-8")
            rels = archive.read("ppt/_rels/presentation.xml.rels").decode("utf-8")
            part = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="(slides/slide\d+\.xml)"', rels))
            frames = [archive.read(f"ppt/{part[rid]}").decode("utf-8").count('type="sldNum"')
                      for rid in re.findall(r'<p:sldId[^>]*r:id="(rId\d+)"', presentation)]
        return re.search(r"<p:presentation\b[^>]*>", presentation).group(0), frames

    def template(self, name: str, **how) -> Path:
        return a_template(self.dir / f"{name}.pptx", **how)

    def test_a_cover_without_a_number_is_not_counted(self) -> None:
        tag, frames = self.built(self.COVER + self.BODY * 2, with_a_cover(self.template("cover", numbered=True)))
        self.assertEqual([0, 1, 1], frames)
        self.assertIn(' firstSlideNum="0"', tag)
        self.assertEqual(1, tag.count("firstSlideNum"))

    def test_a_deck_that_begins_with_a_numbered_page_counts_from_one(self) -> None:
        tag, frames = self.built(self.BODY * 2, with_a_cover(self.template("no-cover", numbered=True)))
        self.assertEqual([1, 1], frames)
        self.assertNotIn("firstSlideNum", tag)

    def test_a_deck_that_numbers_nothing_is_left_alone(self) -> None:
        tag, frames = self.built(self.COVER + self.BODY * 2, with_a_cover(self.template("plain")))
        self.assertEqual([0, 0, 0], frames)
        self.assertNotIn("firstSlideNum", tag)

    def test_where_the_specimen_says_the_count_starts_is_kept(self) -> None:
        for said in (1, 5):
            with self.subTest(said=said):
                template = with_a_cover(self.template(f"says-{said}", numbered=True), counts_from=said)
                tag, frames = self.built(self.COVER + self.BODY, template)
                self.assertEqual([0, 1], frames)
                self.assertIn(f' firstSlideNum="{said}"', tag)
                self.assertEqual(1, tag.count("firstSlideNum"))

    def test_the_first_number_is_read_and_rewritten_in_the_decks_own_tag(self) -> None:
        from pptx_agent_maker.deck.base.archive import Archive

        archive = Archive.unpack(self.template("tag"), self.dir / "unpacked")
        before = (archive.tree / "ppt/presentation.xml").read_text(encoding="utf-8")
        self.assertIsNone(archive.counts_from())
        archive.count_from(0)
        self.assertEqual(0, archive.counts_from())
        archive.count_from(3)
        self.assertEqual(3, archive.counts_from())
        after = (archive.tree / "ppt/presentation.xml").read_text(encoding="utf-8")
        self.assertEqual(before, after.replace(' firstSlideNum="3"', ""), "nothing else in the part moved")


if __name__ == "__main__":
    unittest.main()


def inches(value: float) -> int:
    return round(value * 914400)


def build_one(root: Path, specimen: Path, theme: str = "") -> tuple[int, str]:
    """A project on that specimen with one declared page titled `ONE`, built the way a user builds it."""
    if not root.exists():
        create(root, specimen=specimen)
        (root / "assets" / "deck").mkdir(parents=True)
        (root / "assets" / "deck" / "example.png").write_bytes((root / "assets" / "example" / "example.png").read_bytes())
    settings = root / "workspace.toml"
    text = settings.read_text(encoding="utf-8").split("\n[theme]\n")[0]
    settings.write_text(text + (f"\n[theme]\n{theme}" if theme else ""), encoding="utf-8")
    (root / "deck.toml").write_text(
        'specimen = "specimen.pptx"\nout = "deck.pptx"\n\n'
        f'[[pages]]\nkind = "declare"\ntype = "figure"\ntitle = "{ONE}"\n'
        'figure = "example.png"\nfooter = "出所 (= 見本)"\n', encoding="utf-8")
    said = io.StringIO()
    with contextlib.redirect_stdout(said), contextlib.redirect_stderr(said):
        code = main(["build", str(root), "deck"])
    return code, said.getvalue()


def built_page(deck: Path) -> tuple[str, str]:
    """(the XML, the relationships) of the built page titled `ONE`."""
    with zipfile.ZipFile(deck) as archive:
        name = next(name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
                    and ONE in archive.read(name).decode("utf-8"))
        return (archive.read(name).decode("utf-8"),
                archive.read(name.replace("slides/", "slides/_rels/") + ".rels").decode("utf-8"))


class TheLayoutIsNamedByASpecimenPage(unittest.TestCase):
    """⚠ **型の頁が乗るレイアウトは、部品の名前で決まっていた** (= `slideLayout1.xml`)。Google スライドの
    書き出しでは、その部品が表紙の型 (= 右下に飾りの絵) で、型の頁が表紙の飾りの上に乗った。並べ替えても効かない
    (= 並びではなく名前)。案件が見本の頁を 1 枚名指せば、型の頁はその頁と同じレイアウトに乗る。"""

    def test_without_a_name_the_declared_pages_sit_on_the_layout_part_named_first(self) -> None:
        from pptx_agent_maker.deck.base.under import under_of

        self.assertEqual("slideLayout1.xml", under_of(SHIPPED).layout)

    def test_a_named_page_hands_on_the_layout_it_sits_on(self) -> None:
        from pptx_agent_maker.deck.base.under import under_of

        from pptx import Presentation

        with tempfile.TemporaryDirectory() as tmp:
            path = a_template(Path(tmp) / "two.pptx")
            deck = Presentation(str(path))
            deck.slides.add_slide(deck.slide_layouts[1])       # 2 枚目は、別のレイアウトに乗る頁
            deck.save(str(path))
            first, second = under_of(path, 1), under_of(path, 2)
        self.assertEqual("slideLayout7.xml", first.layout)    # 同梱の見本の頁が乗るレイアウト
        self.assertEqual("slideLayout2.xml", second.layout)
        self.assertTrue(second.title, "the layout read is the named page's (= a title and content layout)")

    def test_a_page_the_specimen_does_not_have_stops(self) -> None:
        from pptx_agent_maker.deck.base.under import under_of

        with self.assertRaises(ValueError) as stopped:
            under_of(SHIPPED, 2)
        self.assertIn("1 pages", str(stopped.exception))

    def test_it_is_written_as_the_number_of_a_page(self) -> None:
        from pptx_agent_maker.layout.base.tokens import ThemeError, theme_from

        self.assertTrue(theme_from({"layout_of_page": 3}))
        for wrong in (0, -1, "3", True, 2.0):
            with self.subTest(wrong=wrong), self.assertRaises(ThemeError):
                theme_from({"layout_of_page": wrong})

    def test_the_built_page_sits_on_the_layout_of_the_named_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, specimen = Path(tmp) / "project", a_template(Path(tmp) / "template.pptx")
            for named, expected in (("", "slideLayout1.xml"), ("layout_of_page = 1\n", "slideLayout7.xml")):
                with self.subTest(named=named):
                    code, said = build_one(root, specimen, named)
                    self.assertEqual(0, code, said)
                    self.assertIn(f"slideLayouts/{expected}", built_page(root / "deck.pptx")[1])

    def test_a_page_the_specimen_does_not_have_stops_the_build_and_says_so(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, said = build_one(Path(tmp) / "project", a_template(Path(tmp) / "t.pptx"), "layout_of_page = 9\n")
        self.assertNotEqual(0, code)
        self.assertIn("layout_of_page", said)


class TheTitleSitsWhereTheTemplatesTitleSits(unittest.TestCase):
    """⚠ **題の帯は道具の余白で置かれ、テンプレートの題の枠の場所を見ていなかった。**マスターの題の枠が
    上の余白より上 (= 0.29 in) に在り、その下 (= 0.74 in) に太い罫線を引く雛形で、型の頁の題の帯
    (= 0.35〜0.94 in) の真ん中を線が通り、取り消し線に見えた。道具はさらに帯の下に自分の線を引いて、線が
    2 本になった。題の枠が在れば帯の上下をそれに合わせ、それでも線が題の字を横切るなら止める。"""

    SEAT = Rect(DEFAULT.frame().left, inches(0.29), DEFAULT.frame().width, inches(0.45))
    RULE = Rect(inches(1.75), inches(0.74), inches(12.18) - inches(1.75), 0)

    def theme_on(self, tmp: str, **template):
        from pptx_agent_maker.deck.base.under import under_of

        return replace(DEFAULT, under=under_of(a_template(Path(tmp) / "t.pptx", **template)))

    def test_the_title_frame_and_the_lines_are_read_with_their_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            under = self.theme_on(tmp, title_at=self.SEAT, line=self.RULE, line_in="master").under
        self.assertEqual(self.SEAT, under.title_frame)
        self.assertEqual(["Line"], [name for name, _ in under.lines])

    def test_the_title_goes_where_the_template_puts_it_and_the_rule_stays_under_it(self) -> None:
        for where in ("master", "layout"):
            with self.subTest(where=where), tempfile.TemporaryDirectory() as tmp:
                theme = self.theme_on(tmp, title_at=self.SEAT, line=self.RULE, line_in=where)
                page = Page(ONE, theme)
                title = placed(page, "title")
                self.assertEqual(self.SEAT.top, title.top)
                # 線はテンプレートが引くので、道具は自分の線を引かず、残りはその線の下から
                self.assertEqual([], [e for e in page.elements if e.kind == "rule"])
                self.assertGreater(page.body.top, self.RULE.top)

    def test_a_title_frame_the_rule_runs_through_ends_at_the_rule(self) -> None:
        tall = Rect(self.SEAT.left, self.SEAT.top, self.SEAT.width, inches(0.75))   # 0.29〜1.04 in
        with tempfile.TemporaryDirectory() as tmp:
            theme = self.theme_on(tmp, title_at=tall, line=self.RULE, line_in="master")
        page = Page(ONE, theme)
        title = placed(page, "title")
        self.assertEqual(tall.top, title.top)
        self.assertLess(title.bottom, tall.bottom, "the band ends near the rule, not at the foot of the frame")
        self.assertEqual([], [e for e in page.elements if e.kind == "rule"])

    def test_without_a_title_frame_a_line_through_the_title_stops_and_names_it(self) -> None:
        from pptx_agent_maker import PageFullError

        frame, row = DEFAULT.frame(), DEFAULT.line_height(DEFAULT.type.title)
        through = Rect(frame.left, frame.top + DEFAULT.spacing.title_height // 2, frame.width, 0)
        with tempfile.TemporaryDirectory() as tmp:
            theme = self.theme_on(tmp, title=False, line=through, line_in="master")
        self.assertLess(frame.top, through.top)
        self.assertLess(through.top, frame.top + DEFAULT.spacing.title_height + row)
        with self.assertRaises(PageFullError) as stopped:
            Page(ONE, theme)
        said = str(stopped.exception)
        for words in ("'Line'", "struck through", "layout_of_page"):
            self.assertIn(words, said)

    def test_the_requested_case_builds_and_the_built_title_stands_at_the_templates_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            code, said = build_one(root, a_template(Path(tmp) / "t.pptx", title_at=self.SEAT, line=self.RULE,
                                                    line_in="master"))
            self.assertEqual(0, code, said)
            self.assertNotIn("FAIL", said)
            page = built_page(root / "deck.pptx")[0]
        title = next(s for s in re.findall(r"<p:sp>.*?</p:sp>", page, re.S) if '<p:ph type="title"/>' in s)
        self.assertIn(f'y="{self.SEAT.top}"', title)
