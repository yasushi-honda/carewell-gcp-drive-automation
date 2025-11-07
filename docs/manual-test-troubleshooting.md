# 手動テスト実行トラブルシューティングガイド

**作成日**: 2025-11-07
**対象**: Cloud Scheduler停止中の手動テスト実行

---

## 🚨 重要: Cloud Scheduler一部停止中

**現状**: `carewell-class01-task01` のみ停止中のため、**№01 課題① のテストは手動実行が必須**です。

**稼働中**: 他の13ジョブ（class01-task02, class02～09）は自動実行継続中です。

**注意**: №01 課題① の自動実行を待つことはできません。

---

## ✅ 手動テスト実行コマンド (基本)

### 標準コマンド

```bash
curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X POST https://carewell-file-collector-imczapxkba-an.a.run.app \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -d '{
  "class_name": "令和7年度 デジタル中核人材養成研修 №01",
  "task_id": "課題①",
  "task_pattern": "課題①業務分析　※～11/3〆切",
  "drive_folder_id": "1gxt-OVloMfJWi73Yjm4v5bjupKL25Pag",
  "spreadsheet_id": "1R1bsr24uyFf67p7_0I0yUA47ap5uIrJE7n89A9NbRYI"
}'
```

---

## ❌ 失敗パターンと解決方法

### 失敗パターン 1: 認証エラー

**症状**:
```
ERROR: (gcloud.auth.print-identity-token) You do not currently have an active account selected.
```

**原因**: gcloud認証が切れている

**解決方法**:
```bash
# ステップ1: 認証状態確認
gcloud auth list

# ステップ2: 認証が切れている場合
gcloud auth login

# ステップ3: プロジェクト設定確認
gcloud config set project carewell-automation

# ステップ4: 再度テスト実行
curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X POST https://carewell-file-collector-imczapxkba-an.a.run.app \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -d '{
  "class_name": "令和7年度 デジタル中核人材養成研修 №01",
  "task_id": "課題①",
  "task_pattern": "課題①業務分析　※～11/3〆切",
  "drive_folder_id": "1gxt-OVloMfJWi73Yjm4v5bjupKL25Pag",
  "spreadsheet_id": "1R1bsr24uyFf67p7_0I0yUA47ap5uIrJE7n89A9NbRYI"
}'
```

---

### 失敗パターン 2: JSONエスケープエラー

**症状**:
```
curl: (3) URL using bad/illegal format or missing URL
```

**原因**: シェルがJSON内のクォートを誤解釈している

**解決方法 (Option A: ファイル経由)**:
```bash
# ステップ1: JSONファイル作成
cat > /tmp/test_payload.json <<'EOF'
{
  "class_name": "令和7年度 デジタル中核人材養成研修 №01",
  "task_id": "課題①",
  "task_pattern": "課題①業務分析　※～11/3〆切",
  "drive_folder_id": "1gxt-OVloMfJWi73Yjm4v5bjupKL25Pag",
  "spreadsheet_id": "1R1bsr24uyFf67p7_0I0yUA47ap5uIrJE7n89A9NbRYI"
}
EOF

# ステップ2: ファイルから読み込んでリクエスト
curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X POST https://carewell-file-collector-imczapxkba-an.a.run.app \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -d @/tmp/test_payload.json
```

**解決方法 (Option B: 環境変数経由)**:
```bash
# ステップ1: 認証トークン取得
TOKEN=$(gcloud auth print-identity-token)

# ステップ2: curlコマンド実行
curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X POST https://carewell-file-collector-imczapxkba-an.a.run.app \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
  "class_name": "令和7年度 デジタル中核人材養成研修 №01",
  "task_id": "課題①",
  "task_pattern": "課題①業務分析　※～11/3〆切",
  "drive_folder_id": "1gxt-OVloMfJWi73Yjm4v5bjupKL25Pag",
  "spreadsheet_id": "1R1bsr24uyFf67p7_0I0yUA47ap5uIrJE7n89A9NbRYI"
}'
```

---

### 失敗パターン 3: HTTPステータスコード 401/403

**症状**:
```
HTTP_CODE:401
または
HTTP_CODE:403
```

**原因**:
- 401: 認証トークンが無効
- 403: 権限不足

**解決方法**:
```bash
# ステップ1: 現在のアカウント確認
gcloud auth list

# ステップ2: プロジェクトの確認
gcloud config get-value project

# ステップ3: 権限確認
gcloud projects get-iam-policy carewell-automation \
  --flatten="bindings[].members" \
  --filter="bindings.members:$(gcloud config get-value account)"

# ステップ4: 認証トークン再取得
gcloud auth print-identity-token

# ステップ5: 再度テスト実行
```

---

### 失敗パターン 4: HTTPステータスコード 500/502/504

**症状**:
```
HTTP_CODE:500  # Internal Server Error
HTTP_CODE:502  # Bad Gateway
HTTP_CODE:504  # Gateway Timeout
```

**原因**:
- 500: Cloud Run内部エラー
- 502: Cloud Runが起動していない
- 504: タイムアウト (25分以上処理中)

**解決方法**:

