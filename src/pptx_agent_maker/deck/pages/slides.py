"""Copying a page from a specimen, and importing one from an earlier deck.

この 2 つは実運用で最も多く呼ばれ、**作り直しが一度も起きなかった層**。座標を書く層を
捨てても、ここは形ごと引き継ぐ。

⚠ **発表者ノートは既定で持ち込まない。**複製元が消えるときに共有された notesSlide が
道連れになり、複製先の参照だけが宙に浮く (= 修復ダイアログの種)。
"""

from __future__ import annotations

import posixpath
import re
import shutil
import zipfile
from pathlib import Path
from typing import Callable

from ..base.archive import CARRIED_FOLDERS, Archive

NOTES_REL = re.compile(r'<Relationship [^>]*notesSlide[^>]*/>')
MEDIA_TARGET = re.compile(r'Target="\.\./media/(image[\w.]+)"')
#: 頁がどのレイアウトの上に乗るか
LAYOUT_TARGET = re.compile(r'Target="\.\./slideLayouts/slideLayout\d+\.xml"')
RELATIONSHIP = re.compile(r"<Relationship\b[^>]*/>")
TARGET = re.compile(r'Target="([^"]+)"')


def duplicate(archive: Archive, source_name: str) -> str:
    """Copy a slide within the deck and return the new part name."""
    new_name = archive.next_slide_name()
    shutil.copy(archive.slide(source_name), archive.slide(new_name))

    source_rels = archive.rels_of(source_name)
    if source_rels.exists():
        rels = NOTES_REL.sub("", source_rels.read_text(encoding="utf-8"))
        rels = _copy_media_within(archive, rels)
        types = (archive.tree / "[Content_Types].xml").read_text(encoding="utf-8")

        def read(part: str) -> bytes | None:
            path = archive.tree / part
            return path.read_bytes() if path.is_file() else None

        rels = _carry_parts(archive, rels, "ppt/slides", read, types)
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
        source_types = zipped.read("[Content_Types].xml").decode("utf-8")
        for name in sorted(set(MEDIA_TARGET.findall(rels))):
            extension = name.rsplit(".", 1)[1]
            carried[name] = archive.next_media_name(extension)
            (archive.tree / "ppt/media" / carried[name]).write_bytes(
                zipped.read(f"ppt/media/{name}"))
            # 種類は持ち込み元の登録を写す (= 拡張子から推測しない)
            archive.register_media(carried[name], _media_type(source_types, name))
        rels = _rename_media(rels, carried)

        def read(part: str) -> bytes | None:
            try:
                return zipped.read(part)
            except KeyError:
                return None

        rels = _carry_parts(archive, rels, "ppt/slides", read, source_types)

    if relayout:
        # ⚠ **宣言で組んだ頁は白紙に描いてある。**持ち込むときレイアウトの参照を
        # そのままにすると、番号だけが引き継がれてテンプレートの別のレイアウト (= 終わりの頁
        # など) の上に乗り、その背景の飾りが出る。テンプレートの 1 枚目へ向け直す。
        rels = LAYOUT_TARGET.sub('Target="../slideLayouts/slideLayout1.xml"', rels)

    archive.slide(new_name).write_text(slide_xml, encoding="utf-8")
    archive.rels_of(new_name).parent.mkdir(parents=True, exist_ok=True)
    archive.rels_of(new_name).write_text(rels, encoding="utf-8")
    archive.register_slide(new_name)
    return new_name


def _carry_parts(archive: Archive, rels: str, owner: str, read: Callable[[str], bytes | None],
                 source_types: str) -> str:
    """Give the page a copy of its own of every chart it shows, and of the data each chart keeps.

    `rels` は `owner` (= その rels の持ち主が居る folder) から見た関係の一覧で、返すのは、指す先を
    新しい名前に向け直した物。`read` は持ち込み元の部品を名前で読む口 (= 無ければ None)。

    ⚠ **頁の XML を写すだけでは、グラフは付いて来ない。**頁はグラフを関係で指しているだけで、
    本体は別の部品に在り、その本体がさらにデータの表を別の部品に持つ。写さなければ指す先が無く、
    元の名前のまま写せば、行き先に既に在る別のグラフを指す。

    ⚠ **グラフが、ここで運べない物を指していたら止める** (= 絵で塗った棒など)。黙って置いて行くと、
    指す先の無い関係が残り、開いたときに修復を言われる。
    """
    def carried(found: re.Match) -> str:
        entry = found.group(0)
        target = TARGET.search(entry)
        if target is None or 'TargetMode="External"' in entry:
            return entry
        part = posixpath.normpath(posixpath.join(owner, target.group(1)))
        folder, name = posixpath.split(part)
        if folder not in CARRIED_FOLDERS:
            if owner in CARRIED_FOLDERS:
                raise ValueError(
                    f"a chart on this page keeps {target.group(1)} beside it, which this toolkit does not "
                    "carry — rebuild the chart from its numbers (`chart`), or bring the page in as a picture")
            return entry
        content = read(part)
        if content is None:
            raise ValueError(f"the page points at {part}, and the deck it comes from has no such part")
        (archive.tree / folder).mkdir(parents=True, exist_ok=True)
        new = archive.next_part_name(folder, name)
        (archive.tree / folder / new).write_bytes(content)
        archive.register_part(f"{folder}/{new}", _part_type(source_types, part))
        own = read(f"{folder}/_rels/{name}.rels")
        if own is not None:
            (archive.tree / folder / "_rels").mkdir(parents=True, exist_ok=True)
            (archive.tree / folder / "_rels" / f"{new}.rels").write_text(
                _carry_parts(archive, own.decode("utf-8"), folder, read, source_types), encoding="utf-8")
        return entry.replace(target.group(0), f'Target="{posixpath.relpath(f"{folder}/{new}", owner)}"')

    return RELATIONSHIP.sub(carried, rels)


def _part_type(content_types: str, part: str) -> str:
    """What the source package says a part is (= by its name, else by its extension)."""
    named = re.search(rf'<Override\s+PartName="/{re.escape(part)}"\s+ContentType="([^"]+)"', content_types)
    if named:
        return named.group(1)
    extension = part.rsplit(".", 1)[-1]
    default = re.search(rf'<Default\s+Extension="{re.escape(extension)}"\s+ContentType="([^"]+)"',
                        content_types, re.I)
    if default:
        return default.group(1)
    raise ValueError(f"the deck being brought from does not say what {part} is")


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


def _media_type(content_types: str, name: str) -> str:
    """What the source package says a media file is (= by its part, else by its extension)."""
    part = re.search(rf'<Override\s+PartName="/ppt/media/{re.escape(name)}"\s+ContentType="([^"]+)"',
                     content_types)
    if part:
        return part.group(1)
    extension = name.rsplit(".", 1)[-1]
    default = re.search(rf'<Default\s+Extension="{re.escape(extension)}"\s+ContentType="([^"]+)"',
                        content_types, re.I)
    if default:
        return default.group(1)
    raise ValueError(f"the deck being imported from does not say what {name} is")
