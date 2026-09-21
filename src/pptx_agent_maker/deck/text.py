"""Replacing the words on a slide.

置換は**完全一致**で、見つからなければ例外にする ― 空振りを黙って通すと「直したつもり」
が残り、焼いた頁を見るまで気づかない (= 実際に何度も起きた)。

⚠ `<a:t>` は `xml:space="preserve"` を持つ形と持たない形が混在するので、属性を許す。
"""

from __future__ import annotations

import html
import re
from pathlib import Path


class ReplacementMissed(ValueError):
    """The text to replace was not on the slide."""


def replace(slide: Path, old: str, new: str, *, count: int = 1) -> None:
    """Swap one run's text for another. Missing means stop."""
    text = slide.read_text(encoding="utf-8")
    pattern = rf"(<a:t[^>]*>){re.escape(html.escape(old, quote=False))}(</a:t>)"
    text, hits = re.subn(pattern, lambda m: m.group(1) + html.escape(new, quote=False) + m.group(2),
                         text, count=count)
    if hits == 0:
        raise ReplacementMissed(
            f"{slide.name}: nothing to replace — {old!r} is not a run on this slide "
            "(replacement is exact; copy the words from the slide, do not retype them)"
        )
    slide.write_text(text, encoding="utf-8")


def words(slide: Path) -> list[str]:
    """Every run on the slide, in document order — what replacement can match."""
    text = slide.read_text(encoding="utf-8")
    return [html.unescape(m.group(1)) for m in re.finditer(r"<a:t[^>]*>(.*?)</a:t>", text, re.S)]


def drop_annotation_marks(slide: Path) -> int:
    """Remove the red call-out boxes an imported page brought with it.

    輸入した頁の注目マークは、元の絵を指していたもの。別の内容の上に残ると嘘になる。
    """
    text = slide.read_text(encoding="utf-8")
    pattern = re.compile(
        r"<p:sp>(?:(?!</p:sp>).)*?(?:FF0000|C00000)(?:(?!</p:sp>).)*?</p:sp>", re.S)
    text, hits = pattern.subn("", text)
    if hits:
        slide.write_text(text, encoding="utf-8")
    return hits
