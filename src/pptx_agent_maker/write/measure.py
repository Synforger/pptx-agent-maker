"""Reading an image's proportions — the one thing the layout layer cannot do itself.

頁の層は python-pptx を知らないまま保つ (= 焼く層が唯一それに触る)。絵の縦横比は
file の中にしか無いので、測る口だけをこちら側に置き、型には関数として渡す。
"""

from __future__ import annotations

from pathlib import Path

from pptx.parts.image import Image


def aspect(path: Path | str) -> float:
    """Width over height, straight off the file.

    ⚠ **宣言に縦横比を書かせない。**手で書くと、絵を差し替えた日に古い比が残って
    潰れた絵が焼ける。
    """
    width, height = Image.from_file(str(path)).size
    if not width or not height:
        raise ValueError(f"{path} reports a zero dimension ({width}x{height})")
    return width / height
