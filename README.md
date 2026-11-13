# 個人学習用Ankiデッキ集

複数のテーマを、テーマごとに独立したデッキとして管理するプロジェクトです。漢検準一級など漢字関連のデッキは保留し、現在は暦、国名・国旗・首都、星座・恒星、世界遺産、自然物のビジュアルデッキを整備しています。

## リリースの取得・作成

[最新リリース](https://github.com/kk2a/anki/releases/latest)には暦3種類、国・地域2種類、星座・恒星3種類、世界遺産2種類、生き物4種類の計14個のAPKGを添付しています。世界遺産と生き物デッキも同じリリースから取得できます。画像はAPKGに同梱しています。

各APKGの `attribution/` に出典・ライセンス説明を収録し、`deck-sources.zip` に元データ・設定・生成スクリプトをまとめています。`SHA256SUMS` は添付ファイルのSHA-256一覧です。個人用の `private/` 配下のファイルと、北宇治デッキのAPKGは公開する添付ファイルに含めていません。

画像を取得済みの環境では、次のコマンドで全デッキを再生成し、リリース用ファイルを `dist/release/` にまとめられます。

```bash
uv run python scripts/build_all.py --skip-kitauji
uv run python scripts/build_release.py --output dist/release
```

初回生成時は、各テーマの取得スクリプトで画像を用意してください。リリース作成スクリプトはAPKGのカード数、ノートIDの重複、出典ファイルを検証し、指定した14個のAPKGだけを収録します。

## 構成

- `decks/<テーマ>/`: テーマごとの設定、データ、出典、生成物
- `scripts/`: 複数テーマで使う共通ビルダー、検証、取得スクリプト
- `decks/calendar/`: 和風月名・二十四節気・干支。項目ごとにapkgを生成します
- `decks/countries/`: 日本を含む196か国の国名・国旗・首都。7地域に分け、首都と国旗の2パックを生成します
- `decks/constellations/`: 88星座・主要恒星27件・星図問題。季節別の3パックを生成します
- `decks/world-heritage/`: UNESCO公式データを使った世界遺産1,273件。通常方向と逆方向を別々のapkgにします
- `decks/fish/`, `decks/plants/`, `decks/flowers/`, `decks/mushrooms/`: 各15件のビジュアルデッキ。画像の出典とライセンスをTSVで管理します
- `decks/kitauji/`: 響け！ユーフォニアム関連の北宇治高校吹奏楽部デッキ

Ankiでは関連するテーマを親デッキの下にまとめます。`::` はAnkiの階層の区切りです。親デッキを選ぶと、その下の地域・季節・方向をまとめて学習できます。

```text
国・地域
  首都
    アジア／中東／欧州／アフリカ／北米／中南米／大洋州
      国名→首都
      首都→国名
  国旗
    アジア／中東／欧州／アフリカ／北米／中南米／大洋州
星座・恒星
  星座名
    春／夏／秋／冬
      日本語名→学名・略号
      学名・略号→日本語名
  主要恒星
    春／夏／秋／冬
      固有名→星座・符号
      星座・符号→固有名
  星図
    春／夏／秋／冬
暦
  和風月名
    月→和風月名
    和風月名→月
  二十四節気
    太陽黄経→節気
    節気→太陽黄経
  干支
    読み・順番→干支
    干支→読み・順番
世界遺産
  手がかり→名称
  名称→登録情報
生き物
  魚介／植物／花／きのこ
```

全体版と地域別・季節別の重複をなくし、「スターター」という表示名も廃止しました。全体を学習するときは親デッキを選びます。ソースの `starter-*` ディレクトリ名と、既存の地域別・季節別ノートの識別子は維持しています。

元データと出典はGitで管理し、`.apkg`と取得画像など再生成できるファイルはGitで管理しません。国旗画像は取得スクリプトで `decks/countries/assets/flags/` に用意します。

## 世界遺産・自然物デッキ

UNESCOのWorld Heritage Listから世界遺産データを取得し、名称問題と登録情報問題を別デッキとして生成します。魚介・植物・花・きのこはWikimedia Commonsの画像を使ったビジュアル問題です。

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

`decks/calendar/japanese-months/`、`decks/calendar/sekki/`、`decks/calendar/eto/` に、それぞれの `deck.toml` があります。各APKGには通常方向と逆方向の子デッキが入り、同じノートから両方向のカードを生成します。項目を重複して収録する `calendar.apkg` は生成しません。

## 国名・国旗・首都デッキ

首都は「国名→首都」と「首都→国名」を同じ地域の下にまとめ、国旗は「国旗→国名」の一方向にします。各地域の合計で196か国を一度ずつ収録します。

| 種類 | APKG | 収録内容 | カード数 |
| --- | --- | --- | ---: |
| 首都 | `country-capital-pack.apkg` | 7地域×2方向 | 392 |
| 国旗 | `country-flag-pack.apkg` | 7地域×1方向 | 196 |

首都パックには従来の国名パックの問題も含みます。`country-name-pack.apkg` と全体版の個別APKGは生成しません。生成するAPKGでは既存の地域別デッキID・ノートIDを維持し、首都の2方向は従来どおり別ノートです。画像もAPKGに同梱します。

パックの再生成は `uv run python scripts/build_country_bundles.py` で実行します。`decks/countries/build/` に出力され、一括再生成スクリプトでも生成します。

国旗は [Sekainokokki.jp](https://www.sekainokokki.jp/organization/un#toc-members) が案内する公式CDNから、元の縦横比のSVGを取得してAPKGに同梱します。画像は同サイトの利用規約でパブリックドメインとされています。

地域は [外務省の地域別インデックス](https://www.mofa.go.jp/mofaj/area/index.html) に基づき、国ごとの分類・出典URL・確認日を `decks/countries/data/country-regions.tsv` に記録しています。日本は外国一覧に掲載されないため、アジアとして補完しています。中央アジア諸国は外務省の「欧州（NIS諸国を含む）」に従います。地域分類の出典はスクリプトとTSVで管理し、カード裏面には表示しません。

| 地域 | 各方向のカード数 | 地域の識別子 |
| --- | ---: | --- |
| アジア | 22 | `asia` |
| 中東 | 15 | `middle-east` |
| 欧州 | 54 | `europe` |
| アフリカ | 54 | `africa` |
| 北米 | 2 | `north-america` |
| 中南米 | 33 | `latin-america` |
| 大洋州 | 16 | `oceania` |

首都から国名を答える問題は `decks/countries/starter-names/`、国旗は `starter-flags/`、国名から首都を答える問題は `starter-capitals/` の各地域ディレクトリで管理します。それぞれの `build/` に `country-name-<地域>.apkg`、`country-flag-<地域>.apkg`、`country-capital-<地域>.apkg` を出力します。

```bash
uv sync
uv run python scripts/fetch_countries.py
uv run python scripts/generate_country_starters.py
for kind in starter-names starter-flags starter-capitals; do
  for region in asia middle-east europe africa north-america latin-america oceania; do
    uv run python scripts/build_topic_deck.py "decks/countries/$kind/$region"
    uv run python scripts/validate_topic.py "decks/countries/$kind/$region"
  done
done
uv run python scripts/build_country_bundles.py
```

一括再生成は `uv run python scripts/build_all.py` で実行します。地域別の元データもこのスクリプトで再生成します。

## 星座デッキ

国立天文台のデータを使い、88星座・主要恒星27件・星図問題を別々のパックにしています。各パックは春夏秋冬の4季節に分かれ、全体版と重複する問題は含みません。

| パック | APKG | カード数 |
| --- | --- | ---: |
| 88星座の日本語名・学名・略号 | `constellation-name-pack.apkg` | 176 |
| 主要恒星の固有名・所属星座・符号 | `main-stars-pack.apkg` | 54 |
| 星図から星座名を答える問題 | `constellation-visual-pack.apkg` | 88 |

88星座は「日本語名→学名・略号」と「学名・略号→日本語名」、主要恒星は「固有名→星座・符号」と「星座・符号→固有名」を季節の下に分けます。通常方向と逆方向は同じノートから作り、説明を共通に保ちます。星図問題は一方向です。生成するAPKGでは既存の季節別デッキID・ノートIDを維持しています。

季節は [国立天文台の一覧](https://www.nao.ac.jp/new-info/constellation.html) の「位置の目安」の月から、次のルールで機械的に分けます。この春夏秋冬の区分は本プロジェクトで定めたもので、国立天文台が示す季節分類ではありません。

| 季節 | 月 | 星座数 | 主要恒星数 |
| --- | --- | ---: | ---: |
| 春 | 3〜5月 | 22 | 8 |
| 夏 | 6〜8月 | 21 | 7 |
| 秋 | 9〜11月 | 23 | 3 |
| 冬 | 12〜2月 | 22 | 9 |

「位置の目安」は、東京で20時（中央標準時）に星座のおよその中心が子午線を通過する時期です。一般的な「春の星座」などの区分とは異なる場合があります。南天の一部は東京から見えず、周極星も特定の季節だけに見えるわけではありません。主要恒星は所属星座の月を使い、へび座は頭部の月を使います。対応表は `decks/constellations/data/constellation-seasons.tsv` に生成します。分類の出典や作成上の注記はスクリプトと資料で管理し、カードのdetailには追加しません。

```bash
uv run python scripts/fetch_constellations.py
uv run python scripts/generate_constellation_starters.py
uv run python scripts/build_constellation_bundles.py
```

パックは `decks/constellations/build/` に出力します。`scripts/build_all.py` でも季節別データとパックを再生成し、個別デッキを検証します。星図PNGは取得スクリプトで `decks/constellations/assets/charts/` に用意し、Gitでは管理しません。

## 既存デッキの移行

APKGの取り込みだけでは、旧名のデッキや全体版の重複カードが残る場合があります。AnkiConnectを有効にしたAnkiを起動し、次のコマンドで移行対象を確認できます。

```bash
uv run python scripts/migrate_deck_hierarchy.py
```

全体版の学習履歴をバックアップだけに残し、地域別・季節別に統一する場合は `--apply` を指定します。移行中はAnkiで学習や編集をしないでください。

```bash
uv run python scripts/migrate_deck_hierarchy.py --apply
```

対象デッキを学習履歴付きAPKGとして `private/hierarchy-migration/<日時>/` に保存してから、既存カードを新しい階層へ移動します。移動先のデッキは新規作成しますが、残すカードのID・学習状態・復習履歴は変更前後で照合します。全体版はカードと履歴を含めてAnkiから削除し、旧名の空デッキも削除します。対象外のデッキと、まだ取り込んでいないテーマは変更しません。バックアップのAPKGを再取り込みすると、削除した全体版も戻ります。

世界遺産は2方向でノートIDとノートタイプ名が重なり、両方を取り込むと問題の向きや配置が混在する不具合をv0.6.0で修正しました。登録情報問題に専用のノートIDを割り当て、2方向のノートタイプ名も分けています。旧版の世界遺産デッキをすでに取り込んでいる場合は、世界遺産デッキを学習履歴付きで書き出してから旧版の世界遺産デッキを削除し、新版の2つのAPKGを取り込んでください。この入れ替えでは旧版の学習履歴は自動では引き継がれません。

既存の国名・首都デッキに以前の「逆向き」テンプレートが残っている場合は、移行処理を停止します。Ankiのブラウザで対象ノートタイプを確認し、「基本」テンプレートとノート本体を残して不要な「逆向き」テンプレートを削除してから再実行してください。

## 北宇治高校吹奏楽部デッキ

```bash
uv sync
uv run python decks/kitauji/scripts/fetch_members.py --download-images --all-images
uv run python decks/kitauji/scripts/build_deck.py
uv run python decks/kitauji/scripts/validate_project.py
```

画像は公式サイトから取得するため、初回生成前に取得コマンドを実行します。画像の利用条件は公式サイトの案内に従います。
