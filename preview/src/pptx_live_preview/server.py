"""HTTP surface: one handler for both the single-deck and folder cases.

画像の URL は中身の hash そのものなので、同じ URL が別の絵を指すことがない。
版番号を URL に足す仕掛けは不要で、ブラウザの永続キャッシュに預けきれる。
"""

from __future__ import annotations

import json
import re
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .state import DeckSet, Opened

ASSETS = Path(__file__).parent / "assets"

# 画像名はキャッシュが付けた 16 桁の hash に限る (= 経路をまたぐ細工を弾く)
_HASH_RE = re.compile(r"^[0-9a-f]{16}$")

# 変化通知は Condition 経由で即時に飛ぶので、ここは「切れた接続にいつ気付くか」
# だけを決める。短くするとモバイルの無線が一度も休めず、閲覧しているだけで
# 電池と通信を食い続ける。
SSE_PING_SECONDS = 20.0

_CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
}


class QuietThreadingHTTPServer(ThreadingHTTPServer):
    """Drop the traceback spam from clients that vanish mid-request.

    ブラウザのタブを閉じる / モバイルがスリープするだけで event stream の接続は
    切れる。socketserver は本ハンドラに入る前の受信で例外を出すため、ハンドラ側の
    try/except では捕まえられず、正常運用でログがトレースバックで埋まる。
    """

    def handle_error(self, request, client_address):  # noqa: D102
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, BrokenPipeError, ConnectionAbortedError)):
            return
        super().handle_error(request, client_address)


