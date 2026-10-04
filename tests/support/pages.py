"""What the tests of the page types all do: build one declared page, and find what was placed on it.

**同じ 3 つが test の file ごとに書かれていた** (= 名前で要素を引く / 見出しの入った箱を引く / 頁を組む)。
1 つは返す物まで違っていて、読む側は file ごとに確かめ直すことになった。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from pptx_agent_maker.layout import types  # noqa: E402
from pptx_agent_maker.layout.base.tokens import DEFAULT, Theme  # noqa: E402
from pptx_agent_maker.write import aspect  # noqa: E402

#: test が使う絵の置き場 (= 数バイトの絵。`dot.png` は 8 x 8、`wide.png` は 16 x 4)
DATA = REPO / "tests" / "data"


def build(spec: dict, theme: Theme = DEFAULT):
    """One declared page, as the toolkit builds it, with its pictures read from `tests/data`."""
    return types.build(spec, lambda name: DATA / name, aspect, theme)


def named(built, text: str):
    """The element that carries exactly these words."""
    return next(e for e in built.build() if getattr(e, "text", None) == text)


def box_of(built, heading: str):
    """The filled box a heading sits in (= the element; its place is `.rect`)."""
    head = named(built, heading).rect
    return next(e for e in built.build() if e.kind == "box" and e.rect.contains(head))
