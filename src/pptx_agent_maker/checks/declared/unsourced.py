"""A declared page that shows a picture, a chart or a table and does not say where it came from.

データの図には出所を置く。頁を見た人が最初に訊くのは「この数字はどこから」で、書いていない頁は、
その場で答えられない数字を見せていることになる。

見るのは宣言で組む頁だけ ― 複製や輸入の頁は、出所をどこに書いたかが頁ごとに違い、宣言からは
読めない。図解 (= 流れ図・道のり・線表) とカードだけの頁は、データを見せていないので対象外。
"""

from __future__ import annotations

from ..base.finding import Finding

NAME = "unsourced"

#: データを見せる部品のキー (= 頁の直下でも、`compose` のマスの中でも同じ名前)
SHOWS = frozenset({"figure", "figures", "table", "chart"})


def _shows_data(written) -> bool:
    if isinstance(written, dict):
        return bool(SHOWS & written.keys()) or any(_shows_data(value) for value in written.values())
    if isinstance(written, list):
        return any(_shows_data(value) for value in written)
    return False


def run(manifest, theme=None, config: dict | None = None) -> list[Finding]:
    """A project may switch the check off (= `[checks] unsourced = false`)."""
    if (config or {}).get(NAME, True) is False:
        return []
    findings: list[Finding] = []
    for number, entry in enumerate(manifest.entries, start=1):
        if entry.kind != "declare" or str(entry.data.get("footer", "")).strip():
            continue
        if _shows_data(entry.data):
            findings.append(Finding(
                NAME, number, str(entry.data.get("title", ""))[:60],
                "shows a picture or a table and names no source — say where it came from in `footer`"))
    return findings
