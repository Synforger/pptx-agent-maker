"""A declared page with more parts than a reader holds in mind.

A part is a picture, a chart, a table, one box, a block of words (= a band, a reading note, a text), or the
shape diagram of a timeline or overlapping circles as one. Lines, arrows, the title, the source line and the
page number are not parts.

`ELEMENTS_RED` is 8: the count of elements an outside slide inspector
(https://github.com/bayramannakov/ai-personal-os-skills, its slide-inspector) marks red on a page.
"""

from __future__ import annotations

from .._internal.page_reading import judged, parts
from ..finding import Finding

NAME = "crowded_page"
READS_PAGES = True

ELEMENTS_RED = 8


def off(config: dict | None) -> bool:
    """A project may switch the check off (= `[checks] crowded_page = false`)."""
    return (config or {}).get(NAME, True) is False


def why(count: int) -> str:
    return (f"{count} parts on the page, {ELEMENTS_RED} at most — take some off, or split the page in two")


def run(manifest, theme=None, config: dict | None = None, pages: dict | None = None) -> list[Finding]:
    if off(config):
        return []
    return [Finding(NAME, number, title, why(len(parts(page))))
            for number, title, page in judged(manifest, pages) if len(parts(page)) > ELEMENTS_RED]
