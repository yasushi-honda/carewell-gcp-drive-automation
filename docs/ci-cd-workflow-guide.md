# CI/CDワークフローガイド

## 概要

Firestoreスキーマ改善プロジェクトでは、安全で自動化されたCI/CDパイプラインを構築し、手動操作のリスクを最小化します。

## CI/CDパイプライン構成

### 1. テストワークフロー (`.github/workflows/test.yml`)

**トリガー**:
- Pull Requestの作成/更新
- `main`ブランチへのpush
- 手動実行

**実行内容**:
- ✅ ユニットテスト（カバレッジ80%以上）
- ✅ 統合テスト（Firestore Emulator使用）
- ✅ セキュリティスキャン（Trivy）
- ✅ コード品質チェック（Black, isort, flake8, mypy）

**使い方**:
```bash
# ローカルで実行
pip install -r requirements-dev.txt
pytest tests/unit/ -v --cov=src
firebase emulators:start --only firestore &
pytest tests/integration/ -v
```

### 2. マイグレーションワークフロー (`.github/workflows/migration.yml`)

**トリガー**: 手動実行のみ

**実行内容**:

#### Dry-runモード（デフォルト）
1. Firestoreバックアップの確認
2. マイグレーションプレビューの生成
3. 影響範囲レポートの出力

#### Executeモード
1. 本番前バックアップの自動作成
2. マイグレーションの実行
3. 検証（file_count vs 実ドキュメント数）
4. ロールバックスクリプトの生成

**使い方**:

```bash
# Step 1: GitHub Actionsからdry-runを実行
# 1. Actionsタブを開く
# 2. "Firestore Migration"ワークフローを選択
# 3. "Run workflow"をクリック
# 4. Mode: "dry-run", Environment: "staging"を選択
# 5. レポートをダウンロードして確認

# Step 2: レポート確認後、executeモードで実行
# 1. "Run workflow"をクリック
# 2. Mode: "execute", Environment: "staging"を選択
# 3. 完了後、アーティファクトからrollback scriptをダウンロード

# Step 3: 本番環境での実行（ステージング成功後）
# 1. Mode: "execute", Environment: "production"を選択
# 2. 実行を承認（GitHub Environment保護ルールで承認が必要）
```

**安全機能**:
- ✅ 自動バックアップ作成
- ✅ Dry-runモードでのプレビュー
- ✅ 検証ステップによる整合性確認
- ✅ ロールバックスクリプトの自動生成
- ✅ GitHub Environment保護（本番環境）

### 3. デプロイワークフロー (`.github/workflows/deploy.yml`)

**トリガー**:
- `main`ブランチへのpush
- 手動実行（緊急時のみテストスキップ可能）

**実行内容**:
1. テストの実行（ユニット+統合）
2. テスト通過後のみデプロイ実行
3. Docker imageのビルド・push
4. Cloud Runへのデプロイ

**使い方**:

```bash
# 通常フロー（自動）
git push origin main  # テスト通過後に自動デプロイ

# 緊急デプロイ（テストスキップ）
# 1. Actionsタブから"Deploy to Cloud Run Functions"を選択
# 2. "Run workflow"をクリック
# 3. "Skip tests"にチェックを入れる（緊急時のみ）
```

### 4. モニタリングワークフロー (`.github/workflows/monitor.yml`)

**トリガー**: 手動実行のみ

**実行内容**:
- ✅ エラー率の監視（目標: 5%未満）
- ✅ Firestore操作の確認
- ✅ file_countの正確性検証
- ✅ Cloud Schedulerジョブの状態確認
- ✅ モニタリングレポートの生成

**使い方**:

```bash
# デプロイ後に実行
# 1. Actionsタブから"Post-Deployment Monitoring"を選択
# 2. "Run workflow"をクリック
# 3. Monitoring duration: 24（時間）を入力
# 4. レポートをダウンロードして確認

# エラー検出時の対応
# 1. monitoring-report.mdを確認
# 2. migration workflowのアーティファクトからrollback.shをダウンロード
# 3. rollback.shを実行
```

## 推奨実装フロー

### Phase 1: 開発とテスト

```bash
# 1. 新しいブランチを作成
git checkout -b feature/firestore-schema-improvement

# 2. ローカルでテストフレームワークをセットアップ
pip install -r requirements-dev.txt

# 3. TDDでFirestoreServiceを実装
# - tests/unit/test_firestore_service.py を作成
# - src/firestore_service.py を修正
# - pytest tests/unit/ -v --cov=src

# 4. マイグレーションスクリプトを実装
# - scripts/migrate_parent_documents.py を作成
# - scripts/rollback_parent_documents.py を作成
# - scripts/fix_file_count.py を作成

# 5. 統合テストを実装
# - tests/integration/ 配下にテストを作成
# - firebase emulators:start --only firestore
# - pytest tests/integration/ -v

# 6. Pull Requestを作成
git push origin feature/firestore-schema-improvement
# GitHubでPR作成 → テストワークフローが自動実行される
```