#### 500エラー
```bash
# ステップ1: Cloud Runログ確認
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector" \
  --limit 50 --format json | \
  jq -r '.[] | select(.severity=="ERROR") | .textPayload'

# ステップ2: エラー内容に応じて対処
# - コードエラーの場合 → 修正してデプロイ
# - 一時的なエラーの場合 → 再実行
```

#### 502エラー
```bash
# ステップ1: Cloud Run稼働状況確認
gcloud run services describe carewell-file-collector \
  --region=asia-northeast1 \
  --format='value(status.conditions)'

# ステップ2: 最新リビジョン確認
gcloud run revisions list --service=carewell-file-collector \
  --region=asia-northeast1 --limit=1

# ステップ3: しばらく待ってから再実行 (コールドスタート対策)
sleep 30
# 再度テスト実行
```

#### 504エラー
```bash
# ステップ1: 処理中かどうか確認
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector" \
  --limit 10 --format json | \
  jq -r '.[] | select(.textPayload) | .textPayload' | head -20

# ステップ2: Cloud Runタイムアウト設定確認
gcloud run services describe carewell-file-collector \
  --region=asia-northeast1 \
  --format='value(spec.template.spec.timeoutSeconds)'

# 期待値: 1500 (25分)
# 実際値が異なる場合 → timeout設定を修正
```

---

### 失敗パターン 5: Bash拒否 (User Rejected)

**症状**:
```
The user doesn't want to proceed with this tool use.
```

**原因**: AIエージェントが重要な状態（Cloud Scheduler停止中）を見落として自動実行を待とうとした

**解決方法**:
```bash
# Memory Fileを更新済みのため、次回セッションでは発生しません
# 現在のセッションでは、手動で実行してください

curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X POST https://carewell-file-collector-imczapxkba-an.a.run.app \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -d @/tmp/test_payload.json 2>&1 | head -30
```

---

## ✅ 成功パターン

### 正常な応答

```
{"message": "File collection started for class..."}
HTTP_CODE:200
```

または

```
{"message": "File collection completed successfully..."}
HTTP_CODE:200
```

### 成功後の確認手順

```bash
# ステップ1: ログ確認 (2分待機)
sleep 120

# ステップ2: STEP 1ログ確認
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  resource.labels.revision_name=carewell-file-collector-00223-6mx" \
  --limit 500 --format json | \
  jq -r '.[] | select(.textPayload) | .textPayload' | \
  grep -E "\[STEP 1|Frame refreshed|Pagination control\]"

# ステップ3: 最終結果確認
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  resource.labels.revision_name=carewell-file-collector-00223-6mx" \
  --limit 100 --format json | \
  jq -r '.[] | select(.textPayload and (.textPayload | contains("File collection completed"))) | .textPayload'
```

---

## 🔧 デバッグコマンド集

### 現在のリビジョン確認
```bash
gcloud run revisions list --service=carewell-file-collector \
  --region=asia-northeast1 --limit=3 \
  --format="table(metadata.name,status.conditions[0].status,metadata.creationTimestamp)"
```

### トラフィックルーティング確認
```bash
gcloud run services describe carewell-file-collector \
  --region=asia-northeast1 \
  --format='value(status.traffic[0].revisionName,status.traffic[0].percent)'
```

### Cloud Scheduler状態確認
```bash
gcloud scheduler jobs list --location=asia-northeast1 \
  --format="table(name,state,lastAttemptTime)"
```

### 最新ログ確認 (全リビジョン)
```bash
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector" \
  --limit 20 --format json | \
  jq -r '.[] | "\(.timestamp) [\(.resource.labels.revision_name)] \(.textPayload // .jsonPayload.message)"'
```

---

## 📌 チェックリスト

### テスト実行前
- [ ] gcloud認証確認 (`gcloud auth list`)
- [ ] プロジェクト設定確認 (`gcloud config get-value project`)
- [ ] 最新リビジョン確認 (`gcloud run revisions list --limit=1`)
- [ ] トラフィックルーティング確認 (`gcloud run services describe`)

### テスト実行
- [ ] 手動テストコマンド実行
- [ ] HTTP 200レスポンス確認
- [ ] 2分待機 (ログ出力待ち)

### テスト後
- [ ] [STEP 1 START]ログ確認
- [ ] [Frame refreshed]ログ確認
- [ ] [Pagination control found]ログ確認
- [ ] "File collection completed"ログ確認
- [ ] processed/failed/skipped件数確認

---

## 🆘 それでも失敗する場合

1. **最新のドキュメント確認**:
   - `docs/test-analysis-2025-11-07-revision-00223-*.md`
   - `.serena/memories/system_current_state.md`

2. **過去の類似インシデント検索**:
   ```bash
   grep -r "similar_error_message" docs/incident-*.md
   ```

3. **Memory Files確認**:
   ```bash
   ls -la .serena/memories/
   ```

4. **GitHub Issues確認**:
   ```bash
   gh issue list --label="bug,timeout"
   ```

---

**最終更新**: 2025-11-07 23:00 JST
**メンテナー**: AI Agent (Claude Code)
