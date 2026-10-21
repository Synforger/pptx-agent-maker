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
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn
from pptx.util import Emu, Pt

from ..layout.parts.elements import Bar, Chart, Diamond, Element, Ellipse, Figure, Fill, Line, Table, Text, TEXT_INSET_Y, bullet_indent
from ..layout.base.tokens import DEFAULT, MARK_FACE, Theme

ALIGN = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}
#: 文字を持つ図形の形 → プリセット (= `page.SHAPES`)
PRESET = {"rect": MSO_SHAPE.RECTANGLE, "home": MSO_SHAPE.PENTAGON, "chevron": MSO_SHAPE.CHEVRON,
          "voice": MSO_SHAPE.ROUNDED_RECTANGULAR_CALLOUT}

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
        elif isinstance(element, Line):
            _line(slide, element, theme)
        elif isinstance(element, Ellipse):
            _ellipse(slide, element, theme)
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
        MSO_SHAPE.ROUNDED_RECTANGLE if element.rounded else MSO_SHAPE.RECTANGLE,
        Emu(element.rect.left), Emu(element.rect.top), Emu(element.rect.width), Emu(element.rect.height),
    )
    if element.rounded:
        # 角の丸みは短い辺に対する比で書く (= 既定のままだと、背の高いカードほど丸みが大きくなる)
        shape.adjustments[0] = min(theme.spacing.gap_s / min(element.rect.width, element.rect.height), 0.5)
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
    if element.shape == "voice":
        _voice(shape, element, theme)
        return
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


def _voice(shape, element: Bar, theme: Theme) -> None:
    """A speech bubble: its tail to the lower left, its words inside with the room of a box.

    尾の先はプリセットの調整値で書く (= 図形の真ん中からの、幅と高さに対する比)。先は左の角の丸みの内側、
    吹き出しの下の間隔 (= `gap_m`) の 3 分の 2 まで ― 誰の声かの字は、その間隔の下に置かれる (= `Page.voices`)。
    """
    s, rect = theme.spacing, element.rect
    shape.adjustments[0] = (2 * s.pad - rect.width / 2) / rect.width
    shape.adjustments[1] = (rect.height / 2 + s.gap_m * 2 / 3) / rect.height
    if element.fill:
        shape.fill.solid()
        shape.fill.fore_color.rgb = _colour(element.fill)
    else:
        shape.fill.background()
    _edge(shape, element.outline, theme)
    _plain(shape)
    frame = shape.text_frame
    frame.word_wrap = True
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = Emu(s.pad)
    paragraph = frame.paragraphs[0]
    paragraph.alignment = ALIGN[element.align]
    run = paragraph.add_run()
    run.text = element.text
    run.font.size = Pt(element.size)
    run.font.color.rgb = _colour(element.colour)
    run.font.name = theme.type.family


