"""An album: pictures listed in a file, shown as the pages of one deck, with no rendering.

見本の頁 (= 頁の形をした絵) を、資料と同じ画面で並べて見るための口。形は再生リスト (= M3U) と同じ。
"""

from __future__ import annotations

from PIL import Image

from pptx_live_preview import state as st


def _picture(path, colour):
    Image.new("RGB", (1600, 900), colour).save(path)
    return path


def test_an_album_shows_its_pictures_as_pages_with_their_notes(tmp_path):
    _picture(tmp_path / "a.jpg", (200, 40, 40))
    pictures = tmp_path / "pictures"
    pictures.mkdir()
    _picture(pictures / "b.png", (40, 40, 200))
    (tmp_path / "examples.album").write_text(
        "# 業務の報告 / 1 頁目\na.jpg\n\n# 大きな数字\n# 2 行目の注記\npictures/b.png\n", encoding="utf-8")
    decks = st.DeckSet(tmp_path)
    decks.rescan_and_rerender(force=True)
    (deck,) = [decks.deck(name) for name in decks.deck_names()]
    detail = deck.detail()
    assert detail["error"] is None
    assert detail["slides"] == 2
    assert detail["notes"] == ["業務の報告 / 1 頁目", "大きな数字\n2 行目の注記"]
    with Image.open(deck.cache.thumb_path(detail["pages"][1])) as thumb:
        assert max(thumb.size) <= 854, "the page list does not carry full-size pictures"


def test_an_album_naming_a_picture_that_is_not_there_says_so(tmp_path):
    (tmp_path / "broken.album").write_text("gone.jpg\n", encoding="utf-8")
    decks = st.DeckSet(tmp_path)
    decks.rescan_and_rerender(force=True)
    deck = decks.deck("broken")
    assert "not there" in deck.error and "gone.jpg" in deck.error
