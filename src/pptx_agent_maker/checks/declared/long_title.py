"""A declared page's title that runs past two lines.

題のプレースホルダを持つ頁は、焼いた deck の側で同じ名前の検査が見る (= `rules/long_title.py`)。ここは
宣言で組む頁 ― 題の文と文字の大きさと枠の幅が全部分かっているので、頁が題の帯の高さを取るのと同じ
数 (= `Theme.title_lines`) を読む。
"""

from __future__ import annotations

from ...layout.base.tokens import Theme
from ..base.finding import Finding
from ..rules.long_title import LIMIT, NAME, off, why

__all__ = ["NAME", "run"]


def run(manifest, theme: Theme, config: dict | None = None) -> list[Finding]:
    if off(config):
        return []
    findings: list[Finding] = []
    for number, entry in enumerate(manifest.entries, start=1):
        title = str(entry.data.get("title", "")) if entry.kind == "declare" else ""
        lines = theme.title_lines(title) if title else 0
        if lines > LIMIT:
            findings.append(Finding(NAME, number, title[:60], why(lines)))
    return findings
