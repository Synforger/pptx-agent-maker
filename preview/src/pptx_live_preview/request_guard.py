"""Decide which requests the preview answers, from their headers alone.

`server` calls this before it looks at a project. No file, socket or state is touched here.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence

LOOPBACK_NAMES = frozenset({"localhost", "127.0.0.1", "[::1]"})
DEFAULT_PORTS = {"http": 80, "https": 443}
PORT_MAX = 65535
# What a browser says of a request that the page itself, or the person, started.
OWN_SITES = frozenset({"same-origin", "none"})

_AUTHORITY_RE = re.compile(r"(?P<name>\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9._-]+)(?::(?P<port>[0-9]{1,5}))?")


def refusal(hosts: Sequence[str], origins: Sequence[str], sites: Sequence[str], *,
            is_change: bool, allowed_names: Callable[[], frozenset[str]]) -> str | None:
    """Why a request is refused, or None when it is to be answered.

    The name is checked because a page elsewhere can point its own name at loopback, and the browser then
    takes the preview for that page's origin. The origin is checked because such a page can send a request
    without being able to read the answer. A client that is not a browser sends neither `Origin` nor
    `Sec-Fetch-Site` and is let through on the name alone. `allowed_names` is called only for a name that
    is not loopback, so a list that cannot be read never closes loopback.
    """
    host = _authority(hosts[0]) if len(hosts) == 1 else None
    if host is None:
        return "the request does not name one valid host"
    name, port = host
    if name not in LOOPBACK_NAMES and name not in allowed_names():
        return "this host name is not allowed; add it to the preview's allowed-hosts.txt (see its setup guide)"
    if origins and not (len(origins) == 1 and _is_own_origin(origins[0], name, port)):
        return "the request comes from another origin"
    if is_change and any(site not in OWN_SITES for site in sites):
        return "another site started this change"
    return None


def _authority(text: str) -> tuple[str, int | None] | None:
    """The name in one spelling and the port written after it, or None for anything else."""
    found = _AUTHORITY_RE.fullmatch(text)
    if found is None:
        return None
    port = int(found["port"]) if found["port"] else None
    if port is not None and port > PORT_MAX:
        return None
    return found["name"].lower().rstrip("."), port


def _is_own_origin(origin: str, name: str, port: int | None) -> bool:
    scheme, separator, rest = origin.partition("://")
    sender = _authority(rest) if separator and scheme in DEFAULT_PORTS else None
    if sender is None:
        return False
    # A browser leaves the scheme's default port out of both headers, and a proxy may write it in.
    default = DEFAULT_PORTS[scheme]
    sender_name, sender_port = sender
    return sender_name == name and (sender_port or default) == (port or default)
