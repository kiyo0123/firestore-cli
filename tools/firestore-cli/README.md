# `fs` — Firestore 学習用 CLI

Google Cloud Firestore を **gcloud 風のサブコマンド**で操作できる、学習用の
シンプルな CLI。database / collection / document / subcollection / query
という Firestore の中心概念を一通り触って学べます。

**ツール非依存**: これは素の Python CLI です。Claude Code・Codex・ただの
シェル、どこからでも `python3 fs.py <args>` で同じように動きます。Claude Code
の skill 機構には依存しません。

## セットアップ（必須）

1. 依存パッケージ（唯一の外部依存）:

   ```bash
   pip install google-cloud-firestore
   ```

2. GCP 認証（どちらか）:

   ```bash
   gcloud auth application-default login
   # または
   export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
   ```

3. プロジェクト設定（優先順位: `--project` フラグ > `GOOGLE_CLOUD_PROJECT`
   環境変数 > config ファイル > ADC 既定）:

   ```bash
   python3 tools/firestore-cli/fs.py config set project <YOUR_PROJECT_ID>
   ```

4. （任意）エイリアスを貼ると `fs ...` で呼べます:

   ```bash
   alias fs='python3 /absolute/path/to/tools/firestore-cli/fs.py'
   ```

設定は `${XDG_CONFIG_HOME:-~/.config}/firestore-cli/config.json` に保存され、
リポジトリ外です。API キー等の秘密情報は保存・コミットしません。

## コマンド一覧（gcloud 風 noun-verb）

```
fs config set project <id>            # プロジェクトを保存
fs config set database <id>           # database を保存 (既定: (default))
fs config list                        # 現在の設定と実効値

fs db create [--database ID] [--location nam5]
fs db list
fs db describe [--database ID]

fs collections list [<doc-path>]      # root / document 配下の collection
fs collections create <col> --doc-id <id> --data '<json>'

fs documents list <col-path> [--limit N]
fs documents get <doc-path> [--format json]
fs documents add <col-path> --data '<json>'        # 自動 ID
fs documents set <doc-path> --data '<json>' [--merge]
fs documents update <doc-path> --data '<json>'
fs documents delete <doc-path> [--yes]

fs query <col-path> [--where "field OP value"]... [--order-by field[:desc]] [--limit N] [--format json]

fs help
```

データ入力は `--data '<json>'` / `--data-file <path>` / `--data @-`（stdin）。

## パスの考え方（subcollection 対応）

スラッシュ区切りで指定します。**segment 数が奇数なら collection、偶数なら
document** です。

| パス | 種類 |
|---|---|
| `users` | collection |
| `users/alice` | document |
| `users/alice/orders` | subcollection |
| `users/alice/orders/o1` | document |

## Firestore の学習ポイント

- **collection は暗黙生成**: Firestore に「空の collection を作る」操作は
  ありません。最初の document を書いた時点で collection が現れます。
  `fs collections create` はこの「最初の document を作る」操作です。
- **subcollection**: document の下にぶら下がる collection。上のパス表で
  segment を伸ばすだけで辿れます。
- **query**: `--where` の演算子は
  `== != < <= > >= in array-contains`。複数 `--where` は AND。
  `--order-by` と組み合わせると、Firestore が複合インデックスを要求する
  ことがあります（エラーメッセージにインデックス作成 URL が出ます）。

## クイックスタート例

```bash
fs collections create demo --doc-id a --data '{"n": 1}'
fs documents add demo --data '{"n": 2}'
fs documents list demo
fs documents get demo/a --format json
fs documents update demo/a --data '{"n": 10}'
fs documents add demo/a/sub --data '{"k": 1}'   # subcollection
fs collections list demo/a
fs query demo --where "n > 1" --order-by n:desc --limit 5
fs documents delete demo/a --yes
```

## スコープ外（学習用のため意図的に除外）

REPL/対話シェル、batch/transaction、index 管理、export/import、
Timestamp/GeoPoint 等の高度な型、リアルタイム listener、
Firestore エミュレータ切替。

## トラブルシュート

| 症状 | 対処 |
|---|---|
| `google-cloud-firestore がインストールされていません` | `pip install google-cloud-firestore` |
| `GCP の認証情報が見つかりません` | `gcloud auth application-default login` |
| `GCP プロジェクトが未設定です` | `fs config set project <id>` |
| `PermissionDenied` | IAM ロール（`roles/datastore.user` 等）を確認 |
| query で index を要求された | エラー内の URL からインデックスを作成 |
