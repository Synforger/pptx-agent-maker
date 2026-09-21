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
from pptx.util import Emu, Pt

from ..layout.page import Element, Figure, Fill, Table, Text
from ..layout.tokens import DEFAULT, Theme

ALIGN = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}


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
    slide.shapes.add_picture(
        str(element.source), Emu(element.rect.left), Emu(element.rect.top),
        Emu(element.rect.width), Emu(element.rect.height),
    )


def _table(slide, element: Table, theme: Theme) -> None:
    rows, columns = len(element.rows), len(element.rows[0])
    shape = slide.shapes.add_table(
        rows, columns, Emu(element.rect.left), Emu(element.rect.top),
        Emu(element.rect.width), Emu(element.rect.height),
    )
    table = shape.table
    table.first_row = element.header
    for row in table.rows:
        row.height = Emu(theme.table_row_height())
    for r, row in enumerate(element.rows):
        for c, value in enumerate(row):
            cell = table.cell(r, c)
            cell.margin_top = Emu(theme.spacing.cell_pad_y)
            cell.margin_bottom = Emu(theme.spacing.cell_pad_y)
            cell.margin_left = Emu(theme.spacing.cell_pad_x)
            cell.margin_right = Emu(theme.spacing.cell_pad_x)
            cell.text = value
            paragraph = cell.text_frame.paragraphs[0]
            paragraph.alignment = PP_ALIGN.LEFT
            for run in paragraph.runs:
                run.font.size = Pt(theme.type.body if r or not element.header else theme.type.body)
                run.font.bold = bool(r == 0 and element.header)
                run.font.name = theme.type.family
                colour = element.highlight.get((r, c))
                run.font.color.rgb = _colour(colour or theme.palette.ink)


def save(deck: Presentation, path: Path | str) -> Path:
    """Write the deck out and hand back where it landed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    deck.save(str(path))
    return path
