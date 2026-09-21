"""Words the specimen left behind.

型見本を複製して差し替え忘れると、**前の週の文言がそのまま出る**。もっともらしく読めるので
目では気づけない。差し替えるはずだった語を宣言し、残っていれば止める。
"""

from __future__ import annotations

from pathlib import Path

from ..finding import Finding
from ..slide import read

NAME = "unreplaced"


def run(deck: Path, config: dict | None = None) -> list[Finding]:
    """`stale_words` は案件が宣言する (= 前の週の名前・版・日付など)。"""
    words = [w for w in (config or {}).get("stale_words", []) if w]
    if not words:
        return []
    findings: list[Finding] = []
    for page in read(deck):
        for text in page.texts():
            for word in words:
                if word in text:
                    findings.append(Finding(
                        NAME, page.number, text.strip()[:60],
                        f"still says {word!r} — the specimen's words were not replaced"))
                    break
    return findings
