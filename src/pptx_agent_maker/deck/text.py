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
    pattern = rf"(<a:t\b[^>]*(?<!/)>){re.escape(html.escape(old, quote=False))}(</a:t>)"
    text, hits = re.subn(pattern, lambda m: m.group(1) + html.escape(new, quote=False) + m.group(2),
                         text, count=count)
    if hits == 0:
        raise ReplacementMissed(
            f"{slide.name}: nothing to replace — {old!r} is not a run on this slide "
            "(replacement is exact; copy the words from the slide, do not retype them)"
        )
    slide.write_text(text, encoding="utf-8")


def forget_descriptions(slide: Path) -> int:
    """Drop the alt text and titles shapes carry (= often a file name, never seen on the page)."""
    text = slide.read_text(encoding="utf-8")
    hits = 0
    while True:  # 1 つの図形が両方を持つので、当たらなくなるまで
        text, more = re.subn(r'(<p:cNvPr\b[^>]*?)\s(?:descr|title)="[^"]*"', r"\1", text)
        if not more:
            break
        hits += more
    if hits:
        slide.write_text(text, encoding="utf-8")
    return hits


def words(slide: Path) -> list[str]:
    """Every run on the slide, in document order — what replacement can match."""
    text = slide.read_text(encoding="utf-8")
    return [html.unescape(m.group(1))
            for m in re.finditer(r"<a:t\b[^>]*(?<!/)>(.*?)</a:t>", text, re.S)]


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


#: テンプレートへ上げる頁で、案件の文言の代わりに置く語の頭 (= `<文言 3>`)。
#: 次の案件の差し替え忘れは、この頭を `stale_words` に入れて検査が止める。
STAND_IN = "<文言"


def stand_in(slide: Path, *, keep: set[str], replace: list[tuple[str, str]],
             names: dict[str, str], hits: dict[str, int]) -> list[tuple[str, str]]:
    """Every run becomes a numbered stand-in, unless it is kept or a `replace` touched it.

    ⚠ **既定は抜く側。**上げた物は次の案件すべてに配られるので、残す語を指し忘れても
    書き直せば済むが、抜く語を指し忘れると前の先方の中身が次の先方に届く。
    `names` は元の文言 → 仮の語 (= 同じ文言には同じ番号。頁と recipe をまたいで共有する)。
    返すのは (元の文言, 置いた文言) の並び (= 人が読んで `--keep` を決めるため)。
    PowerPoint が埋める欄 (= 頁番号などの `<a:fld>`) は触らない。
    """
    from lxml import etree

    ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    tree = etree.parse(str(slide))
    placed: list[tuple[str, str]] = []
    for t in tree.iter(f"{ns}t"):
        if t.getparent() is not None and t.getparent().tag == f"{ns}fld":
            continue
        original = t.text or ""
        if not original.strip():
            continue
        t.text = decide(original, keep=keep, replace=replace, names=names, hits=hits)
        placed.append((original, t.text))
    tree.write(str(slide), xml_declaration=True, encoding="UTF-8", standalone=True)
    return placed


def decide(original: str, *, keep: set[str], replace: list[tuple[str, str]],
           names: dict[str, str], hits: dict[str, int]) -> str:
    """What one piece of the project's words becomes in the template."""
    text, touched = original, False
    for old, new in replace:
        if old in text:
            hits[old] = hits.get(old, 0) + text.count(old)
            text, touched = text.replace(old, new), True
    if touched or original.strip() in keep:
        return text
    if original not in names:
        names[original] = f"{STAND_IN} {len(names) + 1}>"
    return names[original]
