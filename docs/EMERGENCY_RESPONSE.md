# 緊急時対応マニュアル

**対象**: 本番環境でトラブルが発生した場合の対応手順
**最終更新**: 2025-11-18

---

## 🚨 緊急時の基本原則

### 優先順位

1. **🔴 サービス復旧** - 最優先
2. **🟡 原因調査** - 復旧後
3. **🟢 恒久対策** - 調査後

### 行動指針

- ✅ **落ち着いて対応** - パニックは禁物
- ✅ **ドキュメント確認** - 過去の類似ケースを確認
- ✅ **ログを残す** - 対応内容を記録
- ❌ **憶測で対応しない** - 必ずログ/データで確認

---

## 📋 緊急度判定

| 緊急度 | 症状 | 対応時間 |
|--------|------|---------|
| 🔴 Critical | Dashboard完全停止、全てのScheduler Job失敗 | 即座 |
| 🟡 High | 一部のScheduler Job失敗、データ同期遅延 | 1時間以内 |
| 🟢 Medium | 表示の不具合、一部データ欠損 | 1営業日以内 |
| ⚪ Low | 軽微なUI不具合 | 通常対応 |

---

## 🔴 Critical: Dashboard 完全停止

### 症状

- https://carewell-automation.web.app/ にアクセスできない
- 500エラーまたは白い画面

### 対応手順

#### Step 1: GitHub Actions 確認（2分）

```bash
# ブラウザで確認
https://github.com/yasushi-honda/carewell-gcp-drive-automation/actions

# 最新のDeployワークフローが失敗していないか確認
```

**失敗している場合**:
- エラーログを確認
- 前回成功したコミットに`git revert`を検討

---

#### Step 2: Firebase Hosting 確認（3分）

```bash
# Firebase Console で確認
https://console.firebase.google.com/project/carewell-automation/hosting

# デプロイ履歴を確認
# - 最新デプロイの状態
# - ロールバック可能か
```

**ロールバックが必要な場合**:
```bash
# Firebase CLI でロールバック
firebase hosting:rollback

# または GitHub で前回成功したコミットに戻す
git revert HEAD
git push origin main
```

---

#### Step 3: Firestore Security Rules 確認（5分）

```bash
# Firestore Console で確認
https://console.firebase.google.com/project/carewell-automation/firestore/rules

# Security Rules が誤って更新されていないか確認
```

**修正が必要な場合**:
```bash
# GitHub で firestore.rules を確認
cat dashboard/firestore.rules

# 必要に応じて修正 → Push → GitHub Actions で自動デプロイ
```

---

### 復旧確認

✅ Dashboard にアクセスできる
✅ クラス一覧が表示される
✅ 学生詳細ページが表示される

---

## 🟡 High: Cloud Scheduler Job 失敗

### 症状

- `/admin/sync-students-from-sheets` が失敗している
- 学生データが同期されない

### 対応手順

#### Step 1: Cloud Scheduler ログ確認（2分）

```bash
gcloud logging read "resource.type=cloud_scheduler_job AND
  resource.labels.job_id=carewell-student-sync-daily AND
  severity>=ERROR" \
  --limit=10 \
  --freshness=1d
```

**確認項目**:
- HTTP Status Code
- エラーメッセージ

---

#### Step 2: Cloud Run ログ確認（3分）

```bash
gcloud logging read "resource.type=cloud_run_revision AND
  resource.labels.service_name=carewell-file-collector AND
  severity>=ERROR" \
  --limit=20 \
  --freshness=1d
```

**確認項目**:
- エラーの種類（Google Sheets読み取りエラー、Firestore書き込みエラー）
- スタックトレース

---

#### Step 3: 手動実行でテスト（5分）

```bash
TOKEN=$(gcloud auth print-identity-token)

curl -X POST \
  "https://carewell-file-collector-imczapxkba-an.a.run.app/admin/sync-students-from-sheets" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"
```

**成功する場合**:
- Cloud Scheduler の設定問題（Service Account権限など）

