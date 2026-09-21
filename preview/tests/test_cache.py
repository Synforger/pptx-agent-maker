"""保管庫の性質を固定する: 同じ絵は 1 枚、要らない絵は消える、開き直しても読める。"""

from __future__ import annotations

import json

import pytest

from pptx_live_preview.cache import DeckCache, deck_key


@pytest.fixture
def cache(tmp_path):
    return DeckCache(tmp_path / "store")


def _shot(tmp_path, name, pages):
    """1 回ぶんの描画結果を作る (= 焼きたての絵が置かれた作業フォルダ)。"""
    work = tmp_path / name
    work.mkdir(parents=True, exist_ok=True)
    full, small = [], []
    for i, content in enumerate(pages, start=1):
        p = work / f"page-{i}.jpg"
        p.write_bytes(content)
        full.append(p)
        t = work / f"thumb-{i}.jpg"
        t.write_bytes(b"small:" + content)
        small.append(t)
    return full, small


def test_identical_pages_are_stored_once(cache, tmp_path):
    """同じ中身の頁が何枚あっても実体は 1 つ。"""
    pages, thumbs = _shot(tmp_path, "a", [b"same", b"same", b"other"])
    render = cache.adopt("src-1", pages, thumbs)
    assert len(render.pages) == 3
    assert render.pages[0] == render.pages[1]
    assert len(list(cache.pages_dir.glob("*.jpg"))) == 2


def test_unchanged_page_keeps_its_name(cache, tmp_path):
    """変わっていない頁は描き直しても同じ名前 = 同じ URL のまま。"""
    first = cache.adopt("src-1", *_shot(tmp_path, "a", [b"p1", b"p2"]))
    second = cache.adopt("src-2", *_shot(tmp_path, "b", [b"p1", b"p2-changed"]))
    assert second.pages[0] == first.pages[0]
    assert second.pages[1] != first.pages[1]


def test_pages_and_thumbs_are_paired(cache, tmp_path):
    """原寸と小さい絵は同じ名前で対になる (= 片方だけ欠けない)。"""
    render = cache.adopt("src-1", *_shot(tmp_path, "a", [b"p1", b"p2"]))
    for h in render.pages:
        assert cache.page_path(h).is_file()
        assert cache.thumb_path(h).is_file()


def test_source_match_short_circuits(cache, tmp_path):
    cache.adopt("src-1", *_shot(tmp_path, "a", [b"p1"]))
    assert cache.matches_source("src-1") is True
    assert cache.matches_source("src-2") is False


def test_empty_store_matches_nothing(cache):
    assert cache.current is None
    assert cache.matches_source("src-1") is False


def test_superseded_images_are_swept(cache, tmp_path):
    """今の描画が指していない絵は残さない。"""
    cache.adopt("src-1", *_shot(tmp_path, "a", [b"p1", b"p2"]))
    cache.adopt("src-2", *_shot(tmp_path, "b", [b"p1", b"p3"]))
    assert len(list(cache.pages_dir.glob("*.jpg"))) == 2
    assert len(list(cache.thumbs_dir.glob("*.jpg"))) == 2


def test_store_survives_reopening(cache, tmp_path):
    """別インスタンスで開き直しても読める (= 再起動で焼き直さない土台)。"""
    cache.adopt("src-1", *_shot(tmp_path, "a", [b"p1", b"p2"]))
    reborn = DeckCache(cache.root)
    assert reborn.current is not None
    assert reborn.current.source == "src-1"
    assert reborn.current.pages == cache.current.pages
    assert reborn.matches_source("src-1") is True


def test_corrupt_index_is_discarded_not_fatal(cache, tmp_path):
    """索引が壊れていても落ちない (= 焼き直し 1 回で復帰する)。"""
    cache.adopt("src-1", *_shot(tmp_path, "a", [b"p1"]))
    cache.index_path.write_text("{ not json", encoding="utf-8")
    reborn = DeckCache(cache.root)
    assert reborn.current is None
    assert reborn.matches_source("src-1") is False


def test_index_is_valid_json_on_disk(cache, tmp_path):
    cache.adopt("src-1", *_shot(tmp_path, "a", [b"p1"]))
    raw = json.loads(cache.index_path.read_text(encoding="utf-8"))
    assert raw["source"] == "src-1"
    assert len(raw["pages"]) == 1


def test_deck_key_separates_same_name_in_different_folders(tmp_path):
    """別フォルダの同名デッキが同じ置き場を共有しない。"""
    a = tmp_path / "one" / "w3.pptx"
    b = tmp_path / "two" / "w3.pptx"
    assert deck_key(a) != deck_key(b)
    assert deck_key(a).startswith("w3-")


def test_deck_key_is_filesystem_safe(tmp_path):
    """名前に使えない文字が混じっても置き場の名前は安全に保つ。"""
    key = deck_key(tmp_path / "w3 (最終) /版.pptx")
    assert "/" not in key and " " not in key
