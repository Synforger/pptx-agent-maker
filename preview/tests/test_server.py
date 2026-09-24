"""HTTP 面の経路と守りを固定する。

実サーバを立てて叩く。見るのは「どの住所が何を返すか」と「画像名として
細工された経路を弾くか」で、描画そのものは差し替える。
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from pptx_live_preview import state as st
from pptx_live_preview.render import Rasterized
from pptx_live_preview.server import QuietThreadingHTTPServer, make_handler


@pytest.fixture
def live(tmp_path, monkeypatch):
    """2 デッキぶんの偽の描画結果を載せたサーバを起動する。"""
    pages = {"w1": [b"w1-p1", b"w1-p2"], "w2": [b"w2-p1"]}

    def fake_to_pdf(pptx, work_dir, profile):
        work_dir.mkdir(parents=True, exist_ok=True)
        pdf = work_dir / "d.pdf"
        pdf.write_bytes(pptx.stem.encode())
        return pdf

    def fake_rasterize(pdf, work_dir, dpi):
        stem = pdf.read_bytes().decode()
        full = work_dir / "full"
        small = work_dir / "small"
        full.mkdir(parents=True, exist_ok=True)
        small.mkdir(parents=True, exist_ok=True)
        out, thumbs = [], []
        for i, content in enumerate(pages[stem], start=1):
            p = full / f"page-{i}.jpg"
            p.write_bytes(content)
            out.append(p)
            t = small / f"thumb-{i}.jpg"
            t.write_bytes(b"small:" + content)
            thumbs.append(t)
        return Rasterized(pages=out, thumbs=thumbs)

    monkeypatch.setattr(st, "to_pdf", fake_to_pdf)
    monkeypatch.setattr(st, "rasterize", fake_rasterize)
    monkeypatch.setattr(st.notes_mod, "extract", lambda p: ["note one", "note two"])
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    for name in pages:
        (tmp_path / f"{name}.pptx").write_bytes(b"x")

    deckset = st.DeckSet(tmp_path)
    deckset.rescan_and_rerender(force=True)

    server = QuietThreadingHTTPServer(("127.0.0.1", 0), make_handler(deckset))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    yield base, deckset
    server.shutdown()


def get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.read(), dict(r.headers)


def get_json(url):
    _status, body, _headers = get(url)
    return json.loads(body)


def status_of(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as exc:
        return exc.code


def test_index_and_assets_are_served(live):
    base, _ = live
    for path, needle in (("/", b"<title>"), ("/app.css", b"#filmstrip"), ("/app.js", b"loadDecks")):
        status, body, _ = get(base + path)
        assert status == 200
        assert needle in body


def test_index_carries_its_style_and_script_inline(live):
    """相乗り配信で末尾スラッシュが落ちても無地にならないよう、資産は埋め込む。"""
    base, _ = live
    _status, body, _headers = get(base + "/")
    assert b'href="./app.css"' not in body
    assert b'src="./app.js"' not in body
    assert b"#filmstrip" in body   # stylesheet folded in
    assert b"loadDecks" in body    # script folded in


def test_deck_list_is_light(live):
    """一覧に頁ごとの重い情報を混ぜない (= デッキが増えても軽い)。"""
    base, _ = live
    decks = get_json(base + "/api/decks")
    assert [d["name"] for d in decks] == ["w1", "w2"]
    assert "pages" not in decks[0]
    assert decks[0]["slides"] == 2


def test_deck_detail_carries_pages_and_notes(live):
    base, _ = live
    detail = get_json(base + "/api/decks/w1")
    assert len(detail["pages"]) == 2
    assert detail["notes"] == ["note one", "note two"]


def test_pages_and_thumbs_are_served_by_content_hash(live):
    base, _ = live
    detail = get_json(base + "/api/decks/w1")
    h = detail["pages"][0]
    status, body, headers = get(f"{base}/api/pages/w1/{h}.jpg")
    assert status == 200
    assert body == b"w1-p1"
    assert "immutable" in headers["Cache-Control"]
    _s, thumb, _h = get(f"{base}/api/thumbs/w1/{h}.jpg")
    assert thumb == b"small:w1-p1"


def test_unknown_deck_and_page_are_404(live):
    base, _ = live
    assert status_of(base + "/api/decks/nope") == 404
    detail = get_json(base + "/api/decks/w1")
    assert status_of(f"{base}/api/pages/nope/{detail['pages'][0]}.jpg") == 404
    assert status_of(f"{base}/api/pages/w1/{'0' * 16}.jpg") == 404


def test_image_names_outside_the_hash_shape_are_refused(live):
    """画像名はキャッシュが付けた 16 桁の hash だけを通す。"""
    base, _ = live
    for bad in ("..%2f..%2fetc%2fpasswd", "short", "versions.json", "x" * 16):
        assert status_of(f"{base}/api/pages/w1/{bad}.jpg") == 404


def test_meta_reports_the_mode(live):
    base, _ = live
    meta = get_json(base + "/api/meta")
    assert meta["folder"] is True
    assert meta["title"]


def test_unknown_route_is_404(live):
    base, _ = live
    assert status_of(base + "/nope") == 404
    assert status_of(base + "/api/nope") == 404