### Phase 2: ステージング環境でのマイグレーション

```bash
# 1. PRをマージ（テスト通過後）
# → 自動的にデプロイワークフローが実行される

# 2. マイグレーションのdry-runを実行
# GitHub Actions > Firestore Migration > Run workflow
# - Mode: dry-run
# - Environment: staging
# → レポートを確認

# 3. executeモードで実行
# GitHub Actions > Firestore Migration > Run workflow
# - Mode: execute
# - Environment: staging
# → rollback scriptをダウンロード

# 4. 動作確認
# - test_request.shで統合テスト
# - ダッシュボードで課題数を確認
```

### Phase 3: 本番環境へのマイグレーション

```bash
# 1. マイグレーション前の準備
# - 関係者に通知
# - 実行タイミング決定（平日9:00-12:00推奨）

# 2. 本番マイグレーションのdry-run
# GitHub Actions > Firestore Migration > Run workflow
# - Mode: dry-run
# - Environment: production
# → レポートを確認・承認

# 3. 本番マイグレーション実行
# GitHub Actions > Firestore Migration > Run workflow
# - Mode: execute
# - Environment: production
# - GitHub Environment保護により承認が必要
# → rollback scriptをダウンロード・保管

# 4. モニタリング開始
# GitHub Actions > Post-Deployment Monitoring > Run workflow
# - Duration: 24
# → 1時間ごとに結果を確認

# 5. 24時間後の最終確認
# - エラーゼロを確認
# - file_count正確性を確認
# - 成功レポートを関係者に共有
```

## ロールバック手順

### 自動ロールバック（推奨）

```bash
# 1. migration workflowのアーティファクトからrollback.shをダウンロード
# 2. 実行権限を付与
chmod +x rollback.sh

# 3. 実行
./rollback.sh
```

### 手動ロールバック

```bash
# 1. Cloud Runを旧リビジョンに切り戻し
gcloud run services update-traffic carewell-file-collector \
  --to-revisions PREVIOUS_REVISION=100 \
  --region asia-northeast1

# 2. 親ドキュメントを削除
python scripts/rollback_parent_documents.py --confirm

# 3. 動作確認
./test_request.sh
```

## トラブルシューティング

### テストが失敗する

**原因**: コード変更により既存機能が破壊された

**対応**:
1. ローカルでテストを実行: `pytest tests/unit/ -v`
2. エラーメッセージを確認
3. コードを修正
4. 再度push → CIが自動実行

### マイグレーションでエラーが発生

**原因**: Firestore接続エラー、権限不足、データ不整合

**対応**:
1. エラーログを確認（Actions > Migration workflow > Logs）
2. バックアップから復元が必要か判断
3. 必要に応じてrollback.shを実行
4. 問題を修正後、再度dry-runから実行

### デプロイ後にエラー率が上昇

**原因**: コードのバグ、Firestore設定ミス

**対応**:
1. モニタリングレポートを確認
2. Cloud Runのログを確認
3. ロールバック実行: `./rollback.sh`
4. 問題を修正後、再度テスト→デプロイ

### file_countが不正確

**原因**: 並行アップロード時の競合、親ドキュメント更新失敗

**対応**:
```bash
# 1. 不整合を確認
python scripts/verify_file_count.py

# 2. 修正
python scripts/fix_file_count.py --execute
```

## セキュリティとベストプラクティス

### 1. 本番環境の保護

- ✅ GitHub Environmentで本番環境を保護
- ✅ マイグレーション実行には承認が必要
- ✅ Workload Identity FederationでGCPに認証
- ✅ サービスアカウントに最小権限を付与

### 2. 自動バックアップ

- ✅ マイグレーション前に自動バックアップ作成
- ✅ バックアップの保存場所を記録
- ✅ ロールバックスクリプトに復元手順を含める

### 3. 段階的デリバリー

- ✅ PR時にテスト自動実行
- ✅ ステージング環境で検証
- ✅ 本番環境は承認後のみ
- ✅ 24時間モニタリング

### 4. 可観測性

- ✅ すべての操作をログ記録
- ✅ エラー率を自動監視
- ✅ file_count正確性を定期検証
- ✅ モニタリングレポートを自動生成

## 次のステップ

1. **テストフレームワークのセットアップ**: `pip install -r requirements-dev.txt`
2. **ユニットテストの作成**: `tests/unit/test_firestore_service.py`
3. **FirestoreServiceの実装**: `src/firestore_service.py`の拡張
4. **マイグレーションスクリプトの作成**: `scripts/migrate_parent_documents.py`
5. **PR作成**: テストワークフローが自動実行される

これらのCI/CDパイプラインにより、手動操作を最小化し、安全で確実な実装プロセスを実現します。
