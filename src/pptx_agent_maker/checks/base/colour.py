"""Reading a colour the way PowerPoint paints it: a hex value, or a theme colour with its adjustments.

⚠ **測れない色は None を返す。**グラデーション・絵の塗り・透過、読み方の分からない調整は、どの色に
見えるかを決められない。決められない物を赤にしない (= 誤検出は「黙らせるためだけの直し」を書かせる)。
"""

from __future__ import annotations

import colorsys
import re

from ...layout.base.tokens import contrast  # noqa: F401 - 明暗差の数え方は道具の中で 1 つ (= 組む側と同じ)

SRGB = re.compile(r'<a:srgbClr val="([0-9A-Fa-f]{6})"\s*(/>|>(.*?)</a:srgbClr>)', re.S)
SCHEME = re.compile(r'<a:schemeClr val="(\w+)"\s*(/>|>(.*?)</a:schemeClr>)', re.S)
SYSTEM = re.compile(r'<a:sysClr\b[^>]*\blastClr="([0-9A-Fa-f]{6})"')
ADJUST = re.compile(r'<a:(\w+) val="(-?\d+)"\s*/>')
#: 色を変えても見え方が決まる調整 (= 明るさの掛け算と足し算)。ほかが付いた色は測らない
KNOWN = {"lumMod", "lumOff"}
#: マスターが書いていない時の、地と文字の読み替え (= PowerPoint の既定)
DEFAULT_MAP = {"bg1": "lt1", "tx1": "dk1", "bg2": "lt2", "tx2": "dk2"}


class Palette:
    """A deck's theme colours, read through its master's colour map."""

    def __init__(self, theme_xml: str = "", master_xml: str = "") -> None:
        self.colours: dict[str, str] = {}
        scheme = re.search(r"<a:clrScheme\b.*?</a:clrScheme>", theme_xml, re.S)
        if scheme:
            for name in ("dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3", "accent4",
                         "accent5", "accent6", "hlink", "folHlink"):
                slot = re.search(rf"<a:{name}>(.*?)</a:{name}>", scheme.group(0), re.S)
                if slot:
                    value = SRGB.search(slot.group(1)) or SYSTEM.search(slot.group(1))
                    if value:
                        self.colours[name] = value.group(1).upper()
        self.map = dict(DEFAULT_MAP)
        mapping = re.search(r"<p:clrMap\b([^>]*)/>", master_xml)
        if mapping:
            self.map.update(re.findall(r'(\w+)="(\w+)"', mapping.group(1)))

    def scheme(self, name: str) -> str | None:
        return self.colours.get(self.map.get(name, name))


def _adjusted(hex_value: str, adjustments: str) -> str | None:
    found = ADJUST.findall(adjustments or "")
    if any(name not in KNOWN for name, _ in found):
        return None  # 透過・色合い・濃淡は、どの色に見えるかを決めない
    if not found:
        return hex_value.upper()
    red, green, blue = (int(hex_value[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hue, light, saturation = colorsys.rgb_to_hls(red, green, blue)
    values = dict((name, int(value) / 100000) for name, value in found)
    light = min(1.0, max(0.0, light * values.get("lumMod", 1.0) + values.get("lumOff", 0.0)))
    red, green, blue = colorsys.hls_to_rgb(hue, light, saturation)
    return "".join(f"{round(c * 255):02X}" for c in (red, green, blue))


def solid(xml: str, palette: Palette) -> str | None:
    """The colour of the first solid fill in `xml`, or None when it cannot be told."""
    fill = re.search(r"<a:solidFill>(.*?)</a:solidFill>", xml, re.S)
    if not fill:
        return None
    body = fill.group(1)
    hexed = SRGB.search(body)
    if hexed:
        return _adjusted(hexed.group(1), hexed.group(3))
    themed = SCHEME.search(body)
    if themed:
        base = palette.scheme(themed.group(1))
        return _adjusted(base, themed.group(3)) if base else None
    system = SYSTEM.search(body)
    return system.group(1).upper() if system else None
