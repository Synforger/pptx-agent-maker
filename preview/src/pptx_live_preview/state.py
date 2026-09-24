"""Watch decks and keep their rendered state.

単一デッキは「デッキが 1 枚だけの集合」として同じ型で扱う。かつては単一用と
フォルダ用に状態・画面・応答・起動が別々にあり、頁差分のような細かい処理が
2 箇所に複製されていた。
"""

from __future__ import annotations

import threading
from collections.abc import Iterable
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

from . import notes as notes_mod
from .cache import DeckCache, cache_root, deck_key, digest
from .render import DEFAULT_DPI, THUMB_DPI, ProfilePool, RenderError, rasterize, to_pdf

# 同時に走らせる soffice の数。変換は 1 本あたり CPU 1 コアと数百 MB を使うので、
# デッキ数ぶん無制限に起動するとフォルダが育ったときにマシンごと詰まる。
MAX_RENDER_WORKERS = 4

# LibreOffice のプロファイル置き場。デッキの絵と同じくプロセスの寿命から切り離す
# (= 使い回さないと 1 本ごとに初期化の分だけ遅い、理由は render.ProfilePool)。
PROFILES = ProfilePool(cache_root() / "_libreoffice", MAX_RENDER_WORKERS)


class DeckState:
    """Render state for one .pptx (mtime-watched, rerendered only on change)."""

    def __init__(self, pptx: Path, dpi: int = DEFAULT_DPI, cache_dir: Path | None = None) -> None:
        self.pptx = pptx
        self.dpi = dpi
        self.cache = DeckCache(cache_dir or (cache_root() / deck_key(pptx)))
        self.error: str | None = None
        self.last_ms = 0
        self.notes: list[str] = []
        # 通知用の単調増加カウンタ。キャッシュの版とは別物で、こちらは「画面を
        # 描き直す必要がある変化が起きた」ことだけを表す。
        self.version = 0
        self._last_mtime = 0.0
        self._pending_mtime: float | None = None
        self.cond = threading.Condition()
        # 前回の実行が焼いた絵はキャッシュに残っている。起動直後から見えるように
        # ここで拾っておく (= 再起動のたびに全頁を焼き直して待つ、が消える)。
        if self.cache.current is not None:
            self.notes = notes_mod.extract(pptx)

    @property
    def slides(self) -> int:
        cur = self.cache.current
        return len(cur.pages) if cur else 0

    def rerender_if_stale(self, force: bool = False, rebuild: bool = False) -> bool:
        """Rerender iff the file settled at a new mtime (or force=True).

        書き込み途中のデッキを掴まないよう、新しい mtime を 1 度見ただけでは描かず、
        次の巡回でも同じ値なら「書き終わった」とみなして描く。ビルダーが数十 MB の
        zip を書いている最中に読むと、壊れた入力で render error が出て
        次の巡回まで表示が化ける。

        force は落ち着き待ちを飛ばすだけ (= 起動時と手動)。キャッシュに同じ中身の
        絵があれば描き直さない。rebuild だけがキャッシュを無視して焼き直す。
        """
        try:
            mtime = self.pptx.stat().st_mtime
        except FileNotFoundError:
            return False
        if not force:
            if mtime == self._last_mtime:
                self._pending_mtime = None
                return False
            if mtime != self._pending_mtime:
                self._pending_mtime = mtime  # 書き込み中かもしれない、次の巡回で確かめる
                return False
        self._last_mtime = mtime
        self._pending_mtime = None

        start = time.monotonic()
        changed = self._render_once(rebuild)
        self.last_ms = int((time.monotonic() - start) * 1000)
        if changed:
            with self.cond:
                self.version += 1
                self.cond.notify_all()
        return changed

    def _render_once(self, rebuild: bool) -> bool:
        """Return True when something the browser can see actually changed."""
        try:
            # 解像度も判定材料に混ぜる。デッキが同じでも焼く細かさを変えたら
            # 焼き直さないと、キャッシュに古い粗さの絵が残ったままになる。
            source = f"{digest(self.pptx.read_bytes())}@{self.dpi}/{THUMB_DPI}"
        except OSError as exc:
            return self._fail(f"cannot read deck: {exc}")

        # 中身が前回と同じなら、最も重い LibreOffice の変換ごと飛ばす。更新時刻
        # だけが動く吐き直しと、プロセスの再起動が、どちらもここで止まる。
        if not rebuild and self.cache.matches_source(source):
            return self._clear_error()

        with TemporaryDirectory(prefix="pptx-live-work-") as tmp:
            work = Path(tmp)
            try:
                with PROFILES.lease() as profile:
                    pdf = to_pdf(self.pptx, work, profile)
                raster = rasterize(pdf, work, self.dpi)
            except RenderError as exc:
                return self._fail(str(exc))
            self.cache.adopt(source, raster.pages, raster.thumbs)
        self.notes = notes_mod.extract(self.pptx)
        self.error = None
        return True

    def _fail(self, message: str) -> bool:
        had = self.error
        self.error = message
        return had != message  # 同じ失敗の繰り返しでは画面を叩き起こさない

    def _clear_error(self) -> bool:
        if self.error is None:
            return False
        self.error = None
        return True

    def summary(self) -> dict:
        """Light payload for the deck list (no per-page data)."""
        cur = self.cache.current
        return {
            "name": self.pptx.stem,
            "slides": self.slides,
            "error": self.error,
            "version": self.version,
            "last_ms": self.last_ms,
            "last_rendered_at": cur.at if cur else 0.0,
        }

    def detail(self) -> dict:
        """Full payload for the deck being viewed."""
        cur = self.cache.current
        pages = list(cur.pages) if cur else []
        return {
            **self.summary(),
            "pages": pages,
            "notes": (self.notes + [""] * len(pages))[:len(pages)],
        }


