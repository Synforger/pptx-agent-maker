"""Shapes that leave the page.

宣言層で組んだ頁では起きない (= 割った枠は親の中に在る)。**起きるのは複製と輸入**で、
過去の週に手で置かれた座標がそのまま来る。旧世代の検査は「文字が枠に収まるか」しか見ず、
枠そのものの飛び出しを 1 行ぶん通した。
"""

from __future__ import annotations

from pathlib import Path

from ..finding import Finding
from ..slide import read, slide_size

NAME = "off_page"
SLACK = 12700  # 1pt: shadows and borders legitimately sit a hair outside


def run(deck: Path, config: dict | None = None) -> list[Finding]:
    width, height = slide_size(deck)
    findings: list[Finding] = []
    for page in read(deck):
        for shape in page.shapes():
            if (shape.left < -SLACK or shape.top < -SLACK
                    or shape.right > width + SLACK or shape.bottom > height + SLACK):
                label = (shape.texts() or ["(no text)"])[0][:40]
                findings.append(Finding(
                    NAME, page.number, f"{shape.kind} {label!r}",
                    "sits outside the page — it will be cut off when presented"))
    return findings
