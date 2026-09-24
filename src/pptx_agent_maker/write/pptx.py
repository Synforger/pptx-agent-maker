"""Turn declared elements into a .pptx.

宣言層は座標だけを持ち、pptx のことを何も知らない。ここが唯一 python-pptx に触る層で、
**壊れた pptx の種を作らない**のもここの責任:

* 図形のプリセットを使わない (= 矢印のプリセット 1 つで PowerPoint が修復を言い出した実例がある)
* 空の run を書かない (= 文字の無い run は修復の種)
* 表示から外したスライドを残さない (= 孤児のスライドも同じ)
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

from ..layout.page import Element, Figure, Fill, Table, Text
from ..layout.tokens import DEFAULT, Theme

ALIGN = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}

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
            _fill(slide, element)
        elif isinstance(element, Text):
            _text(slide, element, theme)
        elif isinstance(element, Figure):
            _figure(slide, element)
        elif isinstance(element, Table):
            _table(slide, element, theme)
    return slide


def _fill(slide, element: Fill) -> None:
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Emu(element.rect.left), Emu(element.rect.top),
        Emu(element.rect.width), Emu(element.rect.height),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = _colour(element.colour)
    shape.line.fill.background()
    shape.shadow.inherit = False
    # A shape with no text still carries an empty paragraph; give it nothing to
    # render rather than an empty run.
    shape.text_frame.paragraphs[0].text = ""


def _text(slide, element: Text, theme: Theme) -> None:
    if not element.text.strip():
        return  # never write an empty run
    box = slide.shapes.add_textbox(
        Emu(element.rect.left), Emu(element.rect.top),
        Emu(element.rect.width), Emu(element.rect.height),
    )
    frame = box.text_frame
    frame.word_wrap = True
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE if element.kind in {"band_text", "title", "caption"} else MSO_ANCHOR.TOP
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
