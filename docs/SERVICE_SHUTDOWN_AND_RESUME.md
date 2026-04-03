# サービス停止・再開手順

## 停止日: 2026-04-03

## 停止理由
課金完全停止（年度区切り）。来年度に再開可能な状態で保存。

---

## 停止したリソース一覧

### 1. Cloud Scheduler（25ジョブ → 全てPAUSED）

| ジョブ名 | 元のスケジュール | 状態 |
|---------|----------------|------|
| carewell-class01-task01 | 0,30 * * * * | PAUSED |
| carewell-class01-task02 | 5,35 * * * * | PAUSED |
| carewell-class02-task01 | 10,40 * * * * | PAUSED |
| carewell-class02-task02 | 15,45 * * * * | PAUSED |
| carewell-class03-task01 | 20,50 * * * * | PAUSED |
| carewell-class03-task02 | 25,55 * * * * | PAUSED |
| carewell-class04-task01 | 0,30 * * * * | PAUSED |
| carewell-class04-task02 | 5,35 * * * * | PAUSED |
| carewell-class05-task01 | 10,40 * * * * | PAUSED |
| carewell-class05-task02 | 15,45 * * * * | PAUSED |
| carewell-class08-task01 | 20,50 * * * * | PAUSED |
| carewell-class08-task02 | 25,55 * * * * | PAUSED |
| carewell-class09-task01 | 0,30 * * * * | PAUSED |
| carewell-class09-task02 | 5,35 * * * * | PAUSED |
| carewell-class10-task01 | 10,40 * * * * | PAUSED |
| carewell-class10-task02 | 15,45 * * * * | PAUSED |
| carewell-automation-pattern1 | */30 * * * * | PAUSED |
| carewell-automation-pattern2 | 5,35 * * * * | PAUSED |
| carewell-automation-pattern3 | 10,40 * * * * | PAUSED |
| carewell-automation-pattern4 | 15,45 * * * * | PAUSED |
| carewell-automation-pattern5 | 20,50 * * * * | PAUSED |
| carewell-automation-pattern8 | 25,55 * * * * | PAUSED |
| carewell-automation-pattern9 | 30,0 * * * * | PAUSED |
| carewell-automation-pattern10 | 3,33 * * * * | PAUSED |
| carewell-student-sync-daily | 0 17 * * * | PAUSED |

### 2. Cloud Run（2サービス → 変更なし）
- `carewell-file-collector`: min-instances=0（元から）。リクエストなしで課金ゼロ。
- `carewell-automation`（レガシー）: 同上。

### 3. GitHub Actions（5ワークフロー → 全て無効化）
- Deploy to Cloud Run Functions → **disabled**
- Deploy Carewell Dashboard to Firebase Hosting → **disabled**
- Firestore Migration → **disabled**
- Post-Deployment Monitoring → **disabled**
- Run Tests → **disabled**
- pages-build-deployment → active（GitHub Pages、影響なし）

### 4. Artifact Registry
- `carewell-functions` リポジトリ: latestタグのイメージのみ保持、古いイメージ削除済み

### 5. 変更なし（データ保持）
- **Firestore** (`carewell-native`): データそのまま保持。読み書きがないためストレージ課金のみ（数円/月）
- **Firebase Hosting** (`carewell-automation.web.app`): 無料枠内。Dashboard閲覧可能
- **Secret Manager**: 2シークレット保持（$0.12/月）
- **Workload Identity Federation**: 設定保持（課金なし）

---

## 再開手順（来年度）

### Step 1: GitHub Actions ワークフロー有効化

```bash
# リポジトリ管理者アカウントで実行
gh auth switch --user yasushi-honda
gh workflow enable "Deploy to Cloud Run Functions"
gh workflow enable "Deploy Carewell Dashboard to Firebase Hosting"
gh workflow enable "Firestore Migration"
gh workflow enable "Post-Deployment Monitoring"
gh workflow enable "Run Tests"
```

### Step 2: Cloud Scheduler ジョブ再開

```bash
# gcloud設定切替
gcloud config configurations activate carewell-automation

# 全ジョブ再開
for job in $(gcloud scheduler jobs list --location=asia-northeast1 --format="value(name.basename())"); do
  gcloud scheduler jobs resume "$job" --location=asia-northeast1
done

# 確認
gcloud scheduler jobs list --location=asia-northeast1 --format="table(name.basename(),state)"
```

### Step 3: 動作確認

1. Cloud Schedulerが次のスケジュールで実行されることを確認
2. Cloud Runログでリクエスト処理を確認:
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=carewell-file-collector" --limit 10
   ```
3. Dashboard（https://carewell-automation.web.app/）でデータ更新を確認

### Step 4: 必要に応じて

- **新年度のクラスに対応**: Cloud Schedulerジョブの追加・更新
- **Carewell Webサービスの認証情報更新**: Secret Managerの値を更新
- **コードの更新が必要な場合**: `git push origin main` でGitHub Actionsが自動デプロイ

---

## 月額課金見込み（停止後）

| リソース | 月額見込み |
|---------|----------|
| Firestore ストレージ | ~数円 |
| Secret Manager | ~$0.12 |
| Firebase Hosting | $0（無料枠） |
| Cloud Run | $0（リクエストなし） |
| Cloud Scheduler | $0（PAUSED） |
| Artifact Registry | ~数円（1イメージ） |
| **合計** | **~$0.20/月** |
