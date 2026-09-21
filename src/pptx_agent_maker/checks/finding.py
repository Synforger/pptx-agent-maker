"""What a check reports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    """One problem on one page of a built deck."""

    check: str
    page: int
    what: str
    why: str

    def render(self) -> str:
        return f"page {self.page}: {self.what}  <- {self.why}"
