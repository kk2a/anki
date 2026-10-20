# 個人学習用Ankiデッキ集

複数のテーマを、テーマごとに独立したデッキとして管理するプロジェクトです。漢検準一級など漢字関連のデッキは保留し、現在は暦と国名・国旗・首都から整備しています。

## 構成

- `decks/<テーマ>/`: テーマごとの設定、データ、出典、生成物
- `scripts/`: 複数テーマで使う共通ビルダー、検証、取得スクリプト
- `decks/calendar/`: 和風月名・二十四節気・干支。項目ごとに独立したapkgを生成します
- `decks/countries/`: 日本を含む196か国の国名・国旗・首都。3種類のapkgを生成します
- `decks/kitauji/`: 響け！ユーフォニアム関連の北宇治高校吹奏楽部デッキ

元データと出典はGitで管理し、`.apkg`と取得画像など再生成できるファイルはGitで管理しません。国旗画像は取得スクリプトで `decks/countries/assets/flags/` に用意します。

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

国データと国旗画像を取得し、3種類のデッキを生成します。

```bash
uv sync
uv run python scripts/fetch_countries.py
uv run python scripts/build_topic_deck.py decks/countries/country-name
uv run python scripts/build_topic_deck.py decks/countries/country-flag
uv run python scripts/build_topic_deck.py decks/countries/capital
uv run python scripts/validate_topic.py decks/countries/country-name
uv run python scripts/validate_topic.py decks/countries/country-flag
uv run python scripts/validate_topic.py decks/countries/capital
```

- `country-name.apkg`: 首都から国名を答えるカードと、国名から首都を答えるカード
- `country-flag.apkg`: 国旗から国名を答えるカード
- `country-capital.apkg`: 国名から首都を答えるカードと、首都から国名を答えるカード

国名と首都名は日本語で収録します。国旗は `flag-icons` のSVGを取得し、生成したapkgに同梱します。

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
