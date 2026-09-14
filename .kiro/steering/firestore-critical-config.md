# Firestore Critical Configuration Rules

**IMPORTANT: This steering document is ALWAYS loaded. Read carefully before any Firestore-related changes.**

## Purpose

Prevent configuration mistakes and design specification violations when working with Firestore.

## Critical Rules

### Rule 1: Database Name is resolved per academic year (NEVER hardcode a literal)

**2026-09-14改訂**: 令和7年度・令和8年度が同一DB（`carewell-native`）を共有していたため、
令和8年度ダッシュボードに令和7年度の受講者データが混在表示される事故が発生した。
以降、本番DBは年度ごとに完全に分離する（詳細: `docs/SERVICE_SHUTDOWN_AND_RESUME.md`
「年度切替チェックリスト」）。

- ✅ Production/scripts: `src/config/classes.py`の`resolve_firestore_database_id()`を
  必ず経由する。DB名を文字列リテラルで直書きしない
- ✅ 年度→DB名のマッピングは`src/config/classes.py`の`FIRESTORE_DATABASE_IDS_BY_YEAR`
  にコードとして管理する（現在: 令和7年度=`carewell-native`、令和8年度=`carewell-2026`）
- ✅ Test (unit/integration, emulator): `carewell-native`のままでよい（エミュレータ上の
  任意のDB名ラベルであり、本番DB選択ロジックとは無関係。resolverのロジック自体を
  検証するテストは`tests/unit/test_classes_config.py`を参照）
- ✅ Dashboard(フロントエンド): `dashboard/src/config/firebase.ts`の`getDb()`は
  年度ごとにビルド時のリテラルを更新する（Hostingサイト自体も年度ごとに分離済み
  のため、動的resolverは不要）
- ❌ NEVER use `(default)` database
- ❌ `resolve_firestore_database_id()`に環境変数による上書き機構を追加しない
  （`resolve_student_spreadsheet_id()`とは異なり、DB接続先の誤上書きは
  Firestore Rulesを経由しないAdmin SDK書き込みで前年度DBを汚染しうるため、
  正当なユースケースがない限り持たせない。`/plan-crossreview`でのcodex指摘）
- ❌ 前年度DB（例: `carewell-native`）は年度切替完了後、クライアントSDKからの
  読み書きをFirestore Rulesで全面denyにする（`dashboard/firestore-legacy-frozen.rules`）。
  ただしAdmin SDK/gcloud等のサーバー側アクセスはこれを迂回できる点に注意
  （プロジェクトIAM権限を持つ主体に限られるため別途のIAM再設計は不要と判断済み）

**Reference documents:**

- `.kiro/specs/firestore-schema-improvement/requirements.md` (Lines 1-10)
- `docs/firestore-schema-improvement-implementation.md` (Line 529)
- `docs/SERVICE_SHUTDOWN_AND_RESUME.md` 「年度切替チェックリスト」

**Code locations to verify:**

- `src/config/classes.py`: `FIRESTORE_DATABASE_IDS_BY_YEAR` / `resolve_firestore_database_id()`
- `src/firestore_service.py` Line 20: `firestore.Client(database=resolve_firestore_database_id())`
- `dashboard/src/config/firebase.ts`: `getFirestore(firebaseApp, '<年度のDB名>')`
- `dashboard/firebase.json`: `firestore`配列（年度ごとのDB + 前年度の凍結ルール）

### Rule 2: Collection Path Structure is FIXED

**Correct path structure (as per design specification):**

```text
submissions/{class_name}/tasks/{task_id}/files/{composite_key}
```

**Incorrect paths (legacy, DO NOT USE):**

- ❌ `{class_name}/{task_id}/documents/{composite_key}`
- ❌ `{class_name}/{task_id}/files/{composite_key}`

**Reference documents:**

- `.kiro/specs/firestore-schema-improvement/design.md` (Lines 51-75)

**Code locations to verify:**

- `src/firestore_service.py`:
  - Line 67-72: `_update_task_metadata()` method
  - Line 127-133: `check_already_uploaded_by_student_date()` method
  - Line 186-193: `check_already_uploaded()` method
  - Line 270-277: `record_upload()` method

### Rule 3: task_pattern Parameter is REQUIRED

**When calling `record_upload()`, MUST pass `task_pattern` from Cloud Scheduler request.**

**Common mistake:**

