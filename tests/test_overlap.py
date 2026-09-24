"""Things printed on top of each other — and the far larger number that only look it.

⚠ **枠と、描かれる物は別。**前の世代の検査は枠どうしで見ていたので、画面では離れている
物が重なりとして上がった ― 実デッキに当てて出たものは、開いて見た限りどれも
「枠は掛かるが文字は届いていない」だった。最後は「自作の頁だけ見る」で黙らせていて、
その逃げ方だと本当の重なりも見ない。
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from pptx_agent_maker.checks.rules import overlap  # noqa: E402

SLIDE = """<?xml version="1.0"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:cSld><p:spTree>{shapes}</p:spTree></p:cSld></p:sld>"""

BOX = """<p:sp><p:nvSpPr><p:cNvPr id="{id}" name="t{id}"/><p:cNvSpPr txBox="1"/>
<p:nvPr>{placeholder}</p:nvPr></p:nvSpPr>
<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>
<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>
<p:txBody><a:bodyPr wrap="square"/><a:lstStyle/><a:p><a:pPr algn="{align}"/>
<a:r><a:rPr sz="{size}"/><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp>"""


def a_box(number, x, y, w, h, text, size=1200, align="l", placeholder=""):
    return BOX.format(id=number, x=x, y=y, w=w, h=h, text=text, size=size, align=align,
                      placeholder=placeholder)


class _Page:
    """A page and what it sits on, without going through a file."""

    def __init__(self, shapes, beneath=""):
        from pptx_agent_maker.checks.slide import BuiltSlide, shapes_in

        self.page = BuiltSlide(1, "slide1.xml", SLIDE.format(shapes="".join(shapes)),
                               tuple(shapes_in(SLIDE.format(shapes="".join(beneath)))))

    def findings(self):
        import pptx_agent_maker.checks.rules.overlap as rule

        original = rule.read
        rule.read = lambda _: [self.page]
        try:
            return rule.run(Path("unused.pptx"))
        finally:
            rule.read = original


class TextOverText(unittest.TestCase):
    def test_two_lines_of_text_on_the_same_spot_are_found(self) -> None:
        found = _Page([a_box(1, 0, 0, 4000000, 400000, "うえの文字"),
                       a_box(2, 0, 100000, 4000000, 400000, "したの文字")]).findings()
        self.assertTrue(found, "重なっている文字が上がらない")

    def test_a_wide_box_whose_words_stop_early_is_not_a_finding(self) -> None:
        """⚠ **これが前の世代の誤検出そのもの。**枠は掛かるが、文字は届いていない。"""
        found = _Page([a_box(1, 0, 0, 9000000, 400000, "短い題"),
                       a_box(2, 8000000, 0, 1000000, 400000, "右端", align="r")]).findings()
        self.assertEqual(found, [], f"枠が掛かっただけで上がった: {[f.why for f in found]}")

    def test_a_right_aligned_box_is_measured_from_its_right_edge(self) -> None:
        found = _Page([a_box(1, 0, 0, 9000000, 400000, "みぎよせ", align="r"),
                       a_box(2, 0, 100000, 1000000, 400000, "ひだり")]).findings()
        self.assertEqual(found, [], "右寄せの枠を左端から測っている")


class TextOverTheLayout(unittest.TestCase):
    def test_a_word_printed_over_the_logo_is_found(self) -> None:
        logo = a_box(9, 10000000, 0, 1500000, 800000, "LOGO")
        found = _Page([a_box(1, 9500000, 0, 2000000, 400000, "ロゴに掛かる長い見出しです")],
                      beneath=[logo]).findings()
        self.assertTrue(found, "下敷きに掛かった文字が上がらない")
        self.assertIn("layout", found[0].why)

    def test_a_title_that_stops_before_the_logo_is_not_a_finding(self) -> None:
        """⚠ 実デッキで上がっていたのはこれ ― 題の枠は全幅、文字はロゴの手前で終わる。"""
        logo = a_box(9, 10000000, 0, 1500000, 800000, "LOGO")
        found = _Page([a_box(1, 0, 0, 11000000, 400000, "短い題")], beneath=[logo]).findings()
        self.assertEqual(found, [], f"枠が全幅なだけで上がった: {[f.why for f in found]}")

    def test_an_empty_placeholder_is_not_something_on_the_page(self) -> None:
        """⚠ レイアウトのプレースホルダは頁いっぱいに取られている (= 中身は頁が入れる)。"""
        empty = a_box(9, 0, 0, 11000000, 6000000, "", placeholder='<p:ph type="body"/>')
        found = _Page([a_box(1, 0, 0, 3000000, 400000, "本文の文字")], beneath=[empty]).findings()
        self.assertEqual(found, [], "空のプレースホルダと重なったことにされた")


if __name__ == "__main__":
    unittest.main()
