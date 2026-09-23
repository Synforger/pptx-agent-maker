---
name: deck
description: Build or change a slide deck with pptx-agent-maker. Use when asked to make, edit, rebuild or review a .pptx deck in a project that has a workspace.toml — declaring pages from the page types, copying from a specimen, importing a page from an earlier deck, checking a built deck, or folding a person's hand edits back in.
---

# Building a deck

**道具は `pptx-agent-maker`、案件はその外の folder。**案件を見つける口は `workspace.toml` 1 枚で、
それ以外に外の path を書かない。

案件の folder の中だけで完結する (= `Taskfile.yml` が道具への口を持つ)。

## 順番

1. **既に在るものを見る** ― `task show` と、案件の `*.toml` / `*.pptx`。
   **同じ役割の頁が過去の回に在れば、複製するか輸入する** (= 作り直さない)
2. **manifest を書く / 直す** ― 並びの真値はここ 1 枚。頁の作り方は 3 つだけ
   (`copy` / `import` / `declare`)
3. **組む** ― `task build -- w1` (= 組んで検査まで)
4. **焼いて見る** ― `task preview`、または pptx を画像にして 1 枚ずつ見る。
   ⚠ **検査が通っても、読みやすさは座標に出ない。**目で見るまで終わりでない
5. **人が直したら取り込む** ― `task review -- w1.pptx` で差分を出し、置換の対を manifest に写す

## 宣言で頁を組む

**型を選ぶ。**`figure` / `figures` / `figure_grid` / `flow` / `cards` / `board` / `agenda` の 7 つ。
⚠ **座標を書く口はどこにも無い。**版面の並びは固定で、書いた帯だけが出る:

```
題 → 条件の帯 → カード → 本体 → 表 → 読み方 → 結論の帯 → 出所
```

型が決めるのは**本体**だけで、カード・表・読み方・要点・キャプションは**どの型にも**添えられる。

```toml
[[pages]]
kind = "declare"
type = "figure"
title = "この頁が何の頁か"
figure = "a.png"          # assets/<この manifest の名前>/ から引く
caption = "図の読み方を 1 行"
conclusion = "持ち帰ってほしい 1 行"
```

## 型に収まらない頁が出たら

**型を足す。**手で図形を置く道は無い (= その口を塞いだのが、この道具の設計そのもの)。
手順 = 道具の `docs/reference/adding-a-type.ja.md`。⚠ **足す前に、付属で足りないかを見る**
(= カード・表・読み方・要点で済むことが多い)。

## 見た目

**`specimen.pptx` 1 枚が持つ。**複製した頁も、型で組んだ頁も、PowerPoint で手で足した頁も
そこから取る。`workspace.toml` の `[theme]` はその上に重ねる例外 (= 書いた色だけ上書き)。

## 組めないもの (= 直そうとせず、形を変える)

| 拒まれるもの | なぜ |
|---|---|
| 図解を 1 つも持たない頁 | 表と文章だけの頁は、読み手が使えない (= `cards` / `board` / `agenda` は骨格なので例外) |
| 表の空セル | 値が無いなら「―」。空欄は埋め忘れと見分けが付かない |
| 10pt を割る文字 | 席から読めない |
| 枠に入らない表 | PowerPoint は表を縮めず枠を伸ばす。頁から溢れる |
| 知らないキー | 綴り違いを捨てると、書いたつもりで頁には無い |
| 手編集された deck への上書き | 人の直しは退避してから、`review` で取り込む |

## やらないこと

- **寸法・色・文字を頁が決めない** ― 同じ役割が毎回同じ形で出ることが、回をまたいだ比較の前提
- **案件のものを道具側に置かない** ― 並べ方・素材・見た目は案件のもの。道具が持つのは型まで
- **1 往復 1 修正を繰り返さない** ― 焼く前に、その頁の文言と中身を決め切る
