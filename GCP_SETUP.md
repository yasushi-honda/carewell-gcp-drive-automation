# GCP環境セットアップガイド

このドキュメントでは、carewell-gcp-drive-automationのGCP環境セットアップ手順を説明します。

## 前提条件

- GCPプロジェクト: `carewell-automation`
- gcloud CLIがインストール済み
- プロジェクトオーナーまたは十分な権限を持つアカウント

## 1. 初期設定

### プロジェクトの設定

```bash
# プロジェクトを設定
gcloud config set project carewell-automation

# 現在の設定を確認
gcloud config list
```

### リージョンの設定

```bash
# デフォルトリージョンを設定
gcloud config set run/region asia-northeast1
```

## 2. 必要なAPIの有効化

```bash
# すべての必要なAPIを一括有効化
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  firestore.googleapis.com \
  drive.googleapis.com \
  sheets.googleapis.com \
  cloudlogging.googleapis.com
```

### 有効化の確認

```bash
# 有効化されたAPIのリストを確認
gcloud services list --enabled | grep -E "(cloudbuild|run|artifact|secret|firestore|drive|sheets)"
```

## 3. Secret Managerの設定

### シークレットの作成

```bash
# Carewell ユーザーIDの設定
echo -n "YOUR_CAREWELL_USER_ID" | \
  gcloud secrets create carewell-user-id \
    --data-file=- \
    --replication-policy="automatic"

# Carewell パスワードの設定
echo -n "YOUR_CAREWELL_PASSWORD" | \
  gcloud secrets create carewell-password \
    --data-file=- \
    --replication-policy="automatic"
```

### シークレットの確認

```bash
# シークレット一覧を確認
gcloud secrets list

# シークレットの詳細を確認（値は表示されない）
gcloud secrets describe carewell-user-id
gcloud secrets describe carewell-password
```

## 4. Firestoreの設定

### Firestoreデータベースの作成

```bash
# Firestoreをネイティブモードで作成
gcloud firestore databases create \
  --location=asia-northeast1
```

### 作成の確認

```bash
# Firestoreの状態を確認
gcloud firestore databases list
```

**注意:** Firestoreは一度作成すると削除できません。プロジェクト全体を削除する必要があります。

## 5. Artifact Registryの設定

```bash
# Dockerリポジトリの作成
gcloud artifacts repositories create carewell-functions \
  --repository-format=docker \
  --location=asia-northeast1 \
  --description="Docker images for Carewell automation functions"
```

### リポジトリの確認

```bash
gcloud artifacts repositories list
```

## 6. サービスアカウントの設定

### デフォルトCompute Engine サービスアカウントの確認

```bash
# プロジェクト番号を取得
PROJECT_NUMBER=$(gcloud projects describe carewell-automation --format="value(projectNumber)")

# サービスアカウントのメールアドレス
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "Service Account: ${SERVICE_ACCOUNT}"
```

### IAM権限の付与

```bash
# Secret Manager Secret Accessor
gcloud projects add-iam-policy-binding carewell-automation \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"

# Cloud Datastore User (Firestore用)
gcloud projects add-iam-policy-binding carewell-automation \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/datastore.user"

# Service Account Token Creator（ADC用）
gcloud iam service-accounts add-iam-policy-binding ${SERVICE_ACCOUNT} \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/iam.serviceAccountTokenCreator"
```

### 権限の確認

```bash
# 付与された権限を確認
gcloud projects get-iam-policy carewell-automation \
  --flatten="bindings[].members" \
  --filter="bindings.members:${SERVICE_ACCOUNT}"
```

## 7. Google Drive フォルダの準備

### フォルダの作成と共有

1. Google Driveでアップロード先フォルダを作成
2. フォルダを右クリック → 「共有」
3. サービスアカウントのメールアドレスを追加:
   ```
   [PROJECT_NUMBER]-compute@developer.gserviceaccount.com
   ```
4. 権限を「編集者」に設定
5. フォルダIDをメモ（URLから取得）:
   ```
   https://drive.google.com/drive/folders/[THIS_IS_THE_FOLDER_ID]
   ```

## 8. Google Spreadsheetsの準備

### スプレッドシートの作成と共有

1. Google Sheetsで新規スプレッドシートを作成
2. 「共有」をクリック
3. サービスアカウントのメールアドレスを追加:
   ```
   [PROJECT_NUMBER]-compute@developer.gserviceaccount.com
   ```
