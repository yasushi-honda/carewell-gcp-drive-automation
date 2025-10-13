# Firestore Schema Improvement 実装ドキュメント

## 目次

1. [実装概要](#実装概要)
2. [アーキテクチャ説明](#アーキテクチャ説明)
3. [コード変更詳細](#コード変更詳細)
4. [マイグレーション手順](#マイグレーション手順)
5. [ロールバック手順](#ロールバック手順)
6. [トラブルシューティング](#トラブルシューティング)
7. [今後の拡張性](#今後の拡張性)

---

## 実装概要

### 目的

Firestoreの提出ファイル管理スキーマを改善し、タスクレベルでのメタデータ集約を実現します。これにより、以下の課題を解決します：

- **クエリ効率化**: 各タスクのファイル数を親ドキュメントから直接取得可能
- **データ整合性**: アトミック操作によるファイルカウントの正確性保証
- **スケーラビリティ**: サブコレクション全体をスキャンせずに統計情報を取得
- **将来の拡張性**: 提出期限、ステータス、統計情報などの追加が容易

### 新しいスキーマ構造

```
Firestore (carewell-native)
└── {class_name}                          # コレクション（例: "令和7年度 デジタル中核人材養成研修 №01"）
    └── {task_id}                         # 親ドキュメント（例: "課題①"）
        ├── task_id: string               # タスクID
        ├── task_pattern: string          # タスク表示名/パターン
        ├── file_count: number            # ファイル数（アトミックインクリメント）
        ├── created_at: timestamp         # 作成日時
        └── last_updated: timestamp       # 最終更新日時
        └── documents/                    # サブコレクション
            └── {composite_key}           # ファイルドキュメント
                ├── student_id: string
                ├── student_name: string
                ├── filename: string
                ├── drive_file_id: string
                ├── drive_folder_id: string
                ├── submit_date: string
                ├── composite_key: string
                └── uploaded_at: timestamp
```

### 実装範囲

**実装済み機能:**

1. **FirestoreService拡張** (`src/firestore_service.py`)
   - `_update_task_metadata()`: 親ドキュメントの作成/更新
   - `record_upload()`: ファイルアップロード時の親ドキュメント自動更新

2. **マイグレーションスクリプト** (`scripts/migrate_parent_documents.py`)
   - 既存データからの親ドキュメント作成
   - Dry-runモードによる事前確認
   - バリデーション機能
   - JSON形式のレポート出力

3. **ロールバックスクリプト** (`scripts/rollback_parent_documents.py`)
   - 親ドキュメントの削除（サブコレクション保持）
   - 安全確認機能（`--confirm`フラグ必須）

4. **メンテナンススクリプト** (`scripts/fix_file_count.py`)
   - file_count不整合の検出と修正
   - クラス/タスク単位でのフィルタリング機能

5. **データ検証スクリプト** (`scripts/check_duplicates.py`)
   - composite_key重複チェック
   - drive_file_id重複チェック
   - 親ドキュメントとサブコレクションの整合性確認

6. **テストスイート**
   - ユニットテスト: FirestoreService、各スクリプト
   - インテグレーションテスト: ファイルアップロード、マイグレーション
   - Firestore Emulatorを使用したローカルテスト環境

---

## アーキテクチャ説明

### 設計思想

#### 1. Fail-Open戦略

親ドキュメントの更新に失敗しても、ファイルドキュメントの作成は継続します。これにより、システムの高可用性を維持します。

```python
# _update_task_metadata() は失敗時にFalseを返すが、
# record_upload() は処理を継続する
self._update_task_metadata(class_name, task_id, task_pattern)

# ファイルドキュメントは必ず作成される
doc_ref.set(record)
```

**理由:**
- メタデータの不整合よりも、ファイル紛失の方が重大
- メタデータは後から `fix_file_count.py` で修正可能
- ユーザー体験の優先（エラーでアップロードが止まらない）

#### 2. アトミック操作によるfile_count管理

並行アップロードでもfile_countの正確性を保証するため、Firestoreの`Increment()`を使用します。

```python
update_data = {
    "file_count": firestore.Increment(1),  # アトミックインクリメント
    "last_updated": firestore.SERVER_TIMESTAMP,
}
```

**利点:**
- Read-Modify-Writeパターンによる競合を回避
- トランザクション不要で高速
- Firestoreサーバー側で実行されるため確実

#### 3. SERVER_TIMESTAMPの使用

タイムスタンプはサーバー側で生成することで、クライアント間の時刻ずれを防止します。

```python
"created_at": firestore.SERVER_TIMESTAMP,
"last_updated": firestore.SERVER_TIMESTAMP,
```

**利点:**
- クライアント時刻の不正確さを回避
- 全ドキュメントで一貫したタイムゾーン（UTC）
- Firestore Emulatorでもテスト可能

#### 4. merge=Trueによる安全な更新

既存ドキュメントがある場合は更新、ない場合は作成を１回の操作で実行します。

```python
task_ref.set(update_data, merge=True)
```

**利点:**
- 既存フィールドを上書きしない
- トランザクション不要
- べき等性の保証

### データフロー

#### 新規ファイルアップロード時

```
1. check_already_uploaded()
   └─> サブコレクションで重複チェック

2. record_upload()
   ├─> _update_task_metadata()
   │   ├─> 親ドキュメント存在チェック
   │   ├─> created_atを条件付きで設定
   │   └─> Increment(1)でfile_countを更新
   │
   └─> ファイルドキュメント作成
       └─> サブコレクション documents/ に追加
```

#### マイグレーション実行時

```
1. migrate_parent_documents(dry_run=True)
   └─> プレビュー実行（書き込みなし）

2. migrate_parent_documents(dry_run=False)
   ├─> KNOWN_CLASSES × KNOWN_TASK_IDS をスキャン
   ├─> 各タスクについて:
   │   ├─> 親ドキュメント存在確認（既存ならスキップ）
   │   ├─> サブコレクションのファイル数カウント
   │   └─> 親ドキュメント作成
   └─> JSONレポート生成

3. validate_migration()
   └─> file_countと実際のドキュメント数を比較
```

---

## コード変更詳細

### 1. FirestoreService拡張

#### ファイル: `src/firestore_service.py`

#### 1.1 新規メソッド: `_update_task_metadata()`

親ドキュメントのメタデータを更新または作成します。

```python
def _update_task_metadata(
    self, class_name: str, task_id: str, task_pattern: str
) -> bool:
    """
    Update or create task parent document with metadata.

    Args:
        class_name: Class name
        task_id: Task ID (e.g., "課題①")
        task_pattern: Task pattern/title for display

    Returns:
        True if successful, False if error occurred (fail-open strategy)
    """
    try:
        task_ref = self.db.collection(class_name).document(task_id)

        # Check if document exists to determine if created_at should be set
        doc = task_ref.get()

        # Prepare update data with atomic increment
        update_data = {
            "task_id": task_id,
            "task_pattern": task_pattern,
            "file_count": firestore.Increment(1),
            "last_updated": firestore.SERVER_TIMESTAMP,
        }

        # Add created_at only for new documents
        if not doc.exists:
            update_data["created_at"] = firestore.SERVER_TIMESTAMP

        # Use merge=True to create or update
        task_ref.set(update_data, merge=True)

        logger.info(f"Updated task document: {class_name}/{task_id}")
        return True

    except Exception as e:
        logger.error(
            f"Failed to update task document {class_name}/{task_id}: {e}",
            exc_info=True,
        )
        # Continue processing (fail-open strategy)
        return False
```

**重要なポイント:**

1. **created_at条件設定**: 既存ドキュメントには`created_at`を設定しない
   ```python
   if not doc.exists:
       update_data["created_at"] = firestore.SERVER_TIMESTAMP
   ```

2. **アトミックインクリメント**: 並行処理でも正確
   ```python
   "file_count": firestore.Increment(1)
   ```

3. **merge=True**: 既存フィールドを保護
   ```python
   task_ref.set(update_data, merge=True)
   ```

4. **Fail-open**: エラー時もFalseを返して処理継続を許可

#### 1.2 変更メソッド: `record_upload()`

新しいパラメータ `task_pattern` を追加し、親ドキュメント更新を統合しました。

```python
def record_upload(
    self,
    class_name: str,
    task_id: str,
    student_name: str,
    student_id: str,
    filename: str,
    drive_file_id: str,
    drive_folder_id: str,
    submit_date: str,
    metadata: Optional[dict] = None,
    task_pattern: Optional[str] = None,  # ← 新規パラメータ
) -> bool:
    """
    Record successful file upload and update parent document metadata.
    """
    try:
        # Default task_pattern to task_id if not provided
        task_pattern = task_pattern or task_id

        # Update parent document metadata (fail-open: continue even if this fails)
        self._update_task_metadata(class_name, task_id, task_pattern)

        # Create file document record
        # ... (既存のファイルドキュメント作成処理)
```

**後方互換性:**
- `task_pattern`はオプショナルパラメータ
- 指定されない場合は`task_id`をデフォルト値として使用
- 既存のコードは変更不要

---

### 2. マイグレーションスクリプト

#### ファイル: `scripts/migrate_parent_documents.py`

#### 2.1 主要関数: `migrate_parent_documents()`

```python
def migrate_parent_documents(dry_run: bool = True, db=None) -> Dict:
    """
    Migrate parent documents for all known classes and tasks.

    Args:
        dry_run: If True, preview only without writing
        db: Firestore client instance (optional, for testing with emulator)

    Returns:
        Dict with migration results
    """
```

**機能:**

1. **Dry-runモード** (デフォルト)
   - 実際の書き込みなしでプレビュー
   - 作成予定の親ドキュメント一覧を表示

2. **実行モード** (`--execute`)
   - 親ドキュメントを実際に作成
   - 既存の親ドキュメントはスキップ

3. **エミュレーター対応**
   - `db`パラメータでFirestoreクライアントを注入可能
   - インテグレーションテストで使用

#### 2.2 バリデーション機能: `validate_migration()`

マイグレーション後のfile_count正確性を検証します。

```python
def validate_migration() -> Dict:
    """
    Validate that file_count matches actual document count.

    Returns:
        Dict with validation results:
        - success: bool (True if no mismatches)
        - total_checked: int
        - mismatches: List[Dict]
    """
```

**検証内容:**
- 親ドキュメントの`file_count`と実際のサブコレクション数を比較
- 不一致がある場合は詳細を出力

#### 2.3 レポート生成: `save_report_json()`

マイグレーション結果をJSON形式で保存します。

```python
# レポートファイル名: migration_report_YYYYMMDD_HHMMSS.json
{
  "timestamp": "20250110_123456",
  "migration": {
    "success": true,
    "dry_run": false,
    "created_documents": 5,
    "skipped_documents": 3,
    ...
  },
  "validation": {
    "success": true,
    "total_checked": 8,
    "mismatches": []
  }
}
```

---

### 3. ロールバックスクリプト

#### ファイル: `scripts/rollback_parent_documents.py`

緊急時に親ドキュメントを削除します（サブコレクションは保持）。

#### 3.1 主要関数: `rollback_parent_documents()`

```python
def rollback_parent_documents(confirm: bool = False) -> Dict:
    """
    Delete parent documents for all known classes and tasks.

    Args:
        confirm: If True, actually delete. If False, preview only.

    Returns:
        Dict with rollback results
    """
```

**安全機能:**

1. **デフォルトはプレビューモード**
   - 実際の削除には `--confirm` フラグが必須

2. **サブコレクション保護**
   - 親ドキュメントのみを削除
   - `documents/`サブコレクションは保持される

3. **警告メッセージ**
   - 削除前に警告を表示
   - 操作が不可逆であることを明示

---

### 4. メンテナンススクリプト

#### ファイル: `scripts/fix_file_count.py`

file_countの不整合を検出・修正します。

#### 4.1 主要関数: `fix_file_count()`

```python
def fix_file_count(
    dry_run: bool = True,
    class_name: Optional[str] = None,
    task_id: Optional[str] = None,
) -> Dict:
    """
    Detect and fix file_count mismatches.
    """
```

**機能:**

1. **フィルタリング**
   - `--class-name`: 特定クラスのみ処理
   - `--task-id`: 特定タスクのみ処理（`--class-name`と併用）

2. **不整合検出**
   - 親ドキュメントの`file_count`と実際のドキュメント数を比較
   - 差分を計算して表示

3. **修正実行** (`--execute`)
   - 実際のドキュメント数に基づいてfile_countを更新
   - `last_updated`タイムスタンプも更新

**使用例:**

```bash
# 全体の不整合をチェック
python scripts/fix_file_count.py --dry-run

# 特定クラスの不整合を修正
python scripts/fix_file_count.py --execute --class-name "令和7年度 デジタル中核人材養成研修 №01"

# 特定タスクの不整合を修正
python scripts/fix_file_count.py --execute \
  --class-name "令和7年度 デジタル中核人材養成研修 №01" \
  --task-id "課題①"
```

---

### 5. テストスイート

#### 5.1 ユニットテスト

**ファイル: `tests/unit/test_firestore_service.py`**

FirestoreServiceの各メソッドをモック使用でテストします。

主要テストケース:
- `test_update_task_metadata_creates_new_document_with_created_at`: 新規作成時のcreated_at設定
- `test_update_task_metadata_updates_existing_without_created_at`: 既存更新時のcreated_at非設定
- `test_record_upload_calls_update_task_metadata`: 親ドキュメント更新の統合

**ファイル: `tests/unit/test_migrate_parent_documents.py`**

マイグレーションスクリプトの論理をテストします。

**ファイル: `tests/unit/test_rollback_parent_documents.py`**

ロールバックスクリプトの論理をテストします。

**ファイル: `tests/unit/test_fix_file_count.py`**

メンテナンススクリプトの論理をテストします。

#### 5.2 インテグレーションテスト

**ファイル: `tests/integration/test_file_upload.py`**

Firestore Emulatorを使用したEnd-to-Endテスト。

主要テストケース:
1. `test_new_file_upload_creates_parent_and_increments_count`: 初回アップロードで親ドキュメント作成
2. `test_second_file_upload_increments_count`: 2回目のアップロードでfile_countが2に
3. `test_multiple_uploads_maintain_accurate_count`: 5回のアップロードでfile_countが5
4. `test_task_pattern_defaults_to_task_id`: task_patternのデフォルト動作確認
5. `test_duplicate_file_upload_skips_and_count_unchanged`: 重複検出動作確認
6. `test_concurrent_uploads_maintain_count_accuracy`: 並行アップロードでの正確性確認

**ファイル: `tests/integration/test_migration.py`**

マイグレーションスクリプトのEnd-to-Endテスト。

主要テストケース:
1. `test_migration_creates_parent_documents_with_correct_count`: 正しいfile_countで親ドキュメント作成
2. `test_migration_skips_existing_parent_documents`: 既存の親ドキュメントをスキップ
3. `test_migration_dry_run_mode`: Dry-runモードで書き込みなし

#### 5.3 Firestore Emulator設定

**ファイル: `tests/integration/conftest.py`**

```python
@pytest.fixture
def emulator_client():
    """Provide Firestore client connected to emulator."""
    os.environ["FIRESTORE_EMULATOR_HOST"] = "localhost:8080"

    client = firestore.Client(
        project="test-project",
        database="carewell-native"
    )

    yield client

    # Cleanup: Delete all collections
    delete_all_collections(client)
```

**CI/CD統合:**
- GitHub Actionsで自動的にエミュレーター起動
- テスト実行後に自動クリーンアップ

---

## マイグレーション手順

### 前提条件

1. **Python環境**: Python 3.9以上
2. **認証**: GCPサービスアカウント認証済み
3. **権限**: Firestore Native Mode (`carewell-native`) への読み書き権限
4. **バックアップ**: Firestoreのバックアップ取得済み（本番環境の場合）

### ステップ1: Dry-run実行（プレビュー）

まず、dry-runモードでマイグレーション内容を確認します。

```bash
# 環境設定
export GOOGLE_CLOUD_PROJECT="carewell-automation"
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/.config/gcloud/application_default_credentials.json"

# Dry-run実行
cd /path/to/carewell-gcp-drive-automation
python scripts/migrate_parent_documents.py --dry-run
```

**出力例:**

```
============================================================
DRY RUN MODE
============================================================

📚 Processing class: 令和7年度 デジタル中核人材養成研修 №01
  🔍 Would create 課題①: file_count=15
  🔍 Would create 課題②: file_count=8
  ⏭️  Skipping 課題③: No files in documents subcollection

📚 Processing class: 令和7年度 デジタル中核人材養成研修 №02
  ⏭️  Skipping 課題①: Parent document already exists
  🔍 Would create 課題②: file_count=12

============================================================
MIGRATION SUMMARY
============================================================

Mode: DRY RUN (Preview Only)
Total Classes: 2
Total Tasks Processed: 6
Parent Documents Would Be Created: 3
Parent Documents Skipped: 3
Errors: 0
Success: ✅ Yes

🔍 PREVIEW OF DOCUMENTS TO BE CREATED:

  - 令和7年度 デジタル中核人材養成研修 №01/課題①: file_count=15
  - 令和7年度 デジタル中核人材養成研修 №01/課題②: file_count=8
  - 令和7年度 デジタル中核人材養成研修 №02/課題②: file_count=12

💡 To execute migration, run with --execute flag
```

**確認ポイント:**
- ✅ 作成予定の親ドキュメント数が妥当か
- ✅ file_countの値が期待通りか
- ✅ エラーが発生していないか
- ✅ スキップされるべきドキュメントがスキップされているか

### ステップ2: 実行（Execute）

Dry-runの結果を確認し、問題がなければ実際にマイグレーションを実行します。

```bash
# マイグレーション実行
python scripts/migrate_parent_documents.py --execute
```

**出力例:**

```
============================================================
MIGRATION MODE
============================================================

📚 Processing class: 令和7年度 デジタル中核人材養成研修 №01
  ✅ Created 課題①: file_count=15
  ✅ Created 課題②: file_count=8
  ⏭️  Skipping 課題③: No files in documents subcollection

📚 Processing class: 令和7年度 デジタル中核人材養成研修 №02
  ⏭️  Skipping 課題①: Parent document already exists
  ✅ Created 課題②: file_count=12

🔍 Running post-migration validation...

============================================================
VALIDATING MIGRATION
============================================================

  ✅ OK: 令和7年度 デジタル中核人材養成研修 №01/課題①ー count=15
  ✅ OK: 令和7年度 デジタル中核人材養成研修 №01/課題② - count=8
  ✅ OK: 令和7年度 デジタル中核人材養成研修 №02/課題① - count=20
  ✅ OK: 令和7年度 デジタル中核人材養成研修 №02/課題② - count=12

============================================================
VALIDATION SUMMARY
============================================================

Total Parent Documents Checked: 4
Mismatches Found: 0
Validation ✅ PASSED

============================================================
MIGRATION SUMMARY
============================================================

Mode: EXECUTION
Total Classes: 2
Total Tasks Processed: 6
Parent Documents Created: 3
Parent Documents Skipped: 3
Errors: 0
Success: ✅ Yes

============================================================
VALIDATION RESULTS
============================================================

Validation: ✅ PASSED
Total Checked: 4
Mismatches: 0

📄 Report saved to: migration_report_20250110_143022.json
```

**成功の確認:**
- ✅ `Success: ✅ Yes`
- ✅ `Validation: ✅ PASSED`
- ✅ エラーが0件
- ✅ JSONレポートが保存されている

### ステップ3: 検証（Validation Only）

マイグレーション後、いつでもバリデーションを実行できます。

```bash
# バリデーションのみ実行
python scripts/migrate_parent_documents.py --validate-only
```

**file_count不整合が見つかった場合:**

```
============================================================
VALIDATION SUMMARY
============================================================

Total Parent Documents Checked: 5
Mismatches Found: 1
Validation ❌ FAILED

⚠️  FILE_COUNT MISMATCHES:

  令和7年度 デジタル中核人材養成研修 №01/課題①:
    Stored:  15
    Actual:  17
    Diff:    +2

💡 Run scripts/fix_file_count.py to fix mismatches
```

この場合、次のステップで修正します。

### ステップ4: 不整合修正（必要な場合のみ）

file_count不整合が見つかった場合、修正スクリプトを実行します。

```bash
# 不整合をプレビュー
python scripts/fix_file_count.py --dry-run

# 不整合を修正
python scripts/fix_file_count.py --execute
```

**出力例:**

```
============================================================
FIX MODE - UPDATING FILE_COUNT
============================================================

📚 Processing class: 令和7年度 デジタル中核人材養成研修 №01
  ✅ Fixed 課題①: 15 → 17 (diff=+2)
  ✅ OK: 課題② - file_count=8 (accurate)

============================================================
FIX FILE_COUNT SUMMARY
============================================================

Mode: EXECUTION
Total Classes: 2
Total Tasks Processed: 6
Parent Documents Checked: 4
Mismatches Found: 1
Documents Fixed: 1
Errors: 0
Success: ✅ Yes
```

### ステップ5: 最終確認

マイグレーション完了後、Firestoreコンソールで確認します。

**確認項目:**

1. **親ドキュメントの存在確認**
   - Firestoreコンソールで `{class_name}/{task_id}` を確認
   - `task_id`, `task_pattern`, `file_count`, `created_at`, `last_updated`が設定されていること

2. **サブコレクションの保持確認**
   - `{class_name}/{task_id}/documents` サブコレクションが存在すること
   - ファイルドキュメントが失われていないこと

3. **file_countの正確性確認**
   - 親ドキュメントの`file_count`とサブコレクションのドキュメント数が一致すること

4. **アプリケーション動作確認**
   - 新しいファイルアップロードが正常に動作すること
   - ダッシュボード（今後実装予定）でデータが表示されること

---

## ロールバック手順

マイグレーションに問題が発生した場合、以下の手順でロールバックします。

### 緊急ロールバック（親ドキュメント削除）

親ドキュメントを削除し、マイグレーション前の状態に戻します。

**注意:** サブコレクションは保持されるため、ファイルデータは失われません。

#### ステップ1: ロールバック内容のプレビュー

```bash
# プレビュー実行
python scripts/rollback_parent_documents.py
```

**出力例:**

```
============================================================
PREVIEW MODE (--confirm required to delete)
============================================================

⚠️  This is a PREVIEW. No documents will be deleted.
⚠️  Use --confirm flag to actually delete parent documents.

📚 Processing class: 令和7年度 デジタル中核人材養成研修 №01
  🔍 Would delete 課題①: file_count=15 (subcollections preserved)
  🔍 Would delete 課題②: file_count=8 (subcollections preserved)

============================================================
ROLLBACK SUMMARY
============================================================

Mode: PREVIEW (--confirm required to delete)
Total Classes: 2
Total Tasks Processed: 6
Parent Documents Would Be Deleted: 2
Parent Documents Skipped: 4
Errors: 0
Success: ✅ Yes

🔍 PREVIEW OF DOCUMENTS TO BE DELETED:

  - 令和7年度 デジタル中核人材養成研修 №01/課題①: file_count=15
  - 令和7年度 デジタル中核人材養成研修 №01/課題②: file_count=8

⚠️  IMPORTANT NOTES:
  - Parent documents will be deleted
  - Subcollections (documents) will be PRESERVED
  - This operation is IRREVERSIBLE

💡 To execute rollback, run with --confirm flag
```

#### ステップ2: ロールバック実行

プレビューを確認し、問題がなければロールバックを実行します。

```bash
# ロールバック実行（--confirmフラグ必須）
python scripts/rollback_parent_documents.py --confirm
```

**出力例:**

```
============================================================
ROLLBACK MODE - DELETING PARENT DOCUMENTS
============================================================

📚 Processing class: 令和7年度 デジタル中核人材養成研修 №01
  ✅ Deleted 課題①: file_count=15 (subcollections preserved)
  ✅ Deleted 課題②: file_count=8 (subcollections preserved)

============================================================
ROLLBACK SUMMARY
============================================================

Mode: EXECUTION
Total Classes: 2
Total Tasks Processed: 6
Parent Documents Deleted: 2
Parent Documents Skipped: 4
Errors: 0
Success: ✅ Yes
```

#### ステップ3: ロールバック後の確認

1. **親ドキュメントの削除確認**
   - Firestoreコンソールで `{class_name}/{task_id}` が存在しないこと

2. **サブコレクションの保持確認**
   - `{class_name}/{task_id}/documents` サブコレクションが残っていること
   - ファイルドキュメント数が変わっていないこと

3. **アプリケーション動作確認**
   - 既存のファイルアップロード機能が動作すること（親ドキュメントは自動再作成される）

### 再マイグレーション

ロールバック後、問題を修正してから再度マイグレーションを実行できます。

```bash
# 1. Dry-runで確認
python scripts/migrate_parent_documents.py --dry-run

# 2. 問題なければ実行
python scripts/migrate_parent_documents.py --execute
```

---

## トラブルシューティング

### 問題1: file_count不整合

**症状:**
- `validate_migration()` でMismatchesが報告される
- 親ドキュメントの`file_count`と実際のドキュメント数が一致しない

**原因:**
- マイグレーション中のファイルアップロード
- 部分的な失敗による不整合
- 手動でのドキュメント編集

**解決策:**

```bash
# 不整合を確認
python scripts/fix_file_count.py --dry-run

# 不整合を修正
python scripts/fix_file_count.py --execute

# 特定クラスのみ修正
python scripts/fix_file_count.py --execute --class-name "令和7年度 デジタル中核人材養成研修 №01"
```

### 問題2: マイグレーション中のエラー

**症状:**
- マイグレーション実行中に`❌ Error processing`が表示される
- `Success: ❌ No`になる

**原因:**
- Firestore接続エラー
- 権限不足
- ドキュメント構造の問題

**解決策:**

1. **エラー詳細の確認**
   ```bash
   # エラー内容を確認
   python scripts/migrate_parent_documents.py --execute 2>&1 | tee migration_error.log
   ```

2. **権限確認**
   ```bash
   # サービスアカウントの権限確認
   gcloud projects get-iam-policy carewell-automation \
     --flatten="bindings[].members" \
     --filter="bindings.members:serviceAccount:YOUR_SA@PROJECT.iam.gserviceaccount.com"
   ```

3. **Firestore接続確認**
   ```bash
   # Firestoreへの接続確認
   gcloud firestore databases describe carewell-native --project=carewell-automation
   ```

4. **部分的なロールバックと再実行**
   ```bash
   # エラーが発生したクラス/タスクのみロールバック
   # (現在のスクリプトは全体削除のみ対応、将来的に改善予定)

   # 再マイグレーション
   python scripts/migrate_parent_documents.py --execute
   ```

### 問題3: Increment()が動作しない

**症状:**
- file_countが更新されない
- 並行アップロードでfile_countが不正確

**原因:**
- Firestoreクライアントのバージョン問題
- エミュレーター使用時の制限

**解決策:**

1. **google-cloud-firestoreのバージョン確認**
   ```bash
   pip show google-cloud-firestore
   # Version: 2.11.0以上が推奨
   ```

2. **エミュレーター使用時の注意**
   - Firestore Emulatorは`Increment()`をサポートしています
   - `FIRESTORE_EMULATOR_HOST`環境変数が正しく設定されているか確認

3. **手動修正**
   ```bash
   # file_countを手動で修正
   python scripts/fix_file_count.py --execute
   ```

### 問題4: created_atが設定されない

**症状:**
- 親ドキュメントに`created_at`フィールドが存在しない
- インテグレーションテストで`AssertionError: assert 'created_at' in parent_data`

**原因:**
- `_update_task_metadata()`が既存ドキュメントと判断している
- ドキュメント存在チェックのタイミング問題

**解決策:**

1. **コード確認**
   ```python
   # src/firestore_service.py の _update_task_metadata()
   doc = task_ref.get()

   if not doc.exists:
       update_data["created_at"] = firestore.SERVER_TIMESTAMP
   ```

2. **親ドキュメントを再作成**
   ```bash
   # 1. ロールバック
   python scripts/rollback_parent_documents.py --confirm

   # 2. 再マイグレーション
   python scripts/migrate_parent_documents.py --execute
   ```

### 問題5: テストがFirestore Emulatorに接続できない

**症状:**
- インテグレーションテストで接続エラー
- `Connection refused` エラー

**原因:**
- Firestore Emulatorが起動していない
- `FIRESTORE_EMULATOR_HOST`環境変数が未設定

**解決策:**

1. **エミュレーター起動確認**
   ```bash
   # エミュレーターのプロセス確認
   ps aux | grep firebase

   # エミュレーターが起動していない場合
   gcloud emulators firestore start --host-port=localhost:8080
   ```

2. **環境変数設定**
   ```bash
   export FIRESTORE_EMULATOR_HOST="localhost:8080"
   ```

3. **テスト実行**
   ```bash
   pytest tests/integration/ -v
   ```

### 問題6: CI/CDでテストが失敗する

**症状:**
- GitHub Actionsでインテグレーションテストが失敗
- ローカルでは成功する

**原因:**
- CI環境でFirestore Emulatorが正しく起動していない
- 環境変数の設定漏れ

**解決策:**

1. **GitHub Actions設定確認** (`.github/workflows/test.yml`)
   ```yaml
   - name: Start Firestore Emulator
     run: |
       gcloud emulators firestore start --host-port=localhost:8080 &
       sleep 5

   - name: Run Integration Tests
     env:
       FIRESTORE_EMULATOR_HOST: localhost:8080
     run: |
       pytest tests/integration/ -v --cov
   ```

2. **エミュレーター起動待機時間の調整**
   ```yaml
   # sleep時間を延長
   sleep 10
   ```

3. **ログ確認**
   ```bash
   # GitHub Actionsのログで確認
   # "Firestore Emulator started on localhost:8080"が表示されているか
   ```

### 問題7: 新しいクラス/タスクが認識されない

**症状:**
- マイグレーション時に新しいクラス/タスクがスキップされる
- `KNOWN_CLASSES`や`KNOWN_TASK_IDS`に含まれていない

**原因:**
- `src/config/classes.py`が更新されていない

**解決策:**

1. **classes.py更新**
   ```python
   # src/config/classes.py

   KNOWN_CLASSES = [
       "令和7年度 デジタル中核人材養成研修 №01",
       "令和7年度 デジタル中核人材養成研修 №02",
       "新しいクラス名",  # 追加
   ]

   KNOWN_TASK_IDS = [
       "課題①",
       "課題②",
       "課題③",
       "新しいタスクID",  # 追加
   ]
   ```

2. **再マイグレーション**
   ```bash
   # 新しいクラス/タスクのみがマイグレーションされる
   python scripts/migrate_parent_documents.py --execute
   ```

---

## 今後の拡張性

### 1. 新しいメタデータフィールドの追加

親ドキュメントに新しいフィールドを追加する場合:

**例: 提出期限（deadline）フィールドの追加**

#### ステップ1: FirestoreServiceの拡張

```python
# src/firestore_service.py

def _update_task_metadata(
    self,
    class_name: str,
    task_id: str,
    task_pattern: str,
    deadline: Optional[str] = None,  # 新規パラメータ
) -> bool:
    """Update or create task parent document with metadata."""

    update_data = {
        "task_id": task_id,
        "task_pattern": task_pattern,
        "file_count": firestore.Increment(1),
        "last_updated": firestore.SERVER_TIMESTAMP,
    }

    # 新規フィールドの追加
    if deadline:
        update_data["deadline"] = deadline

    if not doc.exists:
        update_data["created_at"] = firestore.SERVER_TIMESTAMP

    task_ref.set(update_data, merge=True)
```

#### ステップ2: record_upload()の更新

```python
def record_upload(
    self,
    class_name: str,
    task_id: str,
    # ... 既存パラメータ ...
    task_pattern: Optional[str] = None,
    deadline: Optional[str] = None,  # 新規パラメータ
) -> bool:
    task_pattern = task_pattern or task_id

    self._update_task_metadata(
        class_name, task_id, task_pattern, deadline=deadline
    )
```

#### ステップ3: マイグレーションスクリプトの更新

```python
# scripts/migrate_parent_documents.py

parent_data = {
    "task_id": task_id,
    "task_pattern": task_id,
    "file_count": file_count,
    "deadline": None,  # デフォルト値を設定
    "created_at": firestore.SERVER_TIMESTAMP,
    "last_updated": firestore.SERVER_TIMESTAMP,
}
```

#### ステップ4: テストの追加

```python
# tests/unit/test_firestore_service.py

def test_update_task_metadata_with_deadline(mock_firestore):
    """Test that deadline field is included when provided."""
    service = FirestoreService()

    service._update_task_metadata(
        class_name="Test Class",
        task_id="課題①",
        task_pattern="課題①",
        deadline="2025-12-31",
    )

    # Verify deadline was included in update_data
    assert "deadline" in mock_firestore.set.call_args[0][0]
```

### 2. 統計情報の追加

親ドキュメントに集計情報を追加する場合:

**例: 平均スコア（average_score）フィールドの追加**

```python
# src/firestore_service.py

def record_upload(
    self,
    # ... 既存パラメータ ...
    score: Optional[float] = None,
) -> bool:
    # ファイルドキュメントにスコアを保存
    record = {
        # ... 既存フィールド ...
        "score": score,
    }

    # 親ドキュメントの平均スコアを更新
    if score is not None:
        self._update_average_score(class_name, task_id, score)

def _update_average_score(
    self, class_name: str, task_id: str, new_score: float
) -> bool:
    """Update average score using transaction."""
    try:
        task_ref = self.db.collection(class_name).document(task_id)

        @firestore.transactional
        def update_in_transaction(transaction, task_ref):
            snapshot = task_ref.get(transaction=transaction)
            data = snapshot.to_dict()

            current_avg = data.get("average_score", 0.0)
            current_count = data.get("file_count", 0)

            # 新しい平均を計算
            new_avg = (current_avg * current_count + new_score) / (current_count + 1)

            transaction.update(task_ref, {
                "average_score": new_avg,
                "last_updated": firestore.SERVER_TIMESTAMP,
            })

        transaction = self.db.transaction()
        update_in_transaction(transaction, task_ref)
        return True

    except Exception as e:
        logger.error(f"Failed to update average score: {e}")
        return False
```

### 3. 複数データベースのサポート

現在は`carewell-native`データベースのみをサポートしていますが、複数データベースに対応する場合:

```python
# src/firestore_service.py

class FirestoreService:
    def __init__(self, database: str = "carewell-native"):
        """
        Initialize Firestore client.

        Args:
            database: Firestore database name (default: carewell-native)
        """
        self.db = firestore.Client(database=database)
        self.database_name = database
```

**マイグレーションスクリプトの更新:**

```python
# scripts/migrate_parent_documents.py

def migrate_parent_documents(
    dry_run: bool = True,
    db=None,
    database: str = "carewell-native",  # 新規パラメータ
) -> Dict:
    if db is None:
        db = firestore.Client(database=database)
```

### 4. カスタムバリデーションルールの追加

バリデーション時に追加のチェックを行う場合:

```python
# scripts/migrate_parent_documents.py

def validate_migration_extended() -> Dict:
    """Extended validation with additional checks."""

    # 基本バリデーション
    result = validate_migration()

    # 追加チェック: task_patternの存在確認
    pattern_issues = []
    for class_name in KNOWN_CLASSES:
        for task_id in KNOWN_TASK_IDS:
            task_ref = db.collection(class_name).document(task_id)
            task_doc = task_ref.get()

            if task_doc.exists:
                data = task_doc.to_dict()
                if not data.get("task_pattern"):
                    pattern_issues.append({
                        "class_name": class_name,
                        "task_id": task_id,
                        "issue": "Missing task_pattern field"
                    })

    result["pattern_issues"] = pattern_issues
    return result
```

### 5. Pub/Sub連携による非同期処理

大規模なマイグレーションの場合、Pub/Subを使用した非同期処理:

```python
# scripts/migrate_parent_documents_async.py

from google.cloud import pubsub_v1

def publish_migration_task(class_name: str, task_id: str):
    """Publish migration task to Pub/Sub."""
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path("carewell-automation", "migration-tasks")

    data = json.dumps({
        "class_name": class_name,
        "task_id": task_id,
    }).encode("utf-8")

    publisher.publish(topic_path, data)

def migrate_parent_documents_async():
    """Publish all migration tasks to Pub/Sub."""
    for class_name in KNOWN_CLASSES:
        for task_id in KNOWN_TASK_IDS:
            publish_migration_task(class_name, task_id)
```

**Cloud Functionでの処理:**

```python
# functions/process_migration_task.py

def process_migration_task(event, context):
    """Cloud Function to process single migration task."""
    data = json.loads(base64.b64decode(event['data']).decode('utf-8'))

    class_name = data["class_name"]
    task_id = data["task_id"]

    # 単一タスクのマイグレーション実行
    migrate_single_task(class_name, task_id)
```

### 6. モニタリングとアラート

Cloud Monitoringとの統合:

```python
# src/firestore_service.py

from google.cloud import monitoring_v3

class FirestoreService:
    def __init__(self):
        self.db = firestore.Client(database="carewell-native")
        self.metrics_client = monitoring_v3.MetricServiceClient()

    def _update_task_metadata(self, ...):
        try:
            # ... 既存処理 ...

            # メトリクス記録
            self._record_metric("parent_document_update_success", 1)
            return True

        except Exception as e:
            # メトリクス記録
            self._record_metric("parent_document_update_failure", 1)

            # アラート送信
            self._send_alert(f"Failed to update parent document: {e}")
            return False

    def _record_metric(self, metric_name: str, value: int):
        """Record custom metric to Cloud Monitoring."""
        # Cloud Monitoring API を使用してメトリクス記録
        pass

    def _send_alert(self, message: str):
        """Send alert to notification channel."""
        # Cloud Monitoring Alerts または Slack通知
        pass
```

---

## 付録

### A. 関連ファイル一覧

| ファイル | 種類 | 説明 |
|---------|------|------|
| `src/firestore_service.py` | コア | Firestoreサービス（親ドキュメント管理） |
| `scripts/migrate_parent_documents.py` | スクリプト | マイグレーションスクリプト |
| `scripts/rollback_parent_documents.py` | スクリプト | ロールバックスクリプト |
| `scripts/fix_file_count.py` | スクリプト | file_count修正スクリプト |
| `tests/unit/test_firestore_service.py` | テスト | FirestoreServiceユニットテスト |
| `tests/unit/test_migrate_parent_documents.py` | テスト | マイグレーションユニットテスト |
| `tests/unit/test_rollback_parent_documents.py` | テスト | ロールバックユニットテスト |
| `tests/unit/test_fix_file_count.py` | テスト | file_count修正ユニットテスト |
| `tests/integration/test_file_upload.py` | テスト | ファイルアップロード統合テスト |
| `tests/integration/test_migration.py` | テスト | マイグレーション統合テスト |
| `tests/integration/conftest.py` | テスト | Firestore Emulator設定 |
| `.github/workflows/test.yml` | CI/CD | GitHub Actions設定 |

### B. 環境変数

| 変数名 | 説明 | 例 |
|--------|------|-----|
| `GOOGLE_CLOUD_PROJECT` | GCPプロジェクトID | `carewell-automation` |
| `GOOGLE_APPLICATION_CREDENTIALS` | サービスアカウント認証情報ファイルパス | `$HOME/.config/gcloud/application_default_credentials.json` |
| `FIRESTORE_EMULATOR_HOST` | Firestore Emulatorホスト（テスト時のみ） | `localhost:8080` |

### C. よく使うコマンド

```bash
# マイグレーション
python scripts/migrate_parent_documents.py --dry-run     # プレビュー
python scripts/migrate_parent_documents.py --execute     # 実行
python scripts/migrate_parent_documents.py --validate-only  # バリデーションのみ

# ロールバック
python scripts/rollback_parent_documents.py              # プレビュー
python scripts/rollback_parent_documents.py --confirm    # 実行

# file_count修正
python scripts/fix_file_count.py --dry-run               # プレビュー
python scripts/fix_file_count.py --execute               # 実行
python scripts/fix_file_count.py --execute --class-name "クラス名"  # 特定クラス

# テスト実行
pytest tests/unit/ -v                                    # ユニットテスト
pytest tests/integration/ -v                             # 統合テスト
pytest tests/ -v --cov                                   # 全テスト+カバレッジ

# Firestore Emulator
gcloud emulators firestore start --host-port=localhost:8080  # 起動
export FIRESTORE_EMULATOR_HOST="localhost:8080"         # 環境変数設定
```

### D. 参考資料

- [Firestore Native Mode Documentation](https://cloud.google.com/firestore/docs)
- [Firestore Data Model Best Practices](https://firebase.google.com/docs/firestore/data-model)
- [Firestore Increment Documentation](https://firebase.google.com/docs/firestore/manage-data/add-data#increment_a_numeric_value)
- [Firestore Emulator Documentation](https://firebase.google.com/docs/emulator-suite/install_and_configure)
- [Google Cloud Python Client Libraries](https://googleapis.dev/python/firestore/latest/)

---

## 変更履歴

| 日付 | バージョン | 変更内容 | 担当者 |
|------|-----------|---------|--------|
| 2025-01-10 | 1.0 | 初版作成 | AI Assistant (Claude) |

---

## フィードバック

このドキュメントに関する質問、提案、問題報告は、GitHubのIssueまたはPull Requestでお願いします。

**リポジトリ:** `carewell-gcp-drive-automation`
**ドキュメントパス:** `docs/firestore-schema-improvement-implementation.md`
