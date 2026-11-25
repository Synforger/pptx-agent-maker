"""A declared page that shows a picture, a chart or a table and does not say where it came from, in a deck that goes out.

出所の行は、社外に出す資料で、数字・引用・他の人の図の出典が要る時だけ頁に置く。ほかの資料の出どころは
頁の `why` が持ち、頁には出さない。資料が社外に出るかは道具からは読めないので、検査は案件が
`[checks] unsourced = true` と書いた時だけ回る (= 書かなければ回らない)。

見るのは宣言で組む頁だけ ― 複製や輸入の頁は、出所をどこに書いたかが頁ごとに違い、宣言からは
読めない。図解 (= 流れ図・道のり・線表) とカードだけの頁は、データを見せていないので対象外。
"""

from __future__ import annotations

from ..finding import Finding

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
    """Only for a project that switches the check on (= `[checks] unsourced = true`, a deck that goes out)."""
    if (config or {}).get(NAME, False) is not True:
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
