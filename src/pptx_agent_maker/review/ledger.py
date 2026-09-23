"""Remembering what the toolkit last wrote, so a human edit is never overwritten.

⚠ **これが無いと、人が GUI で直した版を次のビルドが黙って消す。**実際に一度、
手で直した版を「余計な複製」と判断して消し、復元できなくした。

記録するのは中身の hash 1 つだけ (= 焼き直しても同じ宣言なら同じ hash)。
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

#: 道具が案件の folder に置く唯一のもの。**案件の持ち物と同じ階層に散らさない** ―
#: 直下に並ぶのはマニフェストと焼いたデッキと素材だけ、という形を守る。
STATE = ".pptx-agent-maker"
LEDGER = "built.json"
LAST = "last"


def _state(deck: Path) -> Path:
    return Path(deck).parent / STATE


def _digest(deck: Path) -> str:
    return hashlib.sha256(Path(deck).read_bytes()).hexdigest()


def _path(deck: Path) -> Path:
    return _state(deck) / LEDGER


def remember(deck: Path) -> None:
    """Record the deck as the toolkit's own output, and keep one copy of it.

    ⚠ **1 世代だけ。**旧世代はビルドのたびに控えを増やし、片付ける口が無いまま大きく膨らんで
    なった。ここが残すのは「最後に機械が焼いた 1 本」で、人の直しとの差分を取るためだけに在る。
    """
    deck = Path(deck)
    ledger = _path(deck)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    known = json.loads(ledger.read_text()) if ledger.is_file() else {}
    known[deck.name] = _digest(deck)
    ledger.write_text(json.dumps(known, indent=2, sort_keys=True), encoding="utf-8")

    shelf = _state(deck) / LAST
    shelf.mkdir(parents=True, exist_ok=True)
    shutil.copy2(deck, shelf / deck.name)


def last_machine_build(deck: Path) -> Path | None:
    """The copy of what the toolkit last wrote, if there is one."""
    candidate = _state(deck) / LAST / Path(deck).name
    return candidate if candidate.is_file() else None


def touched_by_hand(deck: Path) -> bool:
    """True when the file on disk is not what the toolkit last wrote."""
    deck = Path(deck)
    if not deck.is_file():
        return False
    ledger = _path(deck)
    if not ledger.is_file():
        return True  # something is there that we never wrote
    known = json.loads(ledger.read_text())
    return known.get(deck.name) != _digest(deck)
