"""Checking a deck after it is built.

    slide.py    焼いたものを読み直す
    rules/      1 検査 1 file
    finding.py  当たりの形

宣言層は置く前に解くので、ここが見るのは**宣言層を通っていない頁** ― テンプレートの複製と、
過去デッキからの輸入。どちらも座標は過去の誰かが手で置いたもので、誰も保証していない。

⚠ **これは焼いた後の検査であって、読みやすさの保証ではない。**座標が正しくても、
どれを見ればよいかは人が決める。焼いて目で見る工程は消えない。
"""

from __future__ import annotations

from pathlib import Path

from .finding import Finding
from .rules import ALL as CHECKS

__all__ = ["Finding", "CHECKS", "run_all", "report"]


def run_all(deck: Path | str, config: dict | None = None) -> list[Finding]:
    """Every check over one built deck."""
    deck = Path(deck)
    findings: list[Finding] = []
    for check in CHECKS:
        findings.extend(check.run(deck, config or {}))
    return findings


def report(findings: list[Finding]) -> str:
    """The findings, then a line per check so a clean deck still says what was looked at."""
    lines = [finding.render() for finding in findings]
    lines.append("")
    for check in CHECKS:
        count = sum(1 for f in findings if f.check == check.NAME)
        lines.append(f"  {'FAIL' if count else 'ok':4}  {check.NAME:<16} {count}")
    return "\n".join(lines)
