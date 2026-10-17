# 国語（漢字以外）

漢検準一級の漢字問題はいったん保留し、漢字の読み書きそのものを主目的にしない国語デッキを管理する。

## 作成順

情報を整理しやすく、答えがぶれにくいものから作成する。

1. `keigo-basic`: 敬語の種類、働き、基本表現
2. `grammar-parts`: 品詞と文中での働き
3. `grammar-conjugation`: 動詞・形容詞・形容動詞の活用
4. `onomatopoeia`: 擬音語・擬態語と意味、用例
5. `idioms`: 慣用句と意味、用例
6. `proverbs`: ことわざと意味、用例

現代文読解、文章表現、類義語・対義語は、出典とカード形式を決めてから追加する。

## 漢字の扱い

漢字を答えさせる問題、漢字の書き分け、熟語の構成、漢字の読みを主目的にする問題は、この範囲に含めない。例文や慣用句の表記に漢字が含まれることはあるが、出題の中心は敬語・文法・意味・用法とする。

## ファイル構成

各項目を独立したデッキとして管理し、通常方向と逆方向のカードを生成する。

```text
decks/japanese-language/
├── README.md
├── keigo-basic/
│   ├── deck.toml
│   └── data/
├── grammar-parts/
│   ├── deck.toml
│   └── data/
├── grammar-conjugation/
│   ├── deck.toml
│   └── data/
├── onomatopoeia/
│   ├── deck.toml
│   └── data/
├── idioms/
│   ├── deck.toml
│   └── data/
└── proverbs/
    ├── deck.toml
    └── data/
```

各デッキの `data/` には原則として `facts.tsv` と `sources.tsv` を置く。画像や音声などの取得データは、国旗と同じくスクリプトで用意し、Gitでは管理しない。