```python
# ❌ WRONG: Missing task_pattern parameter
firestore_service.record_upload(
    class_name, task_id, student_name, student_id,
    filename, drive_file_id, drive_folder_id, submit_date,
    metadata=metadata
)
# Result: task_pattern defaults to task_id → incorrect metadata in Firestore

# ✅ CORRECT: Pass task_pattern
firestore_service.record_upload(
    class_name, task_id, student_name, student_id,
    filename, drive_file_id, drive_folder_id, submit_date,
    metadata=metadata,
    task_pattern=task_pattern  # ← This parameter is REQUIRED
)
```

**Reference documents:**

- `.kiro/specs/firestore-schema-improvement/requirements.md` (Lines 98-102)
- `.kiro/specs/firestore-schema-improvement/design.md` (Lines 367-374)

**Code location to verify:**

- `src/main.py` Line 183-194: `firestore_service.record_upload()` call

### Rule 4: Atomic Increment for file_count

**Parent document `file_count` MUST use `firestore.Increment(1)`:**

```python
# ✅ CORRECT: Atomic increment
update_data = {
    "task_id": task_id,
    "task_pattern": task_pattern,
    "file_count": firestore.Increment(1),  # ← Atomic operation
    "last_updated": firestore.SERVER_TIMESTAMP,
}

# ❌ WRONG: Manual increment
doc = task_ref.get()
current_count = doc.to_dict().get("file_count", 0)
update_data = {
    "file_count": current_count + 1  # ← Race condition possible
}
```

**Reference documents:**

- `.kiro/specs/firestore-schema-improvement/design.md` (Lines 403-407)

**Code location to verify:**

- `src/firestore_service.py` Line 78-83: `_update_task_metadata()` method

## Pre-Commit Checklist

Before committing changes to Firestore-related files:

- [ ] Verified database name is `carewell-native` (NOT `(default)`)
- [ ] Verified collection path uses: `submissions/{class_name}/tasks/{task_id}/files/{composite_key}`
- [ ] Verified `task_pattern` is passed to `record_upload()` from Cloud Scheduler request
- [ ] Verified `file_count` uses `firestore.Increment(1)`
- [ ] Read the relevant design document sections
- [ ] Unit tests pass
- [ ] Integration tests pass with Firestore Emulator

## Design Document Reference

**Files that require reading design docs before modification:**

| File | Design Document | Key Sections |
|------|----------------|--------------|
| `src/firestore_service.py` | `.kiro/specs/firestore-schema-improvement/design.md` | Lines 351-430, 493-502 |
| `src/main.py` | `.kiro/specs/firestore-schema-improvement/requirements.md` | Lines 96-104 |
| `tests/conftest.py` | `docs/firestore-schema-improvement-implementation.md` | Lines 520-536 |
| `tests/integration/test_file_upload.py` | `.kiro/specs/firestore-schema-improvement/design.md` | Lines 51-75 |

## Past Incidents (Learn from mistakes)

### Incident 1: Database Name Mistake (2025-11-04)

**What happened:**

- Changed `carewell-native` to `(default)` in `tests/conftest.py`
- Assumption: Firestore Emulator only supports `(default)` database
- Did not check original design documentation

**Impact:**

- Integration tests used wrong database
- Mismatch between test and production environments
- Required revert commit

**Lesson:**

> "Firestoreのデータベースの元々の設計についてちゃんとドキュメントを確認してから対応してくださいね"

### Incident 2: Missing task_pattern Parameter (2025-11-04)

**What happened:**

- `main.py` received `task_pattern` from Cloud Scheduler
- Did not pass `task_pattern` to `record_upload()`
- Result: `task_pattern` defaulted to `task_id`

**Impact:**

- Incorrect metadata in Firestore for ALL pages (1st, 2nd, etc.)
- Dashboard displays simplified task titles
- Example: Expected "課題①業務分析　※～11/3〆切" → Got "課題①"

**Lesson:**

- Always verify ALL required parameters are passed
- Design specifications list required parameters

### Incident 3: Collection Path Mistake (Original bug)

**What happened:**

- Used old path: `{class_name}/{task_id}/documents/{composite_key}`
- Correct path: `submissions/{class_name}/tasks/{task_id}/files/{composite_key}`

**Impact:**

- Duplicate check failed (searching wrong location)
- Files re-downloaded repeatedly
- 156 expected files → 197+ downloaded

