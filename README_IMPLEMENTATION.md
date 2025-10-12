# Firestoreスキーマ改善 実装ガイド

## 🎯 プロジェクト概要

Firestoreのデータ構造を改善し、タスク親ドキュメントにメタデータを保存することで、動的な課題管理を可能にします。

**重要な制約**:
- ✅ 既存の重複チェック機能を100%維持
- ✅ 後方互換性の完全保証（Cloud Scheduler設定変更不要）
- ✅ fail-open戦略の継続（高可用性優先）
- ✅ データ損失ゼロ

## 🚀 クイックスタート

### 1. 依存関係のインストール

```bash
# 本番依存関係
pip install -r requirements.txt

# 開発・テスト依存関係
pip install -r requirements-dev.txt

# Firebase CLIのインストール（Firestore Emulator用）
npm install -g firebase-tools
```

### 2. テストの実行

```bash
# ユニットテストのみ
pytest tests/unit/ -v --cov=src

# 統合テスト（Firestore Emulator必要）
firebase emulators:start --only firestore &
pytest tests/integration/ -v

# すべてのテスト
pytest tests/ -v --cov=src --cov-report=html
```

### 3. ローカル開発

```bash
# Firestore Emulatorを起動
firebase emulators:start --only firestore

# 別ターミナルでテストを実行
export FIRESTORE_EMULATOR_HOST=localhost:8080
export GCP_PROJECT=demo-test
pytest tests/ -v
```

## 📋 実装チェックリスト

### Phase 1: テスト駆動開発（TDD）

- [x] テストフレームワークのセットアップ
- [ ] **Task 2.1**: `_update_task_metadata`のテスト作成
  - [ ] `test_update_task_metadata_creates_new_document`
  - [ ] `test_update_task_metadata_increments_file_count`
  - [ ] `test_update_task_metadata_fails_gracefully`
- [ ] **Task 2.2**: `_update_task_metadata`の実装
- [ ] **Task 2.3**: `record_upload`拡張のテスト作成
- [ ] **Task 2.4**: `record_upload`の実装
- [ ] **Task 2.5**: `check_already_uploaded`不変性テスト

### Phase 2: マイグレーション

- [ ] **Task 3.1**: マイグレーションスクリプトのテスト作成
- [ ] **Task 3.2**: `migrate_parent_documents.py`の実装
- [ ] **Task 3.3**: 検証ロジックの実装
- [ ] **Task 3.4**: レポート出力機能の実装
- [ ] **Task 4.1**: `rollback_parent_documents.py`の作成
- [ ] **Task 4.2**: `fix_file_count.py`の作成

### Phase 3: 統合テスト

- [ ] **Task 5.1**: Firestore Emulator環境のセットアップ
- [ ] **Task 5.2**: 新規ファイルアップロードのテスト
- [ ] **Task 5.3**: 重複ファイルアップロードのテスト
- [ ] **Task 5.4**: 並行アップロードのテスト
- [ ] **Task 5.5**: マイグレーションスクリプトのテスト

### Phase 4: CI/CD統合

- [x] GitHub Actionsワークフローの作成
  - [x] `test.yml`: PR時の自動テスト
  - [x] `migration.yml`: 手動マイグレーション
  - [x] `deploy.yml`: テスト通過後のデプロイ
  - [x] `monitor.yml`: 本番モニタリング
- [ ] **Task 6.1**: ステージングでのdry-run実行
- [ ] **Task 6.2**: ステージングでのマイグレーション実行
- [ ] **Task 6.3**: ステージングでのコードデプロイ

### Phase 5: 本番デプロイ

- [ ] **Task 7.1**: Firestoreバックアップの確認
- [ ] **Task 7.2**: 本番マイグレーション実行
- [ ] **Task 7.3**: 本番コードデプロイ
- [ ] **Task 7.4**: 24時間モニタリング

### Phase 6: ドキュメント

- [ ] **Task 8.1**: 実装ドキュメントの作成
- [ ] **Task 8.2**: 運用手順書の作成

## 🔧 開発ワークフロー

### ブランチ戦略

```bash
# 新しいfeatureブランチを作成
git checkout -b feature/firestore-schema-improvement

# 実装・テスト・コミット
git add .
git commit -m "feat: implement _update_task_metadata with tests"

# Push & Pull Request作成
git push origin feature/firestore-schema-improvement
# → GitHub ActionsでテストワークフローDOが自動実行される
```

### TDDサイクル

1. **Red**: テストを書く（失敗する）
   ```bash
   pytest tests/unit/test_firestore_service.py::test_update_task_metadata_creates_new_document -v
   # → FAILED
   ```

