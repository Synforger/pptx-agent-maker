"""Turn declared elements into a .pptx.

宣言層は座標だけを持ち、pptx のことを何も知らない。ここが唯一 python-pptx に触る層で、
**壊れた pptx の種を作らない**のもここの責任:

* 図形のプリセットは矩形と、道のりの矢羽根 2 つ (= `homePlate` / `chevron`) だけ。矢羽根は尖りの
  深さの調整値ごと PowerPoint で開き、修復が出ないことを確かめてから入れた (= 修復の確認で止まる
  わざと壊した file と並べて見分けた)。ほかのプリセットは、同じ確かめを済ませるまで使わない ―
  前の世代で矢印のプリセット 1 つが修復を言い出した実例があり、原因は記録に残っていない。
  菱形は矩形を 45 度回して描く
* 空の run を書かない (= 文字の無い run は修復の種)
* 表示から外したスライドを残さない (= 孤児のスライドも同じ)
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

from ..layout.page import Bar, Diamond, Element, Figure, Fill, Table, Text
from ..layout.tokens import DEFAULT, Theme

ALIGN = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}
#: 文字を持つ図形の形 → プリセット (= `page.SHAPES`)
PRESET = {"rect": MSO_SHAPE.RECTANGLE, "home": MSO_SHAPE.PENTAGON, "chevron": MSO_SHAPE.CHEVRON}

#: 「スタイルなし・罫線なし」。PowerPoint が新しい表に付ける既定のスタイルは
#: **テーマの accent1 で見出しを塗る**ので、色の出どころが palette と 2 つに割れる。
NO_TABLE_STYLE = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"


def _colour(value: str) -> RGBColor:
    return RGBColor.from_string(value)


def new_deck(theme: Theme = DEFAULT) -> Presentation:
    """An empty deck at the theme's slide size."""
    deck = Presentation()
    deck.slide_width = Emu(theme.slide.width)
    deck.slide_height = Emu(theme.slide.height)
    return deck


def add_page(deck: Presentation, elements: list[Element], theme: Theme = DEFAULT):
    """Place one declared page onto a new slide."""
    slide = deck.slides.add_slide(deck.slide_layouts[6])  # 6 = blank
    for element in elements:
        if isinstance(element, Fill):
            _fill(slide, element, theme)
        elif isinstance(element, Bar):
            _bar(slide, element, theme)
        elif isinstance(element, Diamond):
            _diamond(slide, element)
        elif isinstance(element, Text):
            _text(slide, element, theme)
        elif isinstance(element, Figure):
            _figure(slide, element)
        elif isinstance(element, Table):
            _table(slide, element, theme)
    return slide


def _plain(shape) -> None:
    """Take the theme's shape style off, so what is written here is all the shape has.

    ⚠ **図形はテーマの「図形のスタイル」を引いて生まれる** (= 影・線・文字色の参照)。影は
    `shadow.inherit = False` で止めてあるが、参照そのものは残り、LibreOffice はそれを読んで
    影を描く ― PowerPoint には無い影が、絵に焼いたときだけ全部の図形に付いていた。
    色と線はここが自分で書くので、参照ごと外す。
    """
    shape.shadow.inherit = False
    style = shape._element.find(qn("p:style"))
    if style is not None:
        shape._element.remove(style)


def _edge(shape, outline: str, theme: Theme, *, dashed: bool = False) -> None:
    """The line round a shape, or none: every shape says which, so none inherits one."""
    if not outline:
        shape.line.fill.background()
        return
    shape.line.color.rgb = _colour(outline)
    shape.line.width = Emu(theme.spacing.hairline)
    if dashed:
        shape.line.dash_style = MSO_LINE_DASH_STYLE.DASH


def _fill(slide, element: Fill, theme: Theme) -> None:
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Emu(element.rect.left), Emu(element.rect.top),
        Emu(element.rect.width), Emu(element.rect.height),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = _colour(element.colour)
    _edge(shape, element.outline, theme)
    _plain(shape)
    # A shape with no text still carries an empty paragraph; give it nothing to
    # render rather than an empty run.
    shape.text_frame.paragraphs[0].text = ""


def _bar(slide, element: Bar, theme: Theme) -> None:
    """A shape with its words inside it (= one shape, so it moves as one)."""
    shape = slide.shapes.add_shape(
        PRESET[element.shape], Emu(element.rect.left), Emu(element.rect.top),
        Emu(element.rect.width), Emu(element.rect.height),
    )
    if element.shape != "rect":
        # 尖りの深さはプリセットの調整値 (= 短い辺に対する比) で書く。既定のままだと、段の高さで
        # 深さが変わり、隣の段の切り欠きと噛み合わない
        shape.adjustments[0] = theme.spacing.chevron_point / min(element.rect.width,
                                                                 element.rect.height)
    if element.fill:
        shape.fill.solid()
        shape.fill.fore_color.rgb = _colour(element.fill)
    else:
        shape.fill.background()
    _edge(shape, element.outline, theme, dashed=element.dashed)
    _plain(shape)
    frame = shape.text_frame
    frame.word_wrap = True
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    frame.margin_left = frame.margin_right = Emu(theme.spacing.bar_pad_x)
    frame.margin_top = frame.margin_bottom = Emu(0)
    paragraph = frame.paragraphs[0]
    if not element.text.strip():
        paragraph.text = ""  # never write an empty run
        return
    paragraph.alignment = ALIGN[element.align]
    run = paragraph.add_run()
    run.text = element.text
    run.font.size = Pt(element.size)
    run.font.bold = element.bold
    run.font.color.rgb = _colour(element.colour)
    run.font.name = theme.type.family


