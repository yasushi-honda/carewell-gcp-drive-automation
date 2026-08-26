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

⚠️⚠️ **無条件の一括resumeは絶対に行わないこと**（2026-08-26クロスレビューで発見）。
既存ジョブのmessage-bodyには`class_name`（年度）・`task_pattern`（実際の課題名）・
`drive_folder_id`/`spreadsheet_id`（保存先）がベタ書きされており、これらは**令和7年度用のまま**
resumeしても自動更新されない。無条件で一括resumeすると、令和7年度のclass_nameのままジョブが
稼働し始め、しかもDashboard・保守スクリプトは既に令和8年度側だけを見ているため誤動作が
サイレントに進行する（詳細: `docs/SERVICE_SHUTDOWN_AND_RESUME.md`本ファイル下部
「令和8年度（2026年度）再開ステータス」参照）。

**正しい手順**: ジョブを1件ずつ確認し、令和8年度用に検証済みのmessage-bodyへ更新してから
個別にresumeすること。

```bash
# gcloud設定切替
gcloud config configurations activate carewell-automation

# 現在の状態確認（まずは一覧を見るだけ、resumeしない）
gcloud scheduler jobs list --location=asia-northeast1 --format="table(name.basename(),state)"

# 対象ジョブ1件ごとに、現在のmessage-bodyを確認
JOB_NAME="carewell-classXX-taskXX"  # 対象ジョブ名に置き換える
gcloud scheduler jobs describe "${JOB_NAME}" --location=asia-northeast1 --format json \
  | jq '.httpTarget.body' -r | base64 -d | jq .

# 令和8年度用に検証済みのclass_name/task_pattern/drive_folder_id/spreadsheet_idへ更新
# （詳細手順: docs/cloud-scheduler-operations-guide.md「4. ジョブパラメータの更新」）
gcloud scheduler jobs update http "${JOB_NAME}" \
  --location=asia-northeast1 \
  --message-body='{"class_name":"...","task_id":"...","task_pattern":"...","drive_folder_id":"...","spreadsheet_id":"..."}'

# 更新・検証済みのジョブのみ個別にresume
gcloud scheduler jobs resume "${JOB_NAME}" --location=asia-northeast1
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

---

## 令和8年度（2026年度）再開ステータス

**最終更新**: 2026-08-26（grip + codexによるクロスレビュー実施済み）

### ✅ 完了

- 実機検証: ログインフォーム・ページ構造・ページネーション・件数照合ロジックが2026年現在も変更なく動作することを確認（令和7年度№01の209件を正しく検出・重複判定、ダミーIDによる安全なCloud Run疎通テスト）
- JACCW発行の令和8年度募集要項PDFで、今年度も研修セットは№1〜10の全10セット（構成変更なし）と確認。研修期間2026年9月〜2027年1月、№8=山形県地域限定・他は全国
- 令和8年度コース存在確認: №01〜07・09は課題①がポータル上に既に存在（ダミーID呼び出しで確認）。№08・10は受講申込開始が9/24でまだコース未作成（コードのno-op設計により実害なし）
- `src/config/classes.py` / `dashboard/src/config/classes.ts`: 令和7年度→令和8年度、№06・07追加（全10クラス）に更新
- 各種ドキュメント・保守スクリプトの年度表記更新（既存8クラス分はDrive/Sheets流用可否が未検証のためTODO化・無効化）

### ⚠️ 今回のクロスレビューで発見した既存バグ（年度対応とは無関係）

`scripts/migrate_parent_documents.py` / `rollback_parent_documents.py` / `verify_file_count.py` /
`fix_file_count.py` / `check_duplicates.py` の5スクリプトが、現行の本番書込み先スキーマ
（`submissions/{class_name}/tasks/{task_id}/files/{...}`）ではなく、旧スキーマ
（`{class_name}/{task_id}/documents/{...}`）を対象にしていることを実ファイルで確認。
年度・クラスに関わらず現在のFirestoreデータに対して機能していない可能性が高い。
特に`fix_file_count.py --execute`・`rollback_parent_documents.py`は書込み・削除を伴うため
**修正されるまで実行厳禁**。今回は年度対応のスコープ外として、コード変更はせず各ファイル冒頭に
注記のみ追加した。別途修正タスクとして起票を検討。

### ⬜ 未完了（次回セッション以降）

1. **全10クラス分のDrive/Sheets令和8年度流用可否確認**: 既存8クラスの保存先ID（scripts内にベタ書き）を令和8年度でもそのまま使ってよいか確認。不可の場合は新規作成
2. **№06・07用のGoogle Drive/Sheets新規作成**（そもそも未作成）
3. **№06・07の「課題②」実在確認**（実機テストで確認できたのは課題①のみ）
4. **実際の`task_pattern`文字列の年度別確定**（例:「課題①業務分析　※～11/3〆切」相当の令和8年度版）
5. **Cloud Scheduler**: 既存ジョブのmessage-body個別更新（令和7→令和8、上記Step 2参照）＋№06・07の新規4ジョブ作成。cronスロットは`20,50 * * * *`/`25,55 * * * *`が比較的空き（詳細: `docs/cloud-scheduler-operations-guide.md`付録A）
6. **GitHub Actions 5ワークフローの有効化**
7. **上記「発見した既存バグ」5スクリプトのスキーマ修正**
8. **№08・10**: 9/24以降にポータル上でコースが実際に現れるか再確認（現時点では申込開始日からの推測に過ぎない未検証の仮説）
