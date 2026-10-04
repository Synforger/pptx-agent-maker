"""Stages left to right, each holding its nodes."""

from __future__ import annotations

from ...base.geometry import Rect
from ...parts.page import Page, PageFullError
from ..core.read import Spec
from ..core.registry import PageTypeError, register
from ..core.stack import aligned_rows, place_stack, stage_stacks


@register("flow", needs=["stages"], takes=["align_rows"])
def _flow(page: Page, spec: Spec, area: Rect) -> None:
    """Stages left to right, each holding its nodes, each with what is settled below.

    `align_rows = true` は、同じ順番のノードを段をまたいで横に揃える (= 行が「誰の仕事か」の
    ような意味を持つ頁のため。行の高さはその行で一番高いノードに合わせる)。書かなければ、
    ノードは段ごとに自分の言葉の高さで積まれる。

    ⚠ **段の間の向きは文字で置く** (= `marker`)。矢印のプリセット 1 つで PowerPoint が
    修復を言い出した実例がある。
    """
    stages = spec.get("stages")
    if len(stages) < 2:
        raise PageTypeError("flow: a flow needs at least two stages")
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
