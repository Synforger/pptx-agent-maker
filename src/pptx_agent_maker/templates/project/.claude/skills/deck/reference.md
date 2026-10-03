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
| `roadmap` | `stages` | `align_rows` | 到達点までの段を矢羽根で左から右へ。各段の下にノード |
| `compose` | `rows` | ― | 本体を段とマスで書く。マスに部品を 1 つ (= 上の型も入る)。図が無くても通る |
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
  { heading = "Device", body = "reads the tag", icon = "device.png" },   # アイコンを置く書き方
]
settled = "one queue"                                  # 任意。段の下に置く 1 行
```

- **ノードは 2 通りに書ける** ― `["見出し", "本文"]` か、`{ heading = …, body = …, tone = …, icon = … }`
  (= `body` と `tone` と `icon` は省ける)。**カードも同じ 2 通りで書ける**
- **`icon` は箱の左上に置く絵** (= 素材は図と同じく `assets/` から。文字はその右に寄る)。縦横比は
  保ったまま 1 辺 1.2cm の正方形に収まる。読めるのは PNG / JPEG などの絵で、⚠ **SVG は拒まれる**
  (= 表示する大きさの数倍で PNG に書き出す)。濃い地の箱には明るい色の絵を使う。アイコンは頁の図には
  数えない (= 図の要る頁が、アイコンだけで通ることは無い)
- **`tone` は色の役** ― `box` (= 既定) / `band` / `tint` / `accent` / `good` / `bad`、または案件が
  `[theme.grounds]` で名前を付けた地 (= 下の「見た目」)。色そのものは `[theme.palette]` と `[theme.grounds]` が持つ。⚠ **`good` / `bad` は読み (= 良い / 悪い) を示す物にだけ使う**
  (= 飾りで塗ると、色が意味を持たなくなる)
- **薄い地 (= `box` / `band` / `tint`) の箱は、その地を濃くした色の細い枠を持つ** (= 紙の上で端が
  読める。カードの箱も、線表の棒も同じ)。濃い地の箱に枠は無い。枠の色は地から出るので書かない
- **`align_rows = true`** は、行が意味を持つ頁のため (= 上から 1 番目は誰、2 番目は誰)。
  行の高さはその行で一番高いノードに揃う。書かなければ、ノードは段ごとに自分の高さで積まれる
- ノードの高さは中の文字が実際に折れる行数で決まる (= 書体ごとに測った字幅で数える)
- **文字の大きさ** ― 段の名前 14pt、ノードの見出し 16pt、**本文と `settled` は 12pt**。10pt は
  出所と絵の下の説明だけに使う (= 頁の中身には使わない)

### `roadmap` の書き方

```toml
[[pages]]
kind = "declare"
type = "roadmap"
title = "…"
align_rows = true                                      # 任意。flow と同じ

[[pages.stages]]
name = "Early Nov | 0.4.0"                             # 矢羽根の中の名前 (= 時期と版)
nodes = [
  ["Core", "reads every input"],                       # flow のノードと同じ書き方
  { heading = "Docs", body = "how to start", tone = "tint", icon = "docs.png" },
]

[[pages.stages]]
name = "Jan | 1.0"
goal = true                                            # 任意。最後の段だけ。到達点として強調する
nodes = [ ["Release", "anyone can install it"] ]
```

- **段は左から右へ矢羽根で並ぶ** ― 最初の段は左が平ら、2 段目からは左が切り欠かれ、前の段の先が
  そこへ入る。向きは矢羽根が示すので、段の間に → は置かない
- **`goal = true` は最後の段だけ** (= ほかの段に書くと拒まれる)。到達点の矢羽根は濃い地で、名前が
  一回り大きい (= 16pt。ほかの段は 14pt)。ほかの段の矢羽根は薄い地に枠
- 段のキーは `name` / `nodes` / `goal` だけ (= flow の `settled` は読まない)。段は 2 つ以上
- 長い名前は矢羽根の中で折れ、全部の矢羽根がいちばん高い名前に揃う
- 収まらない頁は縮めずに止まる (= ノードを短くするか、段を 2 頁に分ける)

### `compose` の書き方 (= どの型にも無い組み方)

```toml
[[pages]]
kind = "declare"
type = "compose"
title = "目標と、それを支える 2 本の柱"

