"""Dividing the frame: the only place coordinates exist."""

from . import types
from .base.geometry import Rect, cm, pt
from .parts.page import Page, PageFullError
from .base.tokens import DEFAULT, Palette, Spacing, Theme, Type
from .types.core.registry import PageTypeError

__all__ = ["Rect", "cm", "pt", "Page", "PageFullError", "Theme", "Type", "Palette",
           "Spacing", "DEFAULT", "types", "PageTypeError"]
