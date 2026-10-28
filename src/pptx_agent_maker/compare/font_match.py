"""Whether a typeface a deck names is one this machine has, from what `fc-match` answered.

`fonts.py` asks `fc-match` and calls this with its answer; touches no file and starts no command.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_IGNORED = re.compile(r"[\s_-]")


def _key(name: str) -> str:
    return _IGNORED.sub("", name).casefold()


def is_installed(requested: str, matched_families: Iterable[str]) -> bool:
    """The requested typeface is among the family names `fc-match` found for it.

    ⚠ **`fc-match` は無い書体にも、いちばん近い別の書体を答える** (= Meiryo を頼むと Verdana)。答えがあることでは
    入っているか分からないので、頼んだ名前が答えの家族名のどれかと同じかを見る。fontconfig の決め方に合わせ、
    大文字小文字と空白とハイフンは区別しない (= `Yu Gothic` と `YuGothic` は同じ家族)。
    """
    return _key(requested) in {_key(family) for family in matched_families}