def _line(slide, element: Line, theme: Theme) -> None:
    """A straight connector between two points, its arrowhead (if any) at the end.

    矢じりは線の書式 (= `a:tailEnd`) で付ける。並びは決まっている (= 塗り・破線の後に端) ― 順を違えた file を
    PowerPoint は修復しようとする。
    """
    (x1, y1), (x2, y2) = element.start, element.end
    shape = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Emu(x1), Emu(y1), Emu(x2), Emu(y2))
    style = shape._element.find(qn("p:style"))
    if style is not None:                      # テーマの線の書式を引かない (= `_plain` と同じ理由)
        shape._element.remove(style)
    shape.line.color.rgb = _colour(element.colour)
    shape.line.width = Emu(theme.spacing.hairline * 3 // 2)
    if element.arrow:
        line = shape.line._get_or_add_ln()
        line.append(line.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"}))


def _ellipse(slide, element: Ellipse, theme: Theme) -> None:
    """A circle, its ground let through as asked (= `a:alpha` on the fill), with a thin edge."""
    rect = element.rect
    shape = slide.shapes.add_shape(MSO_SHAPE.OVAL, Emu(rect.left), Emu(rect.top), Emu(rect.width), Emu(rect.height))
    shape.fill.solid()
    shape.fill.fore_color.rgb = _colour(element.colour)
    if element.clear:
        colour = shape.fill._xPr.find(qn("a:solidFill"))[0]
        colour.append(colour.makeelement(qn("a:alpha"), {"val": str(round((1 - element.clear) * 100000))}))
    _edge(shape, element.outline, theme)
    _plain(shape)
    shape.text_frame.paragraphs[0].text = ""


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
    frame.word_wrap = element.kind not in {"label", "marker", "kicker_beside", "code"}
    if not frame.word_wrap:
        # ⚠ **折り返さない枠は、枠を字に合わせない。**python-pptx が文字の枠に付ける既定 (= 字に合わせて
        # 枠を直す) を残していた間は、全角の短い名前が 1 文字ずつ縦に折れた ― 全角だけの名前は枠の幅が
        # 字の幅ちょうどで、LibreOffice はその幅で折る (= 焼いた絵で出た。PowerPoint では折れない)
        frame.auto_size = MSO_AUTO_SIZE.NONE
    if element.kind in {"label", "lane", "marker", "kicker_beside"}:
        frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = Emu(0)
    elif element.kind == "agenda_mark":
        # 目次の小項目の印は、 隣の字の箱と同じ高さに乗るよう上下の余白を残し、 左右だけ 0 にする
        frame.margin_left = frame.margin_right = Emu(0)
    elif theme.spacing.text_inset != DEFAULT.spacing.text_inset:
        # ⚠ **詰めた使い方では、枠の左右の余白を数えたとおりに書く。**書かなければ pptx の既定 (= 手元で
        # 読ませる資料の値) のままで、字の入る幅が道具の数えた幅より狭く、狭い箱で見積もりより 1 行多く折れた
        frame.margin_left = frame.margin_right = Emu(theme.spacing.text_inset)
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE if element.kind in {
        "band_text", "title", "caption", "label", "lane", "stage", "marker", "kicker_beside", "agenda_number"} else MSO_ANCHOR.TOP
    # 題は、乗るレイアウトに題の枠が在れば、その枠として書く (= 色・書体・太さはテンプレートのもの)
    titled = element.kind == "title" and theme.under.title
    for index, line in enumerate(element.text.split("\n")):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.alignment = ALIGN[element.align]
        if element.bullets:
            _bulleted(paragraph, element.size)
        run = paragraph.add_run()
        run.text = line
        run.font.size = Pt(element.size)
        if titled:
            continue
        run.font.bold = element.bold
        run.font.color.rgb = _colour(element.colour)
        run.font.name = element.family or theme.type.family
    if titled:
        _as_title(box, theme)


def _bulleted(paragraph, size: float) -> None:
    """Make a paragraph a bullet: a dot in front, and the lines it wraps onto stand in with the words.

    ⚠ **点は段落の書式で書く** (= 字で入れない)。字で入れた点は、折り返した行が点の下へ回り込み、人が
    PowerPoint で行を足しても点が付かない。字下げの幅は数える側と同じ (= `bullet_indent`)。
    """
    properties = paragraph._p.get_or_add_pPr()
    indent = bullet_indent(size)
    properties.set("marL", str(indent))
    properties.set("indent", str(-indent))
    properties.append(properties.makeelement(qn("a:buChar"), {"char": "\u2022"}))


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
#: 白抜きの印の縁の太さ (= 線の太さの倍率)
RING = 1.5

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

    # 目盛りの線は引かない。値の数字を棒に付けたグラフは、値の軸も出さない (= 同じ数を 2 度見せない)。
    # 範囲を書いたグラフ (= `scale`) だけは、軸と、目盛りごとの薄い線を出す (= 読み手が範囲の中の位置を測る。下)
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
    if element.scale is not None:
        low, high, step = element.scale
        chart.value_axis.minimum_scale = low
        chart.value_axis.maximum_scale = high
        chart.value_axis.major_unit = step
        chart.value_axis.has_major_gridlines = True
        grid = chart.value_axis.major_gridlines.format.line
        grid.color.rgb = _colour(element.line)
        grid.width = Emu(theme.spacing.hairline)
    elif not element.axis and element.pinned is None:
        _zero_end(chart, element)
    if element.pinned:
        _pin(chart, element)
    _words(holder, element, theme)

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


def _words(holder, element: Chart, theme: Theme) -> None:
    """The words a chart carries (= what points at a point, what is said beside a name), and the thin line to the point."""
    for callout in element.callouts:
        if callout.line is not None:
            _fill(holder, Fill("callout", callout.line, element.colour), theme)
        _text(holder, Text("label", callout.words, callout.text, callout.size or element.size,
                           callout.colour or element.colour, align=callout.align), theme)


def _zero_end(chart, element: Chart) -> None:
    """Hold 0 at the end of a hidden value axis, so the bars stand in the ratio of their numbers.

    ⚠ **値の軸を隠したグラフは、軸の端を描く側の自動に任せない。**近い値ばかりのグラフ (= 75 / 75 / 67) で、
    描く側 (= LibreOffice、PowerPoint も Excel と同じ決め方) は下限を 0 より上に取り、67 の棒が 75 の棒の
    半分以下の高さに見えた。軸が隠れているので、読み手は下限が 0 でないことに気づけない。値が全部 0 以上なら
    下限を、全部 0 以下なら上限を 0 に置く (= 正と負が混ざるグラフは、自動でも 0 をまたぐ)。
    """
    values = [value for series in element.series for value in series.values if value is not None]
    if values and min(values) >= 0:
        chart.value_axis.minimum_scale = 0
    elif values and max(values) <= 0:
        chart.value_axis.maximum_scale = 0


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
    それぞれに名前を書く。目盛りの線は引かない (= ほかのグラフと同じ。`grid` を言ったグラフを除く)。
    名前を付けた点は、点の横にその字を置く。描く範囲を道具が決めたグラフ (= `plane`) は、それを書き出す。
    """
    data = XyChartData()
    for series in element.series:
        drawn = data.add_series(series.name)
        for x, y in zip(series.xs, series.values):
            drawn.add_data_point(x, y)
    # ⚠ **行ごとの言葉を持つグラフは、言葉と 1 つのグループにまとめる** (= 注記と同じ。別々のままだと、人が
    # グラフを動かしたとき、言葉が元の場所に置き去りになる)
    holder = slide if not element.callouts else slide.shapes.add_group_shape()
    frame = element.rect
    chart = holder.shapes.add_chart(XL_CHART_TYPE.XY_SCATTER, Emu(frame.left), Emu(frame.top),
                                    Emu(frame.width), Emu(frame.height), data).chart
    _dress(chart, element, theme)
    for axis, name in ((chart.category_axis, element.x_title), (chart.value_axis, element.y_title)):
        axis.has_major_gridlines = bool(element.grid)
        if element.grid:
            lines = axis.major_gridlines.format.line
            lines.color.rgb = _colour(element.grid)
            lines.width = Emu(theme.spacing.hairline)
        axis.major_tick_mark = XL_TICK_MARK.NONE
        axis.format.line.color.rgb = _colour(element.line)
        if not name:
            continue
        axis.has_title = True
        words = axis.axis_title.text_frame
        words.text = name
        for run in words.paragraphs[0].runs:
            run.font.size = Pt(element.size)
            run.font.bold = False
            run.font.name = theme.type.family
            run.font.color.rgb = _colour(element.colour)
    # 縦の軸を出さないグラフ (= 行を並べるグラフ。縦は行の番号で、読み手に見せる数ではない)
    if not element.axis:
        chart.value_axis.visible = False
    if element.plane:
        _plane(chart, element)
    _words(holder, element, theme)
    # 点の間に線は引かれない (= この種類のグラフを、python-pptx は線なしで書き出す)
    for drawn, series in zip(chart.plots[0].series, element.series):
        drawn.marker.style = XL_MARKER_STYLE.CIRCLE
        drawn.marker.size = round(series.mark) or POINT
        if series.outline:
            # 縁のある印 (= 色が空なら白抜き。縁は点より太く引く)
            _solid(drawn.marker.format, series.colour, series.outline, theme)
            drawn.marker.format.line.width = Emu(round(theme.spacing.hairline * RING))
        else:
            _solid(drawn.marker.format, series.colour)
        for label in series.labels:
            _name_point(drawn.points[label.index].data_label, label, element, theme)


def _name_point(data_label, label, element: Chart, theme: Theme) -> None:
    """Set one point's words beside it (= its own text, not the number the chart would print)."""
    frame = data_label.text_frame
    # ⚠ 折り返さない (= 点の横の言葉は、道具が測った幅で置いた。描く側の折り返しに任せると、言葉が縦に伸びて隣に乗る)
    frame.word_wrap = False
    for number, line in enumerate(label.text.split("\n")):
        paragraph = frame.paragraphs[0] if number == 0 else frame.add_paragraph()
        run = paragraph.add_run()
        run.text = line
        run.font.size = Pt(label.size or element.size)
        run.font.name = theme.type.family
        run.font.color.rgb = _colour(element.colour)
    data_label.position = XL_LABEL_POSITION.LEFT if label.left else XL_LABEL_POSITION.RIGHT


def _plane(chart, element: Chart) -> None:
    """Hold the plot of a chart of points where the page worked it out: its area, and both axes.

    横の軸を対数にするのは、軸の `c:scaling` の頭に底を書くこと (= python-pptx に口が無い)。対数の軸の
    目盛りの間は、底の倍数 (= 10 なら 10 の累乗ごと)。
    """
    plane = element.plane
    _hold(chart, plane.inner)
    for axis, (low, high, step) in ((chart.category_axis, plane.x), (chart.value_axis, plane.y)):
        axis.minimum_scale = low
        axis.maximum_scale = high
        axis.major_unit = step
    if plane.log:
        scaling = chart.category_axis._element.find(qn("c:scaling"))
        scaling.insert(0, scaling.makeelement(qn("c:logBase"), {"val": "10"}))
    if plane.down:
        chart.value_axis.reverse_order = True
    if plane.x_format:
        chart.category_axis.tick_labels.number_format = plane.x_format
        chart.category_axis.tick_labels.number_format_is_linked = False


def _hold(chart, inner: tuple[float, float, float, float]) -> None:
    """Write where the plot sits: `c:plotArea`'s first child, as fractions of the chart's frame."""
    area = chart._chartSpace.chart.plotArea
    layout = area.makeelement(qn("c:layout"), {})
    manual = layout.makeelement(qn("c:manualLayout"), {})
    layout.append(manual)
    for tag, value in (("layoutTarget", "inner"), ("xMode", "edge"), ("yMode", "edge"),
                       *zip(("x", "y", "w", "h"), (f"{part:.6f}" for part in inner))):
        manual.append(manual.makeelement(qn(f"c:{tag}"), {"val": value}))
    for existing in area.findall(qn("c:layout")):
        area.remove(existing)
    area.insert(0, layout)


def _pin(chart, element: Chart) -> None:
    """Hold the plot where the page worked it out: its area inside the frame, and the value axis.

    描く範囲は `c:plotArea` の頭に、枠に対する比で書く (= `inner`: 軸の字や凡例を含まない、棒や線の入る
    矩形そのもの)。値の軸は端から端と目盛りの間を書く。
    """
    pinned = element.pinned
    _hold(chart, pinned.inner)
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
    # 列の数は、区切りでない最初の行が言う (= 区切りは 1 つのセルの行)
    rows, columns = len(element.rows), len(next(row for r, row in enumerate(element.rows) if r not in element.bands))
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
    plain = theme.table_look == "plain"
    # 本文の縞は、区切りの行を数えずに続ける (= 区切りが入っても、縞の並びは同じ)
    above = 0
    for r, row in enumerate(element.rows):
        heading = bool(element.header and r == 0)
        if r in element.bands:
            above += 1
            _band(table, r, columns, row[0], element.bands[r], theme, plain)
            continue
        for c, value in enumerate(row):
            cell = table.cell(r, c)
            _pad(cell, theme)
            # 地の濃さを言ったセルは、差し色をその段まで薄めた地。字は、その地の上で読める方の色
            ground = (theme.palette.shade(element.shades[(r, c)]) if (r, c) in element.shades
                      else _cell_colour(theme, heading, r - above))
            cell.fill.solid()
            cell.fill.fore_color.rgb = _colour(ground)
            if plain:
                _rules(cell, theme)
            cell.text = value
            mark = (r, c) in element.marks
            # 字は地の上で読める方の色 (= 見出し行の地は案件の差し色。薄い差し色に白い字を決め打つと
            # 読めない見出しになった)
            ink = theme.palette.words_on(ground, theme.type.body, heading)
            _cell_words(cell, theme, bold=heading, colour=element.highlight.get((r, c)) or ink, mark=mark)


def _pad(cell, theme: Theme) -> None:
    cell.margin_top = Emu(theme.spacing.cell_pad_y)
    cell.margin_bottom = Emu(theme.spacing.cell_pad_y)
    cell.margin_left = Emu(theme.spacing.cell_pad_x)
    cell.margin_right = Emu(theme.spacing.cell_pad_x)


def _cell_words(cell, theme: Theme, *, bold: bool, colour: str, mark: bool = False) -> None:
    # ⚠ **セルの文の行は、全部同じに書く。**改行を含む文は行ごとに別の段落になる。最初の段落にだけ
    # 大きさ・色・書体を付けていた間は、改行の後の行が pptx の既定の大きさ (= 18pt) で出た
    for paragraph in cell.text_frame.paragraphs:
        paragraph.alignment = PP_ALIGN.LEFT
        for run in paragraph.runs:
            run.font.size = Pt(theme.type.body)
            run.font.bold = bold
            run.font.name = MARK_FACE if mark else theme.type.family
            run.font.color.rgb = _colour(colour)
            if mark:
                _every_script(run, MARK_FACE)


def _band(table, r: int, columns: int, words: str, painted: tuple[str, str], theme: Theme, plain: bool) -> None:
    """A row that divides the table: one cell across every column, in bold.

    ⚠ **またぐ列の全部のセルに、地と罫線を書く。**またがれた側にも同じ地と罫線を持たせておくと、
    PowerPoint で区切りをセルに分け直しても、見た目が変わらない。
    """
    ground, ink = painted
    for c in range(columns):
        cell = table.cell(r, c)
        _pad(cell, theme)
        cell.fill.solid()
        cell.fill.fore_color.rgb = _colour(ground)
        if plain:
            _rules(cell, theme)
    first = table.cell(r, 0)
    if columns > 1:
        first.merge(table.cell(r, columns - 1))
    first.text = str(words)
    _cell_words(first, theme, bold=True, colour=ink)


def _rules(cell, theme: Theme) -> None:
    """A rule on every side of a cell, in the colour of the rules (= `table_look = "plain"`).

    ⚠ **罫線は地より前に書く。**セルの性質の中の並びは、左・右・上・下の線、それから地 (= schema の決め)。
    並びが違う file を PowerPoint は修復しようとする。
    """
    properties = cell._tc.get_or_add_tcPr()
    for index, side in enumerate(("lnL", "lnR", "lnT", "lnB")):
        line = properties.makeelement(qn(f"a:{side}"), {"w": str(theme.spacing.hairline)})
        fill = line.makeelement(qn("a:solidFill"), {})
        fill.append(fill.makeelement(qn("a:srgbClr"), {"val": theme.palette.rule}))
        line.append(fill)
        properties.insert(index, line)


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
    """見出しは差し色、本文は 1 行おきに薄く敷く (= 横に目が滑らないように)。

    `table_look = "plain"` の表は、見出しを灰の地に、本文は縞なしの紙の色にする (= 目を滑らせるのは罫線)。
    """
    if theme.table_look == "plain":
        return theme.palette.wash if heading else theme.palette.paper
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
