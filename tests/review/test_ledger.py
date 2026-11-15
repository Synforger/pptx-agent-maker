"""Tests for the ledger of what the toolkit last wrote: a deck is matched by name in one Unicode form."""

from __future__ import annotations

import json
import unicodedata
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pptx_agent_maker.review.ledger import LEDGER, STATE, remember, touched_by_hand

#: A deck name with voiced kana, so its composed (NFC) and decomposed (NFD) forms differ.
TYPED = "\u8cc7\u6599\u30c7\u30c3\u30ad.pptx"
DECOMPOSED = unicodedata.normalize("NFD", TYPED)


class LedgerNameTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.assertNotEqual(TYPED, DECOMPOSED)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_an_entry_written_under_the_decomposed_name_is_found_by_the_typed_one(self) -> None:
        deck = self.folder / TYPED
        deck.write_bytes(b"built")
        remember(deck)
        ledger = self.folder / STATE / LEDGER
        known = json.loads(ledger.read_text())
        ledger.write_text(json.dumps({DECOMPOSED: known[TYPED]}), encoding="utf-8")
        self.assertFalse(touched_by_hand(deck))

    def test_the_ledger_keys_a_deck_by_its_composed_name(self) -> None:
        deck = self.folder / DECOMPOSED
        deck.write_bytes(b"built")
        remember(deck)
        known = json.loads((self.folder / STATE / LEDGER).read_text())
        self.assertEqual(list(known), [TYPED])

    def test_a_deck_changed_after_the_build_is_still_seen_as_touched(self) -> None:
        deck = self.folder / TYPED
        deck.write_bytes(b"built")
        remember(deck)
        deck.write_bytes(b"edited by hand")
        self.assertTrue(touched_by_hand(deck))


if __name__ == "__main__":
    unittest.main()
