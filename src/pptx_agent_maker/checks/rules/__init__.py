"""One check per file. Each has a NAME and a run(deck, config) -> list[Finding]."""

from . import empty_cells, internal_names, off_page, overlap, type_floor, unreplaced, untyped_parts

ALL = (off_page, overlap, type_floor, empty_cells, internal_names, unreplaced, untyped_parts)

__all__ = ["ALL", "off_page", "overlap", "type_floor", "empty_cells",
           "internal_names", "unreplaced", "untyped_parts"]
