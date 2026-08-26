# Student Sync Feature 完全引き継ぎドキュメント

**作成日**: 2025-11-30
**作成者**: Claude Code AI Agent
**対象**: 新規AIエージェント・開発者向け

---

## 目次

1. [機能概要](#機能概要)
2. [システム構成図](#システム構成図)
3. [データフロー図](#データフロー図)
4. [ER図（データ設計）](#er図データ設計)
5. [実装詳細](#実装詳細)
6. [Cloud Scheduler 設定](#cloud-scheduler-設定)
7. [Dashboard 手動同期機能](#dashboard-手動同期機能)
8. [Google Sheets 設定](#google-sheets-設定)
9. [処理フロー図](#処理フロー図)
10. [WBS（作業分解図）](#wbs作業分解図)
11. [ガントチャート](#ガントチャート)
12. [トラブルシューティング](#トラブルシューティング)
13. [改修・拡張ガイド](#改修拡張ガイド)

---

## 機能概要

### 目的

Google Sheets の学生マスターデータを Firestore に同期し、全ての提出ファイルに最新の学生情報を反映する。

### 主要機能

| 機能 | 説明 |
|------|------|
| **学生マスター同期** | Google Sheets → Firestore `students/` コレクション |
| **ファイル Backfill** | `students/` → `files/` 内の非正規化データ更新 |
| **論理削除** | L列「無効」チェックボックスで `status: "inactive"` に設定 |
| **手動同期** | Dashboard 管理者モードから即座に同期実行 |
| **自動同期** | Cloud Scheduler で毎日 JST 02:00 に自動実行 |

### 影響範囲

```
Google Sheets (統合_受講者リスト)
    ↓ 同期
Firestore students/ コレクション
    ↓ Backfill
Firestore files/ コレクション (全クラス・全課題)
    ↓ リアルタイム反映
Dashboard (https://carewell-automation.web.app/)
```

---

## システム構成図

```mermaid
graph TB
    subgraph "Google Cloud Platform"
        subgraph "Cloud Scheduler"
            CS[carewell-student-sync-daily<br/>毎日 JST 02:00]
        end

        subgraph "Cloud Run"
            CR[carewell-file-collector<br/>Python Flask API]
        end

        subgraph "Firestore"
            FS_S[students/ コレクション]
            FS_F[submissions/.../files/ コレクション]
        end
    end

    subgraph "Google Workspace"
        GS[Google Sheets<br/>統合_受講者リスト]
    end

    subgraph "Firebase Hosting"
        DB[Dashboard<br/>Vue.js SPA]
    end

    subgraph "User"
        ADMIN[管理者]
        USER[一般ユーザー]
    end

    CS -->|POST /admin/sync-students-from-sheets<br/>OIDC Auth| CR
    CR -->|Read A:L| GS
    CR -->|Write| FS_S
    CR -->|Write| FS_F

    ADMIN -->|Firebase Login| DB
    DB -->|POST /admin/sync-students-from-sheets<br/>Authorization: Bearer Firebase ID token| CR

    FS_S -->|Real-time Listener| DB
    FS_F -->|Real-time Listener| DB

    USER --> DB
```

---

## データフロー図

```mermaid
sequenceDiagram
    participant GS as Google Sheets
    participant CS as Cloud Scheduler
    participant CR as Cloud Run API
    participant FS as Firestore
    participant DB as Dashboard
    participant Admin as 管理者

    Note over CS,CR: 自動同期 (毎日 JST 02:00)
    CS->>CR: POST /admin/sync-students-from-sheets<br/>{"backfill": true}
    CR->>GS: Read A:L columns
    GS-->>CR: Student data (1400+ rows)

    loop For each student
        CR->>FS: Upsert students/{student_id}<br/>merge=True
    end

    loop For each file in submissions
        CR->>FS: Update files/{file_id}<br/>denormalized student data
    end

    CR-->>CS: 200 OK {students_synced, files_backfilled}

    Note over Admin,DB: 手動同期
    Admin->>DB: Firebase Loginでログイン（管理者許可リスト登録済みのアカウント）
    Admin->>DB: Click "データ同期" button
    DB->>CR: POST /admin/sync-students-from-sheets<br/>Authorization: Bearer Firebase ID token<br/>{"backfill": true}
    CR-->>DB: 200 OK {status, counts}
    DB->>Admin: Toast notification (success/error)
```

---

## ER図（データ設計）

```mermaid
erDiagram
    GOOGLE_SHEETS_統合_受講者リスト {
        string A_氏名
        string B_ふりがな
        string C_日介番号 PK
        string D_勤務先法人名称
        string E_勤務先名称
        string F_種別サービス
        string G_種別サービス_手動
        string H_グループ
        int I_通し番号
        string J_受講生番号
        string K_クラス
        boolean L_無効
    }

    FIRESTORE_STUDENTS {
        string student_id PK
        string name
        string furigana
        string company
        string office
        string service_type
        string group
        int serial_number
        string student_number
        string class_name
        string status "active or inactive"
        timestamp created_at
        timestamp last_updated
    }

    FIRESTORE_FILES {
        string composite_key PK
        string student_id FK
        string student_name
        string student_furigana
        string student_group
        string student_status
        string student_company
        string student_office
        string student_service_type
        int student_serial_number
        string student_number
        string filename
        string drive_file_id
        timestamp submit_date
    }

    GOOGLE_SHEETS_統合_受講者リスト ||--o{ FIRESTORE_STUDENTS : "同期"
    FIRESTORE_STUDENTS ||--o{ FIRESTORE_FILES : "Backfill (非正規化)"
```

### フィールドマッピング

| Google Sheets 列 | Firestore students/ フィールド | 備考 |
|-----------------|------------------------------|------|
| A: 氏名 | `name` | |
| B: ふりがな | `furigana` | |
| C: 日介番号 | `student_id` (ドキュメントID) | Primary Key |
| D: 勤務先法人名称 | `company` | |
| E: 勤務先名称 | `office` | |
| F: 種別サービス | `service_type` | G列が空の場合に使用 |
| G: 種別サービス（手動） | `service_type` | 優先使用 |
| H: グループ | `group` | デフォルト: "未分類" |
| I: 通し番号 | `serial_number` | int型 |
| J: 受講生番号 | `student_number` | |
| K: クラス | `class_name` | |
| L: 無効 | `status` | TRUE→"inactive", FALSE/空→"active" |

---

## 実装詳細

### ファイル構成

```
src/
├── main.py                    # API エンドポイント定義
│   ├── sync_students_from_sheets()  # Line 443-504
│   ├── _sync_students()             # Line 506-603
│   └── _backfill_all_files()        # Line 605-725
├── sheets_service.py          # Google Sheets 読み取り
│   └── get_student_data()           # Line 234-342
└── firestore_service.py       # Firestore 書き込み
    ├── create_student()             # Line 456-494
    └── get_all_students()           # Line 496-520

dashboard/src/
├── App.vue                    # 同期ボタン・トースト通知
└── composables/
    └── useStudentSync.ts      # API 呼び出し composable
```

### 主要コード解説

#### 1. L列「無効」フラグの処理 (`sheets_service.py`)

```python
# Line 299-302
# Check L列「無効」flag (checkbox returns "TRUE" or "FALSE" as string)
is_inactive = (
    row[11].strip().upper() == "TRUE" if row[11] else False
)

# Line 310
"status": "inactive" if is_inactive else "active",  # L列に基づく
```

#### 2. Backfill 処理 (`main.py`)

```python
# Line 679-691 - 常に上書き（スキップ条件なし）
update_data = {
    "student_furigana": student.get("furigana", ""),
    "student_group": student.get("group", "未分類"),
    "student_status": student.get("status", "active"),
    "student_company": student.get("company", ""),
    "student_office": student.get("office", ""),
    "student_service_type": student.get("service_type", ""),
    "student_serial_number": student.get("serial_number", 0),
    "student_number": student.get("student_number", ""),
}
file_doc.reference.update(update_data)
```

#### 3. Dashboard 同期ボタン (`App.vue`)

```vue
<button
  v-if="isAdmin"
  @click="handleSync"
  :disabled="syncing"
>
  <!-- スピナー or 同期アイコン -->
  {{ syncing ? '同期中...' : 'データ同期' }}
</button>
```

---

## Cloud Scheduler 設定

### Job 詳細

| 項目 | 値 |
|------|-----|
| **Job 名** | `carewell-student-sync-daily` |
| **スケジュール** | `0 17 * * *` (UTC) = JST 02:00 |
| **リージョン** | `asia-northeast1` |
| **HTTP メソッド** | `POST` |
| **URL** | `https://carewell-file-collector-imczapxkba-an.a.run.app/admin/sync-students-from-sheets` |
| **リクエストボディ** | `{"backfill": true}` |
| **認証** | OIDC Token |
| **サービスアカウント** | `carewell-automation-sa@carewell-automation.iam.gserviceaccount.com` |
| **タイムアウト** | 180秒 |
| **リトライ** | 最大3回、バックオフ 10-300秒 |

### 確認コマンド

```bash
# Job 設定確認
gcloud scheduler jobs describe carewell-student-sync-daily --location=asia-northeast1

# 手動実行
gcloud scheduler jobs run carewell-student-sync-daily --location=asia-northeast1

# 一時停止
gcloud scheduler jobs pause carewell-student-sync-daily --location=asia-northeast1

# 再開
gcloud scheduler jobs resume carewell-student-sync-daily --location=asia-northeast1
```

---

## Dashboard 手動同期機能

### アクセス方法

```
https://carewell-dashboard-2026.web.app/
```

右上の「ログイン」ボタンから、`admins` コレクションに登録済みの Google アカウントでログインする（Issue #12、詳細は [docs/admin-authentication.md](admin-authentication.md) 参照）。

### 機能詳細

| 項目 | 説明 |
|------|------|
| **表示条件** | Firebase Authentication でログイン済み、かつ管理者許可リスト（`admins` コレクション）に登録済み |
| **ボタン位置** | ヘッダー右上（ナビゲーションの左） |
| **ボタン色** | 緑色 (`bg-green-600`) |
| **処理中表示** | スピナーアニメーション + 「同期中...」テキスト |
| **完了通知** | トースト通知（右上、5秒後自動消去） |

### API 呼び出し

```typescript
// dashboard/src/composables/useStudentSync.ts
const SYNC_API_URL =
  'https://carewell-file-collector-imczapxkba-an.a.run.app/admin/sync-students-from-sheets';

const response = await fetch(SYNC_API_URL, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ backfill: true }),
});
```

### 注意事項

- Cloud Run サービスは **public** に設定されている（認証不要）
- Dashboard からの呼び出しは管理者モードでのみ可能（UI 制限）
- 同期処理には 30秒〜2分程度かかる

---

## Google Sheets 設定

### スプレッドシート情報

| 項目 | 値 |
|------|-----|
| **スプレッドシートID** | `1AQ12-h3n_NmN2kWxi4Z_g354X0wmUyMKAPeAsXJwu_w` |
| **シート名** | `統合_受講者リスト` |
| **読み取り範囲** | `A:L` |
| **データ開始行** | 2行目（1行目はヘッダー） |

### L列「無効」チェックボックス設定

1. L1 セルに `無効` と入力（ヘッダー）
2. L2:L2000 を選択
3. データ → データの入力規則 → チェックボックス
4. 保存

### 動作

| L列の状態 | Firestore `status` |
|----------|-------------------|
| ✓ (TRUE) | `"inactive"` |
| 空 / チェックなし (FALSE) | `"active"` |

---

## 処理フロー図

```mermaid
flowchart TD
    START([開始]) --> CHECK_TRIGGER{トリガー}

    CHECK_TRIGGER -->|Cloud Scheduler| AUTO[自動同期<br/>JST 02:00]
    CHECK_TRIGGER -->|Dashboard ボタン| MANUAL[手動同期]

    AUTO --> CALL_API
    MANUAL --> CALL_API

    CALL_API[POST /admin/sync-students-from-sheets<br/>backfill=true] --> READ_SHEETS

    READ_SHEETS[Google Sheets 読み取り<br/>A:L 列] --> PARSE_DATA

    PARSE_DATA[データパース<br/>L列→status マッピング] --> SYNC_STUDENTS

    SYNC_STUDENTS[Phase 1: students/ 同期] --> LOOP_STUDENTS

    LOOP_STUDENTS{全学生処理完了?}
    LOOP_STUDENTS -->|No| UPSERT_STUDENT[Upsert students/student_id<br/>merge=True]
    UPSERT_STUDENT --> LOOP_STUDENTS
    LOOP_STUDENTS -->|Yes| CHECK_BACKFILL

    CHECK_BACKFILL{backfill=true?}
    CHECK_BACKFILL -->|No| RETURN_RESULT
    CHECK_BACKFILL -->|Yes| BACKFILL_FILES

    BACKFILL_FILES[Phase 2: files/ Backfill] --> LOOP_FILES

    LOOP_FILES{全ファイル処理完了?}
    LOOP_FILES -->|No| UPDATE_FILE[Update files/file_id<br/>非正規化データ上書き]
    UPDATE_FILE --> LOOP_FILES
    LOOP_FILES -->|Yes| RETURN_RESULT

    RETURN_RESULT[結果返却<br/>students_synced, files_backfilled] --> END([終了])
```

---

## WBS（作業分解図）

```mermaid
mindmap
  root((Student Sync Feature))
    Stage 1: L列「無効」フラグ
      sheets_service.py 修正
        読み取り範囲 A:K→A:L
        L列→status マッピング
      ドキュメント更新
      テスト・デプロイ
    Stage 2: Backfill 改修
      _backfill_all_files 修正
        スキップ条件削除
        常に上書き
      Cloud Scheduler 設定
        backfill=true 追加
      ドキュメント更新
    Stage 3: Dashboard 手動同期
      useStudentSync.ts 作成
        API 呼び出し
        状態管理
      App.vue 修正
        同期ボタン追加
        トースト通知
      デプロイ・動作確認
    Stage 4: Google Sheets 設定
      L列ヘッダー追加
      チェックボックス設定
    Stage 5: ドキュメント整備
      引き継ぎドキュメント
      Mermaid 図
```

---

## ガントチャート

```mermaid
gantt
    title Student Sync Feature 実装スケジュール
    dateFormat  YYYY-MM-DD HH:mm
    axisFormat  %H:%M

    section Stage 1: L列フラグ
    sheets_service.py 修正    :done, s1a, 2025-11-30 03:48, 5m
    ドキュメント更新          :done, s1b, after s1a, 3m
    コミット・プッシュ        :done, s1c, after s1b, 2m

    section Stage 2: Backfill
    _backfill_all_files 修正  :done, s2a, after s1c, 5m
    Cloud Scheduler 設定      :done, s2b, after s2a, 3m
    コミット・プッシュ        :done, s2c, after s2b, 2m

    section Stage 3: Dashboard
    useStudentSync.ts 作成    :done, s3a, after s2c, 8m
    App.vue 修正              :done, s3b, after s3a, 10m
    コミット・プッシュ        :done, s3c, after s3b, 2m
    デプロイ待機              :done, s3d, after s3c, 5m

    section Stage 4: Sheets
    L列設定（ユーザー作業）   :done, s4a, after s3d, 5m

    section Stage 5: ドキュメント
    引き継ぎドキュメント作成  :active, s5a, after s4a, 30m
```

---

## トラブルシューティング

### 問題1: 同期ボタンが表示されない

**原因**: 管理者としてログインしていない、または管理者許可リストに未登録

**解決**:
1. 管理者として許可された Google アカウントでログインしているか確認
2. `admins` コレクションにそのメールアドレスが登録されているか確認（`python scripts/seed_admins.py --list`）
3. ブラウザの DevTools Console/Network で 401/403 エラーが出ていないか確認

### 問題2: 同期エラー「Failed to fetch」

**原因**: Cloud Run サービスがダウンまたはネットワークエラー

**解決**:
```bash
# Cloud Run サービス状態確認
gcloud run services describe carewell-file-collector --region=asia-northeast1

# ログ確認
gcloud logging read "resource.type=cloud_run_revision AND
  resource.labels.service_name=carewell-file-collector" --limit=20
```

### 問題3: L列のチェックが反映されない

**原因**:
- Google Sheets の L列が正しく設定されていない
- 同期が実行されていない

**解決**:
1. Google Sheets で L列のデータ検証がチェックボックスになっているか確認
2. Dashboard から手動同期を実行
3. Firestore Console で `students/{student_id}` の `status` フィールドを確認

### 問題4: Backfill が遅い

**原因**: ファイル数が多い（数千件）

**対応**:
- Cloud Scheduler のタイムアウトを延長（現在180秒）
- 必要に応じてバッチ処理に改修

---

## 改修・拡張ガイド

### 新しいフィールドを追加する場合

1. **Google Sheets** に列を追加
2. **sheets_service.py** の `get_student_data()` を修正
   - 読み取り範囲を拡張
   - `student_data` dict にフィールド追加
3. **firestore_service.py** の `create_student()` を修正（必要に応じて）
4. **main.py** の `_backfill_all_files()` を修正
   - `update_data` dict にフィールド追加

### 同期頻度を変更する場合

```bash
# 例: 6時間ごとに変更
gcloud scheduler jobs update http carewell-student-sync-daily \
  --location=asia-northeast1 \
  --schedule="0 */6 * * *"
```

### Dashboard にフィルタリング機能を追加する場合

1. `useStudents.ts` で `status` フィールドによるフィルタリングを実装
2. UI にトグルスイッチを追加（「無効な受講生を表示」）

### 物理削除を実装する場合

**注意**: 現在は論理削除のみ。物理削除は慎重に検討が必要。

1. **Google Sheets** から削除されたレコードを検出するロジックを追加
2. **Firestore** から対応するドキュメントを削除
3. **関連する `files/` ドキュメント**の処理を検討

---

## 関連ドキュメント

- [STUDENT_SYNC_AUTOMATION_HANDOVER.md](STUDENT_SYNC_AUTOMATION_HANDOVER.md) - 運用ガイド
- [DASHBOARD_CLASS_DISPLAY.md](DASHBOARD_CLASS_DISPLAY.md) - Dashboard クラス表示
- [QUICKSTART.md](QUICKSTART.md) - システム概要

---

## 変更履歴

| 日付 | 変更内容 | 担当 |
|------|---------|------|
| 2025-11-18 | 初期実装（Cloud Scheduler 自動同期） | Claude Code |
| 2025-11-30 | L列「無効」フラグ対応 | Claude Code |
| 2025-11-30 | Backfill 常時実行対応 | Claude Code |
| 2025-11-30 | Dashboard 手動同期ボタン追加 | Claude Code |
| 2025-11-30 | 本ドキュメント作成 | Claude Code |

---

**作成完了日**: 2025-11-30
**レビュー**: 推奨
