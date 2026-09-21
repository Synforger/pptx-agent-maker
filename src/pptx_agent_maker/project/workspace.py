"""The one file that names a path outside this repository.

案件のデータ (= 型見本・manifest・素材・焼いたデッキ) は repo の外に置く。道具が
その在処を知る口はここ 1 つで、コードにも頁にも外の path を書かない。

守っているのは 2 つ:

* **案件が repo の中を指していたら拒む** ― 中に置けば commit に入り、push に入る
* **無い path を黙って返さない** ― 空振りを握り潰すと、気づくのは何時間か後になる
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FILENAME = "workspace.toml"
FOLDERS = ("base", "manifests", "pages", "assets", "output")


class WorkspaceError(RuntimeError):
    """The workspace is missing, malformed, or somewhere it must not be."""


@dataclass(frozen=True)
class Workspace:
    """Where one deck project keeps its things."""

    root: Path
    base: Path
    manifests: Path
    pages: Path
    assets: Path
    output: Path

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
        return cls(
            root=root,
            **{name: root / str(folders.get(name, name)) for name in FOLDERS},
        )

    @staticmethod
    def _refuse_inside_the_repo(root: Path, source: Path) -> None:
        if root == REPO or REPO in root.parents:
            raise WorkspaceError(
                f"{source} points at {root}, which is inside this repository — "
                "a deck project lives outside it, so its data can never reach a push"
            )

    def asset(self, name: str) -> Path:
        """An asset by name. Missing means stop, not carry on with a broken path."""
        return self._existing(self.assets / name, "asset")

    def manifest(self, name: str) -> Path:
        """A manifest by name, with or without the .toml suffix."""
        candidate = self.manifests / name
        if not candidate.suffix:
            candidate = candidate.with_suffix(".toml")
        return self._existing(candidate, "manifest")

    def out(self, name: str) -> Path:
        """Where a built deck goes. The folder is made if it is not there yet."""
        self.output.mkdir(parents=True, exist_ok=True)
        return self.output / name

    @staticmethod
    def _existing(path: Path, what: str) -> Path:
        if not path.exists():
            raise WorkspaceError(f"{what} not found: {path}")
        return path
