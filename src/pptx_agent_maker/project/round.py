"""Starting the next round from the one before.

回ごとのデッキは、前の回の manifest を複製して始めるのがふつう。手で複製すると、
出力の名前 (`out`) を書き換え忘れて**前の回のデッキを上書きする**か、素材の置き場を
作り忘れて最初の build で止まる。ここはその 3 つを 1 手でやる。

⚠ **素材は写さない。**前の回の絵を黙って使い回すと、新しい回なのに古い絵が載った頁が
焼ける。新しい回の `assets/<名前>/` は空で始まり、足りない素材は build が名前を挙げて止める。
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

NAME = re.compile(r"[A-Za-z0-9_-]+")


class RoundError(ValueError):
    """The next round cannot be started as asked."""


def start(root: Path | str, name: str, previous: str) -> Path:
    """Write `<name>.toml` from `<previous>.toml` and make `assets/<name>/`; return the manifest."""
    root = Path(root)
    name, previous = name.removesuffix(".toml"), previous.removesuffix(".toml")
    if not NAME.fullmatch(name):
        raise RoundError(f"{name!r}: a round's name is letters, digits, - and _ (= it names files)")
    source, target = root / f"{previous}.toml", root / f"{name}.toml"
    if not source.is_file():
        raise RoundError(f"no manifest at {source}")
    if target.exists() or (root / f"{name}.pptx").exists():
        raise RoundError(f"{name} is already a round here — pick another name")

    text = source.read_text(encoding="utf-8")
    head, sep, rest = text.partition("[[pages]]")
    head = _set(head, "out", f"{name}.pptx")
    if re.search(r"(?m)^assets\s*=", head):
        head = _set(head, "assets", name)
    written = head + sep + rest
    data = tomllib.loads(written)
    if data.get("out") != f"{name}.pptx":
        raise RoundError(f"could not point {target.name} at {name}.pptx; nothing was written")

    target.write_text(written, encoding="utf-8")
    (root / "assets" / name).mkdir(parents=True, exist_ok=True)
    return target


def _set(head: str, key: str, value: str) -> str:
    """Rewrite one top-level `key = "..."` line (= the part before the first page)."""
    line = f'{key} = "{value}"'
    if re.search(rf"(?m)^{key}\s*=", head):
        return re.sub(rf"(?m)^{key}\s*=.*$", lambda _m: line, head, count=1)
    return line + "\n" + head
