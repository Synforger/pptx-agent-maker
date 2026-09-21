"""DeckState の再描画判定とデッキ集合の走査を固定する。

外部コマンド (LibreOffice / pdftoppm) は呼ばず、PDF 化とラスタライズを
差し替えて判定ロジックだけ見る。
"""

from __future__ import annotations

import os
import threading

import pytest

from pptx_live_preview import state as st
from pptx_live_preview.render import RenderError, Rasterized


class FakeRenderer:
    """to_pdf / rasterize の差し替え。呼ばれた回数と出す中身を制御する。"""

    def __init__(self) -> None:
        self.pages = [b"page-1-v1", b"page-2-v1"]
        self.pdf_calls = 0
        self.raster_calls = 0
        self.pdf_error: str | None = None
        self.raster_error: str | None = None

    def to_pdf(self, pptx, work_dir, profile):
        self.pdf_calls += 1
        if self.pdf_error:
            raise RenderError(self.pdf_error)
        work_dir.mkdir(parents=True, exist_ok=True)
        pdf = work_dir / "deck.pdf"
        # LibreOffice の出力は毎回変わる。判定に使えないことを模す。
        pdf.write_bytes(f"pdf-{self.pdf_calls}".encode())
        return pdf

    def rasterize(self, pdf, work_dir, dpi):
        self.raster_calls += 1
        if self.raster_error:
            raise RenderError(self.raster_error)
        full = work_dir / "full"
        small = work_dir / "small"
        full.mkdir(parents=True, exist_ok=True)
        small.mkdir(parents=True, exist_ok=True)
        pages, thumbs = [], []
        for i, content in enumerate(self.pages, start=1):
            p = full / f"page-{i}.jpg"
            p.write_bytes(content)
            pages.append(p)
            t = small / f"thumb-{i}.jpg"
            t.write_bytes(b"small:" + content)
            thumbs.append(t)
        return Rasterized(pages=pages, thumbs=thumbs)


@pytest.fixture
def fake(monkeypatch):
    r = FakeRenderer()
    monkeypatch.setattr(st, "to_pdf", r.to_pdf)
    monkeypatch.setattr(st, "rasterize", r.rasterize)
    return r


@pytest.fixture
def deck(tmp_path, fake):
    pptx = tmp_path / "w1.pptx"
    pptx.write_bytes(b"initial")
    return st.DeckState(pptx, cache_dir=tmp_path / "cache")


def _touch(path, mtime):
    os.utime(path, (mtime, mtime))


# ---- mtime settling -------------------------------------------------------

def test_first_sighting_waits_for_the_file_to_settle(deck, fake):
    """新しい更新時刻を 1 度見ただけでは描かない (= 書き込み途中かもしれない)。"""
    _touch(deck.pptx, 1000.0)
    assert deck.rerender_if_stale() is False
    assert fake.pdf_calls == 0


def test_renders_once_the_mtime_repeats(deck, fake):
    """同じ更新時刻を 2 回続けて見たら書き終わったとみなして描く。"""
    _touch(deck.pptx, 1000.0)
    deck.rerender_if_stale()
    assert deck.rerender_if_stale() is True
    assert fake.raster_calls == 1
    assert deck.version == 1
    assert deck.slides == 2


def test_keeps_waiting_while_the_file_is_still_growing(deck, fake):
    """更新時刻が動き続ける間は描かない (= 巨大な zip の書き込み中)。"""
    for mtime in (1000.0, 1001.0, 1002.0):
        _touch(deck.pptx, mtime)
        assert deck.rerender_if_stale() is False
    assert fake.pdf_calls == 0


def test_settled_file_is_not_redrawn(deck, fake):
    """描いたあと変化がなければ描き直さない。"""
    _touch(deck.pptx, 1000.0)
    deck.rerender_if_stale()
    deck.rerender_if_stale()
    assert deck.rerender_if_stale() is False
    assert fake.pdf_calls == 1


def test_force_skips_the_wait(deck, fake):
    """force は落ち着き待ちを飛ばす (= 起動時と手動の再描画ボタン)。"""
    _touch(deck.pptx, 1000.0)
    assert deck.rerender_if_stale(force=True) is True
    assert fake.raster_calls == 1


