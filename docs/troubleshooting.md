# 🔧 Carewell Automation - トラブルシューティングガイド

**問題解決の体系的なアプローチ**

---

## 📋 目次

1. [問題発生時の基本フロー](#問題発生時の基本フロー)
2. [症状別トラブルシューティング](#症状別トラブルシューティング)
3. [よくある問題と解決方法](#よくある問題と解決方法)
4. [診断コマンド集](#診断コマンド集)
5. [エスカレーション基準](#エスカレーション基準)

---

## 問題発生時の基本フロー

### 🚨 最初にやること（絶対に守る）

```mermaid
flowchart TD
    START([🚨 問題発生！])
    STOP([❌ STOP!<br/>ドキュメントを読め])

    READ_CRITICAL{📘 CLAUDE.md<br/>CRITICAL 読んだ？}
    READ_MISTAKES{📘 Common Mistakes<br/>確認した？}
    CHECK_MEMORY{📘 Memory files<br/>確認した？}
    SEARCH_PAST{🔍 過去の類似<br/>インシデント検索した？}

    IDENTIFY[✅ 根本原因を特定]
    SNAPSHOT[📸 現状スナップショット]
    PLAN[📋 段階的計画<br/>10フェーズ等]
    VERIFY[✓ 各フェーズで検証]
    DOCUMENT[📝 教訓を記録]
    END([✅ 完了])

    START --> READ_CRITICAL
    READ_CRITICAL -->|NO| STOP
    READ_CRITICAL -->|YES| READ_MISTAKES
    READ_MISTAKES -->|NO| STOP
    READ_MISTAKES -->|YES| CHECK_MEMORY
    CHECK_MEMORY -->|NO| STOP
    CHECK_MEMORY -->|YES| SEARCH_PAST
    SEARCH_PAST -->|NO| STOP
    SEARCH_PAST -->|YES| IDENTIFY

    IDENTIFY --> SNAPSHOT
    SNAPSHOT --> PLAN
    PLAN --> VERIFY
    VERIFY --> DOCUMENT
    DOCUMENT --> END

    style STOP fill:#ff6b6b,color:#fff
    style READ_CRITICAL fill:#ffd93d
    style READ_MISTAKES fill:#ffd93d
    style CHECK_MEMORY fill:#ffd93d
    style SEARCH_PAST fill:#ffd93d
    style END fill:#6bcf7f,color:#fff
```

### 必須チェックリスト（調査前）

- [ ] **CLAUDE.md Lines 11-42**: CRITICAL セクション確認
- [ ] **CLAUDE.md Lines 224-308**: Common Mistakes 確認
- [ ] **Memory files**: incident_response_lessons 確認
- [ ] **過去インシデント**: `git log --grep="keyword"` で検索
- [ ] **設計ドキュメント**: Steering Document 確認

**❌ これらをスキップして調査開始すると、同じ失敗を繰り返す！**

---

## 症状別トラブルシューティング

### 診断フローチャート

```mermaid
flowchart TD
    START([問題発生])

    Q1{Dashboard に<br/>表示されない？}
    Q2{Cloud Scheduler<br/>失敗？}
    Q3{ファイル取得<br/>失敗？}
    Q4{Firestore に<br/>保存されない？}
    Q5{重複ファイル<br/>ダウンロード？}

    A1[📘 CLAUDE.md #4<br/>Dashboard Schema Mismatch<br/>docs/incident-2025-11-05]
    A2[📊 Cloud Run ログ確認<br/>Memory: suggested_commands]
    A3[📘 CLAUDE.md #5<br/>Playwright API エラー<br/>docs/incident-2025-11-05]
    A4[📘 CLAUDE.md #2<br/>task_pattern 確認<br/>docs/incident-2025-11-05]
    A5[📘 CLAUDE.md #3<br/>Collection Path<br/>composite_key 確認]

    GENERAL[一般的なデバッグ<br/>↓ 次セクション参照]

    START --> Q1
    Q1 -->|YES| A1
    Q1 -->|NO| Q2
    Q2 -->|YES| A2
    Q2 -->|NO| Q3
    Q3 -->|YES| A3
    Q3 -->|NO| Q4
    Q4 -->|YES| A4
    Q4 -->|NO| Q5
    Q5 -->|YES| A5
    Q5 -->|NO| GENERAL

    style A1 fill:#fff3cd
    style A2 fill:#fff3cd
    style A3 fill:#fff3cd
    style A4 fill:#fff3cd
    style A5 fill:#fff3cd
```

---

## よくある問題と解決方法

### 1. Dashboard にデータが表示されない

**症状**:
- Dashboard https://carewell-automation.web.app/ でクラス・課題が空表示
- Firestore にはデータがある

**診断手順**:

```bash
# 1. Firestore データ確認
python3 scripts/check-all-classes-firestore.py

# 2. Dashboard がどのパスを読んでいるか確認
# dashboard/src/composables/useFirestore.ts:129 をチェック
```

**よくある原因**:

#### A. スキーマ不一致（CLAUDE.md #4）

```typescript
// ❌ 間違い: 旧スキーマ
const docRef = doc(db, className, taskId);

// ✅ 正しい: 新スキーマ
const docRef = doc(db, "submissions", className, "tasks", taskId);
```

**解決方法**: `docs/incident-2025-11-05-schema-migration-and-playwright-fix.md` 参照

#### B. Firestore Security Rules

```javascript
// firestore.rules を確認
allow read: if request.auth != null;  // 認証が必要な場合
```

**解決方法**: Security Rules を一時的に緩和してテスト

---

### 2. Cloud Scheduler が失敗する

**症状**:
- Cloud Scheduler の `status.code` が 0 以外
- `lastAttemptTime` が更新されない

**診断手順**:

```bash
# 1. Scheduler 状態確認
gcloud scheduler jobs describe carewell-class01-task01 \
  --location=asia-northeast1 \
  --format="value(state,lastAttemptTime,status.code,status.message)"

# 2. Cloud Run ログ確認（最重要）
gcloud logging read "resource.type=cloud_run_revision AND
  resource.labels.service_name=carewell-file-collector AND
  timestamp>=\"$(date -u -d '1 hour ago' '+%Y-%m-%dT%H:%M:%SZ')\"" \
  --limit 50 --format json
```

**よくある原因**:

#### A. タイムアウト (deadline exceeded)

```
status.code: 4
status.message: "Deadline Exceeded"
```

**解決方法**:
- Deadline を延長: `docs/CLASS01_TIMEOUT_ANALYSIS.md` 参照
- 現在の設定: 25分 (1500秒)

#### B. Cloud Run エラー

```
status.code: 14
status.message: "Unavailable"
```

**解決方法**:
- Cloud Run ログでスタックトレース確認
- Playwright エラーの可能性 → 次セクション参照

---

### 3. ファイル取得が失敗する

**症状**:
- Cloud Run ログに `Empty download info returned`
- 特定の学生だけスキップされる

**診断手順**:

```bash
# ログから Playwright エラーを抽出
gcloud logging read "resource.type=cloud_run_revision AND
  resource.labels.service_name=carewell-file-collector AND
  textPayload=~\"playwright\"" \
  --limit 100 --format json | \
  jq -r '.[] | .textPayload' | grep -i error
```

**よくある原因**:

#### A. Playwright API エラー（CLAUDE.md #5）

```python
# ❌ 間違い: 存在しないメソッド
link.wait_for_element_state("visible", timeout=10000)

# ✅ 正しい: Auto-waiting に任せる
link.click()  # 自動で待機
```

**解決方法**: `docs/incident-2025-11-05-schema-migration-and-playwright-fix.md` 参照

#### B. HTML 構造の変更

Carewell Web のHTML構造が変更された場合、セレクタが機能しなくなる。

**解決方法**:
- `src/playwright_automation.py` のセレクタを更新
- Phase 6 の動的リンク検出を参照: `docs/phase_6_dynamic_link_detection.md`

---

### 4. Firestore にデータが保存されない

**症状**:
- Cloud Run ログに成功メッセージ
- Firestore にデータがない

**診断手順**:

```bash
# 1. Firestore Database 名確認
grep -r "carewell-native" src/

# 2. Firestore ログ確認
gcloud logging read "resource.type=cloud_run_revision AND
  textPayload=~\"firestore\"" \
  --limit 50 --format json | \
  jq -r '.[] | .textPayload' | grep -i error
```

**よくある原因**:

#### A. Database 名が間違っている（CLAUDE.md #1）

```python
# ❌ 間違い
db = firestore.Client(database="(default)")

# ✅ 正しい
db = firestore.Client(database="carewell-native")
```

**解決方法**: `CLAUDE.md Lines 166-169` 参照

#### B. task_pattern が渡されていない（CLAUDE.md #2）

```python
# ❌ 間違い: task_pattern が欠落
record_upload(class_name, task_id, ...)

# ✅ 正しい: 全パラメータ必須
record_upload(
    class_name=...,
    task_id=...,
    task_pattern=...,  # ← これが必須
    ...
)
```

**解決方法**: Cloud Scheduler の HTTP body に `task_pattern` を追加

---

### 5. 重複ファイルがダウンロードされる

**症状**:
- 同じファイルが何度もダウンロードされる
- `file_count` が異常に増加

**診断手順**:

```bash
# Firestore で重複確認
python3 <<EOF
from google.cloud import firestore
db = firestore.Client(project="carewell-automation", database="carewell-native")
files = db.collection("submissions").document("令和7年度...").collection("tasks").document("課題①").collection("files").stream()
composite_keys = [f.id for f in files]
duplicates = [k for k in composite_keys if composite_keys.count(k) > 1]
print(f"Duplicates: {duplicates}")
EOF
```

**よくある原因**:

#### A. Collection Path が間違っている（CLAUDE.md #3）

```python
# ❌ 間違い: 旧パス
ref = db.collection(class_name).document(task_id).collection("documents")

# ✅ 正しい: 新パス
ref = db.collection("submissions").document(class_name).collection("tasks").document(task_id).collection("files")
```

**解決方法**: `src/firestore_service.py` のパスを修正

---

## 診断コマンド集

### Cloud Run ログ確認（最優先）

```bash
# 直近50件のログ
gcloud logging read "resource.type=cloud_run_revision AND
  resource.labels.service_name=carewell-file-collector" \
  --limit 50 --format json | \
  jq -r '.[] | "\(.timestamp) [\(.severity)] \(.textPayload // .jsonPayload)"'

# エラーログのみ
gcloud logging read "resource.type=cloud_run_revision AND
  resource.labels.service_name=carewell-file-collector AND
  severity>=ERROR" \
  --limit 20 --format json

# 特定時刻以降のログ
gcloud logging read "resource.type=cloud_run_revision AND
  resource.labels.service_name=carewell-file-collector AND
  timestamp>=\"2025-11-05T12:00:00Z\"" \
  --limit 100 --format json
```

### Cloud Scheduler 状態確認

```bash
# 全ジョブの状態確認
gcloud scheduler jobs list --location=asia-northeast1 \
  --format="table(name,schedule,state,lastAttemptTime,status.code)"

# 特定ジョブの詳細
gcloud scheduler jobs describe carewell-class01-task01 \
  --location=asia-northeast1 \
  --format=json | jq '{
    name: .name,
    state: .state,
    schedule: .schedule,
    lastAttemptTime: .lastAttemptTime,
    status: .status,
    httpTarget: .httpTarget
  }'

# HTTP body の確認
gcloud scheduler jobs describe carewell-class01-task01 \
  --location=asia-northeast1 \
  --format="value(httpTarget.body)" | base64 -d | jq .
```

### Dashboard 確認

```bash
# ブラウザで開く
open https://carewell-automation.web.app/

# curlでステータス確認
curl -I https://carewell-automation.web.app/
```

### Firestore 確認スクリプト

```bash
# 全クラス・全課題のデータ状況確認
python3 scripts/check-all-classes-firestore.py

# 特定クラス・課題の詳細確認
python3 <<EOF
from google.cloud import firestore
db = firestore.Client(project="carewell-automation", database="carewell-native")

# 親ドキュメント確認
task_doc = db.collection("submissions").document("令和7年度 デジタル中核人材養成研修 №01").collection("tasks").document("課題①").get()
if task_doc.exists:
    print(f"Task metadata: {task_doc.to_dict()}")

# ファイル数確認
files = list(db.collection("submissions").document("令和7年度 デジタル中核人材養成研修 №01").collection("tasks").document("課題①").collection("files").stream())
print(f"File count: {len(files)}")
EOF
```

---

## エスカレーション基準

### 自己解決可能

以下の場合は、ドキュメントと過去のインシデント記録で解決可能：

- [ ] CLAUDE.md Common Mistakes に類似事例がある
- [ ] Memory files に解決方法が記載されている
- [ ] 過去のインシデント記録に同じ症状がある
- [ ] エラーメッセージが明確（スタックトレースあり）

### エスカレーション必要

以下の場合は、ユーザーに報告・相談が必要：

- [ ] 設計変更が必要（Steering Document の変更）
- [ ] 外部サービス（Carewell Web）の仕様変更
- [ ] セキュリティリスクが発見された
- [ ] データ損失の可能性がある
- [ ] 複数のシステムに影響する

---

## 対応後の必須作業

### ドキュメント化チェックリスト

- [ ] CLAUDE.md の Common Mistakes に追加
- [ ] Memory files 更新（incident_response_lessons）
- [ ] インシデント記録ドキュメント作成（`docs/incident-YYYY-MM-DD-*.md`）
- [ ] Git commit & push
- [ ] 教訓の共有

---

## 関連ドキュメント

### 必読

- **CLAUDE.md Lines 11-42**: CRITICAL セクション
- **CLAUDE.md Lines 81-126**: Incident Response Workflow
- **CLAUDE.md Lines 224-308**: Common Mistakes to Avoid

### 過去のインシデント記録

- **docs/incident-2025-11-05-schema-migration-and-playwright-fix.md**: Dashboard スキーマ移行 + Playwright エラー
- **docs/dashboard-firestore-schema-migration.md**: Dashboard 専用記録
- **docs/CLASS01_TIMEOUT_ANALYSIS.md**: タイムアウト問題分析

### メモリファイル

- **.serena/memories/incident_response_lessons.md**: 教訓とチェックリスト
- **.serena/memories/suggested_commands.md**: 推奨コマンド集
- **.serena/memories/task_completion_checklist.md**: 完了確認チェックリスト

### 設計ドキュメント

- **.kiro/steering/firestore-critical-config.md**: Firestore 公式仕様
- **.kiro/steering/dashboard-workflow.md**: Dashboard 開発ルール
- **.kiro/specs/**: 機能別詳細設計

---

**最終更新**: 2025/11/05
**バージョン**: 1.0
**メンテナー**: Claude Code
