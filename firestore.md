# Cloud Firestore 入門

> 参考: [Get to Know Cloud Firestore](https://youtu.be/v_hR4K4auoQ) — Firebase YouTube

---

## Firestore とは

Cloud Firestore は Google Cloud が提供する **水平スケーリング対応の NoSQL ドキュメントデータベース**です。

---

## RDB との違い

### RDB（リレーショナルDB）の世界

RDB ではデータを**テーブル**で管理します。各テーブルには**スキーマ**（列の定義と型制約）があり、すべての行は厳密なルールに従います。

```
restaurants テーブル          reviews テーブル
┌────────────────────┐        ┌──────────────────────────────┐
│ id │ name │ rating │        │ id │ restaurant_id │ user_id │
├────┼──────┼────────┤        ├────┼───────────────┼─────────┤
│  1 │ A店  │   4.2  │        │  1 │       1       │    5    │
└────────────────────┘        └──────────────────────────────┘
```

テーブル間の関連は **外部キー（foreign key）** で表現し、データ取得時は **JOIN** でまとめて取得します。この設計原則を**データ正規化**（同じデータは1箇所にだけ置く）と呼びます。

### Firestore（NoSQL）の世界

Firestore では **スキーマがありません**。フィールドの追加・変更が自由で、同じコレクション内でもドキュメントごとに異なるフィールドを持てます。**JOIN も SQL もありません。**

| | RDB | Cloud Firestore |
|---|---|---|
| データ単位 | 行（Row） | ドキュメント（Document） |
| グループ単位 | テーブル（Table） | コレクション（Collection） |
| スキーマ | 固定 | なし（自由） |
| 関連の取得 | JOIN | 不可（別リクエストが必要） |
| スケール | 垂直スケール（サーバー強化） | 水平スケール（サーバー追加） |

---

## NoSQL のトレードオフ

### メリット

**1. スキーマが柔軟**
フィールドの追加・変更に既存データへの影響がありません。新しいフィールドは新しいドキュメントにだけ追加すれば OK です。

**2. 読み取りが高速**
必要なデータを1つのドキュメントにまとめておけば、1回のリクエストで全部取れます。JOIN 不要なのでシンプルです。

**3. 水平スケール**
データが増えても、複数のサーバーに自動で分散してくれます。RDB のように「より強力なサーバーに移す」必要がありません。

> 読み取りと書き込みの比率が 7000:1 になるようなケース（レビューの閲覧 vs プロフィール変更など）では、読み取りを最適化する NoSQL の設計は合理的です。

### デメリット

**1. データの重複が発生する**
JOIN できないため、必要なデータを同じドキュメントにコピーして持ちます。ユーザーのプロフィールを変更したとき、複数のドキュメントを更新しなければなりません。

**2. 防御的なコーディングが必要**
スキーマがないため、クライアント側でフィールドの存在チェックや型チェックが必要です。

---

## Firestore の構造

```
Database（root）
└── Collection（コレクション）    ← rootには必ずCollectionが来る
    └── Document（ドキュメント）  ← Collectionの中身はDocumentのみ
        ├── field: value
        ├── field: value
        └── SubCollection         ← Documentの下にはCollectionを置ける
            └── Document
                └── ...
```

### 4つのルール

1. **コレクションにはドキュメントしか入れられない**（文字列や数値の直接格納は不可）
2. **ドキュメントの上限サイズは 1MB**
3. **ドキュメントは別のドキュメントを直接含められない**（サブコレクションを経由する）
4. **rootにはコレクションしか置けない**

### パスの書き方

コレクションとドキュメントを交互に指定します。

```
restaurants/abc123/reviews/xyz789
↑           ↑      ↑       ↑
Collection  Doc    Collection  Doc
```

```bash
# コレクション一覧
fs collections list

# ドキュメント配下のサブコレクション一覧
fs collections list restaurants/abc123
```

---

## Collection と Document

### Collection（コレクション）

- **明示的に作成しません** — 最初のドキュメントを書き込んだ瞬間に暗黙的に生成されます
- ドキュメントをすべて削除すると、コレクションも消えます

```bash
# "orders" に最初のドキュメントを書いた瞬間にコレクションが生まれる
fs documents add orders --data '{"item":"coffee","price":500}'

fs collections list  # → orders が表示される
```

### Document（ドキュメント）

- フィールド（key-value ペア）の集合。JSON オブジェクトに似ています
- **Document ID** で一意に識別される（RDB の主キーに相当）
- コレクション内でスキーマを統一する必要はありません

```bash
# ID を指定して直接取得（コレクションサイズに関係なく O(1)）
fs documents get restaurants/abc123
```

---

## データ型

Firestore は JSON より豊富な型をサポートします。

| 型 | 説明 | CLI での指定 |
|---|---|---|
| String | 文字列 | `"hello"` |
| Integer / Float | 数値 | `42` / `3.14` |
| Boolean | 真偽値 | `true` / `false` |
| Null | null | `null` |
| Array | 配列 | `[1, 2, 3]` |
| Map | ネストされたオブジェクト | `{"key": "val"}` |
| **Timestamp** | 日時 | `"@now"` または `"@timestamp:2026-05-15T20:00:00Z"` |

```bash
# Timestamp を使った書き込み
fs documents add messages \
  --data '{"name":"alice","message":"hello","createdAt":"@now"}'

# 日時を指定
fs documents set messages/alice \
  --data '{"updatedAt":"@timestamp:2026-05-15T09:00:00Z"}' --merge
```

---

## CRUD 操作

### Create（作成）

```bash
# 自動 ID でドキュメントを追加
fs documents add messages --data '{"name":"alice","message":"hello"}'

# ID を指定して作成（存在しなければ作成、存在すれば上書き）
fs documents set messages/alice --data '{"name":"alice","message":"hello"}'

# 既存フィールドを残しつつ追記（マージ）
fs documents set messages/alice --data '{"age":30}' --merge
```

### Read（読み取り）

```bash
# ドキュメント一覧
fs documents list messages
fs documents list messages --limit 10 --format json

# ID 指定で1件取得
fs documents get messages/alice

# 存在確認（exit 0: 存在する / exit 1: 存在しない）
fs documents exists messages/alice
```

### Update（更新）

```bash
# 指定フィールドのみ更新（他のフィールドは保持）
fs documents update messages/alice --data '{"message":"updated"}'
```

| コマンド | ドキュメントが存在しない場合 | 既存フィールドの扱い |
|---|---|---|
| `set` | 作成する | 上書き（消える） |
| `set --merge` | 作成する | 保持される |
| `update` | **エラー** | 保持される |

### Delete（削除）

```bash
fs documents delete messages/alice        # 確認プロンプトあり
fs documents delete messages/alice --yes  # 確認なし（スクリプト用）
```

> **注意**: ドキュメントを削除しても、配下のサブコレクションは削除されません。

---

## クエリ

Firestore のクエリは**コレクション単位**で実行します。**クエリはデフォルトで shallow**（浅い）です — サブコレクションのデータは自動では取得されません。

> Realtime Database では親を取得すると子もすべて取得されました。Firestore ではそうならないので、トップ20件のレストランを取得しても、各レストランのレビューは取得されません。必要なときに別途リクエストします。

```bash
# 等値
fs query messages --where 'name == alice'

# 比較
fs query messages --where 'likes >= 2'

# 複数条件（AND）
fs query messages --where 'name == alice' --where 'likes >= 1'

# 配列で一致（in は JSON 配列で指定）
fs query messages --where 'status in ["active","trial"]'

# 日付範囲
fs query messages \
  --where 'createdAt >= 2026-05-15T00:00:00Z' \
  --where 'createdAt <= 2026-05-15T23:59:59Z'

# ソート＋件数制限
fs query messages --order-by createdAt:desc --limit 5
```

### 使えるオペレーター

| 演算子 | 説明 |
|---|---|
| `==` / `!=` | 等値・不等値 |
| `<` `<=` `>` `>=` | 大小比較 |
| `in` | 配列のいずれかに一致（JSON 配列で指定） |
| `not-in` | 配列のいずれにも一致しない（JSON 配列で指定） |
| `array-contains` | フィールドの配列が特定の値を含む |
| `array-contains-any` | フィールドの配列がいずれかの値を含む（JSON 配列で指定） |

---

## データモデリングの考え方

### レストランレビューアプリの例

```
restaurants/           ← トップレベルコレクション
  abc123/
    name: "A店"
    rating: 4.2
    reviews/           ← サブコレクション
      review1/
        text: "おいしかった"
        rating: 5
        authorName: "alice"     ← Userドキュメントからコピー（重複）
        authorPhoto: "https://..."  ← 重複データ
```

**なぜ `authorName` をコピーするのか？**
JOIN がないため、レビューを取得するときにユーザー情報を自動で結合できません。必要なユーザー情報（名前・アイコン）をレビュードキュメント内にコピーしておくことで、1回のリクエストで表示に必要な全データを取れます。

**デメリット**: ユーザーが名前を変更したとき、すべてのレビューを更新する必要があります。

---

## Firestore と RDB、どう使い分けるか

### Non-Engineer・AI Agent 開発者には Firestore が向いている

RDB でアプリを作るには、最初に**スキーマ設計**（テーブルの列・型・制約の定義）が必要です。データ構造が変わるたびに `ALTER TABLE` で定義を変更する作業も発生します。

Firestore は**スキーマが不要**です。コード上のオブジェクトをそのままドキュメントとして保存できるため、設計と実装が直結します。AI Agent を使ってアプリを素早く試作する場面では、この柔軟さが大きな強みになります。

```
// コード上のオブジェクト
{
  name: "alice",
  message: "hello",
  createdAt: new Date(),
  tags: ["greeting", "casual"]
}

// そのまま Firestore に保存できる ← テーブル設計不要
```

---

### 使い分けの基準

| | Firestore | RDB（MySQL 等） |
|---|---|---|
| スキーマ設計 | 不要 | 必要（事前定義） |
| 構造の変更 | フィールドを追加するだけ | ALTER TABLE が必要 |
| データの関係 | シンプルな親子関係が得意 | 複雑な多対多の関係が得意 |
| 集計・レポート | 苦手 | SQL で柔軟に対応可能 |
| データ整合性 | アプリ側で担保 | DB レベルで強制できる |
| スケール | 自動（水平） | サーバー強化が必要（垂直） |
| 向いている開発者 | Non-Engineer・AI Agent 開発 | バックエンドエンジニア |

---

### アプリ別の向き・不向き

| アプリの例 | 向いている DB | 理由 |
|---|---|---|
| チャット・SNS | **Firestore** | リアルタイム同期、構造がシンプル |
| ECサイトの商品カタログ | **Firestore** | 商品ごとに属性が異なる |
| ユーザー設定・プロフィール | **Firestore** | オブジェクトをそのまま保存 |
| 銀行・決済の取引履歴 | **RDB** | 整合性・トランザクションが重要 |
| 複雑な在庫・受発注管理 | **RDB** | 多対多の関係、複雑な集計 |
| 社内の経費精算システム | **RDB** | レポーティング・監査が必要 |

---

### 迷ったときの判断フロー

```
アプリを作りたい
    ↓
データ構造は頻繁に変わりそう？
    ↓ Yes                    ↓ No
Firestore              整合性・JOIN・集計が複雑？
                           ↓ Yes        ↓ No
                          RDB        Firestore
```

**結論**: AI Agent でアプリを作る場合は、**まず Firestore から始める**のがおすすめです。整合性の厳密さや複雑な集計が必要になってきたタイミングで RDB を検討すれば十分で、多くのアプリはFirestore だけで完結します。

---

## データベース確認

```bash
fs db list      # データベース一覧
fs db describe  # 詳細（ロケーション・モード確認）
```

## 設定

```bash
fs config set project your-project-id  # プロジェクト ID を設定
fs config list                          # 現在の設定を確認
```