def test_missing_file_is_not_an_error(deck, fake):
    """デッキが消えている間は何もしない (= 差し替えの一瞬)。"""
    deck.pptx.unlink()
    assert deck.rerender_if_stale() is False
    assert fake.pdf_calls == 0


# ---- skipping work --------------------------------------------------------

def test_changing_the_resolution_forces_a_rerender(deck, fake):
    """焼く細かさを変えたら、デッキが同じでも焼き直す (= 古い粗さの絵を残さない)。"""
    deck.rerender_if_stale(force=True)
    assert fake.pdf_calls == 1
    coarser = st.DeckState(deck.pptx, dpi=deck.dpi // 2, cache_dir=deck.cache.root)
    assert coarser.rerender_if_stale(force=True) is True
    assert fake.pdf_calls == 2


def test_unchanged_deck_skips_the_whole_render(deck, fake):
    """中身が同じまま吐き直されたら、一番重い PDF 変換ごと飛ばす。"""
    deck.rerender_if_stale(force=True)
    assert fake.pdf_calls == 1
    _touch(deck.pptx, 2000.0)
    assert deck.rerender_if_stale(force=True) is False  # 画面に見える変化なし
    assert fake.pdf_calls == 1  # LibreOffice を呼んでいない
    assert fake.raster_calls == 1


def test_changed_deck_renders_again(deck, fake):
    """デッキの中身が変われば描き直す。"""
    deck.rerender_if_stale(force=True)
    deck.pptx.write_bytes(b"edited")
    fake.pages = [b"page-1-v1", b"page-2-v2"]
    assert deck.rerender_if_stale(force=True) is True
    assert fake.raster_calls == 2


def test_pdf_bytes_are_never_the_judgement(deck, fake):
    """PDF は毎回バイトが変わる。それを判定材料にしていないことを固定する。"""
    deck.rerender_if_stale(force=True)
    _touch(deck.pptx, 3000.0)
    deck.rerender_if_stale(force=True)
    _touch(deck.pptx, 4000.0)
    deck.rerender_if_stale(force=True)
    assert fake.raster_calls == 1  # 焼き直しは初回だけ


def test_rebuild_ignores_the_store(deck, fake):
    """手動の再描画だけは中身が同じでも焼き直す。"""
    deck.rerender_if_stale(force=True)
    deck.rerender_if_stale(force=True, rebuild=True)
    assert fake.pdf_calls == 2
    assert fake.raster_calls == 2


def test_restart_reuses_the_stored_pages(tmp_path, fake):
    """別インスタンス (= 再起動) でも同じデッキなら焼き直さず、絵はすぐ出る。"""
    pptx = tmp_path / "w1.pptx"
    pptx.write_bytes(b"x")
    cache_dir = tmp_path / "cache"

    first = st.DeckState(pptx, cache_dir=cache_dir)
    first.rerender_if_stale(force=True)
    assert first.slides == 2

    reborn = st.DeckState(pptx, cache_dir=cache_dir)
    assert reborn.slides == 2  # 描く前から前回の絵が見えている
    reborn.rerender_if_stale(force=True)
    assert fake.pdf_calls == 1  # 2 度目の変換は起きていない


# ---- errors ---------------------------------------------------------------

def test_render_failure_is_reported_not_raised(deck, fake):
    """描画に失敗しても落ちず、error に載せて次の巡回へ回す。"""
    fake.pdf_error = "soffice failed"
    assert deck.rerender_if_stale(force=True) is True
    assert deck.error == "soffice failed"


def test_repeated_identical_failure_does_not_wake_the_browser(deck, fake):
    """同じ失敗を繰り返す間は通知しない (= 画面を無意味に叩き起こさない)。"""
    fake.pdf_error = "soffice failed"
    deck.rerender_if_stale(force=True)
    assert deck.rerender_if_stale(force=True) is False
    assert deck.version == 1


def test_recovering_from_an_error_notifies(deck, fake):
    """失敗から復帰したら通知する。"""
    fake.pdf_error = "soffice failed"
    deck.rerender_if_stale(force=True)
    fake.pdf_error = None
    assert deck.rerender_if_stale(force=True) is True
    assert deck.error is None


def test_rasterise_failure_keeps_the_previous_pages(deck, fake):
    """焼き直しに失敗しても、前回の絵は保管庫に残ったまま見える。"""
    deck.rerender_if_stale(force=True)
    deck.pptx.write_bytes(b"edited")
    fake.raster_error = "pdftoppm failed"
    deck.rerender_if_stale(force=True)
    assert deck.error == "pdftoppm failed"
    assert deck.slides == 2


# ---- payloads -------------------------------------------------------------

def test_detail_lines_up_pages_changes_and_notes(deck, fake, monkeypatch):
    """画面へ渡す情報は頁数と同じ長さで揃える (= 添字がずれない)。"""
    monkeypatch.setattr(st.notes_mod, "extract", lambda p: ["only one note"])
    deck.rerender_if_stale(force=True)
    detail = deck.detail()
    assert len(detail["pages"]) == 2
    assert len(detail["notes"]) == 2
    assert detail["notes"][1] == ""


# ---- deck set -------------------------------------------------------------

def test_folder_scan_skips_lock_files(tmp_path, fake):
    """PowerPoint が開いている間だけ置くロックファイルはデッキとして拾わない。

    それ以外の .pptx は名前で選り分けない。どの綴りが「本物のデッキでない」かは
    デッキを作った側の都合で、ここから見えるものではない。
    """
    for name in ("w1.pptx", "w2.pptx", "~$w1.pptx", "notes.txt"):
        (tmp_path / name).write_bytes(b"x")

    deckset = st.DeckSet(tmp_path)
    deckset.rescan_and_rerender()
    assert deckset.deck_names() == ["w1", "w2"]


def test_folder_scan_drops_decks_that_disappear(tmp_path, fake):
    """フォルダから消えたデッキは一覧からも消える。"""
    (tmp_path / "w1.pptx").write_bytes(b"x")
    (tmp_path / "w2.pptx").write_bytes(b"x")

    deckset = st.DeckSet(tmp_path)
    deckset.rescan_and_rerender()
    (tmp_path / "w2.pptx").unlink()
    deckset.rescan_and_rerender()
    assert deckset.deck_names() == ["w1"]


def test_single_deck_is_a_set_of_one(tmp_path, fake):
    """単一デッキも同じ型で扱う (= 単一専用の経路を持たない)。"""
    pptx = tmp_path / "w1.pptx"
    pptx.write_bytes(b"x")
    deckset = st.DeckSet(pptx)
    deckset.rescan_and_rerender(force=True)
    assert deckset.is_folder is False
    assert deckset.deck_names() == ["w1"]
    assert deckset.summaries()[0]["slides"] == 2


def test_single_deck_ignores_siblings(tmp_path, fake):
    """単一指定では同じフォルダの他のデッキを拾わない。"""
    pptx = tmp_path / "w1.pptx"
    pptx.write_bytes(b"x")
    (tmp_path / "w2.pptx").write_bytes(b"x")
    deckset = st.DeckSet(pptx)
    deckset.rescan_and_rerender(force=True)
    assert deckset.deck_names() == ["w1"]


# ---- notification ---------------------------------------------------------

def test_rerender_wakes_event_waiters(deck, fake):
    """再描画で版が進むと、待機スレッドが notify で即時に起きる。"""
    woke = threading.Event()

    def waiter():
        with deck.cond:
            if deck.version == 0:
                deck.cond.wait(timeout=5.0)
            if deck.version > 0:
                woke.set()

    t = threading.Thread(target=waiter)
    t.start()
    _touch(deck.pptx, 1000.0)
    deck.rerender_if_stale()
    deck.rerender_if_stale()
    t.join(timeout=6.0)
    assert woke.is_set()


def test_deck_appearing_wakes_event_waiters(tmp_path, fake):
    """デッキの出現で版が進み、待機スレッドが起きる。"""
    deckset = st.DeckSet(tmp_path)
    woke = threading.Event()

    def waiter():
        with deckset.cond:
            if deckset.version == 0:
                deckset.cond.wait(timeout=5.0)
            if deckset.version > 0:
                woke.set()

    t = threading.Thread(target=waiter)
    t.start()
    (tmp_path / "w1.pptx").write_bytes(b"x")
    deckset.rescan_and_rerender()
    t.join(timeout=6.0)
    assert woke.is_set()
