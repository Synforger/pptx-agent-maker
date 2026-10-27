"""Read a connector back out of the slide XML the way a viewer draws it, to tell where its corners really are.

**書いた物を、書いた側の計算でなく、プリセットの定義から読み直す。** 曲がるコネクタは、枠の左上から右へ進み、曲がり角
ごとに縦と横を交互に進んで右下に着く道を、反転と回転と調整値で動かして描く。ここはその道を XML から再現する。
"""

from __future__ import annotations

import re

Point = tuple[int, int]

#: プリセットの調整値の既定 (= 50%)
DEFAULT_ADJ = 50000


def connectors(xml: str) -> list[str]:
    """Every connector (`p:cxnSp`) of a slide, as its own XML."""
    return re.findall(r"<p:cxnSp>.*?</p:cxnSp>", xml, re.S)


def free_forms(xml: str) -> list[str]:
    """Every shape of a slide that draws its own path (`a:custGeom`), as its own XML."""
    return [shape for shape in re.findall(r"<p:sp>.*?</p:sp>", xml, re.S) if "<a:custGeom" in shape]


def drawn(connector: str) -> tuple[list[Point], str, tuple[int, int, int, int]]:
    """(its points from the begin to the end, which end has the head, the frame) as the file says it is drawn."""
    x, y = (int(v) for v in re.search(r'<a:off x="(-?\d+)" y="(-?\d+)"', connector).groups())
    w, h = (int(v) for v in re.search(r'<a:ext cx="(\d+)" cy="(\d+)"', connector).groups())
    turned = re.search(r'<a:xfrm[^>]*\brot="(\d+)"', connector)
    degrees = int(turned.group(1)) // 60000 if turned else 0
    preset = re.search(r'prst="(\w+)"', connector).group(1)
    adjustments = {name: int(value) for name, value in re.findall(r'<a:gd name="(adj\d)" fmla="val (-?\d+)"', connector)}
    if preset == "line":
        local = [(0, 0), (w, h)]
    else:
        bends = int(preset.removeprefix("bentConnector")) - 1
        x1, y2, x3 = (w * adjustments.get("adj1", DEFAULT_ADJ) / 100000, h * adjustments.get("adj2", DEFAULT_ADJ) / 100000,
                      w * adjustments.get("adj3", DEFAULT_ADJ) / 100000)
        local = {1: [(0, 0), (w, 0), (w, h)],
                 2: [(0, 0), (x1, 0), (x1, h), (w, h)],
                 3: [(0, 0), (x1, 0), (x1, y2), (w, y2), (w, h)],
                 4: [(0, 0), (x1, 0), (x1, y2), (x3, y2), (x3, h), (w, h)]}[bends]
    points = [(px - w / 2, py - h / 2) for px, py in local]
    if 'flipH="1"' in connector:
        points = [(-px, py) for px, py in points]
    if 'flipV="1"' in connector:
        points = [(px, -py) for px, py in points]
    cos, sin = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}[degrees]
    centre = (x + w / 2, y + h / 2)
    found = [(round(centre[0] + px * cos - py * sin), round(centre[1] + px * sin + py * cos)) for px, py in points]
    head = "end" if "<a:tailEnd" in connector else "begin" if "<a:headEnd" in connector else ""
    return found, head, (x, y, w, h)
