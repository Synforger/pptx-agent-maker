"""Several projects behind one page (= Switchboard).

見るのは「案件の一覧が出る」「選び直すとデッキの一覧が替わる」「切り替えた瞬間に待っている
画面へ通知が届く (= keep-alive まで待たされない)」「1 案件の起動では選ぶ欄の口が無い」。
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from pptx_live_preview import state as st
from pptx_live_preview.render import Rasterized
from pptx_live_preview.server import QuietThreadingHTTPServer, make_handler


def _fake_render(monkeypatch):
    def fake_to_pdf(pptx, work_dir, profile):
        work_dir.mkdir(parents=True, exist_ok=True)
        pdf = work_dir / "d.pdf"
        pdf.write_bytes(pptx.stem.encode())
        return pdf

    def fake_rasterize(pdf, work_dir, dpi):
        full, small = work_dir / "full", work_dir / "small"
        full.mkdir(parents=True, exist_ok=True)
        small.mkdir(parents=True, exist_ok=True)
        (full / "page-1.jpg").write_bytes(pdf.read_bytes())
        (small / "thumb-1.jpg").write_bytes(b"small")
        return Rasterized(pages=[full / "page-1.jpg"], thumbs=[small / "thumb-1.jpg"])

    monkeypatch.setattr(st, "to_pdf", fake_to_pdf)
    monkeypatch.setattr(st, "rasterize", fake_rasterize)
    monkeypatch.setattr(st.notes_mod, "extract", lambda p: [])


def _serve(deckset):
    server = QuietThreadingHTTPServer(("127.0.0.1", 0), make_handler(deckset))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def _json(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return json.loads(r.read())


@pytest.fixture
def board(tmp_path, monkeypatch):
    _fake_render(monkeypatch)
    for project, deck in (("alpha", "a1"), ("beta", "b1")):
        (tmp_path / project).mkdir()
        (tmp_path / project / f"{deck}.pptx").write_bytes(b"x")
    switchboard = st.Switchboard({name: st.DeckSet(tmp_path / name)
                                  for name in ("alpha", "beta")})
    switchboard.rescan_and_rerender(force=True)
    server, base = _serve(switchboard)
    yield base, switchboard
    server.shutdown()


def test_the_projects_are_listed_with_the_one_looked_at(board):
    base, _ = board
    assert _json(base + "/api/projects") == {"projects": ["alpha", "beta"], "active": "alpha",
                                             "problems": {}}
    assert [d["name"] for d in _json(base + "/api/decks")] == ["a1"]


def test_choosing_another_project_changes_the_decks(board):
    base, switchboard = board
    before = switchboard.version
    with urllib.request.urlopen(base + "/api/projects/select/beta", timeout=5) as r:
        assert r.status == 202
    for _ in range(50):
        if [d["name"] for d in _json(base + "/api/decks")] == ["b1"]:
            break
        time.sleep(0.05)
    assert [d["name"] for d in _json(base + "/api/decks")] == ["b1"]
    assert switchboard.version > before, "the page would not know the project changed"


def test_a_page_waiting_for_news_hears_the_switch_at_once(board):
    """⚠ 古い案件の待ち合わせで待っている画面を起こさないと、keep-alive まで何も変わらない。"""
    _, switchboard = board
    woke = []

    def wait():
        with switchboard.cond:
            start = time.monotonic()
            switchboard.cond.wait(timeout=10)
            woke.append(time.monotonic() - start)

    waiter = threading.Thread(target=wait)
    waiter.start()
    time.sleep(0.2)
    switchboard.select("beta")
    waiter.join(timeout=12)
    assert woke and woke[0] < 5


def test_an_unknown_project_is_404(board):
    base, _ = board
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(base + "/api/projects/select/gamma", timeout=5)
    assert caught.value.code == 404


def test_a_single_project_page_has_no_projects(tmp_path, monkeypatch):
    _fake_render(monkeypatch)
    (tmp_path / "w1.pptx").write_bytes(b"x")
    server, base = _serve(st.DeckSet(tmp_path))
    try:
        with pytest.raises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(base + "/api/projects", timeout=5)
        assert caught.value.code == 404
    finally:
        server.shutdown()


def test_a_new_project_appears_without_a_restart(tmp_path, monkeypatch):
    """⚠ 常駐の画面は止めないので、`init` した案件が欄に出ないと見るために再起動が要る。"""
    _fake_render(monkeypatch)
    for name in ("alpha", "beta"):
        (tmp_path / name).mkdir()
        (tmp_path / name / f"{name}.pptx").write_bytes(b"x")
    offered = {"alpha": (tmp_path / "alpha", [])}
    board = st.Switchboard({"alpha": st.DeckSet(tmp_path / "alpha")},
                           discover=lambda: dict(offered))
    board.REDISCOVER_SECONDS = 0
    assert board.projects() == ["alpha"]
    offered["beta"] = (tmp_path / "beta", [])
    assert board.projects() == ["alpha", "beta"]
    board.select("beta")
    offered.pop("beta")
    offered.pop("alpha")
    assert board.projects() == ["beta"], "the one being looked at was taken away"


def test_the_decks_are_the_new_projects_as_soon_as_the_switch_answers(board):
    """⚠ 切り替えを裏で済ませていた間は、画面がすぐ取り直す一覧がまだ前の案件だった。"""
    base, _ = board
    with urllib.request.urlopen(base + "/api/projects/select/beta", timeout=5) as r:
        assert r.status == 202
    assert [d["name"] for d in _json(base + "/api/decks")] == ["b1"]  # 待たずに


def test_the_last_opened_deck_and_project_outlive_a_restart(tmp_path, monkeypatch):
    """⚠ 開き直すたびに古い回が出る、を止める (= server が覚え、再起動しても残る)。"""
    _fake_render(monkeypatch)
    for project, decks in (("alpha", ("a1", "a2")), ("beta", ("b1",))):
        (tmp_path / project).mkdir()
        for deck in decks:
            (tmp_path / project / f"{deck}.pptx").write_bytes(b"x")

    def start():
        board = st.Switchboard({name: st.DeckSet(tmp_path / name) for name in ("alpha", "beta")})
        board.rescan_and_rerender(force=True)
        return (board, *_serve(board))

    board, server, base = start()
    assert _json(base + "/api/opened") == {"deck": None}
    urllib.request.urlopen(base + "/api/opened/a2", timeout=5).read()
    urllib.request.urlopen(base + "/api/projects/select/beta", timeout=5).read()
    urllib.request.urlopen(base + "/api/opened/b1", timeout=5).read()
    server.shutdown()

    board, server, base = start()  # 再起動
    try:
        assert _json(base + "/api/projects")["active"] == "beta"
        assert _json(base + "/api/opened") == {"deck": "b1"}
        urllib.request.urlopen(base + "/api/projects/select/alpha", timeout=5).read()
        assert _json(base + "/api/opened") == {"deck": "a2"}, "each project keeps its own"
    finally:
        server.shutdown()


def test_a_deck_that_is_not_there_is_not_remembered(board):
    base, _ = board
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(base + "/api/opened/nope", timeout=5)
    assert caught.value.code == 404


def test_the_deck_list_says_when_each_deck_was_changed(board):
    """覚えが無い時は、一番新しく触ったデッキを開く (= 作業中の回はふつう最新)。"""
    base, _ = board
    assert all(d["modified"] > 0 for d in _json(base + "/api/decks"))


def test_each_page_sees_the_project_it_names(board):
    """⚠ 発表用に 1 案件へ絞った画面は、別の画面が既定の案件を替えても動かない。"""
    base, _ = board
    urllib.request.urlopen(base + "/api/projects/select/beta", timeout=5).read()
    for _ in range(50):
        if [d["name"] for d in _json(base + "/api/decks?p=alpha")] == ["a1"]:
            break
        time.sleep(0.05)
    assert [d["name"] for d in _json(base + "/api/decks?p=alpha")] == ["a1"]
    assert [d["name"] for d in _json(base + "/api/decks")] == ["b1"]  # 名乗らない画面は既定
    assert _json(base + "/api/meta?p=alpha")["title"] == "alpha"


def test_a_project_named_by_a_page_is_kept_up_to_date(tmp_path, monkeypatch):
    """既定でない案件も、画面が見ている間は file を直せば描き直される。"""
    _fake_render(monkeypatch)
    for project in ("alpha", "beta"):
        (tmp_path / project).mkdir()
        (tmp_path / project / f"{project}.pptx").write_bytes(b"x")
    board = st.Switchboard({name: st.DeckSet(tmp_path / name) for name in ("alpha", "beta")})
    board._drawn.add("beta")  # 裏で描き始めない (= test が終わった後まで走る処理を残さない)
    board.get("beta")
    watched = []
    monkeypatch.setattr(board._projects["beta"], "rescan_and_rerender",
                        lambda **kw: watched.append("beta"))
    board.rescan_and_rerender()
    assert watched == ["beta"]


def test_a_project_that_cannot_be_read_stays_and_says_why(tmp_path, monkeypatch):
    """⚠ 読めない案件を欄から黙って消すと、画面を見る人には「デッキが消えた」としか見えない。"""
    _fake_render(monkeypatch)
    for name in ("alpha", "beta"):
        (tmp_path / name).mkdir()
        (tmp_path / name / f"{name}.pptx").write_bytes(b"x")
    offered = {"alpha": (tmp_path / "alpha", []),
               "beta": (tmp_path / "beta", ["specimen"], "workspace.toml could not be read: x")}
    board = st.Switchboard({"alpha": st.DeckSet(tmp_path / "alpha")},
                           discover=lambda: dict(offered))
    board.REDISCOVER_SECONDS = 0
    server, base = _serve(board)
    try:
        listing = _json(base + "/api/projects")
        assert listing["projects"] == ["alpha", "beta"]
        assert listing["problems"] == {"beta": "workspace.toml could not be read: x"}
        assert _json(base + "/api/meta?p=beta")["problem"] == "workspace.toml could not be read: x"
        assert _json(base + "/api/meta?p=alpha")["problem"] is None
        assert [d["name"] for d in _json(base + "/api/decks?p=beta")] == ["beta"], \
            "its decks are still shown"

        version = board.get("beta").version
        offered["beta"] = (tmp_path / "beta", ["specimen"])  # 直った
        assert _json(base + "/api/projects")["problems"] == {}
        assert _json(base + "/api/meta?p=beta")["problem"] is None
        assert board.get("beta").version > version, "the page is woken to drop the note"
    finally:
        server.shutdown()


def test_with_nothing_to_show_the_page_stays_up_and_says_why(tmp_path, monkeypatch):
    """⚠ 案件の無い機械の常駐が起動を断り、launchd が起こし直しては落ち続けた。空のまま起きて理由を言う。"""
    _fake_render(monkeypatch)
    board = st.Switchboard({}, discover=lambda: {}, waiting=lambda: "no projects here yet",
                           opened=st.Opened(tmp_path / "opened.json"))
    board.REDISCOVER_SECONDS = 0
    board.rescan_and_rerender(force=True)  # 見張りの巡回が空でも回る
    server, base = _serve(board)
    try:
        assert _json(base + "/api/projects") == {"projects": [], "active": None, "problems": {}}
        assert _json(base + "/api/decks") == []
        meta = _json(base + "/api/meta")
        assert meta["problem"] == "no projects here yet"
        assert meta["title"] == st.Nothing.TITLE, "the tab is not titled after nothing"
    finally:
        server.shutdown()


def test_the_first_project_to_appear_is_shown_and_wakes_the_empty_page(tmp_path, monkeypatch):
    """空の画面を開いたままでも、最初の案件が出たら欄に出て、待っている画面へ通知が届く。"""
    _fake_render(monkeypatch)
    (tmp_path / "alpha").mkdir()
    (tmp_path / "alpha" / "a1.pptx").write_bytes(b"x")
    offered: dict = {}
    board = st.Switchboard({}, discover=lambda: dict(offered), waiting=lambda: "none yet",
                           opened=st.Opened(tmp_path / "opened.json"))
    board.REDISCOVER_SECONDS = 0
    empty = board.get(None)
    before = empty.version
    assert board.projects() == [] and board.project is None
    offered["alpha"] = (tmp_path / "alpha", [])
    assert board.projects() == ["alpha"]
    assert board.project == "alpha"
    assert empty.version != before, "the page waiting on the empty board is told"
    for _ in range(50):
        if board.get("alpha").deck_names() == ["a1"]:
            break
        time.sleep(0.05)
    assert board.get("alpha").deck_names() == ["a1"]


def test_the_reason_for_nothing_follows_what_the_machine_says(tmp_path):
    """理由は探し直すたびに取り直す (= 設定の file を置いた後も、前の理由が残らない)。"""
    reason = ["no places file"]
    board = st.Switchboard({}, discover=lambda: {}, waiting=lambda: reason[0],
                           opened=st.Opened(tmp_path / "opened.json"))
    board.REDISCOVER_SECONDS = 0
    assert board.get(None).problem == "no places file"
    reason[0] = "nothing to show yet"
    board.projects()
    assert board.get(None).problem == "nothing to show yet"


def test_an_empty_board_looks_for_projects_on_its_own_round(tmp_path, monkeypatch):
    """⚠ 探し直すのは画面が一覧を取りに来た時だけだった。空の画面は通知を待つだけで何も取りに来ないので、
    案件を作っても画面が乗り換えなかった。空の間は、見張りの巡回でも探し直す。"""
    _fake_render(monkeypatch)
    (tmp_path / "alpha").mkdir()
    offered: dict = {}
    board = st.Switchboard({}, discover=lambda: dict(offered), waiting=lambda: "none yet",
                           opened=st.Opened(tmp_path / "opened.json"))
    board.REDISCOVER_SECONDS = 0
    before = board.get(None).version
    offered["alpha"] = (tmp_path / "alpha", [])
    board.rescan_and_rerender()
    assert board.project == "alpha"
    assert board.get(None).version != before
