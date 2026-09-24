"""The one file that names a path outside this repository.

案件のデータ (= テンプレート・manifest・素材・焼いたデッキ) は repo の外に置く。ツールが
その在処を知る口はここ 1 つで、コードにも型にも外の path を書かない。

置き方は 1 つ ― **焼いたデッキと、それを組んだマニフェストが対で直下に並ぶ**。

    <案件>/
    ├── workspace.toml     この設定 (= 予約名)
    ├── specimen.pptx      見た目の元 (= 予約名。この上に頁が書き足される)
    ├── w1.toml            ← 何を並べるか
    ├── w1.pptx            ← それを焼いたもの
    ├── w2.toml
    ├── w2.pptx
    └── assets/
        ├── w1/            マニフェストと同じ名前の folder が、その回の素材
        └── w2/

見た目 (= 書体と色) は**テンプレートが持つ**。`[theme]` はその上に重ねる例外で、テンプレートの
配色がツールの色の使い方と合わないときだけ書く。頁の割り方はツールが持ったまま。

⚠ **回を folder で仕切らない。**開いて確かめるのは焼いたデッキなので、それが
マニフェストの隣に在るのがいちばん短い。素材だけは数が多いので回ごとに分ける。

守っているのは 2 つ:

* **案件が repo の中を指していたら拒む** ― 中に置けば commit に入り、push に入る
* **無い path を黙って返さない** ― 空振りを握り潰すと、気づくのは何時間か後になる
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from ..layout.tokens import ThemeError, theme_from

REPO = Path(__file__).resolve().parents[3]
FILENAME = "workspace.toml"
#: 直下に置く folder (= 素材だけ。マニフェストも焼いたデッキも root に並ぶ)
FOLDERS = ("assets",)
#: root 直下でツールが使う名前 (= マニフェストに使えない)
RESERVED = (FILENAME, "recipes.toml")


class WorkspaceError(RuntimeError):
    """The workspace is missing, malformed, or somewhere it must not be."""


@dataclass(frozen=True)
class Workspace:
    """Where one deck project keeps its things."""

    root: Path
    assets: Path
    settings: dict = field(default_factory=dict)
    #: この案件が宣言した見た目 (= 書体と色。無ければテンプレートのものが使われる)
    look: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | str) -> "Workspace":
        """Read a workspace.toml — or the folder holding one."""
        path = Path(path).expanduser().resolve()
        if path.is_dir():
            path = path / FILENAME
        if not path.is_file():
            raise WorkspaceError(f"no {FILENAME} at {path}")

        with path.open("rb") as handle:
            data = tomllib.load(handle)

        root = Path(str(data.get("root", path.parent))).expanduser()
        root = (path.parent / root).resolve() if not root.is_absolute() else root.resolve()
        cls._refuse_inside_the_repo(root, path)

        folders = data.get("paths", {})
        look = data.get("theme") or {}
        try:
            # 読んだ時点で言う (= 焼く段まで持っていくと、誤りに気づくのが 1 手遅れる)
            theme_from(look)
        except ThemeError as reason:
            raise WorkspaceError(f"{path.name}: {reason}") from reason

        return cls(
            root=root,
            settings=data,
            look=look,
            **{name: root / str(folders.get(name, name)) for name in FOLDERS},
        )

    @staticmethod
    def _refuse_inside_the_repo(root: Path, source: Path) -> None:
        if root == REPO or REPO in root.parents:
            raise WorkspaceError(
                f"{source} points at {root}, which is inside this repository — "
                "a deck project lives outside it, so its data can never reach a push"
            )

    def asset(self, name: str, *, within: str | None = None) -> Path:
        """An asset by name, from the round's own folder.

        `within` はふつうマニフェストの名前 (= `w1.toml` なら `assets/w1/`)。回ごとに
        分けない案件もあるので、その回の folder が無ければ `assets/` 直下を見る。
        """
        if within:
            candidate = self.assets / within / name
            if candidate.exists():
                return candidate
        return self._existing(self.assets / name, "asset")

    def manifest(self, name: str) -> Path:
        """A manifest by name, with or without the .toml suffix."""
        candidate = self.root / name
        if not candidate.suffix:
            candidate = candidate.with_suffix(".toml")
        if candidate.name in RESERVED:
            raise WorkspaceError(
                f"{candidate.name} is the workspace's own file, not a manifest"
            )
        return self._existing(candidate, "manifest")

    def manifests(self) -> list[Path]:
        """Every manifest in the project, in reading order."""
        return sorted(p for p in self.root.glob("*.toml") if p.name not in RESERVED)

    def out(self, name: str) -> Path:
        """Where a built deck goes — beside the manifest that describes it."""
        return self.root / name

    @staticmethod
    def _existing(path: Path, what: str) -> Path:
        if not path.exists():
            raise WorkspaceError(f"{what} not found: {path}")
        return path
