# 参照

## 案件を建てる

```bash
pptx-agent-maker init <案件のフォルダ> --specimen <テンプレート.pptx or それを置いた folder>
```

⚠ **見た目は建てるときに決める** (= あとから `specimen.pptx` を手で置き換えると、
忘れた回だけ顔が変わる)。folder を渡すと `specimen.pptx` と隣の `workspace.toml`
(= 色の表) を一緒に持ってくる。

## manifest

```toml
specimen = "specimen.pptx"     # 予約名。案件の見た目
out = "w1.pptx"                # マニフェストの隣に焼かれる
assets = "w1"                  # 省略すると、この file の名前が素材の folder 名

[[pages]]
kind = "copy"                  # テンプレートの N 頁目を複製して文言を差し替える
page = 1
replace = [["旧", "新"]]

[[pages]]
kind = "import"                # 前のデッキの N 頁目を、手を入れたまま持ってくる
deck = "w0.pptx"
page = 12
pictures = ["a.png", "b.png"]  # 頁の絵を並び順 (= 上の段から、同じ段は左から) で入れ替える
tables = [[["手法", "値"], ["A", "1"]]]  # 表の中身を並び順で入れ替える (= 行と列の数は元と同じ)

[[pages]]
kind = "declare"               # 型で組む
type = "figure"
title = "…"
```

⚠ **`why` は 1 行の覚え書き** (= 200 字、日付を書くと拒まれる)。改訂の履歴は git log が持つ。

## recipe (= `recipes.toml`)

```toml
[recipes.result]                # 名前は英数字・-・_
type = "figures"                # 必須
title = "{method} の結果"        # {穴} は呼ぶ頁の fill で埋める
footer = "採点表から"
```

頁は `kind = "recipe"` / `recipe = "<名前>"` / `fill = { ... }` と、recipe に無いキーだけを書く。
拒まれるもの = recipe が決めたキーの書き換え / 埋め残した穴 / 使わない fill / 無い recipe 名。

上げる: `task promote -- <名前> w1:5 w2:7` (= 2 頁以上、同じ型の `declare` だけ)。

## 会社のテンプレートへ上げる (= `lift`)

```bash
pptx-agent-maker lift <案件> <テンプレートの folder> \
    [--recipe <名前>]... [--page <deck>:<頁>]... \
    [--keep "<そのまま残す文言>"]... [--replace "<案件の語>=<差し替え前提の語>"]...
```

テンプレートの folder = `specimen.pptx` + `workspace.toml` (+ `recipes.toml`)。頁は `specimen.pptx` の
末尾へ、recipe は `recipes.toml` へ。`init --specimen <folder>` が 3 つとも配る。
文言は `--keep` / `--replace` で扱った物のほか、全部 `<文言 N>` になる (= recipe の文言も同じ。
型の名前は除く)。拒まれるもの = 当たらない `--replace` / グラフや埋め込み file を持つ頁 /
テンプレートに既に在る recipe 名。

## 型 (= 本体に何を置くか)

| 型 | 要るもの | この型だけが読むもの | 本体 |
|---|---|---|---|
| `figure` | `figure` | `caption` | 絵を 1 枚、縦横比のまま最大で |
| `figures` | `figures` | ― | 絵を横に並べる (= 説明は絵ごとに `["a.png", "説明"]`) |
| `figure_grid` | `figures` | `columns` | 絵を格子に並べる |
| `flow` | `stages` | `align_rows` | 段を左から右へ、あいだに → |
| `timeline` | `periods` `lanes` | `phases` `milestones` | 期間を左から右、レーンを上から下。レーンの中に棒と印 |
| `cards` | ― | ― | 札だけの頁 (= 図が要らない骨格) |
| `board` | `table` | ― | 表が主役の頁 (= 同上) |
| `agenda` | `buckets` | `highlight` | 章立て (= 同上。`highlight` = 強調する章の番号) |

### `flow` の書き方

