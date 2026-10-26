# 個人学習用Ankiデッキ集

複数のテーマを、テーマごとに独立したデッキとして管理するプロジェクトです。漢検準一級など漢字関連のデッキは保留し、現在は暦、国名・国旗・首都、世界遺産、自然物のビジュアルデッキを整備しています。

## 構成

- `decks/<テーマ>/`: テーマごとの設定、データ、出典、生成物
- `scripts/`: 複数テーマで使う共通ビルダー、検証、取得スクリプト
- `decks/calendar/`: 和風月名・二十四節気・干支。項目ごとに独立したapkgを生成します
- `decks/countries/`: 日本を含む196か国の国名・国旗・首都。全部入り3種類と、地域別スターター21種類のapkgを生成します
- `decks/world-heritage/`: UNESCO公式データを使った世界遺産1,273件。通常方向と逆方向を別々のapkgにします
- `decks/fish/`, `decks/plants/`, `decks/flowers/`, `decks/mushrooms/`: 各15件のビジュアルデッキ。画像の出典とライセンスをTSVで管理します
- `decks/kitauji/`: 響け！ユーフォニアム関連の北宇治高校吹奏楽部デッキ

元データと出典はGitで管理し、`.apkg`と取得画像など再生成できるファイルはGitで管理しません。国旗画像は取得スクリプトで `decks/countries/assets/flags/` に用意します。

## 世界遺産・自然物デッキ

UNESCOのWorld Heritage Listから世界遺産データを取得し、名称問題と登録情報問題を別デッキとして生成します。魚介・植物・花・きのこは、Wikimedia Commonsの画像を使ったビジュアル問題です。

```bash
uv run python scripts/build_all.py \
  --refresh-world-heritage \
  --refresh-visual-taxa \
  --refresh-visual-assets
```

ライセンスと外部データの利用条件は [LICENSES.md](LICENSES.md) にまとめています。外部データと画像を含むAPKGは、デッキごとの出典・ライセンス条件を確認して利用してください。

## 暦デッキ

```bash
uv sync
uv run python scripts/build_topic_deck.py decks/calendar/japanese-months
uv run python scripts/validate_topic.py decks/calendar/japanese-months
uv run python scripts/build_topic_deck.py decks/calendar/sekki
uv run python scripts/validate_topic.py decks/calendar/sekki
uv run python scripts/build_topic_deck.py decks/calendar/eto
uv run python scripts/validate_topic.py decks/calendar/eto
```

`decks/calendar/japanese-months/`、`decks/calendar/sekki/`、`decks/calendar/eto/` に、それぞれの `deck.toml` があります。各デッキは通常方向と逆方向のカードを生成します。

## 国名・国旗・首都デッキ

国名・国旗・首都それぞれを、一つのAPKGにまとめています。各パックには全部入り196枚と、7地域に分かれたスターター計196枚が入っています。

| 種類 | APKG | 収録内容 |
| --- | --- | --- |
| 国名 | `country-name-pack.apkg` | 全部入り＋地域別スターター |
| 国旗 | `country-flag-pack.apkg` | 全部入り＋地域別スターター |
| 首都 | `country-capital-pack.apkg` | 全部入り＋地域別スターター |

必要な種類のパックを一度取り込むだけで、全部入りと地域別スターターの両方が入ります。各パックは8デッキ、392枚です。全部入りとスターターは別々のカードなので、学習状況も独立しています。画像もAPKGに同梱します。

パックの再生成は `uv run python scripts/build_country_bundles.py` で実行します。`decks/countries/build/` に出力され、一括再生成スクリプトでも生成します。全部入りや地域別の個別APKGと同じデッキID・ノートIDを使うため、以前の個別版やスターター版を取り込み済みでも、パックの取り込みで同じカードは追加されません。

国名・国旗・首都は、それぞれ一方向の問題です。

- `country-name.apkg`: 首都から国名を答える196枚
- `country-flag.apkg`: 国旗から国名を答える196枚
- `country-capital.apkg`: 国名から首都を答える196枚

