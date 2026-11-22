"""Read the XML parts of a deck.

`deck.pages` and `review.take` call this.
"""

from __future__ import annotations

from pathlib import Path

from lxml import etree


def _parser() -> etree.XMLParser:
    # The settings python-pptx reads parts with. Named here because older lxml expands entities by default.
    return etree.XMLParser(resolve_entities=False, no_network=True)


def load_part(path: Path | str) -> etree._ElementTree:
    """The tree of a part on disk."""
    return etree.parse(str(path), _parser())


def load_part_text(data: bytes) -> etree._Element:
    """The root of a part held as bytes."""
    return etree.fromstring(data, _parser())
