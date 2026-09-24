"""A .pptx is a zip of XML parts. This opens one, and writes it back.

python-pptx では頁を複製できず、別の pptx から頁を持ってくることもできない
(= 公式に口が無い)。テンプレートの複製と過去デッキからの輸入は、部品を直に触るしかない。
ここはその最下層で、**部品の登録を 1 箇所に集める** ― 登録漏れは PowerPoint の
「修復しますか」に化ける。
"""

from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

#: rels が絵を指す書き方 (= `Target="../media/image3.png"`)
MEDIA_TARGET = re.compile(r'Target="[^"]*?media/([^"]+)"')

SLIDE_TYPE = ("application/vnd.openxmlformats-officedocument.presentationml.slide+xml")
SLIDE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"


class Archive:
    """An unpacked deck. Paths inside are the OOXML part names."""

    def __init__(self, tree: Path) -> None:
        self.tree = Path(tree)

    @classmethod
    def unpack(cls, source: Path, into: Path) -> "Archive":
        into = Path(into)
        if into.exists():
            shutil.rmtree(into)
        into.mkdir(parents=True)
        with zipfile.ZipFile(source) as archive:
            archive.extractall(into)
        return cls(into)

    def pack(self, destination: Path) -> Path:
        """Write the parts back out as a .pptx."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            for part in sorted(self.tree.rglob("*")):
                if part.is_file():
                    archive.write(part, part.relative_to(self.tree))
        return destination

    # -- parts ---------------------------------------------------------------

    def slide(self, name: str) -> Path:
        return self.tree / "ppt/slides" / name

    def rels_of(self, name: str) -> Path:
        return self.tree / "ppt/slides/_rels" / f"{name}.rels"

    def slide_names(self) -> list[str]:
        return sorted(p.name for p in (self.tree / "ppt/slides").glob("slide*.xml"))

    def next_slide_name(self) -> str:
        numbers = [int(m.group(1)) for name in self.slide_names()
                   if (m := re.match(r"slide(\d+)\.xml", name))]
        return f"slide{max(numbers, default=0) + 1}.xml"

    def drop_unreferenced_media(self) -> list[str]:
        """Remove the pictures nothing points at any more, and say which went.

        ⚠ **頁を消しても、その頁の絵は残る。**部品を消すのは参照の側だけなので、
        載せなかった絵が最後まで運ばれる ― デッキが重くなるだけでなく、**載せないと
        決めた絵が納品物の中まで付いてくる**。
        """
        wanted: set[str] = set()
        for rels in self.tree.rglob("*.rels"):
            wanted |= set(MEDIA_TARGET.findall(rels.read_text(encoding="utf-8")))

        media = self.tree / "ppt/media"
        dropped = []
        for picture in sorted(media.glob("*")) if media.is_dir() else []:
            if picture.name not in wanted:
                picture.unlink()
                dropped.append(picture.name)
        return dropped

    def next_media_name(self, extension: str) -> str:
        media = self.tree / "ppt/media"
        media.mkdir(parents=True, exist_ok=True)
        numbers = [int(m.group(1)) for p in media.glob("image*")
                   if (m := re.match(r"image(\d+)", p.name))]
        return f"image{max(numbers, default=0) + 1}.{extension}"

    # -- registration (= the part that, left out, produces a repair prompt) ---

    def register_slide(self, name: str) -> None:
        """Declare a new slide in the content types and the presentation rels."""
        types = self.tree / "[Content_Types].xml"
        override = f'<Override PartName="/ppt/slides/{name}" ContentType="{SLIDE_TYPE}"/>'
        text = types.read_text(encoding="utf-8")
        if override not in text:
            types.write_text(text.replace("</Types>", f"{override}</Types>"), encoding="utf-8")

        rels = self.tree / "ppt/_rels/presentation.xml.rels"
        text = rels.read_text(encoding="utf-8")
        used = [int(m) for m in re.findall(r'Id="rId(\d+)"', text)]
        entry = (f'<Relationship Id="rId{max(used, default=0) + 1}" '
                 f'Type="{SLIDE_REL}" Target="slides/{name}"/>')
        rels.write_text(text.replace("</Relationships>", f"{entry}</Relationships>"),
                        encoding="utf-8")

    def unregister_slide(self, name: str) -> None:
        """Remove a slide and every trace of it: the part, its rels, its notes."""
        types = self.tree / "[Content_Types].xml"
        content_types = types.read_text(encoding="utf-8")

        rels_path = self.rels_of(name)
        if rels_path.exists():
            for notes in re.findall(r'Target="\.\./notesSlides/(notesSlide\d+\.xml)"',
                                    rels_path.read_text(encoding="utf-8")):
                (self.tree / "ppt/notesSlides" / notes).unlink(missing_ok=True)
                (self.tree / "ppt/notesSlides/_rels" / f"{notes}.rels").unlink(missing_ok=True)
                content_types = re.sub(
                    rf'<Override PartName="/ppt/notesSlides/{notes}"[^>]*/>', "", content_types)
            rels_path.unlink()

        self.slide(name).unlink(missing_ok=True)
        content_types = re.sub(rf'<Override PartName="/ppt/slides/{name}"[^>]*/>', "", content_types)
        types.write_text(content_types, encoding="utf-8")

        presentation_rels = self.tree / "ppt/_rels/presentation.xml.rels"
        text = presentation_rels.read_text(encoding="utf-8")
        presentation_rels.write_text(
            re.sub(rf'<Relationship Id="rId\d+"[^>]*Target="slides/{name}"/>', "", text),
            encoding="utf-8")

    def set_order(self, order: list[str]) -> None:
        """Rebuild the slide list so the deck reads in this order."""
        rels = (self.tree / "ppt/_rels/presentation.xml.rels").read_text(encoding="utf-8")
        rid_of = {target: rid for rid, target in re.findall(
            r'<Relationship Id="(rId\d+)"[^>]*Target="slides/(slide\d+\.xml)"/>', rels)}
        missing = [name for name in order if name not in rid_of]
        if missing:
            raise KeyError(f"not registered in the presentation rels: {missing}")

        listing = "".join(f'<p:sldId id="{256 + index}" r:id="{rid_of[name]}"/>'
                          for index, name in enumerate(order))
        presentation = self.tree / "ppt/presentation.xml"
        text = presentation.read_text(encoding="utf-8")
        presentation.write_text(
            re.sub(r"<p:sldIdLst>.*</p:sldIdLst>", f"<p:sldIdLst>{listing}</p:sldIdLst>",
                   text, flags=re.S),
            encoding="utf-8")

    def order_of(self, source: Path | None = None) -> list[str]:
        """Reading order of this deck, or of another .pptx without unpacking it."""
        if source is None:
            presentation = (self.tree / "ppt/presentation.xml").read_text(encoding="utf-8")
            rels = (self.tree / "ppt/_rels/presentation.xml.rels").read_text(encoding="utf-8")
        else:
            with zipfile.ZipFile(source) as archive:
                presentation = archive.read("ppt/presentation.xml").decode("utf-8")
                rels = archive.read("ppt/_rels/presentation.xml.rels").decode("utf-8")
        file_of = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="slides/(slide\d+\.xml)"', rels))
        return [file_of[rid] for rid in re.findall(r'<p:sldId[^>]*r:id="(rId\d+)"', presentation)
                if rid in file_of]
