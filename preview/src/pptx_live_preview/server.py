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

    def _project_key() -> str:
        # 束ねて見る時は案件の名前、1 案件の時は見ている folder (= 案件ごとに覚える)
        return deckset.project if hasattr(deckset, "projects") else str(deckset.source)

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
            deck = deckset.deck(urllib.parse.unquote(deck_name))
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
            path = self.path.split("?", 1)[0]

            if path == "/":
                self._index()
            elif path in ("/app.css", "/app.js"):
                self._asset(path.lstrip("/"))
            elif path == "/api/meta":
                self._json({"title": deckset.title, "folder": deckset.is_folder})
            elif path == "/api/decks":
                self._json(deckset.summaries())
            elif path == "/api/refresh":
                self._refresh()
            elif path == "/api/projects":
                self._projects()
            elif path == "/api/opened":
                self._json({"deck": opened.deck(_project_key())})
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
            deck = deckset.deck(parts[0])
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
            self._json({"projects": deckset.projects(), "active": deckset.project})

        def _select(self, name: str):
            if not hasattr(deckset, "projects") or name not in deckset.projects():
                self._not_found()
                return
            # 切り替えは返事の前に済ませる (= 画面がすぐ取り直す一覧が、もう新しい案件のもの)。
            # 描くのは時間がかかるので裏で (= 描けた順に SSE が届く)
            deckset.select(name)
            threading.Thread(target=deckset.rescan_and_rerender, kwargs={"force": True},
                             daemon=True).start()
            self._json({"ok": True, "active": name}, code=202)

        def _remember(self, deck: str):
            if deckset.deck(deck) is None:
                self._not_found()
                return
            opened.remember_deck(_project_key(), deck)
            self._json({"ok": True})

        def _refresh(self):
            # 手動の再描画だけがキャッシュを無視する (= 中身が同じでも焼き直す)。
            threading.Thread(target=deckset.rescan_and_rerender,
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
                    with deckset.cond:
                        if deckset.version == last:
                            deckset.cond.wait(timeout=SSE_PING_SECONDS)
                        cur = deckset.version
                    if cur != last:
                        last = cur
                        self.wfile.write(f"data: {cur}\n\n".encode())
                    else:
                        self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return

    return Handler
