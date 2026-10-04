"""Reading what a page wrote: the declaration itself, and the tables every type reads the same way.

カード・ノード・棒・段が書ける見た目のキー (= `LOOK_KEYS`) も、色の役の読み方も、ここの 1 か所が持つ。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ...base.tokens import DEFAULT, Theme
from ...parts.look import Style, TONES
from ...parts.page import Card
from .registry import PageTypeError


@dataclass(frozen=True)
class Spec:
    """One declared page, plus the two things it needs from outside.

    `asset` と `aspect` を渡してもらうのは、頁の層が外の path も画像の中身も
    知らないまま保つため (= 座標が在るのはこの層だけ、という境界と同じ理由)。
    """

    data: dict
    asset: Callable[[str], Path]
    aspect: Callable[[Path], float]
    #: 頁の見た目 (= 案件が名前を付けた地を、`tone` として読むため)
    theme: Theme = DEFAULT

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def text(self, key: str, default: str = "") -> str:
        value = self.data.get(key, default)
        return "" if value is None else str(value)

    def figure(self, key: str = "figure") -> tuple[Path, float]:
        """An image by name, with the aspect ratio read off the file itself.

        ⚠ **縦横比を宣言に書かせない。**手で書くと、絵を差し替えた日に古い比が残って
        潰れた絵が焼ける (= 前の世代で実際に起きた)。
        """
        path = self.asset(str(self.data[key]))
        return path, self.aspect(path)

    def figures(self, key: str = "figures") -> list[tuple[Path, float, str]]:
        """Several images, each with its own caption (= `"name.png"` or `[name, caption]`)."""
        out = []
        for item in self.data[key]:
            if isinstance(item, (list, tuple)):
                name, caption = (list(item) + [""])[:2]
            else:
                name, caption = item, ""
            path = self.asset(str(name))
            out.append((path, self.aspect(path), str(caption)))
        return out

    def rows(self, key: str = "table") -> list[list[str]]:
        return [[str(cell) for cell in row] for row in self.data[key]]

    def cards(self) -> list[Card]:
        return [read_card(self, item, f"cards: card {number}")
                for number, item in enumerate(self.data["cards"], start=1)]


def only_keys(item, allowed: set, what: str, hint: str = "") -> None:
    """Refuse a key nobody reads inside a type's own tables, the way a page's keys are."""
    if not isinstance(item, dict):
        raise PageTypeError(f"{what} is {item!r} — write it as a table of keys")
    unknown = sorted(item.keys() - allowed)
    if unknown:
        raise PageTypeError(
            f"{what} does not take {', '.join(unknown)} (= it accepts "
            f"{', '.join(sorted(allowed))}).{hint}")


def read_tone(spec: Spec, item: dict, what: str, unsaid: str) -> str:
    """The tone a table asks for, or `unsaid` when it asks for none.

    書けるのは道具の色の役 (= `TONES`) と、案件が `[theme.grounds]` で名前を付けた地。
    """
    tone = str(item.get("tone", unsaid))
    named = spec.theme.ground_names()
    if tone not in TONES and tone not in named:
        grounds = (f"; this project names {', '.join(named)} in [theme.grounds]" if named
                   else "; a project may name its own in [theme.grounds]")
        raise PageTypeError(
            f"{what} has tone {tone!r} — a tone is one of the palette's roles: "
            f"{', '.join(TONES)}{grounds}")
    return tone


#: 箱・棒・矢羽根のどれにも書ける見た目のキー (= 色の役・アイコン・点線・強調)。1 組を全部が読む
LOOK_KEYS = ("tone", "icon", "tentative", "strong")


def _flag(item: dict, key: str, what: str) -> bool:
    value = item.get(key, False)
    if not isinstance(value, bool):
        raise PageTypeError(f"{what}: `{key}` is true or false, not {value!r}")
    return value


def read_style(spec: Spec, item: dict, what: str, unsaid: str) -> Style:
    """The four looks a table carries, read here for every part shaped like a box.

    `unsaid` は `tone` を書かなかった時の地で、部品ごとに違う (= 箱は `box`、道のりの段は薄い地か
    到達点の濃い地、線表の棒は空 ― 空は「レーンの色」で、置く側が決める)。

    ⚠ **読むのはここ 1 か所。**部品ごとに読んでいた間は、同じ 4 つを 3 か所が別の順で読み、1 つ足す
    たびに 3 か所を直すことになった。
    """
    return Style(read_tone(spec, item, what, unsaid) if "tone" in item else unsaid, _icon(spec, item, what),
                 tentative=_flag(item, "tentative", what), strong=_flag(item, "strong", what))


#: アイコンに読める絵 (= 図と同じ。SVG は pptx に入れるのに描き直しの道具が要るので、まだ読まない)
ICON_FORMATS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff")


def read_card(spec: Spec, item, what: str) -> Card:
    """One card, or one node of a flow or a roadmap (= the same box, written the same two ways).

    書き方は 2 つ ― `["見出し", "本文"]` か、色の役やアイコンを付けるときの
    `{ heading = "…", body = "…", tone = "accent", icon = "device.png", tentative = true,
    strong = true }`。
    """
    if isinstance(item, dict):
        only_keys(item, {"heading", "body", *LOOK_KEYS}, what)
        if not str(item.get("heading", "")).strip():
            raise PageTypeError(f"{what} has no `heading` — a box says what it is")
        return Card(str(item["heading"]), str(item.get("body", "")), read_style(spec, item, what, TONES[0]))
    if isinstance(item, (list, tuple)) and len(item) == 2:
        return Card(str(item[0]), str(item[1]))
    raise PageTypeError(
        f"{what} is {item!r} — write it as [\"heading\", \"body\"], or as a table "
        "{ heading = …, body = …, tone = …, icon = … }")


def _icon(spec: Spec, item: dict, what: str) -> tuple[Path, float] | None:
    """The picture a box carries beside its words, read like any figure (= from the assets)."""
    if "icon" not in item:
        return None
    name = str(item["icon"])
    if Path(name).suffix.lower() not in ICON_FORMATS:
        raise PageTypeError(
            f"{what} has the icon {name!r} — an icon is a picture file "
            f"({' / '.join(ICON_FORMATS)}); export an SVG as PNG, at a few times the size it "
            "is shown")
    path = spec.asset(name)
    return path, spec.aspect(path)