**失敗する場合**:
- Cloud Run の問題（コードエラー、Google Sheets接続エラー）

---

#### Step 4: 原因別対応

##### 原因A: Google Sheets 読み取りエラー

```bash
# Google Sheets を手動で確認
# スプレッドシート ID: 1AQ12-h3n_NmN2kWxi4Z_g354X0wmUyMKAPeAsXJwu_w
# シート名: 統合_受講者リスト

# Service Account の権限確認
# carewell-automation-sa@carewell-automation.iam.gserviceaccount.com
# にスプレッドシートの閲覧権限があるか確認
```

---

##### 原因B: Firestore 書き込みエラー

```bash
# Firestore Console で確認
https://console.firebase.google.com/project/carewell-automation/firestore

# データベース名が carewell-native であることを確認
# インデックスエラーがないか確認
```

**インデックスエラーの場合**:
```bash
# firestore.indexes.json を確認
cat firestore.indexes.json

# 不足しているインデックスを追加
# → Git commit → GitHub Actions で自動デプロイ
```

---

##### 原因C: Service Account 権限不足

```bash
# Cloud Run Invoker 権限の確認
gcloud run services get-iam-policy carewell-file-collector \
  --region=asia-northeast1 | grep carewell-automation-sa

# 権限がない場合は付与
gcloud run services add-iam-policy-binding carewell-file-collector \
  --region=asia-northeast1 \
  --member="serviceAccount:carewell-automation-sa@carewell-automation.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

---

#### Step 5: Job の一時停止（必要に応じて）

```bash
# 繰り返し失敗してアラートが鳴り続ける場合
gcloud scheduler jobs pause carewell-student-sync-daily \
  --location=asia-northeast1

# 修正後に再開
gcloud scheduler jobs resume carewell-student-sync-daily \
  --location=asia-northeast1
```

---

### 復旧確認

✅ Cloud Scheduler Job が成功する
✅ Cloud Run ログに `status: "success"` が記録される
✅ Firestore に学生データが保存される（`last_updated` が最新）
✅ Dashboard に学生情報が表示される

---

## 🟡 High: ファイル収集 Job 失敗

### 症状

- `carewell-class01-task01` などのScheduler Jobが失敗
- 提出ファイルが収集されない

### 対応手順

#### Step 1: Cloud Scheduler ログ確認（2分）

```bash
# 特定のJobのログを確認（例: class01-task01）
gcloud logging read "resource.type=cloud_scheduler_job AND
  resource.labels.job_id=carewell-class01-task01 AND
  severity>=ERROR" \
  --limit=10 \
  --freshness=1d
```

---

#### Step 2: Cloud Run ログ確認（3分）

```bash
gcloud logging read "resource.type=cloud_run_revision AND
  resource.labels.service_name=carewell-file-collector AND
  textPayload=~\"class01\" AND
  severity>=ERROR" \
  --limit=20 \
  --freshness=1d
```

**よくあるエラー**:
- Playwright timeout（ページ読み込みタイムアウト）
- Iframe context error（フレーム切り替えエラー）
- ASP.NET pagination delay（ページネーション待機エラー）

参照: [docs/common-mistakes.md](common-mistakes.md) - インシデント #5, #9, #11, #12

---

#### Step 3: Carewell Webサービス確認（5分）

```bash
# ブラウザで手動アクセス
# Carewell Webサービスにログインできるか確認
# - サイトがダウンしていないか
# - ログインページの構造が変わっていないか
```

**サイト構造が変わっている場合**:
- DevTools で要素を確認
- `src/scraper.py` のセレクタを修正
- 参照: インシデント #11（パラメータ名の変更）

---

#### Step 4: タイムアウト設定確認（3分）

```bash
# Cloud Scheduler のタイムアウト確認
gcloud scheduler jobs describe carewell-class01-task01 \
  --location=asia-northeast1 | grep attemptDeadline

# Cloud Run のタイムアウト確認
gcloud run services describe carewell-file-collector \
  --region=asia-northeast1 | grep timeout