```toml
[[pages]]
kind = "declare"
type = "flow"
title = "…"
align_rows = true                                      # 任意。同じ順番のノードを横に揃える

[[pages.stages]]
name = "Intake"                                        # 段の名前
nodes = [
  ["Triage", "sort by impact"],                        # [見出し, 本文]
  { heading = "No owner", body = "the request waits", tone = "bad" },   # 色の役を付ける書き方
]
settled = "one queue"                                  # 任意。段の下に置く 1 行
```

- **ノードは 2 通りに書ける** ― `["見出し", "本文"]` か、`{ heading = …, body = …, tone = … }`
  (= `body` と `tone` は省ける)
- **`tone` は色の役** ― `box` (= 既定) / `band` / `accent` / `good` / `bad`。色そのものは
  `[theme.palette]` が持つ。⚠ **`good` / `bad` は読み (= 良い / 悪い) を示す物にだけ使う**
  (= 飾りで塗ると、色が意味を持たなくなる)
- **`align_rows = true`** は、行が意味を持つ頁のため (= 上から 1 番目は誰、2 番目は誰)。
  行の高さはその行で一番高いノードに揃う。書かなければ、ノードは段ごとに自分の高さで積まれる
- ノードの高さは中の文字が実際に折れる行数で決まる (= 書体ごとに測った字幅で数える)

### `timeline` の書き方

```toml
[[pages]]
kind = "declare"
type = "timeline"
title = "…"
periods = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]   # 列 = 期間 (左から右)
phases = [                                             # 任意。期間の上に掛ける帯
  { from = 0, to = 3, label = "flexible" },
  { from = 3, to = 6, label = "fixed deadlines" },
]
milestones = [ { at = 5.6, text = "Expo" } ]           # 任意。全レーンを貫く日付

[[pages.lanes]]                                        # レーン = 上から下
name = "Core"
bars = [
  { from = 0, to = 1, text = "1.0 complete" },
  { from = 2.5, to = 3, text = "event (if any)", tentative = true },   # 点線の枠
]
marks = [ { at = 1, text = "1.0 release" } ]           # レーンの中の菱形
```

- **位置は期間の番号** ― 0 が最初の期間の頭、`periods` の数が最後の期間の終わり、半期間なら 0.5
- ⚠ **`phases` と `milestones` は最初の `[[pages.lanes]]` より上に書く** (= TOML では、
  `[[pages.lanes]]` の下に書いたキーはそのレーンのキーになる。下に書くと拒まれる)
- 同じレーンで時期が重なる棒は、自動で段が分かれる
- 棒の名前は棒の中。2 行でも収まらない名前は棒の隣へ出る。印の名前も隣 (= 右が先、端では左)
- 文字は全部 pptx の文字 (= PowerPoint で直せる)。棒は名前ごと 1 つの図形
- 収まらない頁は縮めずに止まる (= レーンを減らすか、2 頁に分ける)

## どの型にも添えられるもの

`cards` / `card_columns` / `table` / `note` / `points`

`card_columns` = カードを何枚ずつ並べるか (= 省略すると全部 1 段)。`figure_grid` の `columns` とは別の数。

⚠ **その型が読まないキーは拒まれる** (= 書いたつもりで頁に無い、を作らない)。

## 枠まわり (= どの頁も同じ順)

`kicker` / `title` / `condition` / `conclusion` / `footer` / `replace`

## 見た目 (= `workspace.toml`)

```toml
[theme]
font = "Arial"

[theme.palette]
ink = "3F3F3F"      # 本文
accent = "0092D1"   # 読みを示す色 (= 表の見出しもここ)
band = "EAF0F8"     # 条件の帯
```

⚠ **ふつうは書かない** ― 見た目は `specimen.pptx` から読まれる。ここに書くのは、テンプレートの
配色がツールの色の使い方と合わないときだけ。差し替えられるのは**書体と色だけ**で、
余白・級数・間隔はツールが持つ。

## 検査

`build` は最後に 7 つを回す ― 頁の外 / **重なり** / 文字の下限 / 表の空セル /
内部 file 名 / テンプレートの語の残り / 種類の登録が無い部品 (= 開けない pptx の種)。`stale_words` は案件の `workspace.toml` に書く。

```toml
[checks]
stale_words = ["案件名", "第 N 回"]
```
