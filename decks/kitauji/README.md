# 北宇治高校吹奏楽部 Anki デッキ

北宇治高校吹奏楽部の部員を、顔、名前、担当楽器、学年の組み合わせで覚えるための個人学習用プロジェクトです。

このREADMEのコマンドは、`decks/kitauji` ディレクトリで実行します。北宇治固有のスクリプトは `scripts/`、データは `data/` にあります。

## 使い方

### 1. 公式の部員情報と画像を取得する

```bash
uv sync
uv run python scripts/fetch_members.py --download-images --all-images
```

このコマンドは、公式の部員一覧ページから91名分の人物データを取得し、`data/members.tsv`に保存します。MVP用に選んだ8名分のデータは`data/mvp.tsv`にも保存され、91名分の顔アイコンは`assets/member/`に保存されます。

公式サイトが配布するアイコンは、個人で楽しむ範囲で利用してください。生成したデッキや画像を再配布する場合は、公式サイトの利用条件を確認してください。

### 2. Ankiデッキを生成する

`uv`で依存関係を同期してから、次のコマンドを実行します。

```bash
uv sync
uv run python scripts/build_deck.py
uv run python scripts/validate_project.py
uv run python scripts/build_deck.py --all
uv run python scripts/validate_project.py --all
```

生成物は`build/kitauji_mvp.apkg`と`build/kitauji_all.apkg`です。全員分を使う場合は、`kitauji_all.apkg`をWindows版Ankiへインポートしてください。

### 3. Windows版Ankiで確認する

1. `build/kitauji_all.apkg`をWindowsへコピーします。
2. Ankiで「ファイル」からインポートを選び、`.apkg`を指定します。
3. `北宇治高校吹奏楽部・顔と部員情報`デッキを開きます。
4. 顔を見て名前を思い出してから解答を表示し、名前・楽器・学年が表示されることを確認します。

最初は数枚を試し、画像の見やすさと、楽器・学年を同時に答える負荷を確認します。逆向きカードが必要になった場合は、`--include-reverse`を付けて再生成します。

初期デッキには、顔画像を見て名前・フリガナ・楽器・学年を答えるカードを1人1枚作ります。カードは濃色背景に白文字で表示し、解答欄には公式ページのプロフィール本文をリンクなしで表示します。出典URLはデータファイルに残しますが、カードには表示しません。`--include-reverse`を付けると、名前から顔を思い出すカードも追加されます。

学習中のキー操作はAnkiの標準設定です。解答表示前は`Space`または`Enter`で解答を表示し、解答表示後は`1`がもう一度、`2`が難しい、`3`が正解、`4`が簡単です。`Space`または`Enter`は解答表示後には`3`（正解）としても使えます。

```bash
uv run python scripts/build_deck.py --include-reverse
```

## データ構成

人物の基本情報と大会記録を別ファイルで管理します。

- `data/members.tsv`: 公式ページから取得した人物情報
- `data/mvp.tsv`: 最初に学習する人物の一覧
- `data/competition_events.tsv`: 大会ごとの時期・大会段階・学校としての結果
- `data/competition_records.tsv`: 大会ごとの人物別の選出状況
- `assets/member/`: 公式サイトから取得した顔アイコン
- `build/`: Ankiにインポートする`.apkg`

大会情報は、大会自体の情報と人物別の選出状況を分けて記録します。大会イベントには作品内の時期、学年、大会段階、学校としての結果、出典URLを保存し、人物記録にはイベントID、人物ID、選出状況、人物別の出典URLを保存します。人物の学年は作品内の時期によって変わるため、`members.tsv`にある現在の学年とは別に、イベント側にも学年を持たせます。

大会記録は先にデータ側へ保存しておきますが、現在のカード裏面には表示しません。人物別の選出結果を確認できる状態になったら、カードへ表示するかどうかを改めて決めます。公式資料で人物別の選出結果を確認できない場合は、推測で`selected`を埋めず、イベント側の学校結果だけを記録します。

`selected`には、確認できた場合だけ`yes`または`no`を入れます。資料から判断できない場合は`unknown`とし、空欄とは区別します。

## 出典

- [北宇治高校吹奏楽部 部員紹介](https://anime-eupho.com/special/member/)
- [『最終楽章 響け！ユーフォニアム』公式サイト](https://anime-eupho.com/)

このプロジェクトは非公式の個人学習用です。
