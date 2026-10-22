"""One check per file. Each has a NAME and a run(deck, config) -> list[Finding]."""

from . import (avoided_words, contrast, empty_cells, internal_names, long_title, low_resolution, near_alignment,
               off_page, overlap, stretched, type_floor, unreplaced, untyped_parts)

ALL = (off_page, overlap, type_floor, empty_cells, internal_names, unreplaced, avoided_words,
       untyped_parts, long_title, contrast, stretched, low_resolution, near_alignment)

__all__ = ["ALL", "off_page", "overlap", "type_floor", "empty_cells",
           "internal_names", "unreplaced", "avoided_words", "untyped_parts", "long_title",
           "contrast", "stretched", "low_resolution", "near_alignment"]
