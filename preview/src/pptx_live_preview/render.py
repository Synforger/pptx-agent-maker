"""Render a .pptx into per-slide JPEG images via LibreOffice + pdftoppm.

2 段構え: LibreOffice が pptx を PDF にし、pdftoppm がその PDF を頁ごとの JPEG
にする。

やり直しの要否は呼び手が .pptx の中身の hash で判断する。PDF の hash では
判断できない — LibreOffice は出力に作成日時を埋めるので、同じデッキから作った
PDF でも毎回バイトが変わる (= 実測で確認済み)。
"""

from __future__ import annotations

import os
import queue
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

# 本画像の解像度。13.33 x 7.5 インチのスライドで 200dpi = 2667 x 1500 px になり、
# Retina で幅 1280px に置いたときの物理 2560px をちょうど満たす。110dpi (= 1467px) では
# 引き伸ばしになり、220dpi 以上は等倍を超えるので容量の払い損。
# 焼く時間の差は小さい (= 頁を分けて並列に焼くため)。
DEFAULT_DPI = 200

# 頁一覧に並べる小さい絵の解像度。本画像を CSS で縮めると 100 頁ぶんの原寸を
# 読み込むことになるので、専用に低い解像度でもう一度焼く。PDF は既に手元に
# あるので追加コストはラスタライズ 1 回分だけ。こちらも Retina で潰れないよう
# 本画像と同じ考えで倍にしてある (= 854 x 480 px)。
THUMB_DPI = 64

# 頁を焼く並列度。pdftoppm は 1 プロセスで頁を順に処理するだけなので、頁範囲を
# 分けて同時に走らせると素直に速くなる (= 出力は同一)。
# デッキが同時に何本走っていても合計がこの数を超えないよう、pool は 1 つに集約する。
_RASTER_WORKERS = max(2, min(8, (os.cpu_count() or 4)))
_RASTER_POOL = ThreadPoolExecutor(max_workers=_RASTER_WORKERS)


class RenderError(RuntimeError):
    """Raised when an external render step fails."""


@dataclass(frozen=True)
class Rasterized:
    """Freshly rendered images, still sitting in a scratch directory."""

    pages: list[Path]
    thumbs: list[Path]


def _resolve(name: str, extra: list[str]) -> str:
    found = shutil.which(name)
    if found:
        return found
    for candidate in extra:
        if Path(candidate).exists():
            return candidate
    raise RenderError(
        f"{name} not found on PATH. Install it (LibreOffice for soffice, "
        f"poppler for pdftoppm) and retry."
    )


def soffice_bin() -> str:
    return _resolve(
        "soffice",
        ["/Applications/LibreOffice.app/Contents/MacOS/soffice"],
    )


def pdftoppm_bin() -> str:
    return _resolve("pdftoppm", [])


def pdfinfo_bin() -> str:
    return _resolve("pdfinfo", [])


def page_count(pdf: Path) -> int:
    """How many pages the PDF has, so the work can be split across processes."""
    result = subprocess.run([pdfinfo_bin(), str(pdf)], capture_output=True, text=True)
    if result.returncode != 0:
        raise RenderError(f"pdfinfo failed: {result.stderr.strip()}")
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split()[1])
    raise RenderError("pdfinfo did not report a page count")


class ProfilePool:
    """Hands out LibreOffice user profiles, one per concurrent conversion.

    プロファイルは LibreOffice の設定と環境の下調べ (= 拡張の登録簿、GPU の能力
    判定) を置く場所で、無いと起動できない。作り直すと初期化に数秒かかるため
    使い回す (= 毎回捨てると、1 本ごとに初期化の分だけ遅い)。

    ただし 1 つのプロファイルを 2 つのプロセスが同時に掴むとロックがぶつかるので、
    同時実行数と同じ数だけ用意して貸し出す。GUI の LibreOffice とも別の場所に
    置く (= 普通に開いている裏で描画が走っても衝突しない)。
    """

    def __init__(self, root: Path, size: int) -> None:
        self.root = root
        self._free: queue.Queue[Path] = queue.Queue()
        for i in range(max(1, size)):
            self._free.put(root / f"profile-{i}")

    @contextmanager
    def lease(self):
        profile = self._free.get()
        try:
            profile.parent.mkdir(parents=True, exist_ok=True)
            yield profile
        finally:
            self._free.put(profile)


def to_pdf(pptx: Path, work_dir: Path, profile: Path) -> Path:
    """Convert ``pptx`` to a PDF inside ``work_dir``, using ``profile``."""
    pptx = pptx.resolve()
    if not pptx.exists():
        raise RenderError(f"deck not found: {pptx}")
    work_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            soffice_bin(),
            "--headless",
            "--norestore",
            f"-env:UserInstallation=file://{profile}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(work_dir),
            str(pptx),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RenderError(
            f"soffice failed: {result.stderr.strip() or result.stdout.strip()}"
        )

    pdf = work_dir / f"{pptx.stem}.pdf"
    if not pdf.exists():
        raise RenderError(f"expected pdf not produced: {pdf}")
    return pdf


def _slices(total: int, parts: int) -> list[tuple[int, int]]:
    """Split 1..total into at most `parts` contiguous page ranges."""
    parts = max(1, min(parts, total))
    size, extra = divmod(total, parts)
    out, start = [], 1
    for i in range(parts):
        span = size + (1 if i < extra else 0)
        out.append((start, start + span - 1))
        start += span
    return out


def _run_pdftoppm(pdf: Path, out_dir: Path, dpi: int, prefix: str,
                  first: int | None = None, last: int | None = None) -> None:
    # JPEG でなく PNG だと同じ DPI でもラスタライズが約 5 倍遅く、ファイルも約 2 倍
    # 重い (= 実測)。
    # スライドは表・図が主体で写真ノイズが少ないため q85 でも文字の可読性は劣化なし。
    cmd = [pdftoppm_bin(), "-jpeg", "-jpegopt", "quality=85", "-r", str(dpi)]
    if first is not None:
        cmd += ["-f", str(first), "-l", str(last)]
    cmd += [str(pdf), str(out_dir / prefix)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RenderError(f"pdftoppm failed: {result.stderr.strip()}")


def _rasterize(pdf: Path, out_dir: Path, dpi: int, prefix: str, total: int) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ranges = _slices(total, _RASTER_WORKERS)
    if len(ranges) == 1:
        _run_pdftoppm(pdf, out_dir, dpi, prefix)
    else:
        list(_RASTER_POOL.map(
            lambda r: _run_pdftoppm(pdf, out_dir, dpi, prefix, r[0], r[1]), ranges))
    return sorted(out_dir.glob(f"{prefix}-*.jpg"))


def rasterize(pdf: Path, work_dir: Path, dpi: int = DEFAULT_DPI) -> Rasterized:
    """Rasterise every page twice: full size for reading, small for the page list."""
    total = page_count(pdf)
    if total < 1:
        raise RenderError("the pdf has no pages")
    pages = _rasterize(pdf, work_dir / "full", dpi, "page", total)
    thumbs = _rasterize(pdf, work_dir / "small", THUMB_DPI, "thumb", total)
    if not pages:
        raise RenderError("pdftoppm produced no pages")
    return Rasterized(pages=pages, thumbs=thumbs)
