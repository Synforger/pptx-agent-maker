"""Create the folder a deck project lives in.

雛形は repo の `templates/project/` に在り、**外へ展開する**。既に在るものは上書きしない
(= 案件の中身を道具が壊さない)。
"""

from __future__ import annotations

import shutil
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[3] / "templates" / "project"


def create(destination: Path | str, *, name: str | None = None) -> Path:
    """Lay the project skeleton down at `destination` and return where it went."""
    destination = Path(destination).expanduser().resolve()
    name = name or destination.name

    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(
            f"{destination} already has something in it — point at an empty folder, "
            "or add the missing pieces by hand"
        )

    shutil.copytree(TEMPLATE, destination, dirs_exist_ok=True)
    settings = destination / "workspace.toml"
    settings.write_text(
        settings.read_text(encoding="utf-8").replace("<project>", name), encoding="utf-8"
    )
    return destination
