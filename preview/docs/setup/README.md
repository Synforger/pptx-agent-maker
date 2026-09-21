# Setup

## 前提環境

| 必要なもの | 用途 | 確認 |
|---|---|---|
| Python 3.10 以上 | 本体 | `python3 --version` |
| LibreOffice (`soffice`) | pptx → PDF 変換 | `soffice --version` |
| poppler (`pdftoppm`) | PDF → 画像 | `pdftoppm -v` |

macOS で LibreOffice を `.app` として入れた場合、 `soffice` が PATH に無くても
`/Applications/LibreOffice.app/Contents/MacOS/soffice` を自動で拾う。 どちらも見つからない
ときは、 何を入れればよいかをエラーメッセージが指す。

`task doctor` で toolchain floor (= `.tooling/versions.yaml` が真値) の充足を診断できる。

## インストール

```bash
git clone <このリポジトリ>
cd pptx-live-preview
task setup     # .venv 作成 + 本体と dev extras を install
```

## 初回起動

```bash
.venv/bin/pptx-live-preview path/to/deck.pptx
```

URL が表示され、 既定ではブラウザが開く (= `--no-open` で抑止)。 初回はデッキ 1 本あたり
数秒〜数十秒かかる (= 頁数と図の量に比例)。 2 回目以降は、 デッキの中身が変わっていなければ
描画を丸ごと飛ばして即座に立ち上がる。

フォルダを渡すと中の `.pptx` を全部拾い、 左上のメニューで切り替えられる (= `Ctrl` + `←` / `→`
でも移動)。 後からフォルダに足したデッキも再起動なしで現れる。

## 別の住所の下で配信する

リバースプロキシで `/pptx` のようなサブパスに相乗りさせても動く。 画面は開かれている
URL から自分の基準位置を割り出し、 見た目と動きの定義は HTML に埋め込んで返すので、
末尾のスラッシュが有っても無くても壊れない。

```bash
# 例: tailscale serve でサブパスに載せる
tailscale serve --bg --set-path /pptx http://127.0.0.1:18096
```

## 描画結果の置き場

焼いた頁は `~/.cache/pptx-live-preview/<デッキ名>-<hash>/` に貯まる (= `XDG_CACHE_HOME` を
設定していればその配下)。 デッキごとに 20 世代まで保持し、 どの世代からも参照されなくなった
絵は自動で消える。 手で消しても次の描画で作り直されるだけで、 壊れることはない。

## アンインストール

`.venv/` を消せば入れたものは消える。 描画結果を含めて消すなら
`rm -rf ~/.cache/pptx-live-preview` も実行する。 常駐させていた場合は先に service 定義を外す
(= [Troubleshooting](../troubleshooting/) 参照)。
