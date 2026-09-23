"""Build slide decks by declaring structure, not coordinates.

    layout/   版面を割る (= 座標が在るのはここだけ)。types が頁の型を持つ
    write/    焼く
"""

from .layout import (DEFAULT, Page, PageFullError, PageTypeError, Palette, Rect,
                     Spacing, Theme, Type, cm, pt, types)

__all__ = ["Rect", "cm", "pt", "Page", "PageFullError", "Theme", "Type", "Palette",
           "Spacing", "DEFAULT", "types", "PageTypeError"]
