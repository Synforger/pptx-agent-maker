"""Blank cells in a table.

空欄は「値が無い」のか「埋め忘れた」のか読み手に区別が付かない。値が無いなら「―」を置く。
⚠ 合計行や見出しの余白は空でよいので、**行の先頭列が埋まっている行**だけを見る。
"""

from __future__ import annotations

from pathlib import Path

from ..finding import Finding
from ..slide import read

NAME = "empty_cells"


def run(deck: Path, config: dict | None = None) -> list[Finding]:
    findings: list[Finding] = []
    for page in read(deck):
        for shape in page.shapes():
            for row_number, row in enumerate(shape.table_rows(), start=1):
                if not row or not row[0].strip():
                    continue
                for column, cell in enumerate(row[1:], start=2):
                    if not cell.strip():
                        findings.append(Finding(
                            NAME, page.number, f"row {row_number} column {column} ({row[0][:20]!r})",
                            "blank cell — write a dash if there is no value"))
    return findings
