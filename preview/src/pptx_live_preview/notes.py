"""Pull speaker notes out of a .pptx without leaving the standard library.

ノートは PDF 経由の描画では落ちるので、元の .pptx から直接読む。.pptx は zip
なので、必要なのは zipfile と XML パーサだけ (= 依存を増やさない)。

対応付けに素直な順番はない。ノートの無いスライドがあると notesSlideN.xml の
番号は頁番号とずれるため、presentation.xml が持つスライドの並び → 各
スライドの関係定義 → ノート、と 3 段辿る。
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"

_NOTES_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide"
_SLIDE_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"


def _rels(zf: zipfile.ZipFile, part: str) -> dict[str, tuple[str, str]]:
    """Relationship id -> (type, resolved target path) for one package part."""
    folder, _, name = part.rpartition("/")
    rels_path = f"{folder}/_rels/{name}.rels" if folder else f"_rels/{name}.rels"
    try:
        root = ET.fromstring(zf.read(rels_path))
    except (KeyError, ET.ParseError):
        return {}
    out: dict[str, tuple[str, str]] = {}
    for rel in root.findall(f"{_REL}Relationship"):
        rid = rel.get("Id")
        target = rel.get("Target", "")
        if not rid:
            continue
        # 相対参照 (= ../notesSlides/notesSlide1.xml) をパッケージ内の絶対位置へ畳む
        base = folder.split("/")
        for piece in target.split("/"):
            if piece == "..":
                if base:
                    base.pop()
            elif piece not in ("", "."):
                base.append(piece)
        out[rid] = (rel.get("Type", ""), "/".join(base))
    return out


def _body_text(zf: zipfile.ZipFile, notes_part: str) -> str:
    """Notes body text only — the slide-number placeholder is not a note."""
    try:
        root = ET.fromstring(zf.read(notes_part))
    except (KeyError, ET.ParseError):
        return ""
    chunks: list[str] = []
    for shape in root.iter(f"{_P}sp"):
        ph = shape.find(f".//{_P}nvSpPr/{_P}nvPr/{_P}ph")
        if ph is None or ph.get("type") != "body":
            continue
        for para in shape.iter(f"{_A}p"):
            line = "".join(t.text or "" for t in para.iter(f"{_A}t"))
            chunks.append(line)
    text = "\n".join(chunks).strip()
    return re.sub(r"\n{3,}", "\n\n", text)


def extract(pptx: Path) -> list[str]:
    """Speaker notes per slide, in slide order; empty strings where there are none.

    読めない .pptx でも例外は投げない。ノートは表示の付け足しなので、取れない
    ことがプレビュー全体を止める理由にはならない。
    """
    try:
        with zipfile.ZipFile(pptx) as zf:
            try:
                pres = ET.fromstring(zf.read("ppt/presentation.xml"))
            except (KeyError, ET.ParseError):
                return []
            pres_rels = _rels(zf, "ppt/presentation.xml")

            out: list[str] = []
            for sld_id in pres.iter(f"{_P}sldId"):
                rid = sld_id.get(f"{_R}id")
                entry = pres_rels.get(rid or "")
                if not entry or entry[0] != _SLIDE_TYPE:
                    out.append("")
                    continue
                slide_part = entry[1]
                notes_part = next(
                    (tgt for typ, tgt in _rels(zf, slide_part).values()
                     if typ == _NOTES_TYPE),
                    None,
                )
                out.append(_body_text(zf, notes_part) if notes_part else "")
            return out
    except (OSError, zipfile.BadZipFile):
        return []
