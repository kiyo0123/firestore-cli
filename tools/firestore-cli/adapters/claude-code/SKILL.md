---
name: firestore-cli
description: Google Cloud Firestore を gcloud 風サブコマンドで操作する学習用 CLI のラッパ。「Firestore を触りたい」「collection / document を見たい・作りたい」「Firestore を学習用に操作」のような依頼で発動。コアは tools/firestore-cli/fs.py の素の Python CLI（Claude Code 非依存）。
---

# Firestore CLI（薄いアダプタ）

これは `tools/firestore-cli/fs.py` を呼ぶ**薄いラッパ**です。実体は
ツール非依存の素の Python CLI で、ロジック・ドキュメントは
`tools/firestore-cli/README.md` を正とします。

## 呼び出し方

リポジトリ内の CLI を直接実行します:

```bash
python3 <repo>/tools/firestore-cli/fs.py <args>
```

`<repo>` はこのリポジトリのチェックアウト先。ユーザー環境に
`alias fs=...` があればそれでも可。

## 前提

- `pip install google-cloud-firestore`
- GCP 認証: `gcloud auth application-default login` または
  `GOOGLE_APPLICATION_CREDENTIALS`
- プロジェクト: `fs config set project <id>`（または `--project` /
  `GOOGLE_CLOUD_PROJECT`）

未設定時は CLI 自身が日本語で具体的な手順を案内します。

## 操作

ユーザー依頼から noun-verb を組み立てて実行し、出力をそのまま提示します。
コマンド体系・パス規約（segment 数が奇数=collection / 偶数=document）・
学習ポイントは `tools/firestore-cli/README.md` を参照。

- 破壊的操作（`documents delete`）は実行前にユーザーへ確認。確定済みなら
  `--yes` を付与。
- 詳細出力が必要なら `--format json`。

このアダプタにロジックを足さないこと（コアを唯一の真実とする）。
