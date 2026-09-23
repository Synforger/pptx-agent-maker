"""Create the folder a deck project lives in.

雛形は**道具の package の中**に在り、そこから外へ展開する。既に在るものは上書きしない
(= 案件の中身を道具が壊さない)。
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

#: ⚠ **package の中に置く。**repo の木に置いていた間は、入れた道具から消えていて
#: `init` が FileNotFoundError で落ちた (= repo から動かしたときだけ動いていた)。
TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "project"


def create(destination: Path | str, *, name: str | None = None,
           specimen: Path | str | None = None) -> Path:
    """Lay the project skeleton down at `destination` and return where it went.

    `specimen` はこの案件の見た目。⚠ **建てる 1 手で決める。**あとから手で上書きする形だと、
    上書きし忘れた回だけ顔が変わる ― 頁を作るより先に、その回だけ別のデッキになる。
    """
    destination = Path(destination).expanduser().resolve()
    name = name or destination.name
    look = _readable_specimen(specimen)

    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(
            f"{destination} already has something in it — point at an empty folder, "
            "or add the missing pieces by hand"
        )

    shutil.copytree(TEMPLATE, destination, dirs_exist_ok=True)
    if look is not None:
        shutil.copy2(look, destination / "specimen.pptx")

    settings = destination / "workspace.toml"
    settings.write_text(
        settings.read_text(encoding="utf-8").replace("<project>", name), encoding="utf-8"
    )
    return destination


def _readable_specimen(given: Path | str | None) -> Path | None:
    """Check the specimen before anything is written.

    ⚠ **建ててから断らない。**先に確かめておかないと、半分だけできた folder が残り、
    建て直そうとすると「空でない」と断られる。
    """
    if given is None:
        return None
    look = Path(given).expanduser()
    if not look.is_file():
        raise FileNotFoundError(f"no specimen at {look}")
    if not zipfile.is_zipfile(look):
        raise ValueError(f"{look} is not a .pptx (= it is not even a zip)")
    return look
