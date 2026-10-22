"""A .pptx is a zip of XML parts. This opens one, and writes it back.

python-pptx では頁を複製できず、別の pptx から頁を持ってくることもできない
(= 公式に口が無い)。テンプレートの複製と過去デッキからの輸入は、部品を直に触るしかない。
ここはその最下層で、**部品の登録を 1 箇所に集める** ― 登録漏れは PowerPoint の
「修復しますか」に化ける。
"""

from __future__ import annotations

import posixpath
import re
import shutil
import zipfile
from pathlib import Path

#: rels が絵を指す書き方 (= `Target="../media/image3.png"`)
MEDIA_TARGET = re.compile(r'Target="[^"]*?media/([^"]+)"')

#: 頁が絵のほかに連れて来る部品の置き場 (= グラフ本体と、グラフが中に持つデータの表)
CARRIED_FOLDERS = ("ppt/charts", "ppt/embeddings")

#: 頁番号の枠 (= 番号は開いた側が入れる)。レイアウトでは「この上の頁が持てる枠」、頁では「この頁は
#: 番号を出す」
NUMBER_FRAME = re.compile(r'<p:ph\b([^>]*\btype="sldNum"[^>]*?)/?>')
#: 資料の根の札と、そこに書かれる「1 枚目の番号」 (= 書かれていなければ 1 から数える)
PRESENTATION_TAG = re.compile(r"<p:presentation\b[^>]*>")
FIRST_NUMBER = re.compile(r'\bfirstSlideNum="(-?\d+)"')

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

    def next_part_name(self, folder: str, name: str) -> str:
        """A name nothing under `folder` has yet, for a part called `name` where it came from.

        番号で終わる名前 (= `chart3.xml`) は、同じ頭と拡張子の中でいちばん大きい番号の次を取る。
        """
        stem, dot, extension = name.rpartition(".")
        head = re.sub(r"\d+$", "", stem)
        taken = [int(found.group(1) or 0) for part in (self.tree / folder).glob(f"{head}*{dot}{extension}")
                 if (found := re.fullmatch(rf"{re.escape(head)}(\d*){re.escape(dot + extension)}", part.name))]
        return f"{head}{max(taken, default=0) + 1}{dot}{extension}"

    def drop_unreferenced_parts(self) -> list[str]:
        """Remove the charts, and the data they keep, that nothing points at any more.

        ⚠ **頁を消しても、その頁のグラフは残る** (= 絵と同じ)。グラフは中にデータの表を持つので、
        載せないと決めた頁の数字が、納品物の中まで付いてくる。グラフを消すとそのデータを指す物が
        無くなるので、何も消えなくなるまで繰り返す。
        """
        types = self.tree / "[Content_Types].xml"
        dropped: list[str] = []
        while True:
            wanted: set[str] = set()
            for rels in self.tree.rglob("*.rels"):
                owner = rels.parent.parent.relative_to(self.tree).as_posix()
                for target in re.findall(r'<Relationship\b(?![^>]*TargetMode="External")[^>]*Target="([^"]+)"',
                                         rels.read_text(encoding="utf-8")):
                    wanted.add(posixpath.normpath(posixpath.join(owner, target)))
            gone = [part for folder in CARRIED_FOLDERS if (self.tree / folder).is_dir()
                    for part in sorted((self.tree / folder).iterdir())
                    if part.is_file() and part.relative_to(self.tree).as_posix() not in wanted]
            if not gone:
                return dropped
            text = types.read_text(encoding="utf-8")
            for part in gone:
                name = part.relative_to(self.tree).as_posix()
                part.unlink()
                (part.parent / "_rels" / f"{part.name}.rels").unlink(missing_ok=True)
                text = re.sub(rf'<Override PartName="/{re.escape(name)}"[^>]*/>', "", text)
                dropped.append(name)
            types.write_text(text, encoding="utf-8")

    # -- registration (= the part that, left out, produces a repair prompt) ---

    def register_part(self, name: str, content_type: str) -> None:
        """Make sure the package says what the part at `name` (= `ppt/charts/chart3.xml`) is.

        拡張子ごとの登録 (= `Default`) が同じ種類を言っていればそれで足りる。違う種類を言っているか
        (= `.xml` はふつう「ただの XML」)、その部品だけの登録が要るときは、部品の名前で登録する。
        """
        extension = name.rsplit(".", 1)[-1]
        types = self.tree / "[Content_Types].xml"
        text = types.read_text(encoding="utf-8")
        default = re.search(rf'<Default\s+Extension="{re.escape(extension)}"\s+ContentType="([^"]+)"', text, re.I)
        if (default and default.group(1) == content_type) or f'PartName="/{name}"' in text:
            return
        entry = (f'<Override PartName="/{name}" ContentType="{content_type}"/>' if default
                 else f'<Default Extension="{extension}" ContentType="{content_type}"/>')
        types.write_text(text.replace("</Types>", f"{entry}</Types>"), encoding="utf-8")

    def register_media(self, name: str, content_type: str) -> None:
        """Make sure the package says what a media file is.

        ⚠ **絵の file を写すだけでは足りない。**種類は拡張子ごとに `[Content_Types].xml` が
        持っていて、絵を 1 枚も持たないテンプレートには png の登録が無い。そこへ絵のある頁を
        持ち込むと、file はあるのに種類が無く、焼いたデッキが開けなくなっていた。
        """
        extension = name.rsplit(".", 1)[-1]
        types = self.tree / "[Content_Types].xml"
        text = types.read_text(encoding="utf-8")
        if re.search(rf'<Default\s+Extension="{re.escape(extension)}"', text, re.I):
            return
        if f'PartName="/ppt/media/{name}"' in text:
            return
        entry = f'<Default Extension="{extension}" ContentType="{content_type}"/>'
        types.write_text(text.replace("</Types>", f"{entry}</Types>"), encoding="utf-8")

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

    def counts_from(self) -> int | None:
        """The number the deck says its first page has, or None when it does not say (= counted from 1)."""
        said = FIRST_NUMBER.search(self._presentation_tag())
        return int(said.group(1)) if said else None

    def count_from(self, first: int) -> None:
        """Say which number the first page has (= `firstSlideNum`, what PowerPoint's "Number slides from" writes)."""
        presentation = self.tree / "ppt/presentation.xml"
        text, tag = presentation.read_text(encoding="utf-8"), self._presentation_tag()
        said = FIRST_NUMBER.sub(f'firstSlideNum="{first}"', tag) if FIRST_NUMBER.search(tag) \
            else tag[:-1] + f' firstSlideNum="{first}">'
        presentation.write_text(text.replace(tag, said, 1), encoding="utf-8")

    def _presentation_tag(self) -> str:
        return PRESENTATION_TAG.search((self.tree / "ppt/presentation.xml").read_text(encoding="utf-8")).group(0)

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
