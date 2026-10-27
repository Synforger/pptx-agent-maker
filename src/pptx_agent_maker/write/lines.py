"""Write a line as a connector: straight, or bent at right angles.

誰が呼ぶか: `pptx.add_page` (= 頁の `Line` を 1 本ずつ)。線の形 (= 真っすぐ・曲がる) だけを知り、頁の他の物は知らない。
"""

from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR
from pptx.oxml.ns import qn
from pptx.util import Emu

from ..layout.parts.elements import Line
from ..layout.tokens import Theme


def write_line(slide, element: Line, theme: Theme) -> None:
    """A connector between two points, straight or bent once, its arrowhead (if any) at the end.

    矢じりは線の書式 (= `a:tailEnd`) で付ける。並びは決まっている (= 塗り・破線の後に端) ― 順を違えた file を
    PowerPoint は修復しようとする。

    曲がる線は、直角に 1 回曲がるコネクタ (= `bentConnector2`)。この形は、始まりから横へ進み、終わりの x で
    縦に曲がる 1 つだけなので、縦へ進んで曲がる線 (= `down`) は終わりから始まりへ引き、矢じりを始まりの端
    (= `a:headEnd`) に付ける。どちらも 1 つの図形なので、人が動かしても折れ目と両端は離れない。
    """
    (x1, y1), (x2, y2) = element.start, element.end
    backwards = element.bend == "down"
    if backwards:
        (x1, y1), (x2, y2) = (x2, y2), (x1, y1)
    shape = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Emu(x1), Emu(y1), Emu(x2), Emu(y2))
    if element.bend:
        _bend(shape, (x1, y1), (x2, y2))
    style = shape._element.find(qn("p:style"))
    if style is not None:                      # テーマの線の書式を引かない (= `_plain` と同じ理由)
        shape._element.remove(style)
    shape.line.color.rgb = RGBColor.from_string(element.colour)
    shape.line.width = Emu(theme.spacing.hairline * 3 // 2)
    if element.arrow:
        line = shape.line._get_or_add_ln()
        line.append(line.makeelement(qn("a:headEnd" if backwards else "a:tailEnd"),
                                     {"type": "triangle", "w": "med", "len": "med"}))


def _bend(shape, begin: tuple[int, int], end: tuple[int, int]) -> None:
    """Make a connector the bent one that runs sideways from `begin` and turns at the x of `end`.

    プリセット `bentConnector2` の道は、枠の左上から右へ進み、右の辺で下へ曲がる 1 つだけ。ほかの 3 つの向きは
    反転と回転で書く。**回転は 0 度か 180 度だけ** (= 90 度は枠が縦横入れ替わって、枠が頁の外へ出る) ― 右へ進む
    線は反転なし、左へ進む線は 180 度。上へ進む線は上下反転 (= 180 度の時は、その逆)。
    LibreOffice で 4 つの向きを焼いて、折れ目の位置が計算と合うことを確かめた書き方で、水平方向の反転は使わない
    (= 左右反転した曲がるコネクタは、LibreOffice が折れ目を逆の角に描く)。
    """
    shape._element.spPr.find(qn("a:prstGeom")).set("prst", "bentConnector2")
    frame = shape._element.spPr.find(qn("a:xfrm"))
    for name in ("rot", "flipH", "flipV"):
        frame.attrib.pop(name, None)
    leftwards = end[0] < begin[0]
    if leftwards:
        frame.set("rot", "10800000")
    if (end[1] < begin[1]) != leftwards:
        frame.set("flipV", "1")
