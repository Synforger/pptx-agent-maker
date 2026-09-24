"""What goes on which page, read from one file in the project.

頁の作り方は 3 つしかない ― **テンプレートを複製する** / **前のデッキから輸入する** /
**宣言層で組む**。manifest はその並びだけを持ち、寸法も色も持たない (= それはツールの token)。

宣言頁は**型を選ぶ**しかない (`type`)。頁の割り方を頁ごとに決められる口を残すほど、
同じ役割の頁が週ごとに別の形になる ― 前の世代では、名前を用意しただけの位置の隣に
名前のない値が積み上がった。型に収まらない頁が出たら、**型を足してから**作る。

⚠ **覚え書きは `why` に 1 行だけ。**`note` は頁の中身 (= 図表の読み方) で、型が読む。
改訂履歴を manifest に積むと、何が載っているかを読む前にそれを通過することになる
(= 前の世代では 1 つのキーに改訂が何本も溜まった)。履歴は git log が持つ ― ここでは
長さと日付を機械が見ていて、**書いた時点で止まる**。

⚠ **真値は 1 枚。**旧世代は manifest と頁 script の両方が絵を決められ、「design の値を
変えても動かない」を 2 度踏んだ。ここでは manifest が並びの真値で、頁の中身は頁が持つ。
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

KINDS = ("copy", "import", "declare")

#: `why` の上限。日本語 1 行がおよそ 45 字なので、覚え書き 3 行ぶんまで許す。
#: 超えるものは覚え書きではなく経緯で、置き場は git log。
WHY_LIMIT = 200
#: 覚え書きの中の日付 (= 改訂履歴が積まれ始めた印)
DATED = re.compile(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b")

#: manifest の運び方に属するキー (= 型へは渡さない)
_NOT_PAGE_DATA = frozenset({"kind", "page", "deck", "replace", "why"})


class ManifestError(ValueError):
    """The manifest cannot be read as a deck."""


@dataclass(frozen=True)
class Entry:
    """One page of the deck being built."""

    kind: str
    page: int | None = None
    deck: str | None = None
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
    #: 素材の置き場 (= 既定はこのマニフェストの名前。`assets/<ここ>/` を見る)
    assets: str = ""

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
                   entries=entries, source=path,
                   assets=str(data.get("assets", path.stem)))

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
        if kind == "declare" and not page.get("type"):
            raise ManifestError(
                f"{where}: a declared page needs `type` (= one of the page types). "
                "A page that fits none of them means a type is missing; add one rather "
                "than placing shapes by hand."
            )

        why = str(page.get("why", ""))
        _check_why(where, why)

        replace = tuple((str(a), str(b)) for a, b in page.get("replace", []))
        data = {key: value for key, value in page.items() if key not in _NOT_PAGE_DATA}
        return Entry(kind=kind, page=page.get("page"), deck=page.get("deck"),
                     type=page.get("type"), data=data,
                     replace=replace, why=why)


def _check_why(where: str, why: str) -> None:
    """Keep the note a note.

    ⚠ **manifest は何が載っているかの宣言で、何があったかの記録ではない。**前の世代では
    1 つのキーに日付つきの改訂が何本も積まれ、頁の一覧を読む前に必ずそこを
    通ることになった。長さと日付のどちらも機械が判定できるので、書いた時点で止める。
    """
    if len(why) > WHY_LIMIT:
        raise ManifestError(
            f"{where}: `why` is {len(why)} characters, over {WHY_LIMIT} — this is a "
            "history, not a note. What happened belongs in the commit that did it."
        )
    found = DATED.search(why)
    if found:
        raise ManifestError(
            f"{where}: `why` carries a date ({found.group(0)}) — dated lines are how a "
            "manifest turns into a changelog. Say why the page is here; git log says when."
        )