2. **Green**: 最小限の実装（テストをパスさせる）
   ```bash
   # src/firestore_service.pyを実装
   pytest tests/unit/test_firestore_service.py::test_update_task_metadata_creates_new_document -v
   # → PASSED
   ```

3. **Refactor**: コードを改善
   ```bash
   # コードの重複を削除、可読性向上
   pytest tests/unit/ -v --cov=src
   # → すべてPASSED、カバレッジ80%以上
   ```

## 🔒 CI/CDワークフロー

### 自動テスト（PR作成時）

```bash
# PRを作成すると自動的に実行される
.github/workflows/test.yml
├── ユニットテスト（カバレッジ80%以上必須）
├── 統合テスト（Firestore Emulator使用）
├── セキュリティスキャン（Trivy）
└── コード品質チェック（Black, isort, flake8, mypy）
```

### 手動マイグレーション（GitHub Actions）

```bash
# 1. Actionsタブ > "Firestore Migration" > "Run workflow"
# 2. Mode: "dry-run", Environment: "staging"
# 3. レポートをダウンロード・確認
# 4. Mode: "execute", Environment: "staging"
# 5. ステージング検証後、Environment: "production"（承認必要）
```

### 自動デプロイ（mainブランチへのマージ時）

```bash
# mainブランチにマージすると自動実行
.github/workflows/deploy.yml
├── テスト実行（ユニット+統合）
├── Dockerイメージビルド
├── Artifact Registryへpush
└── Cloud Runへデプロイ（テスト通過後のみ）
```

### モニタリング（デプロイ後）

```bash
# Actionsタブ > "Post-Deployment Monitoring" > "Run workflow"
# Duration: 24 (hours)
# → エラー率、Firestore操作、file_count正確性を監視
```

## 🛠️ ユーティリティスクリプト

### マイグレーション関連

```bash
# Dry-run（プレビューのみ）
python scripts/migrate_parent_documents.py --dry-run

# 本番実行
python scripts/migrate_parent_documents.py --execute

# ロールバック
python scripts/rollback_parent_documents.py --confirm

# file_count修正
python scripts/fix_file_count.py --execute

# file_count検証
python scripts/verify_file_count.py
```

## 📊 成功基準

実装が完了したと見なされる基準：

1. ✅ すべてのユニットテストがパス（カバレッジ80%以上）
2. ✅ すべての統合テストがパス
3. ✅ マイグレーション後のfile_count検証で不一致ゼロ
4. ✅ 重複チェック機能が100%動作
5. ✅ Cloud Scheduler設定変更なしで動作（後方互換性）
6. ✅ 本番デプロイ後24時間エラーゼロ

## 🚨 トラブルシューティング

### テストが失敗する

```bash
# 詳細なエラー情報を表示
pytest tests/unit/ -v --tb=long

# 特定のテストのみ実行
pytest tests/unit/test_firestore_service.py::test_update_task_metadata_creates_new_document -v

# デバッグモード
pytest tests/unit/ -v -s  # printデバッグが表示される
```

### Firestore Emulatorに接続できない

```bash
# Emulatorが起動しているか確認
lsof -i :8080

# 環境変数を設定
export FIRESTORE_EMULATOR_HOST=localhost:8080
export GCP_PROJECT=demo-test

# firebase.jsonが存在するか確認
cat firebase.json
```

### マイグレーションでエラーが発生

```bash
# ログを確認
python scripts/migrate_parent_documents.py --execute 2>&1 | tee migration.log

# バックアップから復元が必要な場合
gcloud firestore import gs://carewell-automation-backup/[BACKUP_PATH] \
  --database=carewell-native

# ロールバック
python scripts/rollback_parent_documents.py --confirm
```

## 📚 関連ドキュメント

- [タスクドキュメント](.kiro/specs/firestore-schema-improvement/tasks.md)
- [要件定義](.kiro/specs/firestore-schema-improvement/requirements.md)
- [技術設計](.kiro/specs/firestore-schema-improvement/design.md)
- [CI/CDワークフローガイド](docs/ci-cd-workflow-guide.md)

## 🙋 質問・サポート

- Spec-driven開発の詳細: `CLAUDE.md`を参照
- Kiroコマンド: `/kiro:spec-status firestore-schema-improvement`で進捗確認
- GitHub Issues: 問題・質問はIssueで管理

---

**次のステップ**: Task 2.1の実装開始

```bash
# 1. テストファイルを開く
code tests/unit/test_firestore_service.py

# 2. TODOコメントを実装に置き換える
# 3. テストを実行
pytest tests/unit/test_firestore_service.py -v

# 4. Redになることを確認（テストが失敗する）
# 5. src/firestore_service.pyを実装してGreenにする
```
