"""What goes on which page, read from one file in the project.

頁の作り方は 3 つしかない ― **型見本を複製する** / **前のデッキから輸入する** /
**宣言層で組む**。manifest はその並びだけを持ち、寸法も色も持たない (= それは道具の token)。

宣言頁は **型を選ぶ** (`type`) か、案件の頁 script を指す (`module`) かのどちらか。
型で書けるものは型で書く ― 版面の割り方を頁ごとに決められる口を残すほど、同じ役割の
頁が週ごとに別の形になる。

⚠ **覚え書きは `why` に 1 行だけ。**`note` は頁の中身 (= 図表の読み方) で、型が読む。
改訂履歴を manifest に積むと、何が載っているかを読む前にそれを通過することになる
(= 前の世代では 1 つのキーに改訂が何本も溜まった)。履歴は git log が持つ。

⚠ **真値は 1 枚。**旧世代は manifest と頁 script の両方が絵を決められ、「design の値を
変えても動かない」を 2 度踏んだ。ここでは manifest が並びの真値で、頁の中身は頁が持つ。
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

KINDS = ("copy", "import", "declare")

#: manifest の運び方に属するキー (= 型へは渡さない)
_NOT_PAGE_DATA = frozenset({"kind", "page", "deck", "module", "replace", "why"})


class ManifestError(ValueError):
    """The manifest cannot be read as a deck."""


@dataclass(frozen=True)
class Entry:
    """One page of the deck being built."""

    kind: str
    page: int | None = None
    deck: str | None = None
    module: str | None = None
    type: str | None = None
    data: dict = field(default_factory=dict)
    replace: tuple[tuple[str, str], ...] = ()
    why: str = ""


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
        if kind == "declare":
            named = [key for key in ("type", "module") if page.get(key)]
            if not named:
                raise ManifestError(
                    f"{where}: a declared page needs `type` (= one of the page types) "
                    "or `module` (= a file in pages/)"
                )
            if len(named) == 2:
                raise ManifestError(
                    f"{where}: `type` and `module` both given — a page is built one way. "
                    "Drop `module` to use the type, or drop `type` to keep the script."
                )

        replace = tuple((str(a), str(b)) for a, b in page.get("replace", []))
        data = {key: value for key, value in page.items() if key not in _NOT_PAGE_DATA}
        return Entry(kind=kind, page=page.get("page"), deck=page.get("deck"),
                     module=page.get("module"), type=page.get("type"), data=data,
                     replace=replace, why=str(page.get("why", "")))
