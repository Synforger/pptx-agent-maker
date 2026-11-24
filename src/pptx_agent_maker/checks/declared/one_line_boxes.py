"""A declared page with a run of boxes that each hold one line.

Cards, flow nodes, road arrowheads and code boxes that say one line each are a list wearing boxes: the boxes
cost the page its room and the reader's eye a stop each, for a line that bullets would carry. A heading alone
in a box is one line, too.

`ONE_LINE_RUN` is 3: the fewest boxes that read as a run of them (two are a pair).
"""

from __future__ import annotations

from .._internal.page_reading import judged, one_line_boxes
from ..finding import Finding

NAME = "one_line_boxes"
READS_PAGES = True

ONE_LINE_RUN = 3


def off(config: dict | None) -> bool:
    """A project may switch the check off (= `[checks] one_line_boxes = false`)."""
    return (config or {}).get(NAME, True) is False


def why(count: int) -> str:
    return (f"{count} boxes hold one line each ({ONE_LINE_RUN} is the most before it reads as a list in boxes) — "
            "join them into one box, or let a picture or a chart carry the page")


def run(manifest, theme=None, config: dict | None = None, pages: dict | None = None) -> list[Finding]:
    if off(config):
        return []
    return [Finding(NAME, number, title, why(one_line_boxes(page)))
            for number, title, page in judged(manifest, pages) if one_line_boxes(page) >= ONE_LINE_RUN]