def _diamond(slide, element: Diamond) -> None:
    """A square turned 45 degrees, its corners touching the sides of the square given.

    ⚠ **菱形のプリセットを使わない。**矩形を回すだけなら、図形の種類は頁のほかの物と
    同じ 1 つのまま (= プリセットを増やさない)。
    """
    side = round(element.rect.width / 2 ** 0.5)
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Emu(element.rect.left + (element.rect.width - side) // 2),
        Emu(element.rect.top + (element.rect.height - side) // 2),
        Emu(side), Emu(side),
    )
    shape.rotation = 45
    shape.fill.solid()
    shape.fill.fore_color.rgb = _colour(element.colour)
    shape.line.fill.background()
    _plain(shape)
    shape.text_frame.paragraphs[0].text = ""


def _text(slide, element: Text, theme: Theme) -> None:
    if not element.text.strip():
        return  # never write an empty run
    box = slide.shapes.add_textbox(
        Emu(element.rect.left), Emu(element.rect.top),
        Emu(element.rect.width), Emu(element.rect.height),
    )
    frame = box.text_frame
    # 隣の物に付く名前と、段の間の向きは折り返さない。線表の名前と向きは枠の余白も取らない
    # (= 測った幅がそのまま使える幅。向きは狭い列に 1 文字で立つ)
    frame.word_wrap = element.kind not in {"label", "marker"}
    if element.kind in {"label", "lane", "marker"}:
        frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = Emu(0)
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE if element.kind in {
        "band_text", "title", "caption", "label", "lane", "stage", "marker"} else MSO_ANCHOR.TOP
    for index, line in enumerate(element.text.split("\n")):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.alignment = ALIGN[element.align]
        run = paragraph.add_run()
        run.text = line
        run.font.size = Pt(element.size)
        run.font.bold = element.bold
        run.font.color.rgb = _colour(element.colour)
        run.font.name = theme.type.family


def _figure(slide, element: Figure) -> None:
    picture = slide.shapes.add_picture(
        str(element.source), Emu(element.rect.left), Emu(element.rect.top),
        Emu(element.rect.width), Emu(element.rect.height),
    )
    # ⚠ python-pptx は素材の file 名を代替テキストに入れる。頁には見えないが、渡したデッキを
    # 開けば読める ― 案件の素材名が先方に届く経路なので置かない。
    picture._element.nvPicPr.cNvPr.attrib.pop("descr", None)


def _table(slide, element: Table, theme: Theme) -> None:
    rows, columns = len(element.rows), len(element.rows[0])
    shape = slide.shapes.add_table(
        rows, columns, Emu(element.rect.left), Emu(element.rect.top),
        Emu(element.rect.width), Emu(element.rect.height),
    )
    table = shape.table
    _unstyle(table)
    for column, width in zip(table.columns, element.widths):
        column.width = Emu(width)
    for row in table.rows:
        row.height = Emu(theme.table_row_height())
    for r, row in enumerate(element.rows):
        heading = bool(element.header and r == 0)
        for c, value in enumerate(row):
            cell = table.cell(r, c)
            cell.margin_top = Emu(theme.spacing.cell_pad_y)
            cell.margin_bottom = Emu(theme.spacing.cell_pad_y)
            cell.margin_left = Emu(theme.spacing.cell_pad_x)
            cell.margin_right = Emu(theme.spacing.cell_pad_x)
            cell.fill.solid()
            cell.fill.fore_color.rgb = _colour(_cell_colour(theme, heading, r))
            cell.text = value
            paragraph = cell.text_frame.paragraphs[0]
            paragraph.alignment = PP_ALIGN.LEFT
            for run in paragraph.runs:
                run.font.size = Pt(theme.type.body)
                run.font.bold = heading
                run.font.name = theme.type.family
                ink = theme.palette.paper if heading else theme.palette.ink
                run.font.color.rgb = _colour(element.highlight.get((r, c)) or ink)


def _cell_colour(theme: Theme, heading: bool, row: int) -> str:
    """見出しは差し色、本文は 1 行おきに薄く敷く (= 横に目が滑らないように)。"""
    if heading:
        return theme.palette.accent
    return theme.palette.band if row % 2 == 0 else theme.palette.paper


def _unstyle(table) -> None:
    """Take PowerPoint's own style off the table so the palette is the only source of colour.

    ⚠ **表だけ色の出どころが別だった。**`add_table` の既定スタイルはテーマの accent1 で
    見出しを塗り、本文に縞を入れる。案件が `[theme]` で色を変えても表は追随せず、
    さらに見出しの文字色をこちらが決めているので、暗い字が濃い地に乗っていた。
    """
    properties = table._tbl.find(qn("a:tblPr"))
    for banding in ("firstRow", "bandRow"):
        properties.attrib.pop(banding, None)
    style = properties.find(qn("a:tableStyleId"))
    if style is None:
        style = properties.makeelement(qn("a:tableStyleId"), {})
        properties.append(style)
    style.text = NO_TABLE_STYLE


def save(deck: Presentation, path: Path | str) -> Path:
    """Write the deck out and hand back where it landed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    deck.save(str(path))
    return path