[[pages.rows]]                                         # 1 段目: 横幅いっぱいに 1 枚
[[pages.rows.cells]]
card = { heading = "目標", body = "…", tone = "accent" }

[[pages.rows]]                                         # 2 段目: 2 枚を横に
[[pages.rows.cells]]
card = { heading = "0.4.0", body = "…", icon = "core.png" }
[[pages.rows.cells]]
weight = 2                                             # 任意。幅の比 (= 既定 1)
[pages.rows.cells.timeline]                            # 型を 1 マスに丸ごと入れる (= その型の書き方のまま)
periods = ["Nov", "Dec", "Jan"]
[[pages.rows.cells.timeline.lanes]]
name = "Core"
bars = [ { from = 0, to = 2, text = "build" } ]
```

- **段は上から下、マスは左から右**。マスの幅は `weight` の比。マスには部品を 1 つだけ置く:
  `card` (= ノードと同じ 2 通りの書き方) / `figure` (+ `caption`) / `table` / `text` (= 本文の色と大きさの文章) /
  `points` / 型 (= `flow` `roadmap` `timeline` `figures` `figure_grid` `board` `agenda`)。マスに `rows` を書けば入れ子になる
- **高さ** ― カード・表・文章・要点だけの段は**中身の言葉ぶんの高さ**で、同じ段のカードは一番高い物に揃う。
  絵や型の入った段と、段に `weight` を書いた段は、**残りの高さを `weight` の比で分け合う**。分け合う段に置いた
  カードや文章は自分の高さのまま上に寄る。マスの絵は横幅いっぱいで上に寄り、縦が足りなければ縮む
- 座標は書けない (= 割るだけなので、はみ出しも重なりも起きない)。大きさと色は今までどおり決まっている
- 型をマスに入れた時に読むのは、その型のキーだけ (= カード・表・文章は隣のマスに置く)
- 収まらない頁は、どの段のどのマスかを言って止まる (= 縮めない)
- 図が無くても通る (= カードだけの頁も組める)。⚠ だからといって文章だけの頁を作らない

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
tone = "tint"                                          # 任意。このレーンの棒の色の役
bars = [
  { from = 0, to = 1, text = "1.0 complete" },
  { from = 2.5, to = 3, text = "event (if any)", tentative = true },   # 点線の枠
  { from = 3, to = 5, text = "shared work", spans = 2 },   # 任意。このレーンと下のレーンにまたがる
]
marks = [ { at = 1, text = "1.0 release" } ]           # レーンの中の菱形
```

- **位置は期間の番号** ― 0 が最初の期間の頭、`periods` の数が最後の期間の終わり、半期間なら 0.5
- **期間は列ごとに見出しの枠を持つ** (= 表の見出しと同じ地に太字)。列は 1 つおきにごく薄い地で
  塗られ、境に線が立つ (= どの棒がどの期間に掛かるかを、見出しから下へ辿れる)。`phases` の帯は
  その上に、端を期間の枠と揃えて置かれる
- **文字は 12pt か 14pt** ― 頁に収まるなら 14pt、詰まった頁は 12pt (= 1 頁の中では全部同じ大きさ)。
  レーンの名前は 14pt の太字。余った高さは棒の高さに配られ、頁の下に空きを残さない
- ⚠ **`phases` と `milestones` は最初の `[[pages.lanes]]` より上に書く** (= TOML では、
  `[[pages.lanes]]` の下に書いたキーはそのレーンのキーになる。下に書くと拒まれる)
- **レーンの `tone`** は `flow` のノードと同じ語彙 (= `box` / `band` / `tint` / `accent` / `good` / `bad`)。
  書かなければ `box` と `band` の交互。薄い地は 3 つ (= `box` / `band` / `tint`) で、**3 者までを
  色で分けられる**。濃い地 (= `accent` / `good` / `bad`) の上の名前は紙の色になる
- **薄い地の棒は、その地を濃くした色の細い枠を持つ** (= 列の薄い地の上でも棒の端が読める)。
  濃い地の棒に枠は無く、`tentative` の棒は点線の枠のまま
