"""Take the paths out of a reason before the screen shows it.

`server` calls this. A folder's name can hold a client's name, and the screen can be on a projector.
"""

from __future__ import annotations

import re

HIDDEN = "<path>"
# From the first absolute path to the last slash of the line, then up to a word that follows paths in the
# toolkit's reasons. With none of those words the rest of the line goes too: a name can hold spaces and commas.
_PATH_RE = re.compile(
    r"(?<![\w./<>])(?:[A-Za-z]:|~)?/(?=[^\s/])(?:[^\n]*/)?[^\n/]*?"
    r"(?=['\"`]?$|, which | — | points at | \(['\"])",
    re.MULTILINE,
)


def without_paths(reason: str | None) -> str | None:
    """The reason with each absolute path replaced."""
    return None if reason is None else _PATH_RE.sub(HIDDEN, reason)
