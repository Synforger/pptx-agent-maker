"""A page that names a project is answered with that project, or with nothing and why.

pytest runs it against a real server. The decks are never drawn.
"""

from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pptx_live_preview import server as served
from pptx_live_preview import state as st

WAIT_S = 5.0
SHORT_S = 0.05


@pytest.fixture
def names() -> list[str]:
    return ["alpha", "beta"]


@pytest.fixture
def port(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, names: list[str]) -> Iterator[int]:
    monkeypatch.setattr(st.DeckSet, "rescan_and_rerender", lambda self, force=False, rebuild=False: None)
    monkeypatch.setattr(st.Switchboard, "REDISCOVER_SECONDS", 0.0)
    monkeypatch.setattr(served, "SSE_PING_SECONDS", SHORT_S)
    for name in ("alpha", "beta", "gamma"):
        (tmp_path / name).mkdir()
    projects = {}
    for name in names:
        projects[name] = st.DeckSet(tmp_path / name)
        projects[name].decks[name] = st.DeckState(tmp_path / name / f"{name}.pptx")
    board = st.Switchboard(projects, "alpha" if names else None, waiting=lambda: "no projects here yet",
                           discover=lambda: {name: (tmp_path / name, ()) for name in names})
    server = served.QuietThreadingHTTPServer(("127.0.0.1", 0), served.make_handler(board))
    threading.Thread(target=server.serve_forever, args=(0.02,), daemon=True).start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


def read(port: int, path: str) -> Any:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=WAIT_S)
    connection.request("GET", path)
    found = json.loads(connection.getresponse().read())
    connection.close()
    return found


@pytest.mark.parametrize("query", ["p=gamma", "p=", "p=Alpha", "p=alpha%20"])
def test_a_name_not_listed_gets_an_empty_page_and_the_reason(port: int, query: str) -> None:
    assert read(port, f"/api/decks?{query}") == []
    meta = read(port, f"/api/meta?{query}")
    assert "not listed" in meta["problem"]
    assert meta["title"] == st.Nothing.TITLE
    assert read(port, f"/api/opened?{query}") == {"deck": None}


def test_a_listed_name_gets_that_project(port: int) -> None:
    assert [deck["name"] for deck in read(port, "/api/decks?p=beta")] == ["beta"]
    assert read(port, "/api/meta?p=beta")["title"] == "beta"


def test_no_name_gets_the_default_project(port: int) -> None:
    assert [deck["name"] for deck in read(port, "/api/decks")] == ["alpha"]
    assert read(port, "/api/meta")["title"] == "alpha"


def test_a_name_that_leaves_the_list_empties_its_page(port: int, names: list[str]) -> None:
    names.remove("beta")
    assert read(port, "/api/decks?p=beta") == []


@pytest.mark.parametrize("names", [[]])
def test_with_no_projects_the_reason_is_the_machines(port: int) -> None:
    assert read(port, "/api/meta?p=alpha")["problem"] == "no projects here yet"


def test_the_stream_of_an_unlisted_name_ends_once_it_is_listed(port: int, names: list[str]) -> None:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=WAIT_S)
    connection.request("GET", "/events?p=gamma")
    stream = connection.getresponse()
    assert stream.readline().startswith(b"data:")
    names.append("gamma")
    ended = threading.Event()

    def drain() -> None:
        stream.read()
        ended.set()

    threading.Thread(target=drain, daemon=True).start()
    assert ended.wait(WAIT_S / 2), "the page would keep waiting on an empty screen"
    assert "not listed" not in (read(port, "/api/meta?p=gamma")["problem"] or "")