**Lesson:**

- Collection path structure is part of design specification
- Must reference design docs when modifying Firestore queries

## When to Reference This Document

**You should review this steering document when:**

- Modifying any file in `src/` that imports `firestore`
- Writing or modifying tests in `tests/` that use Firestore
- Debugging Firestore-related issues
- Adding new Firestore operations
- Reviewing pull requests that touch Firestore code

## Contact for Questions

If unsure about Firestore configuration:

1. Read the design documents listed above
2. Check past incident descriptions in this file
3. Verify against the pre-commit checklist
4. Ask the user for clarification if design docs are ambiguous

---

## Firestore Indexes Management

### ⚠️ CRITICAL: All Indexes Must Be Defined in Code

**Rule**: すべての Firestore インデックスは `dashboard/firestore.indexes.json` で管理する

**Background**:
- 2025-11-10にBackend用の手動作成インデックスが削除されるインシデント発生
- `firebase deploy --only firestore` は宣言的デプロイのため、定義されていないインデックスを削除
- Infrastructure as Code (IaC) を徹底し、手動作成を禁止

### Required Indexes

#### Backend: Early Duplicate Check (CRITICAL)

**Query**: `src/firestore_service.py:136-139`
```python
collection_ref.where("student_id", "==", student_id)
              .where("submit_date", "==", submit_date)
```

**Index Definition**:

```json
{
  "collectionGroup": "files",
  "queryScope": "COLLECTION_GROUP",
  "fields": [
    {"fieldPath": "student_id", "order": "ASCENDING"},
    {"fieldPath": "submit_date", "order": "ASCENDING"}
  ]
}
```

- **Purpose**: 重複ファイル検出（student_id + submit_date で既存アップロードを検索）
- **Impact if Missing**: すべてのファイルを「新規」と誤判定 → 無限ダウンロード → タイムアウト

#### Dashboard: Student Detail File List

**Query**: `dashboard/src/composables/useSubmissionFileList.ts`

```typescript
collectionGroup(db, 'files')
  .where('student_id', '==', studentId)
```

**Index Definition**:

```json
{
  "collectionGroup": "files",
  "fieldPath": "student_id",
  "indexes": [
    {
      "order": "ASCENDING",
      "queryScope": "COLLECTION_GROUP"
    }
  ]
}
```

- **Purpose**: 学生詳細ページで全課題の提出ファイルを取得
- **Impact if Missing**: Dashboard学生詳細ページがエラー

### Index Management Checklist

**Before Adding New Query**:
- [ ] 複合クエリ（2つ以上の `==`/`range`）か確認
- [ ] 必要なインデックスを `dashboard/firestore.indexes.json` に定義
- [ ] Backend と Dashboard の**両方**のクエリを考慮

**Before Firestore Deploy**:
- [ ] `dashboard/firestore.indexes.json` の内容を確認
- [ ] Backend用インデックス（student_id + submit_date）が存在するか確認
- [ ] Dashboard用インデックス（student_id single field）が存在するか確認

**After Firestore Deploy**:
- [ ] Firestoreコンソールでインデックス一覧を確認: https://console.firebase.google.com/project/YOUR_PROJECT/firestore/indexes
- [ ] Cloud Run ログで「index required」エラーがないか監視
- [ ] 次回のCloud Scheduler実行で正常動作を確認

### Emergency Recovery (インデックス削除時)

**症状**:
- Cloud Scheduler が25分でタイムアウト
- 「Duplicate detected」ログが出ない
- Page 1で無限ループ

**診断**:

```bash
# Cloud Run ログで index エラーを検索
gcloud logging read "resource.type=cloud_run_revision AND
  resource.labels.service_name=carewell-file-collector AND
  (textPayload=~'index' OR textPayload=~'FAILED_PRECONDITION')" \
  --limit 50 --format=json
```

**修正**:

1. `dashboard/firestore.indexes.json` に必要なインデックスを追加
2. `firebase deploy --only firestore:indexes --project carewell-native`
3. インデックス作成完了（数分）を待つ
4. 次回のScheduler実行で正常動作を確認

### Reference

- Incident Report: `docs/common-mistakes.md` Incident #13
- Backend Implementation: `src/firestore_service.py:105-157`
- Firestore Official Docs: https://firebase.google.com/docs/firestore/query-data/indexing
