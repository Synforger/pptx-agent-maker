"""Turning declared pages into files."""

from .measure import aspect
from .pptx import add_page, new_deck, save

__all__ = ["new_deck", "add_page", "save", "aspect"]
