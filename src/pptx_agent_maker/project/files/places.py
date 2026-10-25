"""What the preview offers to look at, read from one file on this machine.

常駐のプレビューは 1 つの port で走り続けるので、見る物を替えるたびに起動し直す形だと、
画面を見る人が起動の仕方を知っている必要がある。見る物の一覧はこの機械の設定 file が持ち、
画面の上の欄で選ぶ:

    # ~/.config/pptx-agent-maker/preview.toml   (= 器の根が在る時は <根>/config/pptx-agent-maker/preview.toml)
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

⚠ **読めない案件も欄から消さない。**`workspace.toml` が読めない案件を黙って飛ばしていた間は、
画面を見る人には「デッキが消えた」としか見えなかった (= 常駐が古い道具のまま走っていて、新しい
欄を書いた案件を読めなかった実例が在る)。欄に残してデッキも見せ、読めなかった理由を添える。
"""

from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path
from typing import NamedTuple

from pptx_live_preview.platform_root import tool_folder

FILENAME = "preview.toml"
#: 探す時に下りない folder (= 控え・ツールの状態)
NOT_PROJECTS = {"_archive", "_edits", ".pptx-agent-maker", "node_modules"}


#: 案件の設定が読めない時に一覧から外す名前 (= `init` が必ず置くテンプレート)
TEMPLATE = "specimen"


class PlacesError(ValueError):
    """The places file cannot be read as places."""


class Offer(NamedTuple):
    """One thing the preview offers: its folder, the decks left out, and why it was not read."""

    folder: Path
    skip: list[str]
    #: 案件の設定が読めなかった理由 (= 読めた物と案件でない folder は None)
    problem: str | None = None


def default_places_file() -> Path:
    """The places file of this machine: under the platform root when one is given, else ~/.config."""
    folder = tool_folder("config")
    if folder is None:
        folder = Path.home() / ".config" / "pptx-agent-maker"
    return folder / FILENAME


def load(path: Path | str | None = None) -> dict:
    """The places file at `path` (= left out: the machine's own), checked."""
    if path is None:
        try:
            path = default_places_file()
        except ValueError as error:  # 根が絶対 path でない
            raise PlacesError(str(error)) from error
    path = Path(path).expanduser()
    if not path.is_file():
        raise PlacesError(
            f"no places file at {path} — write one with [[search]] and [[folder]] entries "
            "(see `pptx_agent_maker.project.files.places`)")
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
            # (= テンプレートを写さずに指す案件は、指した先にそろっている)
            if not (settings.parent / "specimen.pptx").is_file() and not _points_at_a_template(settings):
                continue
            found.append(settings.parent)
    return sorted(found)


def _points_at_a_template(settings: Path) -> bool:
    """Whether a workspace.toml points at a template folder that holds the specimen."""
    try:
        with settings.open("rb") as handle:
            template = tomllib.load(handle).get("template")
    except (OSError, tomllib.TOMLDecodeError):
        return False
    return template is not None and (settings.parent / Path(str(template)).expanduser() / "specimen.pptx").is_file()

def discover(places: dict, skip_of) -> dict[str, Offer]:
    """Name → what is offered under it, for everything the places file offers.

    `skip_of(folder)` は案件のテンプレートの名前を返す (= 案件でない folder には呼ばない)。
    読めない案件は、いつものテンプレートの名前だけを外して残し、読めなかった理由を持たせる
    (= log には書かない。画面が 2 秒ごとに探し直すので、log が埋まる)。
    """
    found: dict[str, Offer] = {}
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
                found[name] = Offer(folder, sorted(skip_of(folder)))
            except Exception as error:  # noqa: BLE001 - 壊れた案件 1 つで一覧を止めない
                found[name] = Offer(folder, [TEMPLATE], f"could not read the project: {error}")
    for entry in places.get("folder", []):
        folder = Path(entry["path"]).expanduser()
        if folder.is_dir():
            found[str(entry["name"])] = Offer(folder, [])
    return found


def unnamed(folder: Path) -> str:
    """A name for a project with no label: no folder name in it, the same on every start."""
    mark = hashlib.sha1(str(Path(folder).resolve()).encode("utf-8")).hexdigest()[:4]
    return f"案件 {mark}"
