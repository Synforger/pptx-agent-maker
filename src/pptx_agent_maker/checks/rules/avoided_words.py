"""Words the project has said not to use.

書き手が自作した訳語 (= 英語の用語を日本語に言い換えた語など) は、読み手が意味を読めない。使わない語と
代わりの語を案件が `[checks.avoid]` に宣言し、頁の字に残っていれば止める。
"""

from __future__ import annotations

from pathlib import Path

from ..finding import Finding
from ..._common.slide import read

NAME = "avoided_words"
#: 設定の表 (= `[checks.avoid]`) の名前
TABLE = "avoid"


def avoided(config: dict | None) -> dict[str, str]:
    """The words not to use, each with the word to write instead (= "" when none is named).

    `false` を書いた語は検査しない (= 案件がテンプレートの語を外す書き方)。
    """
    table = (config or {}).get(TABLE) or {}
    if not isinstance(table, dict):
        raise ValueError(f"[checks.{TABLE}] is a table of \"word not to use\" = \"word to write instead\", not {table!r}")
    words: dict[str, str] = {}
    for word, instead in table.items():
        if instead is False or not word:
            continue
        if not isinstance(instead, str):
            raise ValueError(f"[checks.{TABLE}] {word!r}: write the word to use instead as a string "
                             f"(= \"\" for none), or false to let the word through — not {instead!r}")
        words[word] = instead
    return words


def run(deck: Path, config: dict | None = None) -> list[Finding]:
    """One finding for each avoided word on each page, from the words and the charts on it."""
    words = avoided(config)
    if not words:
        return []
    findings: list[Finding] = []
    for page in read(deck):
        lines = [*page.lines(), *page.chart_lines()]
        for word, instead in words.items():
            line = next((line for line in lines if word in line), None)
            if line is None:
                continue
            why = (f"still says {word!r} — write {instead!r}" if instead
                   else f"{word!r} is on the project's list of words to avoid")
            findings.append(Finding(NAME, page.number, line.strip()[:60], why))
    return findings
