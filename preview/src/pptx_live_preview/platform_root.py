"""Where this tool keeps its files when an agent platform root is given.

環境変数 `AGENT_PLATFORM_ROOT` が在れば、道具は `<根>/<役割>/pptx-agent-maker/` を自分で組む
(= 役割 = config・secrets・state・references・cache)。無ければ `None` を返し、呼ぶ側が今までの
既定の置き場 (= `~/.config` など) に戻る。置き場を決めるのはここ 1 か所で、使う側は役割ごとの
folder の中の名前だけを持つ。
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT_VARIABLE = "AGENT_PLATFORM_ROOT"
TOOL_NAME = "pptx-agent-maker"
ROLES = ("config", "secrets", "state", "references", "cache")


def tool_folder(role: str) -> Path | None:
    """`<root>/<role>/pptx-agent-maker`, or None when no platform root is given."""
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}, not {role!r}")
    given = os.environ.get(ROOT_VARIABLE)
    if not given:
        return None
    root = Path(given)
    # ⚠ 相対 path は、起動した folder によって書く先が変わる。根は絶対 path だけを受ける。
    if not root.is_absolute():
        raise ValueError(f"{ROOT_VARIABLE} must be an absolute path, not {given!r}")
    return root / role / TOOL_NAME
