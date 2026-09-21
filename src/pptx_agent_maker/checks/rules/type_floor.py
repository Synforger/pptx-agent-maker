"""Type smaller than anyone can read from a seat.

⚠ 見るのは**実際に文字を持つ run** だけ (= 空の run の大きさは誰も読まない)。
"""

from __future__ import annotations

from pathlib import Path

from ..finding import Finding
from ..slide import read

NAME = "type_floor"
DEFAULT_FLOOR = 10.0


def run(deck: Path, config: dict | None = None) -> list[Finding]:
    floor = float((config or {}).get("type_floor", DEFAULT_FLOOR))
    findings: list[Finding] = []
    for page in read(deck):
        for shape in page.shapes():
            for size in shape.type_sizes():
                if size < floor:
                    label = (shape.texts() or [""])[0][:40]
                    findings.append(Finding(
                        NAME, page.number, f"{size:g}pt {label!r}",
                        f"below the {floor:g}pt floor — unreadable from a seat"))
    return findings