```

**タイムアウトが短い場合**:
- Cloud Scheduler: `--attempt-deadline=1800s`（30分）
- Cloud Run: `--timeout=1800s`（30分）

参照: インシデント #7（タイムアウト設定）

---

### 復旧確認

✅ Cloud Scheduler Job が成功する
✅ Cloud Run ログに `File collection completed` が記録される
✅ Google Drive にファイルが保存される
✅ Firestore にメタデータが記録される

---

## 🟢 Medium: Dashboard にデータが表示されない

### 症状

- Dashboard は動作するが、学生データやファイル情報が表示されない

### 対応手順

#### Step 1: Firestore データ確認（2分）

```bash
# Firestore Console で確認
https://console.firebase.google.com/project/carewell-automation/firestore/databases/carewell-native/data

# 確認項目:
# - students コレクションにデータが存在するか
# - submissions コレクションにデータが存在するか
# - last_updated フィールドが最新か
```

---

#### Step 2: ブラウザキャッシュクリア（1分）

```bash
# ハードリフレッシュ
# Mac: Cmd + Shift + R
# Windows: Ctrl + Shift + R

# または
# ブラウザのキャッシュとCookieを削除
```

---

#### Step 3: Dashboard デプロイ確認（3分）

```bash
# GitHub Actions の最新デプロイを確認
https://github.com/yasushi-honda/carewell-gcp-drive-automation/actions

# デプロイが成功しているか確認
# - ワークフローの状態
# - デプロイ時刻
```

---

#### Step 4: Firestore Security Rules 確認（5分）

```bash
# Firestore Console で Security Rules を確認
https://console.firebase.google.com/project/carewell-automation/firestore/rules

# 確認項目:
# - allow read: true が設定されているか（本番環境では適切な権限に修正推奨）
# - ルールが正しくデプロイされているか
```

---

### 復旧確認

✅ Dashboard にアクセスできる
✅ クラス一覧が表示される
✅ 学生一覧が表示される
✅ 学生詳細ページでクラス情報が表示される

---

## 🟢 Medium: 新しいクラスが Dashboard ホームページに表示されない

### 症状

- 学生詳細ページには新しいクラスが表示される
- ホームページのクラス一覧カードには表示されない

### 原因

Dashboard の2つの異なるクラス表示実装による。

参照: [docs/DASHBOARD_CLASS_DISPLAY.md](DASHBOARD_CLASS_DISPLAY.md)

---

### 対応手順

#### Step 1: `KNOWN_CLASSES` に追加（5分）

**ファイル**: `dashboard/src/config/classes.ts`

```typescript
export const KNOWN_CLASSES = [
  '令和7年度 デジタル中核人材養成研修 №01',
  '令和7年度 デジタル中核人材養成研修 №02',
  '令和7年度 デジタル中核人材養成研修 №03',
  '令和7年度 デジタル中核人材養成研修 №04',
  '令和7年度 デジタル中核人材養成研修 №05',
  '令和7年度 デジタル中核人材養成研修 №08',
  '令和7年度 デジタル中核人材養成研修 №09',
  '令和7年度 デジタル中核人材養成研修 №10',  // ← 追加
];

export const CLASS_NAME_MAPPING: Record<string, string> = {
  '令和7年度 デジタル中核人材養成研修 №01': 'No1',
  // ... 既存のマッピング
  '令和7年度 デジタル中核人材養成研修 №10': 'No10',  // ← 追加
};
```

---

#### Step 2: Git commit & Push（2分）

```bash
git add dashboard/src/config/classes.ts
git commit -m "feat: Add class №10 to dashboard class list"
git push origin main
```

---

#### Step 3: GitHub Actions デプロイ確認（5分）

```bash
# GitHub Actions を確認
https://github.com/yasushi-honda/carewell-gcp-drive-automation/actions

# デプロイ完了まで約5～10分待つ
```

---

#### Step 4: Dashboard 確認（1分）

```bash
# Dashboard を開く
https://carewell-automation.web.app/

