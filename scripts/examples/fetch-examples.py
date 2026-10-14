#!/usr/bin/env python3
"""Gather the decks people ranked best, for an agent to look at before it plans a deck.

作法 (= deck skill の craft.md) の「作る前に、場面の近い見本を見る」が指す集まりを、機械ごとに
揃える。repo には入れない (= 他者のデータ)。置き場の既定:

    ~/.local/share/pptx-agent-maker/examples/
    ├── INDEX.md            # 場面ごとの一覧と見方 (= agent が最初に開く 1 枚)
    └── slides-align/       # 人が 1 番に選んだ資料 (= Slides-Align、MIT、研究用)
        └── <場面>/<題材>/1-<道具>/page-NN.jpg と page-NN.md

    python3 scripts/examples/fetch-examples.py [--to DIR]

⚠ **取るのは 1 位だけ。**agent が 1 回に開くのは 2〜3 本で、1 位 (= 題材ごとに 1 本、187 本) で足りる。
⚠ **途中で落ちても続きから。**取れた file は飛ばすので、打ち直せば残りだけを取る。配る側で取れない
file は飛ばして数え、一覧の末尾に出す (= 1 file のために全体を止めない)。
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

DEFAULT = Path.home() / ".local" / "share" / "pptx-agent-maker" / "examples"
ALIGN = "https://huggingface.co/datasets/Yqy6/Slides-Align"
ALIGN_API = "https://huggingface.co/api/datasets/Yqy6/Slides-Align/tree/main/"
#: 頁の絵の長辺 (= agent が読む時に縮める大きさ。原寸の 3000px は容量の払い損)
EDGE = 1600
#: 同時に取りに行く数 (= 配る側に優しく、回線を詰めない)
WORKERS = 8
#: 順位の file の製品名と、配る側の folder 名の違い (= 綴りが揃っていない)
FOLDER = {"Skywork-Banana": "Skyworks-Banana", "Skywork": "Skyworks"}
#: 場面の通り名 (= INDEX の見出し)
SCENES = {
    "work_report": "業務の報告",
    "business_plan": "事業計画",
    "product_launch": "製品の発表",
    "course_preparation": "授業の資料",
    "topic_introduction": "題材の紹介",
    "brand_promote": "ブランドの宣伝",
    "personal_statement": "自己紹介",
}

GUIDE = """\
# 良い資料の見本 (= 作る前に見る)

構成案を書く前に、場面の近い資料を 2〜3 本開いて、**話の並べ方** (= 何枚で、どの順で) と
**1 頁の見え方** (= 主役の図、字の量、余白、目を集める所) を見る。作法の真値は道具の deck skill の
`craft.md` で、ここは「人が 1 番に選んだ実物」を見るための置き場。

## 何が在るか

`slides-align/<場面>/<題材>/1-<道具>/` に、同じ依頼から 9 つの AI 道具が作った資料のうち、人が 1 番に
選んだ物 (= 頁の絵 `page-NN.jpg` と、頁ごとの文字の抜き出し `page-NN.md`)。出所は Slides-Align
(= MIT、研究用と明記)。外に出さない。

## 見方

- **真似するのは、構成・量・配置**。⚠ 1 番の多くは頁を丸ごと画像生成で描いた物で、字も絵に焼き込まれ、
  絵の中の綴りが崩れている所がある ― 絵に字を焼く作り方と飾りは真似しない (= 作法の「概念図と工程図は
  図形で組み、画像に文字を焼かない」)