class DeckSet:
    """One or many decks behind a single watch loop and a single event stream.

    Single lock guards deck add/remove/rerender so the watcher thread and the
    HTTP handlers never see a half-updated dict. `version` bumps on any deck-list
    change or any deck rerender, so one event stream drives both "a new deck
    appeared" and "the open deck changed".
    """

    def __init__(self, source: Path, dpi: int = DEFAULT_DPI,
                 skip: Iterable[str] = ()) -> None:
        self.source = source
        self.is_folder = source.is_dir()
        self.title = source.name if self.is_folder else source.stem
        self.dpi = dpi
        #: 見張らない stem (= 焼いた成果ではない pptx が folder に在る場合)
        self.skip = frozenset(skip)
        self.lock = threading.Lock()
        self.cond = threading.Condition(self.lock)
        self.decks: dict[str, DeckState] = {}
        self.version = 0
        # 0.5 秒ごとの巡回のたびに pool を作って捨てないよう、1 個を使い回す
        self._pool = ThreadPoolExecutor(max_workers=MAX_RENDER_WORKERS)

    def _discover(self) -> list[Path]:
        if not self.is_folder:
            return [self.source] if self.source.exists() else []
        return sorted(
            p for p in self.source.glob("*.pptx")
            if not p.name.startswith("~$")  # PowerPoint lock file
            and p.stem not in self.skip
        )

    def rescan_and_rerender(self, force: bool = False, rebuild: bool = False) -> None:
        """force skips the settle wait (= startup); rebuild ignores the store (= refresh button)."""
        with self.lock:
            found = self._discover()
            names = {p.stem for p in found}
            for name in list(self.decks):
                if name not in names:
                    del self.decks[name]
                    self._bump_locked()
            for pptx in found:
                if pptx.stem not in self.decks:
                    self.decks[pptx.stem] = DeckState(pptx, self.dpi)
                    self._bump_locked()
            decks = list(self.decks.values())
        # 各デッキの soffice 変換は重い (数十秒/本) 上に無関係な I/O 待ちなので、
        # デッキ間は並列 (GIL は subprocess 待ちでは問題にならない)。ただし同時本数は
        # 抑える (= 1 本あたり CPU 1 コアと数百 MB、無制限だとフォルダが育つと詰まる)。
        list(self._pool.map(lambda deck: self._rerender_one(deck, force, rebuild), decks))

    def _bump_locked(self) -> None:
        """version を進めて待機中の event stream を起こす (= lock 保持中に呼ぶ)。"""
        self.version += 1
        self.cond.notify_all()

    def _rerender_one(self, deck: DeckState, force: bool, rebuild: bool) -> None:
        if deck.rerender_if_stale(force=force, rebuild=rebuild):
            with self.lock:
                self._bump_locked()

    def deck_names(self) -> list[str]:
        with self.lock:
            return sorted(self.decks)

    def deck(self, name: str) -> DeckState | None:
        with self.lock:
            return self.decks.get(name)

    def summaries(self) -> list[dict]:
        with self.lock:
            return [self.decks[n].summary() for n in sorted(self.decks)]


def watch(deckset: DeckSet, interval: float = 0.5) -> None:
    while True:
        deckset.rescan_and_rerender()
        time.sleep(interval)


class Switchboard:
    """Several projects behind one page, one of them looked at.

    画面と server は 1 つの `DeckSet` を相手にする作りなので、ここはその顔をしたまま、
    中身を選んだ案件へ差し替える。描くのは選んだ案件だけ (= 全案件を起動時に焼くと重い)。

    ⚠ **画面への通知は、今の案件の待ち合わせをそのまま使う。**切り替えたら古い方の待ち手を
    起こし、新しい方へ乗り換えさせる (= 起こさないと、次の keep-alive まで画面が変わらない)。
    """

    def __init__(self, projects: dict[str, DeckSet], first: str | None = None) -> None:
        if not projects:
            raise ValueError("no projects to show")
        self._projects = dict(projects)
        self._name = first if first in self._projects else sorted(self._projects)[0]
        self._switches = 0

    def __getattr__(self, name):  # 画面と server が触る残りは、今の案件のもの
        return getattr(self._projects[self._name], name)

    @property
    def active(self) -> DeckSet:
        return self._projects[self._name]

    @property
    def cond(self) -> threading.Condition:
        return self.active.cond

    @property
    def version(self) -> int:
        # 案件を替えたことも「変化」として画面に届ける (= 版が戻ると画面は描き直さない)
        return self._switches * 1_000_000 + self.active.version

    def projects(self) -> list[str]:
        return sorted(self._projects)

    @property
    def project(self) -> str:
        return self._name

    def select(self, name: str) -> None:
        if name not in self._projects:
            raise KeyError(name)
        if name == self._name:
            return
        previous = self.active
        self._name = name
        self._switches += 1
        self.active.rescan_and_rerender(force=True)
        with previous.cond:
            previous.cond.notify_all()
