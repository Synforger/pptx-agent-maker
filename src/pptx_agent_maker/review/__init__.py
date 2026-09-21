"""The round trip with the person reading the deck.

    ledger.py   道具が最後に焼いたものを覚える (= 手編集を上書きしない)
    compare.py  2 つのデッキの文言を全文で突き合わせる
    fold.py     手編集を退避し、manifest に戻せる形で出す

⚠ **人が直した版を、道具が黙って消さない。**これが守れなかったとき、復元できる控えが
どこにも無かった。退避は自動で、消せない場所に置く。
"""

from __future__ import annotations

from .compare import Change, changes
from .fold import as_manifest_entries, fold, keep_safe
from .ledger import last_machine_build, remember, touched_by_hand

__all__ = ["Change", "changes", "fold", "as_manifest_entries", "keep_safe",
           "remember", "touched_by_hand", "last_machine_build"]
