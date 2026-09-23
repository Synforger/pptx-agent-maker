"""Copying a page from a specimen, and importing one from an earlier deck.

この 2 つは実運用で最も多く呼ばれ、**作り直しが一度も起きなかった層**。座標を書く層を
捨てても、ここは形ごと引き継ぐ。

⚠ **発表者ノートは既定で持ち込まない。**複製元が消えるときに共有された notesSlide が
道連れになり、複製先の参照だけが宙に浮く (= 修復ダイアログの種)。
"""

from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

from .archive import Archive

NOTES_REL = re.compile(r'<Relationship [^>]*notesSlide[^>]*/>')
MEDIA_TARGET = re.compile(r'Target="\.\./media/(image[\w.]+)"')
#: 頁がどのレイアウトの上に乗るか
LAYOUT_TARGET = re.compile(r'Target="\.\./slideLayouts/slideLayout\d+\.xml"')


def duplicate(archive: Archive, source_name: str) -> str:
    """Copy a slide within the deck and return the new part name."""
    new_name = archive.next_slide_name()
    shutil.copy(archive.slide(source_name), archive.slide(new_name))

    source_rels = archive.rels_of(source_name)
    if source_rels.exists():
        rels = NOTES_REL.sub("", source_rels.read_text(encoding="utf-8"))
        rels = _copy_media_within(archive, rels)
        archive.rels_of(new_name).parent.mkdir(parents=True, exist_ok=True)
        archive.rels_of(new_name).write_text(rels, encoding="utf-8")

    archive.register_slide(new_name)
    return new_name


def import_from(archive: Archive, source: Path, page_number: int,
                relayout: bool = False) -> str:
    """Bring one page of another deck in, media and all, by its reading position.

    Part names are an artefact of how a deck was built (`slide64.xml` means nothing),
    so a page from another deck is addressed the way a reader would: by page number.
    """
    source = Path(source)
    order = archive.order_of(source)
    if not 1 <= page_number <= len(order):
        raise IndexError(f"{source.name} has {len(order)} pages; asked for {page_number}")
    source_name = order[page_number - 1]
    new_name = archive.next_slide_name()

    with zipfile.ZipFile(source) as zipped:
        slide_xml = zipped.read(f"ppt/slides/{source_name}").decode("utf-8")
        try:
            rels = zipped.read(f"ppt/slides/_rels/{source_name}.rels").decode("utf-8")
        except KeyError:
            rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/'
                    'package/2006/relationships"/>')
        rels = NOTES_REL.sub("", rels)
        carried: dict[str, str] = {}
        for name in sorted(set(MEDIA_TARGET.findall(rels))):
            extension = name.rsplit(".", 1)[1]
            carried[name] = archive.next_media_name(extension)
            (archive.tree / "ppt/media" / carried[name]).write_bytes(
                zipped.read(f"ppt/media/{name}"))
        rels = _rename_media(rels, carried)

    if relayout:
        # ⚠ **宣言で組んだ頁は白紙に描いてある。**持ち込むときレイアウトの参照を
        # そのままにすると、番号だけが引き継がれて型見本の別のレイアウト (= 終わりの頁
        # など) の上に乗り、その背景の飾りが出る。型見本の 1 枚目へ向け直す。
        rels = LAYOUT_TARGET.sub('Target="../slideLayouts/slideLayout1.xml"', rels)

    archive.slide(new_name).write_text(slide_xml, encoding="utf-8")
    archive.rels_of(new_name).parent.mkdir(parents=True, exist_ok=True)
    archive.rels_of(new_name).write_text(rels, encoding="utf-8")
    archive.register_slide(new_name)
    return new_name


def _copy_media_within(archive: Archive, rels: str) -> str:
    """Give the copy its own media files, so editing one page cannot change another."""
    carried: dict[str, str] = {}
    for name in sorted(set(MEDIA_TARGET.findall(rels))):
        extension = name.rsplit(".", 1)[1]
        carried[name] = archive.next_media_name(extension)
        shutil.copy(archive.tree / "ppt/media" / name,
                    archive.tree / "ppt/media" / carried[name])
    return _rename_media(rels, carried)


def _rename_media(rels: str, carried: dict[str, str]) -> str:
    """Point every media relationship at its new file, all in one pass.

    ⚠ **1 つずつ置換してはいけない。**置換して付けた名前が、次の置換の**探す名前**に
    なることがあり、そのときは前に置き換えた分も巻き込まれる ― 4 枚の絵を持つ頁を
    輸入すると、4 枚とも同じ 1 枚になった (= 焼いて初めて出た。頁の見た目は
    もっともらしいままなので、絵を並べて見るまで気づけない)。
    """
    return MEDIA_TARGET.sub(
        lambda found: f'Target="../media/{carried.get(found.group(1), found.group(1))}"',
        rels)
