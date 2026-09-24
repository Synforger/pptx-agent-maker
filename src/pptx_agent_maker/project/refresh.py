"""Handing an existing project what a newer toolkit carries.

`init` は、その時のツールが持つ task の口と手順書を案件へ**写す**。写した物は案件に残るので、
ツールを更新しても**既存の案件には新しい task も新しい手順書も届かない** ― 案件で起動した
エージェントは、ツールにある口を知らないまま古い手順で組む。

ここはツールが持つ file だけを最新に置き換える。案件の file (= manifest、設定、テンプレート、
素材、焼いたデッキ、recipe) には触らない。置き換える前の版は `.pptx-agent-maker/replaced/<時刻>/`
に控える (= 案件で手を入れていても失わない)。
"""

from __future__ import annotations

import filecmp
import shutil
from datetime import datetime
from pathlib import Path

from .scaffold import TEMPLATE

#: ツールが持ち、案件が持たない file (= 案件の雛形からの相対 path)
TOOL_OWNED = ("Taskfile.yml", "_README.md", ".claude/skills/deck")
STATE = ".pptx-agent-maker"


def refresh(root: Path | str) -> tuple[list[str], Path | None]:
    """Replace the toolkit's own files in a project; return what changed and where the old ones went."""
    root = Path(root)
    changed: list[str] = []
    for owned in TOOL_OWNED:
        source = TEMPLATE / owned
        files = sorted(p for p in source.rglob("*") if p.is_file()) if source.is_dir() else [source]
        for file in files:
            relative = file.relative_to(TEMPLATE).as_posix()
            target = root / relative
            if not target.is_file() or not filecmp.cmp(file, target, shallow=False):
                changed.append(relative)
    if not changed:
        return [], None

    kept = root / STATE / "replaced" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    for relative in changed:
        target = root / relative
        if target.is_file():
            (kept / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, kept / relative)
    for relative in changed:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(TEMPLATE / relative, target)
    return changed, kept if kept.exists() else None
