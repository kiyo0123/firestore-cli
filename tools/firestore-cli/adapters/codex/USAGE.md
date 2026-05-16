# Codex 利用者向け: Firestore CLI の使い方

このディレクトリの CLI はツール非依存の素の Python スクリプトです。
Codex（や任意のエージェント／シェル）からは、リポジトリ内の `fs.py` を
そのまま実行してください。Claude Code の skill 機構は不要です。

## 実行

```bash
python3 tools/firestore-cli/fs.py <args>
```

エイリアス例:

```bash
alias fs='python3 /absolute/path/to/tools/firestore-cli/fs.py'
fs help
```

## 前提（初回のみ）

```bash
pip install google-cloud-firestore
gcloud auth application-default login          # または GOOGLE_APPLICATION_CREDENTIALS
python3 tools/firestore-cli/fs.py config set project <YOUR_PROJECT_ID>
```

## 参照

コマンド一覧・パス規約・学習ポイント・例・トラブルシュートは
`tools/firestore-cli/README.md` を参照してください（こちらが正）。

## Codex から使うときのヒント

- 破壊的操作 `fs documents delete <path>` は対話確認が入ります。
  非対話で実行する場合は `--yes` を付けてください（付けないと
  非 TTY ではエラーで停止します。誤削除防止のため意図的な挙動）。
- 機械処理したいときは `--format json`（`documents get` / `query`）。
- 失敗時はCLI が日本語で原因と対処（依存未導入／認証なし／project 未設定
  ／権限不足など）を出力します。終了コードは成功 0 / エラー 1。