- 同じレーンで時期が重なる棒は、自動で段が分かれる
- **棒は `spans` で下のレーンへまたがれる** (= `spans = 2` はこのレーンと 1 つ下。2 つのレーンに
  分けた仕事の、共通の時期を 1 本で描く)。色は書いたレーンのもの、名前はいつも棒の中。
  ⚠ **またがる棒は、覆うレーンの高さを全部取る** ― その時期 (= 両端を含む) に、覆われるレーンへ
  置いた棒と印は拒まれる。端が接するだけの棒は置ける。覆われるだけのレーンは `bars` を書かなくてよい
- 棒の名前は棒の中。2 行でも収まらない名前は棒の隣へ出る。印の名前も隣 (= 右が先、端では左)
- 文字は全部 pptx の文字 (= PowerPoint で直せる)。棒は名前ごと 1 つの図形
- 収まらない頁は縮めずに止まる (= レーンを減らすか、2 頁に分ける)

## どの型にも添えられるもの

`cards` / `card_columns` / `table` / `note` / `points`

`card_columns` = カードを何枚ずつ並べるか (= 省略すると全部 1 段)。`figure_grid` の `columns` とは別の数。
カードは flow のノードと同じ 2 通りで書ける (= `["見出し", "本文"]` か `{ heading, body, tone, icon }`)。

⚠ **その型が読まないキーは拒まれる** (= 書いたつもりで頁に無い、を作らない)。

## 枠まわり (= どの頁も同じ順)

`kicker` / `title` / `condition` / `conclusion` / `footer` / `replace` / `legend`

`legend = false` は、その頁の凡例を消す (= 下の「意味の名前を付けた地」)。

## 見た目 (= `workspace.toml`)

```toml
[theme]
font = "Arial"

[theme.palette]
ink = "3F3F3F"      # 本文
accent = "0092D1"   # 読みを示す色 (= 表の見出しもここ)
band = "EAF0F8"     # 条件の帯
tint = "E8F3EA"     # 3 つめの薄い地 (= box / band と並べて 3 者を分ける。ここでだけ変えられる)
wash = "F3F3F3"     # 線表の列を 1 つおきに塗る地 (= ここでだけ変えられる)
```

⚠ **ふつうは書かない** ― 見た目は `specimen.pptx` から読まれる。ここに書くのは、テンプレートの
配色がツールの色の使い方と合わないときだけ。差し替えられるのは**書体と色だけ**で、
余白・級数・間隔はツールが持つ。

### 意味の名前を付けた地 (= `[theme.grounds]`)

色で担当や状態を分ける案件は、地の色に**意味の名前**を付けて宣言する:

```toml
[theme.grounds]
"内部向け" = "EAF0F8"     # 日本語の名前は引用符で囲む (= TOML の決まり)
"外部向け" = "FFF4E5"
"共通" = "E8F3EA"
"遅れ" = "8B1E3F"
```

- 頁では `tone = "内部向け"` と書く (= カード・ノード・レーン・`compose` のカード、どこでも)。道具の色の役
  (= `box` / `band` / `tint` / `accent` / `good` / `bad`) もそのまま書ける。同じ名前は宣言できない
- **字の色は地から決まる** ― 本文の色と紙の色のうち、地との差がはっきりする方 (= 濃い地なら紙の色)。
  本文の色の字が乗る薄い地には、地を濃くした色の枠が付く
- **凡例は自動で出る** ― 宣言した名前を使った頁には、本体の真下 (= 表と読み方の上) に色見本と名前が並ぶ。
  並びは宣言の順で、どの頁でも同じ。使っていない名前は出ない。消すのはその頁に `legend = false`
- ⚠ **同じ担当は全部の頁で同じ名前で書く** (= 色を頁ごとに選ばない。色は宣言の 1 か所で決まる)
- 使える名前は `task types` の `tone` の行に出る

## 検査

`build` は最後に 7 つを回す ― 頁の外 / **重なり** / 文字の下限 / 表の空セル /
内部 file 名 / テンプレートの語の残り / 種類の登録が無い部品 (= 開けない pptx の種)。`stale_words` は案件の `workspace.toml` に書く。

```toml
[checks]
stale_words = ["案件名", "第 N 回"]
```
