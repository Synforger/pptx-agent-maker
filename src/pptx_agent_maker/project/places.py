"""What the preview offers to look at, read from one file on this machine.

常駐のプレビューは 1 つの port で走り続けるので、見る物を替えるたびに起動し直す形だと、
画面を見る人が起動の仕方を知っている必要がある。見る物の一覧はこの機械の設定 file が持ち、
画面の上の欄で選ぶ:

    # ~/.config/pptx-agent-maker/preview.toml
    [[search]]            # この folder の下の案件 (= workspace.toml を持つ folder) を並べる
    path = "~/decks"
    depth = 3             # 何段下まで探すか (= 省略すると 3)

    [[folder]]            # この folder をそのまま 1 つとして並べる (= 案件でないデッキの置き場)
    name = "old decks"
    path = "~/decks/archive/output"

    [labels]              # 案件の表示名 (= folder の path → 欄とタブの題に出す名前)
    "~/decks/client-a/deck" = "A"

⚠ **欄とタブの題には folder 名を出さない。**folder 名には先方の名前が入りうるので、発表中に
欄を開いただけで別の会社の名前が並ぶ。表示名を書いていない案件は「案件 」+ folder から作った
短い印 (= 再起動しても変わらない) で出す。発表の時は `?only=<表示名>` で 1 案件に絞る。

案件はそれぞれのテンプレートを一覧から外す。一覧は画面が取りに来るたびに探し直すので、
新しく `init` した案件は再起動なしで欄に出る。
"""

from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path

DEFAULT = Path.home() / ".config" / "pptx-agent-maker" / "preview.toml"
#: 探す時に下りない folder (= 控え・ツールの状態)
NOT_PROJECTS = {"_archive", "_edits", ".pptx-agent-maker", "node_modules"}


class PlacesError(ValueError):
    """The places file cannot be read as places."""


def load(path: Path | str = DEFAULT) -> dict:
    path = Path(path).expanduser()
    if not path.is_file():
        raise PlacesError(
            f"no places file at {path} — write one with [[search]] and [[folder]] entries "
            "(see `pptx_agent_maker.project.places`)")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    unknown = sorted(set(data) - {"search", "folder", "labels"})
    if unknown:
        raise PlacesError(f"{path.name}: only [[search]] and [[folder]] belong here, not {unknown}")
    for kind in ("search", "folder"):
        for entry in data.get(kind, []):
            if not entry.get("path"):
                raise PlacesError(f"{path.name}: a [[{kind}]] entry has no path")
            if kind == "folder" and not entry.get("name"):
                raise PlacesError(f"{path.name}: a [[folder]] entry has no name")
    return data


def projects_under(parent: Path, depth: int = 3) -> list[Path]:
    """Folders under `parent`, `depth` levels at most, that are deck projects."""
    # ⚠ **決めた段数までしか下りない。**全部歩いてから深さで捨てる形だと、大きな folder を
    # 画面が一覧を取りに来るたびに歩き切ることになる。
    found = []
    for level in range(depth + 1):
        for settings in sorted(parent.glob("/".join(["*"] * level + ["workspace.toml"]))):
            parts = settings.parent.relative_to(parent).parts
            if any(p.startswith(".") or p in NOT_PROJECTS for p in parts):
                continue
            # ⚠ `workspace.toml` はほかの道具も使う名前 (= 納品の雛形の作業場もこの名前で持つ)。
            # デッキの案件は `init` が必ず置くテンプレートも持つので、両方そろった folder だけにする
            if not (settings.parent / "specimen.pptx").is_file():
                continue
            found.append(settings.parent)
    return sorted(found)


def discover(places: dict, skip_of) -> dict[str, tuple[Path, list[str]]]:
    """Name → (folder, names to leave out) for everything the places file offers.

    `skip_of(folder)` は案件のテンプレートの名前を返す (= 案件でない folder には呼ばない)。
    読めない案件は黙って飛ばす (= 画面が 2 秒ごとに探し直すので、ここで騒ぐと log が埋まる)。
    """
    found: dict[str, tuple[Path, list[str]]] = {}
    labels = {str(Path(k).expanduser().resolve()): str(v)
              for k, v in (places.get("labels") or {}).items()}
    for entry in places.get("search", []):
        root = Path(entry["path"]).expanduser()
        if not root.is_dir():
            continue
        for folder in projects_under(root, int(entry.get("depth", 3))):
            name = labels.get(str(folder.resolve())) or unnamed(folder)
            if name in found:
                name = f"{name} ({unnamed(folder).split()[-1]})"
            try:
                found[name] = (folder, sorted(skip_of(folder)))
            except Exception:  # noqa: BLE001 - 壊れた案件 1 つで一覧を止めない
                continue
    for entry in places.get("folder", []):
        folder = Path(entry["path"]).expanduser()
        if folder.is_dir():
            found[str(entry["name"])] = (folder, [])
    return found


def unnamed(folder: Path) -> str:
    """A name for a project with no label: no folder name in it, the same on every start."""
    mark = hashlib.sha1(str(Path(folder).resolve()).encode("utf-8")).hexdigest()[:4]
    return f"案件 {mark}"
