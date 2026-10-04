"""The types a page may ask for, and the keys each of them reads."""

from __future__ import annotations

from typing import Callable, Iterable

from ...base.geometry import Rect
from ...parts.page import Page


#: A page type fills the area left for the body, and returns nothing.
Filler = Callable[[Page, "Spec", Rect], None]


#: 枠の宣言 (= 書かなければその帯は取られない)
FRAME_KEYS = frozenset({"type", "kind", "title", "kicker", "condition", "conclusion",
                        "footer", "replace", "legend"})


#: 本体に添えられるもの (= **どの型でも**読まれる。共通の処理が拾う)
#: ⚠ **カードの列数は `card_columns`。**絵の格子の `columns` と同じ名前だった間は、
#: 格子を 3 列にするとカードまで 3 枚ずつに割れ、格子以外の型ではカードの列数を書けなかった。
EXTRA_KEYS = frozenset({"cards", "card_columns", "table", "note", "points"})


TYPES: dict[str, tuple[Filler, frozenset, bool]] = {}


class PageTypeError(ValueError):
    """The declaration does not describe a page any type can build."""


def register(name: str, *, needs: Iterable[str], takes: Iterable[str] = (),
             figure: bool = True) -> Callable[[Filler], Filler]:
    """Declare a page type: what its body needs, what else it reads, and whether it shows a picture.

    ⚠ **`takes` は「この型が読む任意のキー」。**共通の付属 (= `EXTRA_KEYS`) と違って、
    読むのは宣言した型だけ ― 読まない型に書けるままだと、書いた人は書いたつもりで、
    焼いた頁にはそれが無い。実際に `figures` の頁で `caption` を黙って落としていた。
    """
    def decorate(filler: Filler) -> Filler:
        TYPES[name] = (filler, frozenset(needs), frozenset(takes), figure)
        return filler
    return decorate


def check_keys(name: str, data: dict, needs: frozenset,
                takes: frozenset = frozenset()) -> None:
    """Refuse a missing key and an unknown one alike.

    ⚠ **知らないキーを黙って捨てない。**綴り違いを捨てると、書いた人は書いたつもりで、
    焼いた頁にはそれが無い ― 前の世代で「値を変えても動かない」を 2 度踏んだ。
    """
    missing = sorted(needs - data.keys())
    if missing:
        raise PageTypeError(
            f"{name}: missing {', '.join(missing)} — this type is not that page without it"
        )
    unknown = sorted(data.keys() - needs - takes - EXTRA_KEYS - FRAME_KEYS)
    if unknown:
        allowed = ", ".join(sorted(needs | takes | EXTRA_KEYS | FRAME_KEYS))
        raise PageTypeError(
            f"{name}: does not take {', '.join(unknown)} (= it accepts {allowed}). "
            "A key nobody reads is a change that silently never happened."
        )
