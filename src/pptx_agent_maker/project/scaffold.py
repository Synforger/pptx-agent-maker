"""Create the folder a deck project lives in.

プロジェクトテンプレートは**ツールの package の中**に在り、そこから外へ展開する。既に在るものは上書きしない
(= 案件の中身をツールが壊さない)。
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

#: ⚠ **package の中に置く。**repo の木に置いていた間は、入れたツールから消えていて
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
    look, settings = _readable_look(specimen)
    # テンプレートの folder に recipe が上がっていれば、見た目と一緒に配る (= `lift.py`)
    recipes = Path(specimen).expanduser() / "recipes.toml" if specimen is not None else None

    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(
            f"{destination} already has something in it — point at an empty folder, "
            "or add the missing pieces by hand"
        )

    shutil.copytree(TEMPLATE, destination, dirs_exist_ok=True)
    if look is not None:
        shutil.copy2(look, destination / "specimen.pptx")
    if settings is not None:
        shutil.copy2(settings, destination / "workspace.toml")
    if recipes is not None and recipes.is_file():
        shutil.copy2(recipes, destination / "recipes.toml")

    settings = destination / "workspace.toml"
    settings.write_text(
        settings.read_text(encoding="utf-8").replace("<project>", name), encoding="utf-8"
    )
    return destination


def _readable_look(given: Path | str | None) -> tuple[Path | None, Path | None]:
    """Check what the project will look like, before anything is written.

    ⚠ **建ててから断らない。**先に確かめておかないと、半分だけできた folder が残り、
    建て直そうとすると「空でない」と断られる。

    渡せるのは 2 通り ― **テンプレート 1 枚**か、**テンプレートと設定を対で置いた folder**。
    後者が要るのは、pptx のテーマ色が「1 番目の差し色」という枠でしかなく、ツールの側が
    「読みを示す色」「条件の帯」という**意味**で色を使うから ― その 2 つを繋ぐ表は
    テンプレートの中に書けない。対で渡せば、案件は 1 手で自分の見た目になる。
    """
    if given is None:
        return None, None

    where = Path(given).expanduser()
    if where.is_dir():
        look = where / "specimen.pptx"
        if not look.is_file():
            raise FileNotFoundError(f"{where} holds no specimen.pptx")
        settings = where / "workspace.toml"
        return _a_deck(look), settings if settings.is_file() else None

    return _a_deck(where), None


def _a_deck(look: Path) -> Path:
    if not look.is_file():
        raise FileNotFoundError(f"no specimen at {look}")
    if not zipfile.is_zipfile(look):
        raise ValueError(f"{look} is not a .pptx (= it is not even a zip)")
    return look
