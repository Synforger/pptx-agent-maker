"""Which requests the preview's server answers, asked of a real server over HTTP.

pytest runs it. The decks are never drawn: what is measured is the answer to a name, an origin and a method.
"""

from __future__ import annotations

import http.client
import json
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from pptx_live_preview import state as st
from pptx_live_preview.server import QuietThreadingHTTPServer, make_handler

FRONT = "decks.example.test"
WAIT_S = 5.0
REFRESH_COUNT = 6
# `shutdown` waits for one poll of the serving loop, once for every test.
SERVER_POLL_S = 0.02

Ask = Callable[..., tuple[int, bytes, dict[str, str]]]


@pytest.fixture
def board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> st.Switchboard:
    monkeypatch.setattr(st.DeckSet, "rescan_and_rerender", lambda self, force=False, rebuild=False: None)
    monkeypatch.setenv("AGENT_PLATFORM_ROOT", str(tmp_path / "root"))
    projects = {}
    for name in ("alpha", "beta"):
        (tmp_path / name).mkdir()
        deck = tmp_path / name / f"{name}.pptx"
        deck.write_bytes(b"x")
        projects[name] = st.DeckSet(tmp_path / name)
        projects[name].decks[name] = st.DeckState(deck)
    return st.Switchboard(projects, "alpha")


@pytest.fixture
def ask(board: st.Switchboard) -> Iterator[Ask]:
    server = QuietThreadingHTTPServer(("127.0.0.1", 0), make_handler(board))
    threading.Thread(target=server.serve_forever, args=(SERVER_POLL_S,), daemon=True).start()
    port = server.server_address[1]

    def send(path: str, *headers: tuple[str, str], method: str = "GET",
             hosts: tuple[str, ...] | None = None) -> tuple[int, bytes, dict[str, str]]:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=WAIT_S)
        connection.putrequest(method, path, skip_host=True)
        for host in (f"127.0.0.1:{port}",) if hosts is None else hosts:
            connection.putheader("Host", host)
        for header in headers:
            connection.putheader(*header)
        connection.endheaders()
        answer = connection.getresponse()
        body = b"" if answer.getheader("Content-Type") == "text/event-stream" else answer.read()
        found = answer.status, body, dict(answer.getheaders())
        connection.close()
        return found

    yield send
    server.shutdown()
    server.server_close()


def allow(root: Path, text: str) -> None:
    folder = root / "config" / "pptx-agent-maker"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "allowed-hosts.txt").write_text(text, encoding="utf-8")


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.1:18096", "localhost:9000", "LOCALHOST.", "[::1]:18096"])
def test_a_loopback_name_is_answered(ask: Ask, host: str) -> None:
    assert ask("/api/projects", hosts=(host,))[0] == 200


@pytest.mark.parametrize("host", [
    "rebound.example", "rebound.example:18096", "localhost.rebound.example", "127.0.0.1.rebound.example",
    "0.0.0.0:18096", "10.0.0.5", "user@localhost", "localhost/else", "localhost:port", "localhost:99999", "",
])
def test_another_name_is_refused(ask: Ask, host: str) -> None:
    assert ask("/api/projects", hosts=(host,))[0] == 403


@pytest.mark.parametrize("hosts", [(), ("localhost", "rebound.example")])
def test_a_request_without_one_name_is_refused(ask: Ask, hosts: tuple[str, ...]) -> None:
    assert ask("/api/projects", hosts=hosts)[0] == 403


@pytest.mark.parametrize("path", [
    "/", "/app.js", "/app.css", "/api/meta", "/api/decks", "/api/decks/alpha", "/api/opened", "/events",
    "/api/pages/alpha/0000000000000000.jpg", "/api/thumbs/alpha/0000000000000000.jpg", "/no-such-path",
])
def test_the_name_is_checked_on_every_path(ask: Ask, path: str) -> None:
    status, body, _ = ask(path, hosts=("rebound.example",))
    assert status == 403
    assert b"alpha" not in body


def test_a_refused_request_does_not_start_drawing(ask: Ask, board: st.Switchboard) -> None:
    ask("/api/decks?p=beta", hosts=("rebound.example",))
    assert "beta" not in board._drawn


def test_one_line_lets_a_front_end_through_without_a_restart(ask: Ask, tmp_path: Path) -> None:
    assert ask("/api/projects", hosts=(FRONT,))[0] == 403
    allow(tmp_path / "root", f"{FRONT}\n")
    for host in (FRONT, f"{FRONT}:8443", FRONT.upper() + "."):
        assert ask("/api/projects", hosts=(host,))[0] == 200
    assert ask("/api/projects", hosts=(f"other.{FRONT}",))[0] == 403
    allow(tmp_path / "root", "")
    assert ask("/api/projects", hosts=(FRONT,))[0] == 403


def test_the_list_takes_comments_and_no_wildcard(ask: Ask, tmp_path: Path) -> None:
    allow(tmp_path / "root", f"# in front of the preview\n\n  {FRONT}  # the proxy\n*\n*.example.test\n")
    assert ask("/api/projects", hosts=(FRONT,))[0] == 200
    assert ask("/api/projects", hosts=("other.example.test",))[0] == 403


