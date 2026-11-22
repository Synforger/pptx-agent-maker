"""What the preview's answers carry: the reasons it shows, their headers, and who may read what it stores.

pytest runs it. The decks are never drawn.
"""

from __future__ import annotations

import http.client
import json
import stat
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from pptx_live_preview import state as st
from pptx_live_preview.server import QuietThreadingHTTPServer, make_handler

REASONS = [
    ("could not read the project: no workspace.toml at /srv/decks/name one/workspace.toml",
     "could not read the project: no workspace.toml at <path>"),
    ("could not read the project: [Errno 13] Permission denied: '/srv/decks/name, one/workspace.toml'",
     "could not read the project: [Errno 13] Permission denied: '<path>'"),
    ("workspace.toml: `template` points at /srv/name one, which holds no workspace.toml",
     "workspace.toml: `template` points at <path>, which holds no workspace.toml"),
    ("no places file at ~/.config/pptx-agent-maker/preview.toml — write one",
     "no places file at <path> — write one"),
    ("[theme.uses.wide] is written here and in the template at /srv/name one ('wide') — a use is one whole",
     "[theme.uses.wide] is written here and in the template at <path> ('wide') — a use is one whole"),
    ("/srv/a/workspace.toml points at /srv/b, which is inside this repository",
     "<path>, which is inside this repository"),
    ("workspace.toml: 'not_a_key' is not a key of [theme], use and/or type",
     "workspace.toml: 'not_a_key' is not a key of [theme], use and/or type"),
]


@pytest.fixture
def board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> st.Switchboard:
    monkeypatch.setattr(st.DeckSet, "rescan_and_rerender", lambda self, force=False, rebuild=False: None)
    (tmp_path / "alpha").mkdir()
    decks = st.DeckSet(tmp_path / "alpha")
    deck = st.DeckState(tmp_path / "alpha" / "w1.pptx")
    deck.cache.page_path("0" * 16).write_bytes(b"page")
    decks.decks["w1"] = deck
    return st.Switchboard({"alpha": decks}, "alpha")


@pytest.fixture
def port(board: st.Switchboard) -> Iterator[int]:
    server = QuietThreadingHTTPServer(("127.0.0.1", 0), make_handler(board))
    threading.Thread(target=server.serve_forever, args=(0.02,), daemon=True).start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


def answer(port: int, path: str, method: str = "GET") -> tuple[http.client.HTTPResponse, bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request(method, path)
    found = connection.getresponse()
    body = b"" if found.getheader("Content-Type") == "text/event-stream" else found.read()
    connection.close()
    return found, body


@pytest.mark.parametrize("reason, shown", REASONS)
def test_a_reason_is_shown_without_its_paths(port: int, board: st.Switchboard, reason: str, shown: str) -> None:
    board.get("alpha").set_problem(reason, ())
    assert json.loads(answer(port, "/api/meta")[1])["problem"] == shown
    assert json.loads(answer(port, "/api/projects")[1])["problems"] == {"alpha": shown}


@pytest.mark.parametrize("path, method", [
    ("/", "GET"), ("/app.js", "GET"), ("/api/projects", "GET"), ("/events", "GET"), ("/no-such-path", "GET"),
    ("/api/refresh", "GET"), ("/api/projects", "PUT"),
])
def test_every_answer_says_its_type_is_not_to_be_guessed(port: int, path: str, method: str) -> None:
    assert answer(port, path, method)[0].getheader("X-Content-Type-Options") == "nosniff"


def test_a_page_picture_is_kept_by_the_browser_alone(port: int) -> None:
    kept = answer(port, f"/api/pages/w1/{'0' * 16}.jpg")[0].getheader("Cache-Control")
    assert kept == "private, max-age=31536000, immutable"


@pytest.mark.parametrize("makes", ["deck", "opened", "profiles"])
def test_the_store_is_the_owners_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, makes: str) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "store"))
    root = tmp_path / "store" / "pptx-live-preview"
    root.mkdir(parents=True)
    root.chmod(0o755)
    if makes == "deck":
        st.DeckState(tmp_path / "w1.pptx")
    elif makes == "opened":
        st.Opened().remember_project("alpha")
    else:
        with st.ProfilePool(st.PROFILES.root, 1).lease():
            pass
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
