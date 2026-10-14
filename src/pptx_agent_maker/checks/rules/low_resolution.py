"""A picture blown up past the pixels it has.

頁の上で 1 インチに並ぶ画素 (= ppi) が少ない絵は、映すとぼやけて見える。元の絵の画素を、頁の上の
枠の大きさで割って数える (= 切り抜いた絵は残った画素で)。

閾値は 150 ppi (= 案件で外すなら `[checks] low_resolution = false`)。
"""

from __future__ import annotations

from pathlib import Path

from ..base.finding import Finding
from ..base.picture import placed

NAME = "low_resolution"
#: 頁の上で 1 インチに並ぶ画素の下限
FLOOR = 150
#: 1 inch = 914400 EMU
PER_INCH = 914400


def run(deck: Path, config: dict | None = None) -> list[Finding]:
    if (config or {}).get(NAME, True) is False:
        return []
    findings: list[Finding] = []
    for picture in placed(deck):
        width, height = picture.shown_pixels
        if not picture.shape.width or not picture.shape.height:
            continue
        ppi = min(width / (picture.shape.width / PER_INCH), height / (picture.shape.height / PER_INCH))
        if ppi < FLOOR:
            findings.append(Finding(
                NAME, picture.page, f"picture {picture.pixels[0]}x{picture.pixels[1]}px",
                f"shown at {ppi:.0f} ppi, below {FLOOR} — it will look blurred; "
                "use a larger image or show it smaller"))
    return findings