def test_without_a_root_the_list_is_under_the_home_config(
    ask: Ask, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AGENT_PLATFORM_ROOT")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    folder = tmp_path / "home" / ".config" / "pptx-agent-maker"
    folder.mkdir(parents=True)
    (folder / "allowed-hosts.txt").write_text(FRONT, encoding="utf-8")
    assert ask("/api/projects", hosts=(FRONT,))[0] == 200


def test_an_unreadable_list_allows_loopback_only(ask: Ask, tmp_path: Path) -> None:
    allow(tmp_path / "root", "")
    (tmp_path / "root" / "config" / "pptx-agent-maker" / "allowed-hosts.txt").write_bytes(b"\xff\xfe\x00")
    assert ask("/api/projects", hosts=(FRONT,))[0] == 403
    assert ask("/api/projects")[0] == 200


def test_a_relative_root_allows_loopback_only(ask: Ask, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_PLATFORM_ROOT", "relative")
    assert ask("/api/projects", hosts=(FRONT,))[0] == 403
    assert ask("/api/projects")[0] == 200


@pytest.mark.parametrize("host, origin", [
    (FRONT, f"https://{FRONT}"), (f"{FRONT}:443", f"https://{FRONT}"),
    (FRONT, f"http://{FRONT}"), (f"{FRONT}:8443", f"https://{FRONT}:8443"),
    ("localhost:18096", "http://localhost:18096"), ("[::1]:18096", "http://[::1]:18096"),
])
def test_the_previews_own_page_may_change_it(ask: Ask, tmp_path: Path, host: str, origin: str) -> None:
    allow(tmp_path / "root", FRONT)
    headers = (("Origin", origin), ("Sec-Fetch-Site", "same-origin"))
    assert ask("/api/projects/select/beta", *headers, method="POST", hosts=(host,))[0] == 202


@pytest.mark.parametrize("origin", [
    "https://elsewhere.example", "null", "", "http://localhost:3000", "http://127.0.0.1:18096",
    "http://localhost", "http://localhost:18096.elsewhere.example", "file://localhost:18096",
])
@pytest.mark.parametrize("method", ["GET", "POST"])
def test_another_origin_is_refused(ask: Ask, method: str, origin: str) -> None:
    path = "/api/projects" if method == "GET" else "/api/projects/select/beta"
    assert ask(path, ("Origin", origin), method=method, hosts=("localhost:18096",))[0] == 403


def test_two_origins_are_refused(ask: Ask) -> None:
    headers = (("Origin", "http://localhost:18096"), ("Origin", "https://elsewhere.example"))
    assert ask("/api/projects", *headers, hosts=("localhost:18096",))[0] == 403


@pytest.mark.parametrize("site", ["cross-site", "same-site"])
def test_a_change_started_by_another_site_is_refused(ask: Ask, site: str) -> None:
    assert ask("/api/refresh", ("Sec-Fetch-Site", site), method="POST")[0] == 403


@pytest.mark.parametrize("site", ["cross-site", "same-site", "none"])
def test_a_link_from_another_site_still_opens_the_page(ask: Ask, site: str) -> None:
    assert ask("/", ("Sec-Fetch-Site", site))[0] == 200


@pytest.mark.parametrize("path", ["/api/refresh", "/api/opened/alpha", "/api/projects/select/beta"])
def test_reading_changes_nothing(ask: Ask, board: st.Switchboard, path: str) -> None:
    status, _, headers = ask(path)
    assert status == 405
    assert headers["Allow"] == "POST"
    assert board.project == "alpha"
    assert board.opened.deck("alpha") is None


def test_a_post_changes_what_a_read_then_shows(ask: Ask) -> None:
    assert ask("/api/opened/alpha", method="POST")[0] == 200
    assert json.loads(ask("/api/opened")[1]) == {"deck": "alpha"}
    assert ask("/api/projects/select/beta", method="POST")[0] == 202
    assert json.loads(ask("/api/projects")[1])["active"] == "beta"


@pytest.mark.parametrize("path", ["/", "/api/projects", "/api/decks", "/api/opened"])
def test_what_only_reads_takes_no_post(ask: Ask, path: str) -> None:
    assert ask(path, method="POST")[0] == 404


def test_repeated_refreshes_become_one_run_and_one_after_it(
    ask: Ask, board: st.Switchboard, monkeypatch: pytest.MonkeyPatch,
) -> None:
    release, started = threading.Event(), threading.Event()
    runs: list[float] = []

    def draw(force: bool = False, rebuild: bool = False) -> None:
        if rebuild:
            runs.append(time.monotonic())
            started.set()
            release.wait(WAIT_S)

    monkeypatch.setattr(board.active, "rescan_and_rerender", draw)
    assert ask("/api/refresh", method="POST")[0] == 202
    assert started.wait(WAIT_S)
    for _ in range(REFRESH_COUNT):
        assert ask("/api/refresh", method="POST")[0] == 202
    assert len(runs) == 1
    release.set()
    deadline = time.monotonic() + WAIT_S
    while len(runs) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    time.sleep(0.2)
    assert len(runs) == 2


def test_a_failed_refresh_does_not_block_the_next(
    ask: Ask, board: st.Switchboard, monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs: list[bool] = []

    def fail(force: bool = False, rebuild: bool = False) -> None:
        if rebuild:
            runs.append(rebuild)
            raise RuntimeError("could not draw")

    monkeypatch.setattr(board.active, "rescan_and_rerender", fail)
    for expected in (1, 2):
        assert ask("/api/refresh", method="POST")[0] == 202
        deadline = time.monotonic() + WAIT_S
        while len(runs) < expected and time.monotonic() < deadline:
            time.sleep(0.01)
        assert len(runs) == expected
