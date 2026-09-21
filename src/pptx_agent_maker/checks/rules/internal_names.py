"""Our file names on a page someone else reads.

読む側はソースを持っていないので、module 名や script 名は手がかりにならず、
こちらの事情が漏れるだけ。
"""

from __future__ import annotations

import re
from pathlib import Path

from ..finding import Finding
from ..slide import read

NAME = "internal_names"
PATTERNS = (r"\bsrc/", r"\btests?/", r"\.py\b", r"\.json\b", r"\.toml\b", r"\.yaml\b", r"\.yml\b")


def run(deck: Path, config: dict | None = None) -> list[Finding]:
    patterns = [re.compile(p) for p in (config or {}).get("internal_patterns", PATTERNS)]
    findings: list[Finding] = []
    for page in read(deck):
        for text in page.texts():
            for pattern in patterns:
                if pattern.search(text):
                    findings.append(Finding(
                        NAME, page.number, text.strip()[:60],
                        f"names something internal ({pattern.pattern})"))
                    break
    return findings
