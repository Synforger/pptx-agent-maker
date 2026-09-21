"""Build slide decks by declaring structure, not coordinates.

    layout/   版面を割る (= 座標が在るのはここだけ)
    write/    焼く
"""

from .layout import DEFAULT, Page, PageFullError, Palette, Rect, Spacing, Theme, Type, cm, pt

__all__ = ["Rect", "cm", "pt", "Page", "PageFullError", "Theme", "Type", "Palette", "Spacing", "DEFAULT"]