- 1 頁だけを見ず、資料を頭から順に見る (= `page-NN.md` の題を順に読むと、話の筋だけが追える)
"""


def get(url: str, tries: int = 4) -> bytes:
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise
            time.sleep(2 ** attempt)
        except OSError:
            time.sleep(2 ** attempt)
    raise OSError(f"gave up on {url}")


def tree(path: str) -> list[dict] | None:
    try:
        return json.loads(get(ALIGN_API + urllib.parse.quote(path) + "?recursive=true"))
    except urllib.error.HTTPError:
        return None  # 順位は在るが、配る側に folder が無い


def slug(text: str) -> str:
    return re.sub(r"[^\w.-]+", "_", text).strip("_")[:60]


def title_of(markdown: str) -> str:
    # 抜き出しの書き方が 2 通りある (= `**Title:**` と `**Title**:`)
    found = re.search(r"\*\*Title(?::\*\*|\*\*:)\s*(.+)", markdown)
    return found.group(1).strip() if found else ""


def fetch_deck(entry: dict, to: Path) -> dict:
    """One ranked deck: its pages as JPEG and each page's text, skipping what will not come."""
    folder = f'{FOLDER.get(entry["product"], entry["product"])}/{entry["difficulty"]}/{entry["topic"]}'
    files = tree(folder)
    if files is None:
        return {**entry, "missing": True}
    deck = to / entry["difficulty"] / slug(entry["topic"]) / f'{entry["rank"]}-{entry["product"]}'
    deck.mkdir(parents=True, exist_ok=True)
    titles, failed = [], []
    for kind, suffix in (("slide_images", ".png"), ("slide_contents", ".md")):
        names = sorted(f["path"] for f in files
                       if f["type"] == "file" and f"/{kind}/" in f["path"] and f["path"].endswith(suffix))
        for number, path in enumerate(names, 1):
            url = f"{ALIGN}/resolve/main/{urllib.parse.quote(path)}"
            out = deck / f"page-{number:02d}{'.jpg' if kind == 'slide_images' else '.md'}"
            try:
                if not out.exists() and kind == "slide_images":
                    image = Image.open(io.BytesIO(get(url))).convert("RGB")
                    image.thumbnail((EDGE, EDGE))
                    image.save(out, "JPEG", quality=85)
                elif not out.exists():
                    out.write_bytes(get(url))
            except (OSError, ValueError) as error:  # 取れない 1 file で資料ごと捨てない
                failed.append(f"{path}: {error}")
                continue
            if kind == "slide_contents":
                titles.append(title_of(out.read_text(encoding="utf-8", errors="replace")))
    pages = len(list(deck.glob("page-*.jpg")))
    return {**entry, "path": str(deck.relative_to(to.parent)), "pages": pages, "titles": titles,
            "failed": failed}


def slides_align(root: Path) -> list[dict]:
    to = root / "slides-align"
    to.mkdir(parents=True, exist_ok=True)
    rankings = json.loads(get(f"{ALIGN}/resolve/main/Slides-Align.json"))["results"]
    wanted = [r for r in rankings if r["rank"] == 1]
    done = 0

    def one(entry):
        nonlocal done
        result = fetch_deck(entry, to)
        done += 1
        if done % 20 == 0 or done == len(wanted):
            print(f"  slides-align: {done}/{len(wanted)} decks", flush=True)
        return result

    with ThreadPoolExecutor(WORKERS) as pool:
        decks = list(pool.map(one, wanted))
    (to / "decks.json").write_text(json.dumps(decks, ensure_ascii=False, indent=1), encoding="utf-8")
    return decks


def index(root: Path, decks: list[dict]) -> None:
    lines = [GUIDE, "## 場面ごとの一覧\n"]
    by_scene = defaultdict(list)
    for deck in decks:
        if not deck.get("missing"):
            by_scene[deck["difficulty"]].append(deck)
    for scene, name in SCENES.items():
        rows = sorted(by_scene.get(scene, []), key=lambda d: d["topic"])
        if not rows:
            continue
        lines += [f"### {name} (`{scene}`、{len(rows)} 本)\n", "| 題材 | 道具 | 頁 | 1 頁目の題 | folder |",
                  "|---|---|---|---|---|"]
        for d in rows:
            first = (d["titles"][0] if d["titles"] else "").replace("|", "/")[:70]
            lines.append(f'| {d["topic"]} | {d["product"]} | {d["pages"]} | {first} | `{d["path"]}` |')
        lines.append("")
    missing = sum(1 for d in decks if d.get("missing"))
    failed = sum(len(d.get("failed", [])) for d in decks)
    if missing or failed:
        lines.append(f"配る側に folder が無く取れなかった資料: {missing} 本 / 取れなかった file: {failed} 個 "
                     "(= `slides-align/decks.json` の `failed`。打ち直せば取り直す)\n")
    (root / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--to", type=Path, default=DEFAULT, help=f"where to gather (default {DEFAULT})")
    args = parser.parse_args(argv)
    started = time.monotonic()
    root = args.to.expanduser()
    root.mkdir(parents=True, exist_ok=True)
    print("slides-align: fetching the decks ranked first", flush=True)
    decks = slides_align(root)
    index(root, decks)
    got = [d for d in decks if not d.get("missing")]
    failed = sum(len(d.get("failed", [])) for d in decks)
    print(f"{len(got)} decks ({sum(d['pages'] for d in got)} pages), {len(decks) - len(got)} not offered, "
          f"{failed} files that would not come; index at {root / 'INDEX.md'} "
          f"in {time.monotonic() - started:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
