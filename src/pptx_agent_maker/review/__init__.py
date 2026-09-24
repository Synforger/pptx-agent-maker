"""The round trip with the person reading the deck.

    ledger.py   ツールが最後に焼いたものを覚える (= 手編集を上書きしない)
    parts.py    2 つのデッキを部品単位で全量突き合わせる (= 落とさない層)
    compare.py  2 つのデッキの文言を全文で突き合わせる (= 読める形に翻訳する層)
    fold.py     手編集を退避し、manifest に戻せる形で出す

⚠ **人が直した版を、ツールが黙って消さない。**これが守れなかったとき、復元できる控えが
どこにも無かった。退避は自動で、消せない場所に置く。
"""

from __future__ import annotations

from .compare import Change, changes
from .parts import Inventory, Part, compare as compare_parts, render as render_parts
from .fold import as_manifest_entries, fold, keep_safe
from .ledger import last_machine_build, remember, touched_by_hand

__all__ = ["Change", "changes", "fold", "as_manifest_entries", "keep_safe",
           "remember", "touched_by_hand", "last_machine_build",
           "Inventory", "Part", "compare_parts", "render_parts"]
