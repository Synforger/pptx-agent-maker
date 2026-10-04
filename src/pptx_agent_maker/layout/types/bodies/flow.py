"""Stages left to right, each holding its nodes — or, turned, stages top to bottom."""

from __future__ import annotations

from ...base.geometry import Rect
from ...parts.page import Page, PageFullError
from ..core.read import Spec, read_card
from ..core.registry import PageTypeError, register
from ..core.stack import aligned_rows, card_height, place_stack, stage_stacks

#: 流れの向き。`right` は段を左から右 (= 既定)、`down` は段を上から下
DIRECTIONS = ("right", "down")


@register("flow", needs=["stages"], takes=["align_rows", "direction"])
def _flow(page: Page, spec: Spec, area: Rect) -> None:
    """Stages left to right, each holding its nodes, each with what is settled below.

    `direction = "down"` は、段を上から下へ並べる (= `_down`。段の中のノードは横に並び、2 つ以上なら
    そこが分岐になる)。

    `align_rows = true` は、同じ順番のノードを段をまたいで横に揃える (= 行が「誰の仕事か」の
    ような意味を持つ頁のため。行の高さはその行で一番高いノードに合わせる)。書かなければ、
    ノードは段ごとに自分の言葉の高さで積まれる。

    ⚠ **段の間の向きは文字で置く** (= `marker`)。矢印のプリセット 1 つで PowerPoint が
    修復を言い出した実例がある。
    """
    stages = spec.get("stages")
    if len(stages) < 2:
        raise PageTypeError("flow: a flow needs at least two stages")
    direction = spec.get("direction", "right")
    if not isinstance(direction, str) or direction not in DIRECTIONS:
        raise PageTypeError(
            f"flow: `direction` is {direction!r} — a flow runs {' or '.join(repr(way) for way in DIRECTIONS)}")
    if direction == "down":
        _down(page, spec, stages, area)
        return
    aligned = aligned_rows(spec, "flow")

    weights: list[float] = []
    for index in range(len(stages)):
        if index:
            weights.append(0.18)
        weights.append(1.0)
    columns = area.columns(weights, gap=page.theme.spacing.gap_s)

    # ノードの高さは**そのノードの言葉**で決め、段ごとに積む。積んだ高さの最大に全段を
    # 揃えるので、列の下端は揃いながら、1 つしかない段が 2 つ分の空きを抱えることもない。
    gap = page.theme.spacing.gap_s
    wide = columns[0].width
    stacks, stack = stage_stacks(page, spec, stages, wide, aligned, "flow")
    stage_size = page.theme.type.stage
    head_height = max(page.theme.wrapped_height(str(stage["name"]), wide, stage_size, bold=True)
                      for stage in stages)
    # 段の下の 1 行も頁の中身なので、本文の大きさで置く (= 脚注の大きさにしない)
    settled_height = max(
        (page.theme.wrapped_height(str(stage["settled"]), wide - 2 * page.theme.spacing.text_inset)
         for stage in stages if stage.get("settled")), default=0)
    wanted = head_height + gap + stack + (gap + settled_height if settled_height else 0)
    if wanted > area.height:
        raise PageFullError(
            f"this flow needs {wanted} EMU of height and the body has {area.height} — "
            "shorten the nodes or split the stages across two pages; it will not shrink"
        )

    page.drew_a_diagram()  # 段とノードで組んだ流れ図そのものが、この頁の図解
    for index, (stage, column_nodes) in enumerate(zip(stages, stacks)):
        column = columns[index * 2]
        head, rest = column.split_top(head_height, gap=gap)
        page.stage(head, str(stage["name"]))
        body, after = rest.split_top(stack, gap=gap)
        if index:
            # 向きはノードの並びの高さに置く (= 段の名前の横に浮かせない)
            between = columns[index * 2 - 1]
            page.marker(Rect(between.left, body.top, between.width, body.height), "→")
        place_stack(page, body, column_nodes)
        if stage.get("settled") and settled_height:
            page.note(after.split_top(settled_height)[0], str(stage["settled"]))


def _down(page: Page, spec: Spec, stages: list, area: Rect) -> None:
    """Stages top to bottom: the nodes of a stage side by side, its name at its left, an arrow between two.

    左から右の流れ図を転置した形。**段の中のノードは横に並ぶ** ― 1 つなら段の幅いっぱい、2 つ以上なら
    等分で、そこが横への分岐になる (= 分岐と合流は、段ごとのノードの数で書く)。

    * 段の名前は左の列に、1 行で立つ。列の幅は、いちばん長い名前の幅 (= 比では決めない)
    * 段の高さは、その段でいちばん高いノードの高さ (= 横に並ぶノードは同じ高さに揃う)
    * 段の下の 1 行 (= `settled`) は、その段のノードの下に置く
    * 段と段の間に、向きの字を 1 つ (= 高さは、その字 1 行ぶん)

    ⚠ **収まらない流れは止まる** (= 縮めない)。段を減らすか、2 頁に分ける。
    """
    theme, s = page.theme, page.theme.spacing
    if "align_rows" in spec.data:
        raise PageTypeError(
            "flow: `align_rows` lines up the nodes of a flow that runs right — in one that runs down, "
            "the nodes of a stage already share its height")
    gap = s.gap_s
    named = max(theme.width(str(stage["name"]), theme.type.stage, bold=True) for stage in stages)
    if named + s.gap_m >= area.width:
        raise PageFullError("flow: the names of the stages leave their nodes no room — shorter names")
    names, nodes_area = area.columns([named, area.width - named - s.gap_m], gap=s.gap_m)

    rows = []
    for number, stage in enumerate(stages, start=1):
        nodes = [read_card(spec, node, f"flow: stage {number}, node {index}")
                 for index, node in enumerate(stage.get("nodes", []), start=1)]
        if not nodes:
            raise PageTypeError(f"flow: stage {stage['name']!r} has no nodes")
        tall = card_height(page, nodes, nodes_area.width, len(nodes))
        settled = str(stage["settled"]) if stage.get("settled") else ""
        under = theme.wrapped_height(settled, nodes_area.width - 2 * s.text_inset) if settled else 0
        rows.append((str(stage["name"]), nodes, tall, settled, under))

    arrow = theme.line_height(theme.type.marker)
    wanted = (sum(tall + (gap + under if under else 0) for _n, _c, tall, _s, under in rows)
              + (len(rows) - 1) * (arrow + 2 * gap))
    if wanted > area.height:
        raise PageFullError(
            f"this flow needs {wanted} EMU of height and the body has {area.height} — "
            "fewer stages, shorter nodes, or two pages; it will not shrink")

    page.drew_a_diagram()  # 段とノードで組んだ流れ図そのものが、この頁の図解
    top = area.top
    for index, (name, nodes, tall, settled, under) in enumerate(rows):
        if index:
            page.marker(Rect(nodes_area.left, top + gap, nodes_area.width, arrow), "↓")
            top += arrow + 2 * gap
        # ⚠ 段の名前は折り返さない 1 行の名前として置く。列の幅は字の幅ちょうどなので、折り返す枠に
        # 入れると、焼いた絵で 1 文字ずつ縦に折れた
        page.label(Rect(names.left, top, names.width, tall), name, size=theme.type.stage, bold=True)
        page.boxes(Rect(nodes_area.left, top, nodes_area.width, tall), nodes)
        top += tall
        if under:
            page.note(Rect(nodes_area.left, top + gap, nodes_area.width, under), settled)
            top += gap + under
