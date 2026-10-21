"""One run of everything that writes a file on this machine, for `tests/test_platform_root.py` to watch.

`python tests/support/platform_root_scenario.py DECK` を、HOME・TMPDIR・作業 folder を空の
folder に向け、`AGENT_PLATFORM_ROOT` を渡して走らせる。焼く (= LibreOffice まで通す)・開いた物を
覚える・見本の集まりを書く・設定を読む、の順に、置き場を引くすべての経路を 1 度ずつ通る。
試験は走らせた後、根の外に file が 1 つも無いことを数える。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "preview" / "src"))

from pptx_agent_maker.project.files.places import load  # noqa: E402
from pptx_live_preview.state import DeckState, Opened  # noqa: E402


def _fetch_examples():
    spec = importlib.util.spec_from_file_location(
        "fetch_examples", REPO / "scripts" / "examples" / "fetch-examples.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(deck: Path) -> None:
    load()  # 根の config の設定 file (= 試験が置いた物) を読めること

    state = DeckState(deck)
    state.rerender_if_stale(force=True)
    if state.error:
        raise SystemExit(f"the deck did not render: {state.error}")
    Opened().remember_project("scenario")

    examples = _fetch_examples()
    if examples.main(["--no-fetch"]) != 0:
        raise SystemExit("fetch-examples did not finish")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
