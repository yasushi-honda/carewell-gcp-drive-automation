# Firestore Schema Improvement 運用手順書

## 目次

1. [概要](#概要)
2. [日常運用](#日常運用)
3. [新しいクラス/タスクの追加](#新しいクラスタスクの追加)
4. [エラー調査](#エラー調査)
5. [緊急対応](#緊急対応)
6. [定期メンテナンス](#定期メンテナンス)
7. [FAQ](#faq)

---

## 概要

本ドキュメントは、Firestore Schema Improvementの日常運用に関する手順書です。運用担当者が参照し、システムの正常性を維持するために必要な作業を記載しています。

### 対象読者

- システム運用担当者
- 開発チームメンバー
- インシデント対応担当者

### 前提知識

- 基本的なFirestoreの知識
- Cloud Run / Cloud Schedulerの基礎知識
- Bashコマンドラインの基本操作
- GCPコンソールの基本操作

---

## 日常運用

### 1. file_count不整合の確認と修正

file_countの不整合は、システムの正常性を示す重要な指標です。定期的に確認し、必要に応じて修正します。

#### 実行頻度

- **推奨**: 週1回（月曜日午前など）
- **必須**: マイグレーション/デプロイ後24時間以内

#### 手順

**ステップ1: 環境設定**

```bash
# GCPプロジェクト設定
export GOOGLE_CLOUD_PROJECT="carewell-automation"
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/.config/gcloud/application_default_credentials.json"

# 作業ディレクトリに移動
cd /path/to/carewell-gcp-drive-automation
```

**ステップ2: 不整合チェック（Dry-run）**

```bash
# 全体の不整合をチェック
python scripts/fix_file_count.py --dry-run
```

**出力例（正常時）:**

```
============================================================
DRY RUN MODE (--execute to fix)
============================================================

📚 Processing class: 令和7年度 デジタル中核人材養成研修 №01
  ✅ OK: 課題① - file_count=15 (accurate)
  ✅ OK: 課題② - file_count=8 (accurate)

📚 Processing class: 令和7年度 デジタル中核人材養成研修 №02
  ✅ OK: 課題① - file_count=20 (accurate)
  ✅ OK: 課題② - file_count=12 (accurate)

============================================================
FIX FILE_COUNT SUMMARY
============================================================

Mode: DRY RUN (--execute to fix)
Total Classes: 2
Total Tasks Processed: 4
Parent Documents Checked: 4
Mismatches Found: 0
Errors: 0
Success: ✅ Yes

✅ All file_count values are accurate!
```

**出力例（不整合あり）:**

```
============================================================
DRY RUN MODE (--execute to fix)
============================================================

📚 Processing class: 令和7年度 デジタル中核人材養成研修 №01
  🔍 Mismatch detected in 課題①: stored=15, actual=17, diff=+2
  ✅ OK: 課題② - file_count=8 (accurate)

============================================================
FIX FILE_COUNT SUMMARY
============================================================

Mode: DRY RUN (--execute to fix)
Total Classes: 2
Total Tasks Processed: 4
Parent Documents Checked: 4
Mismatches Found: 1
Errors: 0
Success: ✅ Yes

📊 FILE_COUNT MISMATCHES:

  令和7年度 デジタル中核人材養成研修 №01/課題①:
    Stored:  15
    Actual:  17
    Diff:    +2

💡 To fix mismatches, run with --execute flag
```

**ステップ3: 不整合の原因分析**

不整合が検出された場合、以下を確認：

1. **最近のデプロイやマイグレーション**:
   - マイグレーション中のファイルアップロードがあったか
   - デプロイ時にエラーログはないか

2. **手動でのドキュメント編集**:
   - Firestoreコンソールで誰かがドキュメントを手動編集したか

3. **システムエラー**:
   - Cloud Runログでエラーが発生していないか
   - Firestoreへの接続問題はなかったか

**ステップ4: 不整合の修正**

原因を特定し、問題がないことを確認したら修正を実行：

```bash
# 不整合を修正（全体）
python scripts/fix_file_count.py --execute
```

**特定クラス/タスクのみ修正する場合:**

```bash
# 特定クラスのみ
python scripts/fix_file_count.py --execute \
  --class-name "令和7年度 デジタル中核人材養成研修 №01"

# 特定タスクのみ
python scripts/fix_file_count.py --execute \
  --class-name "令和7年度 デジタル中核人材養成研修 №01" \
  --task-id "課題①"
```

**ステップ5: 修正結果の確認**

```
============================================================
FIX MODE - UPDATING FILE_COUNT
============================================================

📚 Processing class: 令和7年度 デジタル中核人材養成研修 №01
  ✅ Fixed 課題①: 15 → 17 (diff=+2)

============================================================
FIX FILE_COUNT SUMMARY
============================================================

Mode: EXECUTION
Total Classes: 2
Total Tasks Processed: 4
Parent Documents Checked: 4
Mismatches Found: 1
Documents Fixed: 1
Errors: 0
Success: ✅ Yes
```

**ステップ6: 記録と報告**

- ✅ 不整合の内容（クラス名、タスクID、差分）を記録
- ✅ 修正実行日時を記録
- ✅ 原因が不明な場合は、チームに報告

---

### 2. バリデーション実行

マイグレーション後や定期的な健全性チェックとして、バリデーションを実行します。

#### 実行頻度

- **必須**: マイグレーション/デプロイ後24時間以内
- **推奨**: 月1回（月初など）

#### 手順

```bash
# バリデーションのみ実行
python scripts/migrate_parent_documents.py --validate-only
```

**出力例（正常時）:**

```
============================================================
VALIDATING MIGRATION
============================================================

  ✅ OK: 令和7年度 デジタル中核人材養成研修 №01/課題① - count=17
  ✅ OK: 令和7年度 デジタル中核人材養成研修 №01/課題② - count=8
  ✅ OK: 令和7年度 デジタル中核人材養成研修 №02/課題① - count=20
  ✅ OK: 令和7年度 デジタル中核人材養成研修 №02/課題② - count=12

============================================================
VALIDATION SUMMARY
============================================================

Total Parent Documents Checked: 4
Mismatches Found: 0
Validation ✅ PASSED
```

**出力例（不整合あり）:**

```
============================================================
VALIDATING MIGRATION
============================================================

  ❌ Mismatch: 令和7年度 デジタル中核人材養成研修 №01/課題① - stored=15, actual=17
  ✅ OK: 令和7年度 デジタル中核人材養成研修 №01/課題② - count=8

============================================================
VALIDATION SUMMARY
============================================================

Total Parent Documents Checked: 4
Mismatches Found: 1
Validation ❌ FAILED

⚠️  FILE_COUNT MISMATCHES:

  令和7年度 デジタル中核人材養成研修 №01/課題①:
    Stored:  15
    Actual:  17
    Diff:    +2

💡 Run scripts/fix_file_count.py to fix mismatches
```

不整合が見つかった場合は、[file_count不整合の確認と修正](#1-file_count不整合の確認と修正)の手順に従って対応します。

---

## 新しいクラス/タスクの追加

新しい研修クラスや課題が追加される場合の手順です。

### 前提条件

- 新しいクラス名/タスクIDが確定している
- Google Driveに対応するフォルダが作成されている

### 手順

#### ステップ1: classes.pyの更新

```bash
# ファイルを編集
vim src/config/classes.py
```

**編集例（新しいクラスを追加）:**

```python
# src/config/classes.py

KNOWN_CLASSES = [
    "令和7年度 デジタル中核人材養成研修 №01",
    "令和7年度 デジタル中核人材養成研修 №02",
    "令和8年度 デジタル中核人材養成研修 №01",  # ← 追加
]

KNOWN_TASK_IDS = [
    "課題①",
    "課題②",
    "課題③",
    # 必要に応じて新しいタスクIDを追加
]
```

#### ステップ2: 変更をコミット

```bash
# 変更を確認
git diff src/config/classes.py

# コミット
git add src/config/classes.py
git commit -m "config: Add new class '令和8年度 デジタル中核人材養成研修 №01'"

# プッシュ
git push origin main
```

#### ステップ3: デプロイ

GitHub Actionsで自動デプロイされることを確認します。

```bash
# GitHub Actionsの実行状況を確認
gh run list --limit 5

# 最新のrunを監視
gh run watch
```

#### ステップ4: マイグレーション実行（本番環境）

新しいクラス/タスクに既存データがある場合、マイグレーションを実行します。

```bash
# Staging環境で確認
python scripts/migrate_parent_documents.py --dry-run

# 問題なければ本番実行
python scripts/migrate_parent_documents.py --execute
```

**注意:** 既存データがない場合（新規クラス/タスク）、マイグレーションは不要です。ファイルアップロード時に親ドキュメントが自動作成されます。

#### ステップ5: 動作確認

1. **ファイルアップロードテスト**
   - 新しいクラス/タスクに対して手動でファイルアップロードを実行
   - Firestoreコンソールで親ドキュメントが作成されていることを確認

2. **file_countの確認**
   ```bash
   python scripts/fix_file_count.py --dry-run \
     --class-name "令和8年度 デジタル中核人材養成研修 №01"
   ```

3. **記録**
   - 追加日時、担当者、確認結果を記録

---

## エラー調査

システムでエラーが発生した場合の調査手順です。

### 1. Cloud Runログの確認

#### ログビューア（GCPコンソール）を使用

1. **GCPコンソール** → **Cloud Run** → `carewell-file-collector`
2. **ログ**タブをクリック
3. **重大度**でフィルタ（ERROR, CRITICAL）

#### gcloudコマンドを使用

```bash
# 最近のエラーログを取得（過去1時間）
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  severity>=ERROR" \
  --limit 50 \
  --format json \
  --freshness 1h

# 特定のエラーメッセージで検索
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  textPayload:\"Failed to update task document\"" \
  --limit 20
```

#### よくあるエラーパターン

**パターン1: Firestore接続エラー**

```
ERROR: Failed to update task document: 503 Service Unavailable
```

**対応:**
- Firestoreのステータスを確認: https://status.cloud.google.com/
- 一時的な問題の場合は自動回復を待つ
- 継続する場合はGCPサポートに連絡

**パターン2: 権限エラー**

```
ERROR: 403 Missing or insufficient permissions
```

**対応:**
1. サービスアカウントの権限を確認
   ```bash
   gcloud projects get-iam-policy carewell-automation \
     --flatten="bindings[].members" \
     --filter="bindings.members:serviceAccount:YOUR_SA@PROJECT.iam.gserviceaccount.com"
   ```

2. 必要な権限を付与
   ```bash
   gcloud projects add-iam-policy-binding carewell-automation \
     --member="serviceAccount:YOUR_SA@PROJECT.iam.gserviceaccount.com" \
     --role="roles/datastore.user"
   ```

**パターン3: file_count更新エラー**

```
ERROR: Failed to update task document 令和7年度 デジタル中核人材養成研修 №01/課題①: DEADLINE_EXCEEDED
```

**対応:**
- タイムアウト設定を確認
- Firestore負荷を確認（Cloud Consoleで確認）
- 不整合がある場合は`fix_file_count.py`で修正

---

### 2. Firestoreコンソールでの確認

#### 手順

1. **GCPコンソール** → **Firestore** → **データ**
2. データベース: `carewell-native`を選択
3. 該当するクラスコレクションを展開
4. タスクドキュメントを確認

#### 確認ポイント

- ✅ 親ドキュメントが存在するか
- ✅ `file_count`フィールドが存在するか
- ✅ `created_at`, `last_updated`タイムスタンプが適切か
- ✅ サブコレクション`documents`が存在するか
- ✅ サブコレクションのドキュメント数と`file_count`が一致するか

---

### 3. アプリケーションログの確認

FirestoreServiceのログを確認します。

```bash
# FirestoreService関連のログを確認
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  textPayload:\"firestore_service\"" \
  --limit 50 \
  --format json

# 特定クラス/タスクのログを確認
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  textPayload:\"令和7年度 デジタル中核人材養成研修 №01\" AND \
  textPayload:\"課題①\"" \
  --limit 20
```

---

## 緊急対応

### 1. 大規模な不整合が発生した場合

#### 症状

- 多数のタスクでfile_countが不正確
- バリデーションで大量の不一致が報告される

#### 対応手順

**ステップ1: 緊急度の評価**

- **高**: ユーザーに影響がある（ダッシュボードの数値が不正確など）
  → 即時対応

- **中**: システム内部の不整合のみ
  → 計画的に対応（営業時間外など）

**ステップ2: 全体の不整合を確認**

```bash
python scripts/fix_file_count.py --dry-run > mismatch_report_$(date +%Y%m%d_%H%M%S).txt
```

**ステップ3: チームに連絡**

- Slackなどで関係者に通知
- 不整合の規模（影響範囲）を報告

**ステップ4: 修正実行**

```bash
# 全体を一括修正
python scripts/fix_file_count.py --execute
```

**ステップ5: 修正結果の確認**

```bash
# バリデーション実行
python scripts/migrate_parent_documents.py --validate-only
```

**ステップ6: 原因調査**

- Cloud Runログでエラーを確認
- デプロイ履歴を確認
- 最近のマイグレーション/メンテナンス作業を確認

---

### 2. マイグレーションが失敗した場合

#### 症状

- マイグレーション実行中にエラーが発生
- `Success: ❌ No`が表示される

#### 対応手順

**ステップ1: エラー内容の確認**

```bash
# エラーログを保存
python scripts/migrate_parent_documents.py --execute 2>&1 | tee migration_error_$(date +%Y%m%d_%H%M%S).log
```

**ステップ2: 部分的な成功を確認**

マイグレーションは部分的に成功している可能性があります。

```bash
# バリデーションで現状を確認
python scripts/migrate_parent_documents.py --validate-only
```

**ステップ3: ロールバック（必要な場合）**

マイグレーションが中途半端な状態の場合、ロールバックを検討：

```bash
# プレビュー
python scripts/rollback_parent_documents.py

# 実行（慎重に）
python scripts/rollback_parent_documents.py --confirm
```

**ステップ4: 原因修正後に再実行**

エラー原因を修正してから、再度マイグレーションを実行：

```bash
# Dry-runで確認
python scripts/migrate_parent_documents.py --dry-run

# 実行
python scripts/migrate_parent_documents.py --execute
```

---

### 3. システムが完全に停止した場合

#### 症状

- Cloud Runサービスが応答しない
- ファイルアップロードが全て失敗

#### 対応手順

**ステップ1: Cloud Runサービスの状態確認**

```bash
# サービスの状態確認
gcloud run services describe carewell-file-collector \
  --region asia-northeast1 \
  --project carewell-automation

# 最近のリビジョンを確認
gcloud run revisions list \
  --service carewell-file-collector \
  --region asia-northeast1 \
  --project carewell-automation
```

**ステップ2: ロールバック（前のリビジョンに戻す）**

```bash
# 前のリビジョンに切り替え
gcloud run services update-traffic carewell-file-collector \
  --to-revisions PREVIOUS_REVISION=100 \
  --region asia-northeast1 \
  --project carewell-automation
```

**ステップ3: 緊急連絡**

- 開発チームに連絡
- ユーザーへの影響を評価
- 必要に応じてステータスページを更新

**ステップ4: ログ分析**

```bash
# 直近のエラーログを確認
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  severity>=ERROR" \
  --limit 100 \
  --format json > emergency_logs_$(date +%Y%m%d_%H%M%S).json
```

---

## 定期メンテナンス

### 月次メンテナンス

#### 実施内容

1. **file_count不整合チェック**
   ```bash
   python scripts/fix_file_count.py --dry-run
   ```

2. **バリデーション実行**
   ```bash
   python scripts/migrate_parent_documents.py --validate-only
   ```

3. **ログレビュー**
   - 過去1ヶ月間のエラーログを確認
   - 頻発するエラーパターンを特定

4. **レポート作成**
   - file_count不整合の発生回数
   - エラー発生件数と内容
   - システム稼働率

#### チェックリスト

- [ ] file_count不整合チェック実行
- [ ] バリデーション実行
- [ ] エラーログレビュー
- [ ] システム稼働率確認
- [ ] レポート作成・共有
- [ ] 次月の改善提案作成

---

### 四半期メンテナンス

#### 実施内容

1. **Firestoreのパフォーマンスレビュー**
   - Cloud Consoleでクエリパフォーマンスを確認
   - インデックス最適化の検討

2. **バックアップ確認**
   ```bash
   # Firestoreのエクスポート状態を確認
   gcloud firestore operations list --project carewell-automation
   ```

3. **セキュリティレビュー**
   - サービスアカウントの権限確認
   - Firestoreセキュリティルールの確認

4. **ドキュメント更新**
   - 運用手順書の見直し
   - 新しい知見の追加

#### チェックリスト

- [ ] Firestoreパフォーマンスレビュー
- [ ] バックアップ状態確認
- [ ] セキュリティレビュー
- [ ] ドキュメント更新
- [ ] 改善提案まとめ

---

## FAQ

### Q1: file_countが実際より少ない場合、どうすればいいですか？

**A:** file_countが実際のドキュメント数より少ない場合は、以下の手順で修正します：

```bash
# 不整合を確認
python scripts/fix_file_count.py --dry-run

# 修正実行
python scripts/fix_file_count.py --execute
```

この不整合は、以下の原因で発生する可能性があります：
- 親ドキュメント更新時のエラー
- マイグレーション中の新規アップロード
- システム障害

---

### Q2: 新しいクラスを追加したが、マイグレーションでスキップされます

**A:** 新しいクラスが`src/config/classes.py`に追加されているか確認してください：

```python
# src/config/classes.py

KNOWN_CLASSES = [
    "令和7年度 デジタル中核人材養成研修 №01",
    "令和7年度 デジタル中核人材養成研修 №02",
    "新しいクラス名",  # ← 追加されていますか？
]
```

追加後、コミットしてデプロイしてから、再度マイグレーションを実行してください。

---

### Q3: マイグレーション後、アップロードが遅くなった気がします

**A:** 親ドキュメントの更新が追加されたため、若干の遅延は正常です。ただし、以下を確認してください：

1. **パフォーマンステスト結果**: インテグレーションテストでは500ms以下を確認済み
2. **実際の遅延時間**: Cloud Runログでレスポンスタイムを確認
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND \
     httpRequest.latency>1s" \
     --limit 20
   ```

明らかに遅延が大きい（1秒以上）場合は、開発チームに報告してください。

---

### Q4: ロールバックを実行すると、ファイルデータも削除されますか？

**A:** いいえ、ロールバックは親ドキュメントのみを削除します。サブコレクション（`documents/`）とファイルドキュメントは保持されます。

```bash
# プレビューで確認できます
python scripts/rollback_parent_documents.py

# 出力:
#   🔍 Would delete 課題①: file_count=15 (subcollections preserved)
#                                          ^^^^^^^^^^^^^^^^^^^^^^
```

---

### Q5: Firestore Emulatorでテストする方法は？

**A:** ローカルでテストする場合は、Firestore Emulatorを使用できます：

```bash
# 1. エミュレーター起動
gcloud emulators firestore start --host-port=localhost:8080 &

# 2. 環境変数設定
export FIRESTORE_EMULATOR_HOST="localhost:8080"

# 3. テスト実行
pytest tests/integration/ -v
```

CI/CD（GitHub Actions）では自動的にエミュレーターが起動されます。

---

### Q6: 親ドキュメントが作成されない場合は？

**A:** 以下を確認してください：

1. **Fail-open戦略**: 親ドキュメント更新に失敗してもファイルドキュメントは作成されます
2. **ログ確認**: エラーログで`Failed to update task document`を検索
3. **権限確認**: Firestoreへの書き込み権限があるか確認
4. **手動修正**: マイグレーションスクリプトで後から作成可能
   ```bash
   python scripts/migrate_parent_documents.py --execute
   ```

---

### Q7: file_countが増えすぎている場合は？

**A:** file_countが実際より多い場合は、重複アップロードやシステムエラーの可能性があります：

1. **サブコレクションを確認**:
   - Firestoreコンソールで実際のドキュメント数を確認
   - 重複ドキュメントがないか確認

2. **修正実行**:
   ```bash
   python scripts/fix_file_count.py --execute
   ```

3. **原因調査**:
   - 重複チェックロジックが正常に動作しているか確認
   - `check_already_uploaded()`のログを確認

---

### Q8: 本番環境でマイグレーションを実行する前の確認事項は？

**A:** 以下のチェックリストを使用してください：

**事前確認:**
- [ ] Firestoreバックアップが取得されている
- [ ] Stagingでマイグレーションが成功している
- [ ] Dry-runで影響範囲を確認済み
- [ ] メンテナンス時間帯（低トラフィック時）に実行予定
- [ ] ロールバック手順を理解している
- [ ] チームメンバーが待機している

**実行時:**
- [ ] Dry-run実行して最終確認
- [ ] 実行コマンドを記録
- [ ] ログをリアルタイムで監視

**実行後:**
- [ ] バリデーション実行
- [ ] file_count不整合チェック
- [ ] アプリケーション動作確認
- [ ] 24時間後に再度確認

---

### Q9: classes.pyを更新したのに、マイグレーションで反映されません

**A:** 以下を確認してください：

1. **デプロイ状態**: GitHub Actionsで最新コードがデプロイされているか確認
   ```bash
   gh run list --limit 5
   ```

2. **ローカル実行の場合**: 最新コードをpull
   ```bash
   git pull origin main
   ```

3. **Pythonパス**: スクリプトが正しい`src/config/classes.py`を読み込んでいるか確認
   ```bash
   python -c "import sys; sys.path.insert(0, 'src'); from config.classes import KNOWN_CLASSES; print(KNOWN_CLASSES)"
   ```

---

### Q10: 緊急時の連絡先は？

**A:** 以下の順序で連絡してください：

1. **開発チームSlack**: `#carewell-automation` チャンネル
2. **オンコール担当者**: （連絡先を記載）
3. **エスカレーション**: （マネージャー連絡先を記載）

緊急度レベル:
- **P0 (Critical)**: システム停止、データ損失のリスク → 即時対応
- **P1 (High)**: 大規模な不整合、機能不全 → 2時間以内
- **P2 (Medium)**: 部分的な不整合、パフォーマンス低下 → 24時間以内
- **P3 (Low)**: 軽微な不整合、非緊急の改善 → 次回メンテナンス時

---

## 付録

### A. よく使うコマンド一覧

```bash
# file_count不整合チェック
python scripts/fix_file_count.py --dry-run

# file_count修正
python scripts/fix_file_count.py --execute

# バリデーション
python scripts/migrate_parent_documents.py --validate-only

# マイグレーション（Dry-run）
python scripts/migrate_parent_documents.py --dry-run

# マイグレーション（実行）
python scripts/migrate_parent_documents.py --execute

# ロールバック（プレビュー）
python scripts/rollback_parent_documents.py

# ロールバック（実行）
python scripts/rollback_parent_documents.py --confirm

# Cloud Runログ確認
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  severity>=ERROR" --limit 50

# GitHub Actions監視
gh run list --limit 5
gh run watch
```

---

### B. メンテナンスカレンダーテンプレート

| 頻度 | 実施内容 | 担当者 | 次回実施予定 | ステータス |
|------|---------|--------|------------|-----------|
| 週次 | file_count不整合チェック | | | |
| 月次 | 月次メンテナンス（バリデーション、ログレビュー） | | | |
| 四半期 | 四半期メンテナンス（パフォーマンスレビュー、ドキュメント更新） | | | |

---

### C. エスカレーションフロー

```
インシデント発生
    ↓
初動対応（運用担当者）
    ↓
【P0/P1】即座にSlackで通知 → オンコール担当者が対応
【P2/P3】Issueを作成 → 計画的に対応
    ↓
解決 → ポストモーテム作成（P0/P1の場合）
```

---

## 変更履歴

| 日付 | バージョン | 変更内容 | 担当者 |
|------|-----------|---------|--------|
| 2025-01-10 | 1.0 | 初版作成 | AI Assistant (Claude) |

---

## フィードバック

本運用手順書に関する質問、提案、改善案は、GitHubのIssueまたはSlackの`#carewell-automation`チャンネルでお願いします。

**リポジトリ:** `carewell-gcp-drive-automation`
**ドキュメントパス:** `docs/operations-guide.md`
