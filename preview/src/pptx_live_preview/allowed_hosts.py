"""Read the host names this machine lets in front of the preview.

`server` calls this for a request whose name is not loopback.
"""

from __future__ import annotations

from .platform_root import config_folder

# A file of its own: the reader of preview.toml refuses the whole list when it meets a key it does not know,
# so a machine could not write the names down before it runs a version that reads them.
FILENAME = "allowed-hosts.txt"


def load_allowed_hosts() -> frozenset[str]:
    """The names in the file, one per line. No names when it is missing or cannot be read."""
    try:
        text = (config_folder() / FILENAME).read_text(encoding="utf-8")
    except (OSError, ValueError):
        return frozenset()
    names = (line.partition("#")[0].strip().lower().rstrip(".") for line in text.splitlines())
    return frozenset(name for name in names if name)
