"""A part the package does not say the type of.

.pptx の中の部品は、`[Content_Types].xml` に拡張子 (`Default`) か部品名 (`Override`) で
種類が登録されていないと読めない。python-pptx は開くことを拒み、PowerPoint は
「修復しますか」を出す。LibreOffice は黙って読むので、変換が通っても安心材料にならない。

⚠ **頁の上には何も出ない種類の壊れ方。**他の検査は頁の中身を見るが、これは箱の側を見る。
実際に、絵を 1 枚も持たないテンプレートへ絵のある頁を持ち込んだとき、絵の file だけが
写って png の登録が無く、焼いたデッキが開けなくなっていた。
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from ..finding import Finding

NAME = "untyped_parts"
_DEFAULT = re.compile(r'<Default\s+Extension="([^"]+)"')
_OVERRIDE = re.compile(r'<Override\s+PartName="([^"]+)"')


def run(deck: Path, config: dict | None = None) -> list[Finding]:
    with zipfile.ZipFile(deck) as archive:
        types = archive.read("[Content_Types].xml").decode("utf-8")
        names = [n for n in archive.namelist()
                 if not n.endswith("/") and n != "[Content_Types].xml"]
    extensions = {e.lower() for e in _DEFAULT.findall(types)}
    overridden = {p.lower() for p in _OVERRIDE.findall(types)}
    findings = []
    for name in names:
        extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if extension in extensions or f"/{name}".lower() in overridden:
            continue
        # 頁の上の問題ではないので頁番号は 0 (= デッキ全体)
        findings.append(Finding(NAME, 0, name,
                                "no content type for this part — the file will not open cleanly"))
    return findings
