# firestore-cli

Google Cloud Firestore を **gcloud 風のサブコマンド**で操作できる学習用の
シンプルな CLI (`fs`)。database / collection / document / subcollection /
query という Firestore の中心概念を一通り触って学べます。

**ツール非依存**: 素の Python CLI です。Claude Code・Codex・ただのシェル、
どこからでも `python3 tools/firestore-cli/fs.py <args>` で同じように動きます。

詳細なドキュメント・パス規約・学習ポイントは
[`tools/firestore-cli/README.md`](tools/firestore-cli/README.md) を参照。

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

3. プロジェクト設定:

   ```bash
   python3 tools/firestore-cli/fs.py config set project <YOUR_PROJECT_ID>
   ```

4. （任意）エイリアスを貼ると `fs ...` で呼べます:

   ```bash
   alias fs='python3 /absolute/path/to/tools/firestore-cli/fs.py'
   ```

設定は `${XDG_CONFIG_HOME:-~/.config}/firestore-cli/config.json` に保存され、
リポジトリ外です。API キー等の秘密情報は保存・コミットしません。

## 使い方（gcloud 風 noun-verb）

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

## トラブルシュート

| 症状 | 対処 |
|---|---|
| `google-cloud-firestore がインストールされていません` | `pip install google-cloud-firestore` |
| `GCP の認証情報が見つかりません` | `gcloud auth application-default login` |
| `GCP プロジェクトが未設定です` | `fs config set project <id>` |
| `PermissionDenied` | IAM ロール（`roles/datastore.user` 等）を確認 |
| query で index を要求された | エラー内の URL からインデックスを作成 |