def make_handler(deckset: DeckSet):
    # 最後に開いた物の覚え (= 束ねて見る時は切り替え盤が持ち、1 案件の時はここで持つ)
    opened = getattr(deckset, "opened", None) or Opened()
    board = deckset if hasattr(deckset, "projects") else None

    def resolve(query: dict) -> tuple[DeckSet, str]:
        """The decks this request is about, and the name they are remembered under.

        ⚠ **どの案件を見るかは画面ごと。**server 全体で 1 つにしていた間は、発表用に 1 案件へ
        絞った画面も、別の端末で案件を替えると一緒に替わった (= 発表中の画面に別の会社の
        資料が出る)。画面は問い合わせのたびに `p` で案件を名乗る。無ければ既定の案件。
        """
        if board is None:
            return deckset, str(deckset.source)
        wanted = (query.get("p") or [None])[0]
        name = wanted if wanted in board.projects() else board.project
        return board.get(name), name

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        # ---- plumbing ----------------------------------------------------

        def _send(self, code, ctype, body: bytes, cache: str = "no-store"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, payload, code: int = 200):
            self._send(code, "application/json", json.dumps(payload).encode())

        def _not_found(self):
            self._send(404, "text/plain", b"not found")

        def _asset(self, name: str):
            path = ASSETS / name
            if not path.is_file():
                self._not_found()
                return
            self._send(200, _CONTENT_TYPES.get(path.suffix, "application/octet-stream"),
                       path.read_bytes())

        def _index(self):
            """Serve the page with its stylesheet and script folded in.

            資産を別 file で引かせると、別の住所の下に相乗りで配信されたとき
            (= tailscale serve の /pptx など) 末尾スラッシュ無しで開かれた瞬間に
            親の住所へ取りに行き、隣のサービスに当たって無地の画面になる。
            埋め込んでしまえば住所の形に関係なく必ず揃う。個別の URL は
            開発時に単体で見るために残してある。
            """
            html = (ASSETS / "index.html").read_text(encoding="utf-8")
            for tag, name, wrap in (
                ('<link rel="stylesheet" href="./app.css">', "app.css", "<style>\n%s\n</style>"),
                ('<script src="./app.js"></script>', "app.js", "<script>\n%s\n</script>"),
            ):
                asset = ASSETS / name
                if tag in html and asset.is_file():
                    html = html.replace(tag, wrap % asset.read_text(encoding="utf-8"))
            self._send(200, "text/html; charset=utf-8", html.encode())

        def _image(self, kind: str, deck_name: str, file_name: str):
            page_hash = file_name.removesuffix(".jpg")
            if not _HASH_RE.match(page_hash):
                self._not_found()
                return
            deck = self.ds.deck(urllib.parse.unquote(deck_name))
            if deck is None:
                self._not_found()
                return
            img = (deck.cache.thumb_path(page_hash) if kind == "thumbs"
                   else deck.cache.page_path(page_hash))
            if not img.is_file():
                self._not_found()
                return
            # URL は中身の hash なので、同じ URL の中身は未来永劫変わらない。
            self._send(200, "image/jpeg", img.read_bytes(),
                       cache="public, max-age=31536000, immutable")

        # ---- routing -----------------------------------------------------

        def do_GET(self):  # noqa: N802
            path, _, query = self.path.partition("?")
            self.ds, self.key = resolve(urllib.parse.parse_qs(query))

            if path == "/":
                self._index()
            elif path in ("/app.css", "/app.js"):
                self._asset(path.lstrip("/"))
            elif path == "/api/meta":
                # 束ねて見る時の題は表示名 (= folder 名には会社の名前が入りうる。タブの題にも出る)
                self._json({"title": self.key if board else self.ds.title,
                            "folder": self.ds.is_folder})
            elif path == "/api/decks":
                self._json(self.ds.summaries())
            elif path == "/api/refresh":
                self._refresh()
            elif path == "/api/projects":
                self._projects()
            elif path == "/api/opened":
                self._json({"deck": opened.deck(self.key)})
            elif path.startswith("/api/opened/"):
                self._remember(urllib.parse.unquote(path[len("/api/opened/"):]))
            elif path.startswith("/api/projects/select/"):
                self._select(urllib.parse.unquote(path[len("/api/projects/select/"):]))
            elif path == "/events":
                self._serve_events()
            elif path.startswith("/api/decks/"):
                self._deck_route(path[len("/api/decks/"):])
            elif path.startswith("/api/pages/") or path.startswith("/api/thumbs/"):
                kind = "pages" if path.startswith("/api/pages/") else "thumbs"
                rest = path[len(f"/api/{kind}/"):]
                if "/" not in rest:
                    self._not_found()
                    return
                deck_name, _, file_name = rest.partition("/")
                self._image(kind, deck_name, file_name)
            else:
                self._not_found()

        def _deck_route(self, rest: str):
            parts = [urllib.parse.unquote(p) for p in rest.split("/") if p]
            if not parts:
                self._not_found()
                return
            deck = self.ds.deck(parts[0])
            if deck is None:
                self._not_found()
                return
            if len(parts) == 1:
                self._json(deck.detail())
                return
            self._not_found()

        def _projects(self):
            # 案件を束ねて見ている時だけ在る (= 1 案件の起動では 404、画面は選ぶ欄を出さない)
            if not hasattr(deckset, "projects"):
                self._not_found()
                return
            self._json({"projects": board.projects(), "active": board.project})

        def _select(self, name: str):
            if board is None or name not in board.projects():
                self._not_found()
                return
            # 既定の案件を替えて覚える (= 名乗らずに開いた画面と、次の起動がここから始まる)。
            # 描くのは `get` が裏で始める (= 描けた順に SSE が届く)
            board.select(name)
            board.get(name)
            self._json({"ok": True, "active": name}, code=202)

        def _remember(self, deck: str):
            if self.ds.deck(deck) is None:
                self._not_found()
                return
            opened.remember_deck(self.key, deck)
            self._json({"ok": True})

        def _refresh(self):
            # 手動の再描画だけがキャッシュを無視する (= 中身が同じでも焼き直す)。
            threading.Thread(target=self.ds.rescan_and_rerender,
                             kwargs={"force": True, "rebuild": True}, daemon=True).start()
            self._json({"ok": True}, code=202)

        def _serve_events(self):
            # 変化は Condition の notify で即時に流れる。ループが回るのは
            # 「変化があった」か「keep-alive の時刻が来た」時だけで、待機中は
            # 一切通信しない (= モバイルの無線と電池への配慮)。
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            last = -1
            try:
                while True:
                    with self.ds.cond:
                        if self.ds.version == last:
                            self.ds.cond.wait(timeout=SSE_PING_SECONDS)
                        cur = self.ds.version
                    if cur != last:
                        last = cur
                        self.wfile.write(f"data: {cur}\n\n".encode())
                    else:
                        self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return

    return Handler