# ハードリフレッシュ（Cmd+Shift+R / Ctrl+Shift+R）
# 新しいクラスが表示されることを確認
```

---

### 復旧確認

✅ Dashboard ホームページに新しいクラスのカードが表示される
✅ カードをクリックするとグループページに遷移できる

---

## 📞 エスカレーション

### 以下の場合はエスカレーションを検討

- 上記の対応手順で復旧しない
- 原因が不明
- データ破損の可能性がある
- セキュリティインシデントの可能性がある

### エスカレーション先

**技術責任者**: （連絡先を記入）

**GitHub Issue**: https://github.com/yasushi-honda/carewell-gcp-drive-automation/issues

---

## 📝 対応後の記録

### 必ず記録すること

1. **インシデント発生日時**
2. **症状**
3. **原因**
4. **対応内容**
5. **復旧日時**
6. **再発防止策**

### 記録場所

**ドキュメント**: `docs/common-mistakes.md` に追加

**フォーマット**:
```markdown
| # | インシデント | 日付 | 影響 | 重要な教訓 |
|---|------------|------|------|-----------|
| 15 | （インシデント名） | 2025-XX-XX | （影響範囲） | ✅ （教訓） |
```

---

## 🛠️ よく使うコマンド集

### Cloud Logging

```bash
# Cloud Scheduler ログ
gcloud logging read "resource.type=cloud_scheduler_job" --limit=50

# Cloud Run ログ
gcloud logging read "resource.type=cloud_run_revision AND
  resource.labels.service_name=carewell-file-collector" --limit=50

# エラーログのみ
gcloud logging read "severity>=ERROR" --limit=50 --freshness=1d
```

---

### Cloud Scheduler

```bash
# Job 一覧
gcloud scheduler jobs list --location=asia-northeast1

# Job 詳細
gcloud scheduler jobs describe JOB_NAME --location=asia-northeast1

# 手動実行
gcloud scheduler jobs run JOB_NAME --location=asia-northeast1

# 一時停止
gcloud scheduler jobs pause JOB_NAME --location=asia-northeast1

# 再開
gcloud scheduler jobs resume JOB_NAME --location=asia-northeast1
```

---

### Cloud Run

```bash
# サービス一覧
gcloud run services list --region=asia-northeast1

# サービス詳細
gcloud run services describe carewell-file-collector --region=asia-northeast1

# リビジョン一覧
gcloud run revisions list --service=carewell-file-collector --region=asia-northeast1

# トラフィック確認
gcloud run services describe carewell-file-collector --region=asia-northeast1 \
  --format="value(spec.traffic)"
```

---

### Firestore

```bash
# データベース一覧
gcloud firestore databases list

# インデックス一覧
gcloud firestore indexes composite list --database=carewell-native
```

---

## 🎓 過去のインシデントから学ぶ

### よくあるパターン

1. **ドキュメントを読まずにコーディング** → インシデント #1, #4, #10, #12
2. **検証なしの仮定** → インシデント #9, #10, #11
3. **複数箇所の設定見落とし** → インシデント #7
4. **IaCの不徹底** → インシデント #13
5. **デプロイ後の検証不足** → インシデント #8
6. **複数の類似機能の混同** → インシデント #14

詳細: [docs/common-mistakes.md](common-mistakes.md)

---

## まとめ

### 緊急時の心得

1. **📖 ドキュメントを確認** - 過去の類似ケースを探す
2. **🔍 ログで検証** - 憶測せず、実際のエラーを確認
3. **🛠️ 段階的に対応** - 一度に複数の変更をしない
4. **📝 記録を残す** - 対応内容を必ずドキュメント化

### トラブルシューティングの基本フロー

```
症状確認 → ログ確認 → 原因特定 → 対応実施 → 復旧確認 → 記録作成
```

---

**作成日**: 2025-11-18
**作成者**: Claude Code AI Agent
**対象**: 緊急時対応担当者
