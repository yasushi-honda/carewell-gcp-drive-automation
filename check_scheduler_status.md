# Cloud Scheduler Status Check Guide

## carewell-class01-task01 の確認手順

### 1. Cloud Scheduler ジョブステータス

**URL**: https://console.cloud.google.com/cloudscheduler?project=carewell-automation

**確認項目**:
- ✅ State: `ENABLED` か？
- ✅ Last Run: 最新の実行時刻
- ✅ Status: `Success` (緑色) か？
- ❌ エラーがある場合は赤色で表示される

---

### 2. Cloud Scheduler ログ

**URL**: https://console.cloud.google.com/logs/query?project=carewell-automation

**クエリ**:
```
resource.type="cloud_scheduler_job"
AND resource.labels.job_id="carewell-class01-task01"
AND resource.labels.location="asia-northeast1"
```

**確認項目**:
- ✅ HTTP Status Code: `200` (正常)
- ❌ `4xx`, `5xx`: エラー
- 最新のログエントリの内容

---

### 3. Cloud Run Function ログ

**URL**: https://console.cloud.google.com/logs/query?project=carewell-automation

**クエリ**:
```
resource.type="cloud_run_revision"
AND resource.labels.service_name="carewell-file-collector"
AND severity>=WARNING
timestamp>="2025-11-05T00:00:00Z"
```

**確認項目**:
- ✅ エラーログが少ない（エラー率 < 5%）
- ❌ "Failed to update task document": Firestore操作失敗
- ❌ "Timeout": タイムアウトエラー
- ❌ "Duplicate": 重複検出エラー

---

### 4. Dashboard での視覚確認

**URL**: https://carewell-automation.web.app/

**確認項目**:
- ✅ クラス01 課題① のデータが表示されているか
- ✅ 最新の提出日時が正しいか
- ✅ ファイル数が正しいか
- ❌ 重複データがないか
- ❌ 欠損データがないか

---

## 問題がある場合の診断フロー

### ケース1: Cloud Scheduler ジョブが `FAILED` 状態

**原因候補**:
- Cloud Run Functionへのリクエストタイムアウト
- Cloud Run Functionが起動していない
- 認証エラー

**確認方法**:
```
# Cloud Run Functionのステータス確認
https://console.cloud.google.com/run/detail/asia-northeast1/carewell-file-collector?project=carewell-automation
```

---

### ケース2: HTTP Status Code が 5xx

**原因候補**:
- Cloud Run Function内部エラー
- Firestore接続エラー
- Drive API エラー

**確認方法**:
Cloud Run Functionログでスタックトレースを確認

---

### ケース3: HTTP Status Code が 4xx

**原因候補**:
- リクエストパラメータ不正
- 認証エラー
- Cloud Scheduler設定エラー

**確認方法**:
Cloud Schedulerジョブ設定を確認（特に `task_pattern` パラメータ）

---

### ケース4: 成功しているがDashboardにデータがない

**原因候補**:
- Firestore書き込み失敗
- データベース名が間違っている（`carewell-native` 以外）
- コレクションパスが間違っている

**確認方法**:
```
# Firestoreコンソールで直接確認
https://console.cloud.google.com/firestore/databases/carewell-native/data/submissions?project=carewell-automation
```

---

## 正常な状態の例

### Cloud Scheduler ログ（正常）
```json
{
  "insertId": "...",
  "jsonPayload": {
    "targetType": "HTTP",
    "url": "https://carewell-file-collector-...",
    "status": "200 OK"
  },
  "resource": {
    "type": "cloud_scheduler_job",
    "labels": {
      "job_id": "carewell-class01-task01",
      "location": "asia-northeast1",
      "project_id": "carewell-automation"
    }
  },
  "timestamp": "2025-11-05T08:45:00.123Z",
  "severity": "INFO"
}
```

### Cloud Run Function ログ（正常）
```
INFO: Processing request for class01 task01
INFO: Found 5 new files to download
INFO: Successfully uploaded file to Drive: file1.pdf
INFO: Successfully recorded upload to Firestore
INFO: Updated task document with file_count: 5
INFO: Request completed successfully
```

---

## チェックリスト

実行前に以下を確認してください：

- [ ] Cloud Scheduler ジョブが `ENABLED` 状態
- [ ] 最新のログに `200 OK` が記録されている
- [ ] Cloud Run Function ログにエラーがない
- [ ] Dashboard にデータが表示されている
- [ ] Firestore `carewell-native` データベースにデータが存在する
- [ ] `task_pattern` パラメータが正しく設定されている

---

## トラブルシューティング連絡先

問題が解決しない場合は、以下のドキュメントを参照：
- `docs/CLASS01_TIMEOUT_ANALYSIS.md` (タイムアウト関連)
- `docs/incident_response_lessons.md` (過去のインシデント)
- `.kiro/specs/firestore-schema-improvement/design.md` (Firestore設計)
