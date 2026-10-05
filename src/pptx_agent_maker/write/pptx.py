"""Turn declared elements into a .pptx.

宣言層は座標だけを持ち、pptx のことを何も知らない。ここが唯一 python-pptx に触る層で、
**壊れた pptx の種を作らない**のもここの責任:

* 図形のプリセットは矩形と、道のりの矢羽根 2 つ (= `homePlate` / `chevron`) だけ。矢羽根は尖りの
  深さの調整値ごと PowerPoint で開き、修復が出ないことを確かめてから入れた (= 修復の確認で止まる
  わざと壊した file と並べて見分けた)。ほかのプリセットは、同じ確かめを済ませるまで使わない ―
  前の世代で矢印のプリセット 1 つが修復を言い出した実例があり、原因は記録に残っていない。
  菱形は矩形を 45 度回して描く
* 空の run を書かない (= 文字の無い run は修復の種)
* グラフは python-pptx の口 (= `add_chart`) だけで書く。グラフ本体・その関係・中のデータの表・種類の
  登録を 1 組で書いてくれるので、どれかが欠けた file を作らない
* 表示から外したスライドを残さない (= 孤児のスライドも同じ)
* 頁番号は、レイアウトの頁番号の枠を頁が持つ形で書く (= PowerPoint が「スライド番号」を入れた頁に
  書く形そのまま)。番号の字を自前の文字の枠で書かない
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData, XyChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION, XL_MARKER_STYLE, XL_TICK_MARK
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn
from pptx.util import Emu, Pt

from ..layout.parts.elements import Bar, Chart, Diamond, Element, Figure, Fill, Table, Text
from ..layout.base.tokens import DEFAULT, MARK_FACE, Theme

ALIGN = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}
#: 文字を持つ図形の形 → プリセット (= `page.SHAPES`)
PRESET = {"rect": MSO_SHAPE.RECTANGLE, "home": MSO_SHAPE.PENTAGON, "chevron": MSO_SHAPE.CHEVRON}

#: 文字の枠が上下に自分で取る余白 (= pptx の既定。左右は `Spacing.text_inset`)
TEXT_INSET_Y = 45720

#: 「スタイルなし・罫線なし」。PowerPoint が新しい表に付ける既定のスタイルは
#: **テーマの accent1 で見出しを塗る**ので、色の出どころが palette と 2 つに割れる。
NO_TABLE_STYLE = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"

#: 頁番号の欄の id。何の欄かは `type` が言い、id は欄を見分けるだけ (= どの頁も同じ値でよい)
NUMBER_FIELD = "{B6F15528-21DE-4FAA-801E-634DDDAF4B2B}"


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
        elif isinstance(element, Chart):
            _chart(slide, element, theme)
    if theme.under.number:
        _number(slide, theme)
    return slide


def _number(slide, theme: Theme) -> None:
    """The page's number, as the placeholder the layout keeps for it.

    書くのは「レイアウトのこの枠を、この頁も持つ」ということだけ。位置・大きさ・字の見た目は何も書かず、
    レイアウトから継ぐ (= テンプレートから複製した頁の番号と同じ所に、同じ見た目で出る)。番号そのものは
    開いた側が入れる。

    ⚠ **枠の名乗りは、レイアウトの物をそのまま写す** (= `type` と `idx`)。食い違うと、頁の枠はレイアウトの
    枠と結び付かず、位置を持たない図形になる。
    """
    shape = parse_xml(
        f'<p:sp {nsdecls("p", "a")}><p:nvSpPr>'
        f'<p:cNvPr id="{slide.shapes._next_shape_id}" name="Slide Number"/>'
        '<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph/></p:nvPr></p:nvSpPr><p:spPr/>'
        f'<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:fld id="{NUMBER_FIELD}" type="slidenum">'
        '<a:rPr lang="en-US"/><a:t>\u2039#\u203a</a:t></a:fld><a:endParaRPr lang="en-US"/></a:p></p:txBody>'
        "</p:sp>")
    held = shape.find(f'.//{qn("p:ph")}')
    for name, value in theme.under.number:
        held.set(name, value)
    slide.shapes._spTree.insert_element_before(shape, "p:extLst")


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


def _edge(shape, outline: str, theme: Theme, *, dashed: bool = False, heavy: bool = False) -> None:
    """The line round a shape, or none: every shape says which, so none inherits one."""
    if not outline:
        shape.line.fill.background()
        return
    shape.line.color.rgb = _colour(outline)
    shape.line.width = Emu(theme.spacing.strong_line if heavy else theme.spacing.hairline)
    if dashed:
        shape.line.dash_style = MSO_LINE_DASH_STYLE.DASH


def _fill(slide, element: Fill, theme: Theme) -> None:
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Emu(element.rect.left), Emu(element.rect.top),
        Emu(element.rect.width), Emu(element.rect.height),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = _colour(element.colour)
    _edge(shape, element.outline, theme, dashed=element.dashed, heavy=element.heavy)
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
    _edge(shape, element.outline, theme, dashed=element.dashed, heavy=element.heavy)
    _plain(shape)
    frame = shape.text_frame
    frame.word_wrap = True
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    frame.margin_left = frame.margin_right = Emu(theme.spacing.bar_pad_x)
    frame.margin_left = Emu(theme.spacing.bar_pad_x + element.lead)
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
    frame.word_wrap = element.kind not in {"label", "marker", "kicker_beside"}
    if not frame.word_wrap:
        # ⚠ **折り返さない枠は、枠を字に合わせない。**python-pptx が文字の枠に付ける既定 (= 字に合わせて
        # 枠を直す) を残していた間は、全角の短い名前が 1 文字ずつ縦に折れた ― 全角だけの名前は枠の幅が
        # 字の幅ちょうどで、LibreOffice はその幅で折る (= 焼いた絵で出た。PowerPoint では折れない)
        frame.auto_size = MSO_AUTO_SIZE.NONE
    if element.kind in {"label", "lane", "marker", "kicker_beside"}:
        frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = Emu(0)
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE if element.kind in {
        "band_text", "title", "caption", "label", "lane", "stage", "marker", "kicker_beside"} else MSO_ANCHOR.TOP
    # 題は、乗るレイアウトに題の枠が在れば、その枠として書く (= 色・書体・太さはテンプレートのもの)
    titled = element.kind == "title" and theme.under.title
    for index, line in enumerate(element.text.split("\n")):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.alignment = ALIGN[element.align]
        run = paragraph.add_run()
        run.text = line
        run.font.size = Pt(element.size)
        if titled:
            continue
        run.font.bold = element.bold
        run.font.color.rgb = _colour(element.colour)
        run.font.name = theme.type.family
    if titled:
        _as_title(box, theme)


def _as_title(box, theme: Theme) -> None:
    """Turn a text box into the page's title placeholder, keeping the place and the size it was given.

    ⚠ **継ぐのは見た目だけ** (= 色・書体・太さ・地)。位置と大きさ、折り返し、縦の寄せ、枠の余白はここが
    書く ― 道具が行を数えて帯の高さを取った、その同じ枠に字が入るように。書かなければレイアウトの
    題の枠の値を継ぎ、数えた行と実際の行が食い違う。
    """
    box.text_frame.auto_size = MSO_AUTO_SIZE.NONE
    shape = box._element
    # ⚠ python-pptx は既定と同じ余白を書き出さない。書かれない値はレイアウトから継ぐので、直に書く
    body = shape.txBody.find(qn("a:bodyPr"))
    for side, inset in (("lIns", theme.spacing.text_inset), ("tIns", TEXT_INSET_Y),
                        ("rIns", theme.spacing.text_inset), ("bIns", TEXT_INSET_Y)):
        body.set(side, str(inset))
    shape.nvSpPr.cNvPr.set("name", "Title")
    held = shape.nvSpPr.cNvSpPr
    held.attrib.pop("txBox", None)
    held.append(held.makeelement(qn("a:spLocks"), {"noGrp": "1"}))
    shape.nvSpPr.nvPr.append(shape.nvSpPr.nvPr.makeelement(qn("p:ph"), {"type": "title"}))
    for own in ("a:prstGeom", "a:noFill"):
        found = shape.spPr.find(qn(own))
        if found is not None:
            shape.spPr.remove(found)


def _figure(slide, element: Figure) -> None:
    picture = slide.shapes.add_picture(
        str(element.source), Emu(element.rect.left), Emu(element.rect.top),
        Emu(element.rect.width), Emu(element.rect.height),
    )
    # ⚠ python-pptx は素材の file 名を代替テキストに入れる。頁には見えないが、渡したデッキを
    # 開けば読める ― 案件の素材名が先方に届く経路なので置かない。
    picture._element.nvPicPr.cNvPr.attrib.pop("descr", None)


#: 点のグラフの点の差し渡し (= pt。本文の字の半分ほど ― 数十個並んでも重なりが読める大きさ)
POINT = 7

#: 描き方 → 書き出すグラフの種類と、値の数字を置く所 (= 棒の外の端 / 点の上 / 段の真ん中)
CHART = {
    "bar": (XL_CHART_TYPE.BAR_CLUSTERED, XL_LABEL_POSITION.OUTSIDE_END),
    "column": (XL_CHART_TYPE.COLUMN_CLUSTERED, XL_LABEL_POSITION.OUTSIDE_END),
    "line": (XL_CHART_TYPE.LINE_MARKERS, XL_LABEL_POSITION.ABOVE),
    "stacked": (XL_CHART_TYPE.COLUMN_STACKED, XL_LABEL_POSITION.CENTER),
}


def _chart(slide, element: Chart, theme: Theme) -> None:
    """A chart with its numbers inside the deck (= PowerPoint's "Edit Data" opens them).

    ⚠ **題を自分で消す。**系列が 1 つのグラフに、PowerPoint は系列の名前を題として出す。何のグラフかは
    頁の題が言っている。

    ⚠ **負の値で色を反転させない。**既定のままだと、負の棒は地の色が抜けて白くなる。
    """
    if element.plot == "scatter":
        _scatter(slide, element, theme)
        return
    kind, where = CHART[element.plot]
    data = CategoryChartData()
    data.categories = list(element.categories)
    for series in element.series:
        data.add_series(series.name, series.values)
    # ⚠ **注記を持つグラフは、注記と 1 つのグループにまとめる。**別々の図形のままだと、人が PowerPoint で
    # グラフを動かしたとき、言葉と線が元の場所に置き去りになる
    holder = slide.shapes.add_group_shape() if element.callouts else slide
    frame = element.frame or element.rect
    chart = holder.shapes.add_chart(kind, Emu(frame.left), Emu(frame.top),
                                    Emu(frame.width), Emu(frame.height), data).chart
    _dress(chart, element, theme)

    # 目盛りの線は引かない。値の数字を棒に付けたグラフは、値の軸も出さない (= 同じ数を 2 度見せない)
    chart.value_axis.has_major_gridlines = False
    chart.value_axis.visible = element.axis
    chart.value_axis.major_tick_mark = XL_TICK_MARK.NONE
    chart.value_axis.format.line.fill.background()
    chart.category_axis.major_tick_mark = XL_TICK_MARK.NONE
    chart.category_axis.format.line.color.rgb = _colour(element.line)
    if element.plot == "bar":
        # 横棒は最初の項目を上に置く (= 表と同じ読み順。既定は下から積む)。項目の並びを逆にすると
        # 値の軸が上へ回るので、いちばん下の項目の側 (= 逆にした後の端) で交わらせて下に戻す
        chart.category_axis.reverse_order = True
        # ⚠ python-pptx の項目の軸には、この設定の口が無い (= 代入しても黙って何も起きない)。
        # 値の軸の側に「項目の軸のいちばん端で交わる」と直に書く
        chart.value_axis._element.find(qn("c:crosses")).set("val", "max")
    if element.pinned:
        _pin(chart, element)
    for callout in element.callouts:
        if callout.line is not None:
            _fill(holder, Fill("callout", callout.line, element.colour), theme)
        _text(holder, Text("label", callout.words, callout.text, element.size, element.colour, align="center"),
              theme)

    for drawn, series in zip(chart.plots[0].series, element.series):
        if element.plot == "line":
            drawn.smooth = False
            drawn.format.line.color.rgb = _colour(series.colour)
            drawn.format.line.width = Emu(theme.spacing.strong_line)
            drawn.marker.style = XL_MARKER_STYLE.CIRCLE
            _solid(drawn.marker.format, series.colour)
            for index, colour in series.points:
                _solid(drawn.points[index].marker.format, colour)
        else:
            drawn.invert_if_negative = False
            _solid(drawn.format, series.colour, series.outline, theme)
            for index, colour in series.points:
                _solid(drawn.points[index].format, colour, series.outline, theme)
        if series.number_format:
            labels = drawn.data_labels
            labels.show_value = True
            labels.number_format = series.number_format
            labels.position = where
            if series.label_colour:
                labels.font.color.rgb = _colour(series.label_colour)


def _dress(chart, element: Chart, theme: Theme) -> None:
    """What every chart shares: no title of its own, the page's type, the legend under the plot."""
    chart.has_title = False
    chart.font.size = Pt(element.size)
    chart.font.name = theme.type.family
    chart.font.color.rgb = _colour(element.colour)
    chart.has_legend = element.legend
    if element.legend:
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False


def _scatter(slide, element: Chart, theme: Theme) -> None:
    """A chart of points: each series its marks, no line between them, both axes named.

    点のグラフは、軸が 2 本とも値の軸 (= 項目を持たない)。読むのは軸からなので、軸は 2 本とも出し、
    それぞれに名前を書く。目盛りの線は引かない (= ほかのグラフと同じ)。
    """
    data = XyChartData()
    for series in element.series:
        drawn = data.add_series(series.name)
        for x, y in zip(series.xs, series.values):
            drawn.add_data_point(x, y)
    frame = element.rect
    chart = slide.shapes.add_chart(XL_CHART_TYPE.XY_SCATTER, Emu(frame.left), Emu(frame.top),
                                   Emu(frame.width), Emu(frame.height), data).chart
    _dress(chart, element, theme)
    for axis, name in ((chart.category_axis, element.x_title), (chart.value_axis, element.y_title)):
        axis.has_major_gridlines = False
        axis.major_tick_mark = XL_TICK_MARK.NONE
        axis.format.line.color.rgb = _colour(element.line)
        axis.has_title = True
        words = axis.axis_title.text_frame
        words.text = name
        for run in words.paragraphs[0].runs:
            run.font.size = Pt(element.size)
            run.font.bold = False
            run.font.name = theme.type.family
            run.font.color.rgb = _colour(element.colour)
    # 点の間に線は引かれない (= この種類のグラフを、python-pptx は線なしで書き出す)
    for drawn, series in zip(chart.plots[0].series, element.series):
        drawn.marker.style = XL_MARKER_STYLE.CIRCLE
        drawn.marker.size = POINT
        _solid(drawn.marker.format, series.colour)


def _pin(chart, element: Chart) -> None:
    """Hold the plot where the page worked it out: its area inside the frame, and the value axis.

    描く範囲は `c:plotArea` の頭に、枠に対する比で書く (= `inner`: 軸の字や凡例を含まない、棒や線の入る
    矩形そのもの)。値の軸は端から端と目盛りの間を書く。
    """
    pinned = element.pinned
    area = chart._chartSpace.chart.plotArea
    layout = area.makeelement(qn("c:layout"), {})
    manual = layout.makeelement(qn("c:manualLayout"), {})
    layout.append(manual)
    for tag, value in (("layoutTarget", "inner"), ("xMode", "edge"), ("yMode", "edge"),
                       *zip(("x", "y", "w", "h"), (f"{part:.6f}" for part in pinned.inner))):
        manual.append(manual.makeelement(qn(f"c:{tag}"), {"val": value}))
    for existing in area.findall(qn("c:layout")):
        area.remove(existing)
    area.insert(0, layout)
    chart.value_axis.minimum_scale = pinned.low
    chart.value_axis.maximum_scale = pinned.high
    chart.value_axis.major_unit = pinned.step
    if element.plot != "line":
        # ⚠ python-pptx は、既定と同じ値 (= 150) を数字を省いて書く。棒の位置はこの値から計算したので、
        # 読む側の既定に任せず数字で書く
        chart.plots[0].gap_width = pinned.gap
        chart.plots[0]._element.find(qn("c:gapWidth")).set("val", str(pinned.gap))


def _solid(format, colour: str, outline: str = "", theme: Theme | None = None) -> None:
    """Paint a series, a point or a marker one colour (= or not at all), with or without an edge."""
    if colour:
        format.fill.solid()
        format.fill.fore_color.rgb = _colour(colour)
    else:
        format.fill.background()
    if outline and theme is not None:
        format.line.color.rgb = _colour(outline)
        format.line.width = Emu(theme.spacing.hairline)
    elif theme is not None:
        format.line.fill.background()
    else:
        format.line.color.rgb = _colour(colour)


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
            # 地の濃さを言ったセルは、差し色をその段まで薄めた地。字は、その地の上で読める方の色
            ground = (theme.palette.shade(element.shades[(r, c)]) if (r, c) in element.shades
                      else _cell_colour(theme, heading, r))
            cell.fill.solid()
            cell.fill.fore_color.rgb = _colour(ground)
            cell.text = value
            mark = (r, c) in element.marks
            paragraph = cell.text_frame.paragraphs[0]
            paragraph.alignment = PP_ALIGN.LEFT
            for run in paragraph.runs:
                run.font.size = Pt(theme.type.body)
                run.font.bold = heading
                run.font.name = MARK_FACE if mark else theme.type.family
                ink = (theme.palette.words_on(ground) if (r, c) in element.shades
                       else theme.palette.paper if heading else theme.palette.ink)
                run.font.color.rgb = _colour(element.highlight.get((r, c)) or ink)
                if mark:
                    _every_script(run, MARK_FACE)


def _every_script(run, face: str) -> None:
    """Name the face for every script a run may be set in, not the Latin one alone.

    ⚠ **印の字 (= ○ ✓ △) を、PowerPoint は欧文の書体で置くとは限らない。**東アジアの書体か記号の
    書体に回されると、名指ししていない側はテーマの書体になり、その書体に字形が無ければ別の書体へ
    落ちる。3 つとも名指しして、どこで開いても同じ字形にする。

    並びは決まっている (= `latin` `ea` `cs` `sym`)。順を違えた file を PowerPoint は修復しようとする。
    """
    properties = run._r.get_or_add_rPr()
    latin = properties.find(qn("a:latin"))
    east = properties.makeelement(qn("a:ea"), {"typeface": face})
    symbol = properties.makeelement(qn("a:sym"), {"typeface": face})
    latin.addnext(east)
    east.addnext(symbol)


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
