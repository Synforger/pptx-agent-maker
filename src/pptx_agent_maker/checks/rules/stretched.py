"""A picture squashed or stretched out of its own shape.

宣言で組む頁は絵の縦横比を保って置く (= 元の比から枠を割る)。**崩れるのは複製と輸入**で、人が
PowerPoint で枠の角を片側だけ引いた絵がそのまま来る。切り抜いた絵は、残った部分の比で比べる。

閾値は比の食い違い 2% (= 目で分かり始める所。案件で外すなら `[checks] stretched = false`)。
"""

from __future__ import annotations

from pathlib import Path

from ..base.finding import Finding
from ..base.picture import ours, placed

NAME = "stretched"
#: 元の比と枠の比の食い違いの上限 (= 2%)
TOLERANCE = 0.02


def run(deck: Path, config: dict | None = None) -> list[Finding]:
    if (config or {}).get(NAME, True) is False:
        return []
    findings: list[Finding] = []
    for picture in ours(placed(deck), config):
        width, height = picture.shown_pixels
        frame = picture.shape.width / picture.shape.height if picture.shape.height else 0
        if not frame or not height:
            continue
        drift = frame / (width / height) - 1
        if abs(drift) > TOLERANCE:
            findings.append(Finding(
                NAME, picture.page, f"picture {picture.pixels[0]}x{picture.pixels[1]}px",
                f"drawn {abs(drift):.0%} {'wider' if drift > 0 else 'taller'} than it is — "
                "restore its own proportions (or crop it) instead of pulling one side"))
    return findings