国旗は [Sekainokokki.jp](https://www.sekainokokki.jp/organization/un#toc-members) が案内する公式CDNから、元の縦横比のSVGを取得してAPKGに同梱します。画像は同サイトの利用規約でパブリックドメインとされています。

スターターは、国名・国旗・首都それぞれを7地域に分けた独立デッキです。[外務省の地域別インデックス](https://www.mofa.go.jp/mofaj/area/index.html) に基づき、国ごとの分類・出典URL・確認日を `decks/countries/data/country-regions.tsv` に記録しています。日本は外国一覧に掲載されないため、アジアとして補完しています。中央アジア諸国は外務省の「欧州（NIS諸国を含む）」に従います。地域分類の出典はスクリプトとTSVで管理し、カード裏面には表示しません。

| 地域 | 各種類のカード数 | 地域の識別子 |
| --- | ---: | --- |
| アジア | 22 | `asia` |
| 中東 | 15 | `middle-east` |
| 欧州 | 54 | `europe` |
| アフリカ | 54 | `africa` |
| 北米 | 2 | `north-america` |
| 中南米 | 33 | `latin-america` |
| 大洋州 | 16 | `oceania` |

国名は `decks/countries/starter-names/`、国旗は `starter-flags/`、首都は `starter-capitals/` の各地域ディレクトリで管理します。それぞれの `build/` に `country-name-<地域>.apkg`、`country-flag-<地域>.apkg`、`country-capital-<地域>.apkg` を出力します。

全部入りとスターターは元データを共有し、スターターのノートIDには `starter-` を付けて区別します。両方を取り込むと、別々のカードとして学習できます。同じスターターを再インポートした場合は既存ノートを更新します。

```bash
uv sync
uv run python scripts/fetch_countries.py
uv run python scripts/generate_country_starters.py
for deck in country-name country-flag capital; do
  uv run python scripts/build_topic_deck.py "decks/countries/$deck"
  uv run python scripts/validate_topic.py "decks/countries/$deck"
done
for kind in starter-names starter-flags starter-capitals; do
  for region in asia middle-east europe africa north-america latin-america oceania; do
    uv run python scripts/build_topic_deck.py "decks/countries/$kind/$region"
    uv run python scripts/validate_topic.py "decks/countries/$kind/$region"
  done
done
```

既存の国名・首都デッキの逆向きカードは、再インポートだけでは残ることがあります。削除する場合は、Ankiのブラウザで対象デッキのカードを開き、「カード」で該当ノートタイプの「逆向き」テンプレートを削除してから新しいAPKGを取り込んでください。「基本」テンプレートとノート本体を残すことで、通常方向の学習履歴を維持できます。

一括再生成は `uv run python scripts/build_all.py` で実行します。地域別の元データもこのスクリプトで再生成します。

## 星座デッキ

国立天文台の一覧をもとに、88星座の名称・学名・略号と主要恒星を収録します。IAUの星図を使ったビジュアル問題も、星座デッキとは別のapkgとして生成します。

```bash
uv run python scripts/fetch_constellations.py
uv run python scripts/build_topic_deck.py decks/constellations/name
uv run python scripts/build_topic_deck.py decks/constellations/main-stars
uv run python scripts/build_topic_deck.py decks/constellations/visual
uv run python scripts/validate_topic.py decks/constellations/name
uv run python scripts/validate_topic.py decks/constellations/main-stars
uv run python scripts/validate_topic.py decks/constellations/visual
```

- `constellation-name.apkg`: 88星座の日本語名と学名・略号
- `main-stars.apkg`: 国立天文台の「おもな恒星」に掲載された27個の恒星
- `constellation-visual.apkg`: 星図を見て星座名を答える問題

星図PNGは取得スクリプトで `decks/constellations/assets/charts/` に用意し、Gitでは管理しません。

## 北宇治高校吹奏楽部デッキ

```bash
uv sync
uv run python decks/kitauji/scripts/fetch_members.py --download-images --all-images
uv run python decks/kitauji/scripts/build_deck.py
uv run python decks/kitauji/scripts/validate_project.py
```

画像は公式サイトから取得するため、初回生成前に取得コマンドを実行します。画像の利用条件は公式サイトの案内に従います。
