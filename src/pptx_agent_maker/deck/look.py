"""Reading a deck's look out of the specimen itself.

見た目は**案件のもの**で、案件が持つのは `specimen.pptx` 1 枚。そこにマスターとテーマが
入っているのに、型で組む頁はそれを通らない (= 白紙に置いてから輸入する構造) ので、
同じ見た目を `workspace.toml` にもう一度書く必要があった。

⚠ **同じことが 2 か所に書いてあると、片方だけ直したときに顔が割れる。**ここはテンプレートの
テーマを読んで、書くのを 1 か所に戻す層。`[theme]` を書けばそちらが勝つ (= テンプレートの
配色がツールの色の使い方 (= 読みを示す色 / 条件の帯) と合わないときの逃げ道)。
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

#: テーマの色の枠 → ツールの色。`scripts/bake-template.py` の対応の逆で、
#: **両方向で同じ 1 つの表を見ている**ことを test が確かめる。
SLOTS = (
    ("dk1", "ink"), ("lt1", "paper"), ("dk2", "muted"), ("lt2", "band"),
    ("accent1", "accent"), ("accent2", "good"), ("accent3", "bad"),
    ("accent4", "rule"), ("accent5", "box"),
)
_SCHEME = re.compile(r"<a:clrScheme.*?</a:clrScheme>", re.S)
_COLOUR = re.compile(r'<a:(\w+)><a:srgbClr val="([0-9A-Fa-f]{6})"/></a:\1>')
_LATIN = re.compile(r'<a:majorFont><a:latin typeface="([^"]*)"')


def look_of(specimen: Path | str) -> dict:
    """The typeface and colours a specimen carries, in the shape `theme_from` reads.

    読めないものは**黙って既定に落とさず、その鍵を返さない** (= 呼ぶ側で既定が埋まる)。
    ⚠ 色を `<a:sysClr>` で持つテンプレート (= Office の既定) からは色が出ない。そこは
    「色を宣言していない」ので、ツールの既定がそのまま使われる。
    """
    specimen = Path(specimen)
    try:
        with zipfile.ZipFile(specimen) as archive:
            theme = archive.read("ppt/theme/theme1.xml").decode("utf-8")
    except (KeyError, OSError, zipfile.BadZipFile):
        return {}

    found = _SCHEME.search(theme)
    colours = dict(_COLOUR.findall(found.group(0))) if found else {}
    palette = {name: colours[slot].upper() for slot, name in SLOTS if slot in colours}

    look: dict = {}
    family = _LATIN.search(theme)
    if family and family.group(1).strip():
        look["font"] = family.group(1)
    if palette:
        look["palette"] = palette
    return look


def merged(specimen: Path | str, declared: dict | None) -> dict:
    """The specimen's look, with whatever the project declared laid over it.

    ⚠ **下地はテンプレート。**案件が持つ見た目は pptx 1 枚で、`[theme]` はその上の例外
    (= テンプレートの配色がツールの色の使い方と合わないときだけ書く)。色は 1 つずつ重なるので、
    差し色だけを宣言しても他の色はテンプレートのまま残る。
    """
    declared = declared or {}
    look = look_of(specimen)
    look.update({key: value for key, value in declared.items() if key != "palette"})
    palette = {**look.get("palette", {}), **(declared.get("palette") or {})}
    if palette:
        look["palette"] = palette
    return look
