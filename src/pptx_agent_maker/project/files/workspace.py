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
配色がツールの色の使い方と合わないときと、文字の大きさを決めるとき (= 資料の使い方 `use` と、
役ごとの上書き `[theme.type]`) に書く。余白と間隔はツールが持ったまま。

⚠ **回を folder で仕切らない。**開いて確かめるのは焼いたデッキなので、それが
マニフェストの隣に在るのがいちばん短い。素材だけは数が多いので回ごとに分ける。

⚠ **テンプレートは写さずに指せる。**`template = "<folder>"` を書くと、その folder の `workspace.toml` を
読み、この案件の設定をその上に重ねる (= 同じ表は鍵ごとに案件の値が勝つ)。`specimen.pptx` も、案件の folder に
無ければテンプレートの folder の物を使う。テンプレートが上げ直されても、案件の側は替え直さなくてよい。
指せるのは 1 段だけ (= テンプレートの `workspace.toml` は、さらに別のテンプレートを指せない)。

守っているのは 2 つ:

* **案件が repo の中を指していたら拒む** ― 中に置けば commit に入り、push に入る
* **無い path を黙って返さない** ― 空振りを握り潰すと、気づくのは何時間か後になる
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from ...layout.base.tokens import ThemeError, theme_from

REPO = Path(__file__).resolve().parents[4]
FILENAME = "workspace.toml"
#: 直下に置く folder (= 素材だけ。マニフェストも焼いたデッキも root に並ぶ)
FOLDERS = ("assets",)
#: root 直下でツールが使う名前 (= マニフェストに使えない)
RESERVED = (FILENAME, "recipes.toml")
#: 案件だけが持つ鍵 (= テンプレートの値を受け継がない。在処はその `workspace.toml` からの相対)
OWN_KEYS = ("root", "paths", "template")


class WorkspaceError(RuntimeError):
    """The workspace is missing, malformed, or somewhere it must not be."""


@dataclass(frozen=True)
class Workspace:
    """Where one deck project keeps its things."""

    root: Path
    assets: Path
    settings: dict = field(default_factory=dict)
    #: この案件が宣言した見た目 (= 書体と色と文字の大きさ。書体と色は、無ければテンプレートのもの)
    look: dict = field(default_factory=dict)
    #: 指しているテンプレートの folder (= `template`。写して持つ案件は None)
    template: Path | None = None

    @classmethod
    def load(cls, path: Path | str) -> "Workspace":
        """Read a workspace.toml — or the folder holding one."""
        path = Path(path).expanduser().resolve()
        if path.is_dir():
            path = path / FILENAME
        if not path.is_file():
            raise WorkspaceError(f"no {FILENAME} at {path}")

        data = cls._read(path)

        root = Path(str(data.get("root", path.parent))).expanduser()
        root = (path.parent / root).resolve() if not root.is_absolute() else root.resolve()
        cls._refuse_inside_the_repo(root, path)

        template = None
        if "template" in data:
            template = (path.parent / Path(str(data["template"])).expanduser()).resolve()
            shared = template / FILENAME
            if not shared.is_file():
                raise WorkspaceError(f"{path.name}: `template` points at {template}, which holds no {FILENAME}")
            inherited = cls._read(shared)
            if "template" in inherited:
                raise WorkspaceError(f"{path.name}: the template at {template} points at a template of its own — "
                                     "a project points at one template, and that template at none")
            data = _laid_over({key: value for key, value in inherited.items() if key not in OWN_KEYS}, data)

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
            template=template,
            **{name: root / str(folders.get(name, name)) for name in FOLDERS},
        )

    def specimen(self, name: str) -> Path:
        """The specimen a manifest names: the project's own, or else the template's it points at."""
        own = self.root / name
        if own.is_file() or self.template is None or not (self.template / name).is_file():
            return own
        return self.template / name

    @staticmethod
    def _read(path: Path) -> dict:
        with path.open("rb") as handle:
            return tomllib.load(handle)

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
            if not (self.assets / name).exists():
                # 探した 2 か所を両方言う (= 回の folder を先に見ている、が分からないと迷う)
                raise WorkspaceError(
                    f"asset not found: {name} (= looked in assets/{within}/ and assets/)")
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


def _laid_over(under: dict, over: dict) -> dict:
    """`over` laid on `under`: a table is merged key by key, anything else is replaced."""
    laid = dict(under)
    for key, value in over.items():
        laid[key] = (_laid_over(laid[key], value) if isinstance(value, dict) and isinstance(laid.get(key), dict)
                     else value)
    return laid
