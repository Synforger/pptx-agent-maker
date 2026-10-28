"""Which typefaces a deck names, and which of them this machine does not have.

`pptx-agent-maker compare` asks this before it prints, so a person who sees pages differ when nothing changed is
told why. Reads the decks and starts `fc-match`; the judging is `font_match.py`.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import zipfile
from collections.abc import Iterable
from pathlib import Path

from ..deck._internal.look import look_of
from .font_match import is_installed

_SLIDE_PART = re.compile(r"ppt/slides/slide\d+\.xml")
_NAMED = re.compile(rb'<a:(?:latin|ea) typeface="([^"]*)"')
_THEME_REFERENCE = "+"


def fonts_named(deck: Path) -> set[str]:
    """The typefaces the runs of a deck's pages name (= `a:latin` and `a:ea`).

    ⚠ **見るのは頁の字が名指した書体で、テーマの書体ではない。**`[theme] font` を宣言した資料はテーマに
    元の書体を残したまま、頁の字に宣言した書体を書く (= 実測: テーマは Meiryo、字 20 件は Hiragino Sans)。
    テーマを読むと、使っていない書体を知らせ、使っている書体を見落とす。字がテーマを指す書体 (= `+mn-lt` など)
    だけ、テーマの書体 (= `look_of`、道具が見本から読むのと同じ所) に置き換える。書体を名指さない字は
    数えない (= 道具が組む頁の字は全部名指している)。
    """
    named: set[str] = set()
    with zipfile.ZipFile(deck) as archive:
        for part in archive.namelist():
            if _SLIDE_PART.fullmatch(part):
                named.update(face.decode("utf-8") for face in _NAMED.findall(archive.read(part)))
    named.discard("")
    references = {face for face in named if face.startswith(_THEME_REFERENCE)}
    if references:
        named -= references
        theme_face = look_of(deck).get("font")
        if theme_face:
            named.add(theme_face)
    return named


def missing_fonts(faces: Iterable[str]) -> list[str] | None:
    """The typefaces among `faces` this machine does not have, in name order; None when `fc-match` is not here.

    ⚠ **LibreOffice は無い書体を、描くたびに別の書体で置き換えることがある。**ここで見るのは fontconfig に
    入っているかで、LibreOffice が自分で見つける書体の一覧と同じとは限らない (= 知らせは目安。この機械で
    測った限り、`fc-match` で無い書体を使う資料は揺れ、有る書体を使う資料は揺れなかった)。
    """
    faces = sorted(set(faces))
    if not faces:
        return []
    fc_match = shutil.which("fc-match")
    if fc_match is None:
        return None
    missing = []
    for face in faces:
        done = subprocess.run([fc_match, "-f", "%{family}", face], capture_output=True, text=True)
        if done.returncode == 0 and not is_installed(face, done.stdout.split(",")):
            missing.append(face)
    return missing
