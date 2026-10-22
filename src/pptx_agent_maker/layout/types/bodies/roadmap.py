"""The road to a goal, as arrowheads."""

from __future__ import annotations

from ...geometry import Rect
from ...parts.page import Page, PageFullError
from ..core.read import LOOK_KEYS, only_keys, read_style, read_weight, Spec
from ..core.registry import PageTypeError, register
from ..core.stack import aligned_rows, fill_stacks, place_stack, stage_stacks


@register("roadmap", needs=["stages"], takes=["align_rows"])
def _roadmap(page: Page, spec: Spec, area: Rect) -> None:
    """The road to a goal: stages left to right as arrowheads, each holding what it delivers.

    段は `name` (= 矢羽根の中。時期と版を「11 月上旬 | 0.4.0」のように書く) と `nodes`
    (= flow と同じ 2 通りの書き方と `tone`、`icon`)。**`nodes` は省ける** (= 矢羽根だけの段。
    全部の段で省けば、矢羽根の帯だけが立つ。一部の段だけ省けば、その段の下は空く)。flow の段は
    中身が要る型なので、省けない。**最後の段だけ** `goal = true` を書ける (= 到達点。濃い地で、
    名前を一回り大きく置く)。`align_rows` は flow と同じ。

    `weight` は段の幅の比 (= 0 より大きい数。書かなければ 1 で、全部の段が書かなければ等分。
    一部の段だけ書いてもよい)。段の下のノードは、自分の列の幅で折り返す。

    矢羽根は最初の段が左の平らな形、2 段目からが左の切り欠いた形で、先が次の段の切り欠きに
    噛み合う。向きは矢羽根が示すので、段の間に「→」は置かない。
    """
    stages = spec.get("stages") or []
    if len(stages) < 2:
        raise PageTypeError("roadmap: a road needs at least two stages")
    for number, stage in enumerate(stages, start=1):
        what = f"roadmap: stage {number}"
        if not isinstance(stage, dict):
            raise PageTypeError(f"{what} is {stage!r} — write it as a table "
                                "{ name = …, nodes = […], goal = … }")
        only_keys(stage, {"name", "nodes", "goal", "weight", *LOOK_KEYS}, what)
        if not str(stage.get("name", "")).strip():
            raise PageTypeError(f"{what} has no `name` — an arrowhead says when it is")
        goal = stage.get("goal", False)
        if not isinstance(goal, bool):
            raise PageTypeError(f"{what}: `goal` is true or false, not {goal!r}")
        if goal and number != len(stages):
            raise PageTypeError(
                f"{what} is marked as the goal, but the goal is where the road ends — "
                "only the last stage takes `goal = true`")
    weights = [read_weight(stage, f"roadmap: stage {number}") for number, stage in enumerate(stages, start=1)]
    aligned = aligned_rows(spec, "roadmap")
    goal = bool(stages[-1].get("goal"))

    theme, s, ty = page.theme, page.theme.spacing, page.theme.type
    gap = s.gap_s
    columns = area.columns(weights, gap=s.gap_m)
    # ノードの折り返しは列の幅で決まるので、幅の違う段は段ごとの幅で数える
    stacks, stack = stage_stacks(page, spec, stages, [column.width for column in columns], aligned,
                                 "roadmap", bare=True)

    # 矢羽根は自分の列から次の列の頭まで伸び、先が次の段の切り欠きに入る (= 最後の段は列の中で
    # 尖る)。文字が使える幅は、プリセットが決めた文字の枠 (= 切り欠きと先を除いた幅) から余白を引く
    point = s.chevron_point
    arrows, sizes = [], []
    for index, (stage, column) in enumerate(zip(stages, columns)):
        last = index == len(stages) - 1
        right = column.right if last else columns[index + 1].left
        shape = "home" if index == 0 else "chevron"
        cut = point // 2 if shape == "home" else 2 * point     # 文字の枠が左右で失う幅
        room = max(right - column.left - cut - 2 * s.bar_pad_x, 1)
        size = ty.heading if last and goal else ty.stage
        style = read_style(spec, stage, f"roadmap: stage {index + 1}", "accent" if last and goal else "band")
        # アイコンは名前の前に字の高さで置く (= 名前の使える幅がそのぶん狭い)
        room = max(room - (theme.line_height(size) + s.gap_s if style.icon else 0), 1)
        tall = theme.wrapped_height(str(stage["name"]), room, size, bold=True) + 2 * s.bar_pad_y
        arrows.append((Rect(column.left, area.top, right - column.left, 1), shape, size, tall, style))
    head_height = max(tall for _r, _s, _z, tall, _style in arrows)

    wanted = head_height + (gap + stack if stack else 0)   # 矢羽根だけの道のりは、帯の高さだけ要る
    if wanted > area.height:
        raise PageFullError(
            f"this roadmap needs {wanted} EMU of height and the body has {area.height} — "
            "shorten the nodes or split the stages across two pages; it will not shrink")

    # 字の高さの資料では、ここは何もしない。頁の高さを使う資料では、ノードが残りの高さを分け合う
    stacks, stack = fill_stacks(page, stacks, stack, area.height - head_height - gap, aligned)

    page.drew_a_diagram()  # 矢羽根とノードで組んだ道のりそのものが、この頁の図解
    for (rect, shape, size, _tall, style), stage, column, column_nodes in zip(
            arrows, stages, columns, stacks):
        page.chevron(Rect(rect.left, area.top, rect.width, head_height), str(stage["name"]), style,
                     shape=shape, size=size)
        _head, rest = column.split_top(head_height, gap=gap)
        place_stack(page, rest.split_top(stack)[0], column_nodes)