4. 権限を「編集者」に設定
5. スプレッドシートIDをメモ（URLから取得）:
   ```
   https://docs.google.com/spreadsheets/d/[THIS_IS_THE_SPREADSHEET_ID]/edit
   ```

## 9. Workload Identity Federation（GitHub Actions用）

### Workload Identity Poolの作成

```bash
# Identity Poolの作成
gcloud iam workload-identity-pools create github-actions-pool \
  --location="global" \
  --display-name="GitHub Actions Pool"

# Providerの作成
gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location="global" \
  --workload-identity-pool="github-actions-pool" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository_owner=='YOUR_GITHUB_USERNAME'"
```

**注意:** `YOUR_GITHUB_USERNAME`を実際のGitHubユーザー名に置き換えてください。

### サービスアカウントへの権限付与

```bash
# GitHub ActionsからArtifact Registryへのアクセスを許可
gcloud artifacts repositories add-iam-policy-binding carewell-functions \
  --location=asia-northeast1 \
  --member="principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-actions-pool/subject/repo:YOUR_GITHUB_USERNAME/carewell-gcp-drive-automation:ref:refs/heads/main" \
  --role="roles/artifactregistry.writer"

# GitHub ActionsからCloud Runへのデプロイを許可
gcloud projects add-iam-policy-binding carewell-automation \
  --member="principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-actions-pool/subject/repo:YOUR_GITHUB_USERNAME/carewell-gcp-drive-automation:ref:refs/heads/main" \
  --role="roles/run.admin"
```

### Workload Identity Provider名の取得

```bash
gcloud iam workload-identity-pools providers describe github-provider \
  --location="global" \
  --workload-identity-pool="github-actions-pool" \
  --format="value(name)"
```

この値をGitHub Secretsに`WIF_PROVIDER`として設定します。

## 10. GitHub Secretsの設定

GitHubリポジトリの Settings → Secrets and variables → Actions で以下を設定：

| Secret名 | 値 | 取得方法 |
|---------|-----|---------|
| `WIF_PROVIDER` | `projects/[PROJECT_NUMBER]/locations/global/workloadIdentityPools/github-actions-pool/providers/github-provider` | 上記コマンドで取得 |
| `WIF_SERVICE_ACCOUNT` | `[PROJECT_NUMBER]-compute@developer.gserviceaccount.com` | プロジェクト番号から生成 |
| `GCP_PROJECT_ID` | `carewell-automation` | プロジェクトID |

## 11. 設定の検証

### すべての設定を確認

```bash
# APIの有効化を確認
echo "=== Enabled APIs ==="
gcloud services list --enabled | grep -E "(cloudbuild|run|artifact|secret|firestore|drive|sheets)"

# シークレットを確認
echo "=== Secrets ==="
gcloud secrets list

# Firestoreを確認
echo "=== Firestore ==="
gcloud firestore databases list

# Artifact Registryを確認
echo "=== Artifact Registry ==="
gcloud artifacts repositories list

# IAM権限を確認
echo "=== IAM Permissions ==="
gcloud projects get-iam-policy carewell-automation \
  --flatten="bindings[].members" \
  --filter="bindings.members:${SERVICE_ACCOUNT}" \
  --format="table(bindings.role)"
```

## トラブルシューティング

### API有効化エラー

```
ERROR: (gcloud.services.enable) PERMISSION_DENIED
```

**対処法:** プロジェクトオーナーまたは`Service Usage Admin`ロールが必要です。

### Secret Manager作成エラー

```
ERROR: (gcloud.secrets.create) PERMISSION_DENIED
```

**対処法:** `Secret Manager Admin`ロールが必要です。

### Firestore作成エラー

```
ERROR: Database already exists
```

**対処法:** Firestoreは既に作成されています。再作成は不要です。

### サービスアカウントが見つからない

```
ERROR: Service account does not exist
```

**対処法:** Compute Engine APIが有効化されると自動的に作成されます。

```bash
gcloud services enable compute.googleapis.com
```

## 次のステップ

1. ✅ すべての設定が完了したら`DEPLOYMENT_CHECKLIST.md`を確認
2. ✅ コードをGitHubにプッシュして自動デプロイをトリガー
3. ✅ デプロイ後、テストリクエストを実行

---

**重要な注意事項:**
- Secret Managerのシークレットは一度作成すると、値の更新は可能ですが削除と再作成には注意が必要
- Firestoreは一度作成すると削除できません
- サービスアカウントのメールアドレスは必ずメモしてください
- Google DriveとSheetsへの共有設定を忘れずに行ってください
