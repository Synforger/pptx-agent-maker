"""What goes on which page, read from one file in the project.

頁の作り方は 3 つしかない ― **型見本を複製する** / **前のデッキから輸入する** /
**宣言層で組む**。manifest はその並びだけを持ち、寸法も色も持たない (= それは道具の token)。

⚠ **真値は 1 枚。**旧世代は manifest と頁 script の両方が絵を決められ、「design の値を
変えても動かない」を 2 度踏んだ。ここでは manifest が並びの真値で、頁の中身は頁が持つ。
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

KINDS = ("copy", "import", "declare")


class ManifestError(ValueError):
    """The manifest cannot be read as a deck."""


@dataclass(frozen=True)
class Entry:
    """One page of the deck being built."""

    kind: str
    page: int | None = None
    deck: str | None = None
    module: str | None = None
    replace: tuple[tuple[str, str], ...] = ()
    note: str = ""


@dataclass(frozen=True)
class Manifest:
    """A deck: which specimen it grows from, where it goes, and its pages."""

    specimen: str
    out: str
    entries: tuple[Entry, ...] = field(default_factory=tuple)
    source: Path | None = None

    @classmethod
    def load(cls, path: Path | str) -> "Manifest":
        path = Path(path)
        if not path.is_file():
            raise ManifestError(f"no manifest at {path}")
        with path.open("rb") as handle:
            data = tomllib.load(handle)

        for required in ("specimen", "out"):
            if not data.get(required):
                raise ManifestError(f"{path.name}: `{required}` is missing")

        pages = data.get("pages", [])
        if not pages:
            raise ManifestError(f"{path.name}: a deck with no pages is not a deck")

        entries = tuple(cls._entry(path, index, page) for index, page in enumerate(pages, start=1))
        return cls(specimen=str(data["specimen"]), out=str(data["out"]),
                   entries=entries, source=path)

    @staticmethod
    def _entry(path: Path, index: int, page: dict) -> Entry:
        kind = str(page.get("kind", "")).strip()
        where = f"{path.name} page {index}"
        if kind not in KINDS:
            raise ManifestError(f"{where}: kind must be one of {', '.join(KINDS)}, not {kind!r}")

        if kind == "copy" and not page.get("page"):
            raise ManifestError(f"{where}: a copied page needs `page` (= the specimen's Nth page)")
        if kind == "import" and not (page.get("deck") and page.get("page")):
            raise ManifestError(f"{where}: an imported page needs `deck` and `page`")
        if kind == "declare" and not page.get("module"):
            raise ManifestError(f"{where}: a declared page needs `module` (= a file in pages/)")

        replace = tuple((str(a), str(b)) for a, b in page.get("replace", []))
        return Entry(kind=kind, page=page.get("page"), deck=page.get("deck"),
                     module=page.get("module"), replace=replace, note=str(page.get("note", "")))
