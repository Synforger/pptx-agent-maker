"""A declared page whose largest part is words, not a picture, a chart or a shape diagram.

The part that takes the most area is what the eye lands on first. When it is a box of words, a card or a
table, the page is read, not seen: the lead should be the figure that proves the title.
"""

from __future__ import annotations

from .._internal.page_reading import is_a_picture, judged, lead
from ..finding import Finding

NAME = "no_lead"
READS_PAGES = True

#: how the lead is called in the message
CALLED = {"box": "a box of words", "text": "a block of words", "table": "a table"}


def off(config: dict | None) -> bool:
    """A project may switch the check off (= `[checks] no_lead = false`)."""
    return (config or {}).get(NAME, True) is False


def why(kind: str) -> str:
    return (f"the largest part of the page is {CALLED.get(kind, kind)} — make a picture, a chart or a shape "
            "diagram the largest, and set the words beside it")


def run(manifest, theme=None, config: dict | None = None, pages: dict | None = None) -> list[Finding]:
    if off(config):
        return []
    return [Finding(NAME, number, title, why(lead(page)))
            for number, title, page in judged(manifest, pages) if lead(page) is not None and not is_a_picture(lead(page))]
