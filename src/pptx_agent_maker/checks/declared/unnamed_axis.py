"""A declared chart of categories whose value axis has no name.

軸が何の数かを言わないグラフは読めない (= 棒に付いた数字も、何の数かは言わない)。値の軸の名前は単位も含めて
書く ― 縦のグラフは `y`、横棒は `x`。項目の軸の名前は、項目そのものが何かを言うので知らせない。

見るのは宣言で組む頁の、項目を持つグラフ (= 頁の直下でも、`compose` のマスの中でも)。点のグラフは 2 つの軸の
名前が無ければ組めない (= 型が止める)。点の列と、数字も値の軸も出さない小さな棒 (= `bare`) は値の軸を持たない。
"""

from __future__ import annotations

from ..finding import Finding

NAME = "unnamed_axis"

#: 値の軸を持ち、軸の名前を書けるグラフの種類と、その値の軸の名前を書くキー
VALUE_AXIS = {"bar": "x", "column": "y", "line": "y", "stacked": "y", "waterfall": "y"}


def _unnamed(written) -> list[str]:
    """The kinds of the charts under `written` whose value axis has no name, in the order they are written."""
    found: list[str] = []
    if isinstance(written, dict):
        chart = written.get("chart")
        if isinstance(chart, dict) and chart.get("kind") in VALUE_AXIS and not chart.get("bare", False) \
                and not str(chart.get(VALUE_AXIS[chart["kind"]], "")).strip():
            found.append(str(chart["kind"]))
        for key, value in written.items():
            if key != "chart":
                found.extend(_unnamed(value))
    elif isinstance(written, list):
        for value in written:
            found.extend(_unnamed(value))
    return found


def run(manifest, theme=None, config: dict | None = None) -> list[Finding]:
    """A project may switch the check off (= `[checks] unnamed_axis = false`)."""
    if (config or {}).get(NAME, True) is False:
        return []
    findings: list[Finding] = []
    for number, entry in enumerate(manifest.entries, start=1):
        if entry.kind != "declare":
            continue
        for kind in _unnamed(entry.data):
            key = VALUE_AXIS[kind]
            findings.append(Finding(
                NAME, number, str(entry.data.get("title", ""))[:60],
                f"a {kind} chart whose value axis has no name — say what is counted, with its unit, in `{key}`"))
    return findings
