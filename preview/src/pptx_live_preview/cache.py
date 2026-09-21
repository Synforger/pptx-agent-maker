"""Content-addressed store for one deck's rendered pages.

絵をその中身の hash で名付けて貯め、「何頁目がどの絵か」の一覧だけを別に持つ。
ここから 2 つが同時に落ちてくる:

* 再起動しても焼き直さない (= 元の .pptx が同じなら前回の一覧をそのまま使う)
* URL が中身と 1 対 1 になる (= 版番号を URL に足す小細工が要らず、
  ブラウザの永続キャッシュが常に正しい)

置き場は一時フォルダではなくユーザーのキャッシュ配下。プロセスの寿命と
絵の寿命を切り離すのがこの構造の要点で、一時フォルダに戻すと上の 2 つが消える。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path


def digest(data: bytes) -> str:
    """Short content hash used for both file names and cache-busting URLs."""
    return hashlib.sha256(data).hexdigest()[:16]


def deck_key(pptx: Path) -> str:
    """Stable per-deck folder name: readable stem plus a hash of the full path.

    stem だけだと別フォルダの同名デッキが同じ置き場を共有してしまう。
    hash だけだと中を覗いたときにどのデッキか分からない。
    """
    stem = "".join(c if c.isalnum() or c in "-_" else "-" for c in pptx.stem)[:40]
    return f"{stem}-{hashlib.sha256(str(pptx).encode()).hexdigest()[:12]}"


def cache_root() -> Path:
    """Base cache directory, honouring XDG_CACHE_HOME when set."""
    base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base else Path.home() / ".cache"
    return root / "pptx-live-preview"


@dataclass(frozen=True)
class Render:
    """What is currently on hand for a deck."""

    at: float
    source: str  # 元 .pptx の hash (= これが同じなら焼き直す必要がない)
    pages: tuple[str, ...]  # 頁順の画像 hash

    def to_json(self) -> dict:
        return {"at": self.at, "source": self.source, "pages": list(self.pages)}

    @staticmethod
    def from_json(d: dict) -> "Render":
        return Render(at=d["at"], source=d["source"], pages=tuple(d["pages"]))


class DeckCache:
    """Per-deck page store: the images, plus which page is which."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.pages_dir = root / "pages"
        self.thumbs_dir = root / "thumbs"
        self.index_path = root / "render.json"
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        self.thumbs_dir.mkdir(parents=True, exist_ok=True)
        self.current: Render | None = self._load()

    def _load(self) -> Render | None:
        try:
            raw = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        try:
            return Render.from_json(raw)
        except (KeyError, TypeError):
            return None  # 壊れた索引は捨てて焼き直す (= 実害は再描画 1 回分)

    def _save(self) -> None:
        tmp = self.index_path.with_suffix(".json.tmp")
        payload = self.current.to_json() if self.current else {}
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, self.index_path)  # 索引の書き換えは原子的に (= 途中を読ませない)

    def matches_source(self, source: str) -> bool:
        """True when what is on hand already came from this exact .pptx."""
        return self.current is not None and self.current.source == source

    def page_path(self, page_hash: str) -> Path:
        return self.pages_dir / f"{page_hash}.jpg"

    def thumb_path(self, page_hash: str) -> Path:
        return self.thumbs_dir / f"{page_hash}.jpg"

    def adopt(self, source: str, pages: list[Path], thumbs: list[Path]) -> Render:
        """Move freshly rendered images into the store and record what they are.

        絵は hash 名で置くので、同じ中身が既にあれば捨てて既存を使う。頁が
        入れ替わっただけの更新では 1 枚も増えない。
        """
        hashes: list[str] = []
        for i, page in enumerate(pages):
            h = digest(page.read_bytes())
            hashes.append(h)
            dest = self.page_path(h)
            if not dest.exists():
                shutil.move(str(page), dest)
            if i < len(thumbs):
                tdest = self.thumb_path(h)
                if not tdest.exists():
                    shutil.move(str(thumbs[i]), tdest)

        self.current = Render(at=time.time(), source=source, pages=tuple(hashes))
        self._save()
        self._prune()
        return self.current

    def _prune(self) -> None:
        """Drop images the current render does not refer to."""
        live = set(self.current.pages) if self.current else set()
        for folder in (self.pages_dir, self.thumbs_dir):
            for img in folder.glob("*.jpg"):
                if img.stem not in live:
                    img.unlink(missing_ok=True)
