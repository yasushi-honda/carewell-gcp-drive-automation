# 重複チェック早期化実装計画

## 📅 作成日
2025-11-04

## 🔗 関連ドキュメント
- [問題分析レポート](./PAGINATION_BUG_ANALYSIS.md)
- [タイムアウト延長計画](./TIMEOUT_EXTENSION_PLAN.md)

## 🎯 目的

download link取得処理**前**に重複チェックを実施することで、処理時間を大幅に短縮します。

## 📋 現状と問題

### 現在の処理フロー（問題あり）

```
1. get_submission_list() [playwright_automation.py]
   ├─ 全ページループ
   │  ├─ 基本情報取得（100件）
   │  ├─ download link取得（100件）← 重複分も含めて処理！
   │  └─ 次ページへ
   └─ 全submission返却（149件）

2. main() [main.py]
   ├─ submissionループ
   │  ├─ 重複チェック（Firestore）← ここで初めてチェック！
   │  ├─ 重複ならスキップ
   │  ├─ ダウンロード
   │  └─ アップロード
   └─ 完了
```

### 時間の無駄

**実測データ**（class01-task01、149件）:
- download link取得: 149件 × 5.5秒 = **820秒**
- うち重複分: 44件 × 5.5秒 = **242秒の無駄**

### 影響

| シナリオ | 現在 | 問題 |
|---------|------|------|
| 初回実行（149件新規） | 約24-30分 | タイムアウト（900秒） |
| 2回目以降（149件全て重複） | 約17分 | 無駄な処理が大半 |

## 🎯 最適化後の処理フロー

### 提案: download link取得前に重複チェック

```
1. get_submission_list(class_name, task_id, firestore_service) [playwright_automation.py]
   ├─ 全ページループ
   │  ├─ 基本情報取得（100件）
   │  ├─ 重複チェック（Firestore）← ★ ここで早期チェック！
   │  ├─ download link取得（非重複のみ）← ★ 必要な分だけ！
   │  └─ 次ページへ
   └─ 全submission返却（重複フラグ付き）

2. main() [main.py]
   ├─ submissionループ
   │  ├─ 重複フラグ確認 ← ★ 既にチェック済み
   │  ├─ 重複ならスキップ
   │  ├─ ダウンロード
   │  └─ アップロード
   └─ 完了
```

### 時間短縮効果

| シナリオ | 現在 | 最適化後 | 短縮 |
|---------|------|----------|------|
| 初回実行（149件新規） | 約24-30分 | 約24-30分 | 変わらず |
| 2回目以降（44件重複） | 約17分 | **約13分** | **4分短縮** |
| 2回目以降（149件全て重複） | 約17分 | **約3分** | **14分短縮** |

**重要**: 初回実行でも900秒（15分）タイムアウトには不足するため、タイムアウト延長も併用します。

## 📝 実装計画

### Phase 1: コード変更

#### 変更ファイル1: `src/playwright_automation.py`

**変更箇所**: `get_submission_list()` メソッド（lines 329-574）

**変更内容**:

1. **メソッドシグネチャの拡張** (line 329)
```python
# Before
def get_submission_list(self) -> dict:

# After
def get_submission_list(
    self,
    class_name: Optional[str] = None,
    task_id: Optional[str] = None,
    firestore_service = None
) -> dict:
```

2. **インポート追加** (top of file)
```python
from typing import Optional
# FirestoreServiceはmain.pyでインポート済みなので型ヒントのみ
```

3. **重複チェック統合** (lines 468-493の前に挿入)
```python
# Before download link loop: Check for duplicates if Firestore service provided
if firestore_service and class_name and task_id:
    logger.info(f"Performing early duplicate check for {len(submission_basics)} submissions")

    for basic in submission_basics:
        # Check if already uploaded
        try:
            existing_upload = firestore_service.check_already_uploaded(
                class_name,
                task_id,
                basic.get("student_id", ""),
                basic.get("filename_placeholder", ""),  # Will check based on student/date
                basic.get("submit_date", ""),
            )

            if existing_upload:
                # Mark as duplicate
                basic["is_duplicate"] = True
                basic["skip_reason"] = "already_uploaded"
                logger.info(f"Duplicate detected (early check): {basic['student_name']}")
            else:
                basic["is_duplicate"] = False
        except Exception as e:
            logger.warning(f"Early duplicate check failed for {basic['student_name']}: {e}")
            # Fail-open: if check fails, treat as non-duplicate
            basic["is_duplicate"] = False
else:
    # No Firestore service provided, mark all as non-duplicate
    logger.info("No Firestore service provided, skipping early duplicate check")
    for basic in submission_basics:
        basic["is_duplicate"] = False
```

4. **download link取得のスキップ** (lines 468-493を修正)
```python
# Second pass: Get download links for non-duplicate submissions only
for basic in submission_basics:
    # Skip download link retrieval for duplicates
    if basic.get("is_duplicate", False):
        # Add to submissions list with minimal info
        submission = {
            **basic,
            "download_url": None,
            "filename": None,
        }
        all_submissions.append(submission)
        logger.info(f"Skipped download link retrieval (duplicate): {basic['student_name']}")
        continue

    # Existing download link retrieval code
    try:
        logger.info(f"Getting download link for: {basic['student_name']}")
        download_info = self._get_download_link(basic["detail_url"], list_url)

        submission = {
            **basic,
            "download_url": download_info.get("url"),
            "filename": download_info.get("filename"),
        }

        all_submissions.append(submission)
        logger.info(f"Added: {basic['student_name']} - {download_info.get('filename')}")

    except Exception as e:
        logger.error(f"Error processing {basic['student_name']}: {e}", exc_info=True)
```

**問題点**: 早期重複チェックにはfilenameが必要だが、download link取得前にはfilenameが不明。

**解決策**:
- Firestoreのcomposite keyは `{student_id}_{filename}_{submit_date}` の形式
- 早期チェックでは `student_id` と `submit_date` のみで検索
- Firestore Queryを使用して該当学生の同日提出を検索

#### 変更ファイル2: `src/firestore_service.py`

**新規メソッド追加**: `check_already_uploaded_by_student_date()`

```python
def check_already_uploaded_by_student_date(
    self,
    class_name: str,
    task_id: str,
    student_id: str,
    submit_date: str,
) -> Optional[dict]:
    """
    Check if student has already uploaded a file on the given date
    (early duplicate check without filename)

    Args:
        class_name: Class name
        task_id: Task ID (e.g., "課題①")
        student_id: Student ID (e.g., N9902913)
        submit_date: Submission date/time

    Returns:
        Upload record dict if exists, None otherwise
    """
    try:
        # Generate partial key pattern for query
        # composite_key format: {student_id}_{filename}_{safe_submit_date}
        safe_submit_date = (
            submit_date.replace(" ", "_").replace(":", "-").replace("/", "-")
        )
        key_prefix = f"{student_id}_"
        key_suffix = f"_{safe_submit_date}"

        # Query for documents matching the pattern
        # Note: Firestore doesn't support wildcard queries, so we need to:
        # 1. Get all documents for this student+task
        # 2. Filter by submit_date in application code
        collection_ref = (
            self.db.collection(class_name)
            .document(task_id)
            .collection("documents")
        )

        # Query by student_id and submit_date fields
        docs = collection_ref.where("student_id", "==", student_id).where(
            "submit_date", "==", submit_date
        ).limit(1).stream()

        for doc in docs:
            logger.info(
                f"File already uploaded (early check): student_id={student_id}, submit_date={submit_date}"
            )
            return doc.to_dict()

        return None

    except Exception as e:
        logger.error(
            f"Error in early duplicate check for student_id={student_id}, submit_date={submit_date}: {e}",
            exc_info=True
        )
        # Return None to allow processing on error (fail-open for availability)
        return None
```

#### 変更ファイル3: `src/main.py`

**変更箇所**: `get_submission_list()` 呼び出し（line 107）

```python
# Before
submission_data = engine.get_submission_list()

# After
submission_data = engine.get_submission_list(
    class_name=class_name,
    task_id=task_id,
    firestore_service=firestore_service
)
```

**変更箇所**: 重複チェックロジック（lines 129-143）

```python
# Before (full check)
existing_upload = firestore_service.check_already_uploaded(
    class_name,
    task_id,
    submission.get("student_id", ""),
    submission["filename"],
    submission.get("submit_date", ""),
)

# After (respect early check result, but verify with filename)
# Check early duplicate flag first
if submission.get("is_duplicate", False):
    logger.info(
        f"Skipping already uploaded file (early check): student_id={submission.get('student_id')}, submit_date={submission.get('submit_date')}"
    )
    skipped_count += 1
    continue

# For non-early-duplicates, perform full check with filename
# (defense-in-depth: catch any edge cases)
existing_upload = firestore_service.check_already_uploaded(
    class_name,
    task_id,
    submission.get("student_id", ""),
    submission["filename"],
    submission.get("submit_date", ""),
)

if existing_upload:
    logger.info(
        f"Skipping already uploaded file (filename check): {submission['filename']} (Drive ID: {existing_upload.get('drive_file_id')})"
    )
    skipped_count += 1
    continue
```

### Phase 2: テスト計画

#### ユニットテスト

**新規テストケース**: `tests/unit/test_firestore_service.py`

```python
def test_check_already_uploaded_by_student_date():
    """Test early duplicate check by student ID and date"""
    # Setup: Insert test data
    # Execute: Call check_already_uploaded_by_student_date
    # Assert: Returns correct duplicate status
```

#### 統合テスト

**テストケース1**: 初回実行（全件新規）
- 期待: 全件download link取得、全件アップロード
- 検証: ログで「Skipped download link retrieval (duplicate)」が0件

**テストケース2**: 2回目実行（全て重複）
- 期待: download link取得0件、アップロード0件
- 検証: ログで「Skipped download link retrieval (duplicate)」が149件

**テストケース3**: 部分重複（44件重複、105件新規）
- 期待: download link取得105件のみ、アップロード105件
- 検証: ログで「Skipped download link retrieval (duplicate)」が44件

#### 本番テスト

**テスト環境**: carewell-class01-task01（149件）

**テスト手順**:
1. Firestore cleanupで全データ削除（初回実行シミュレーション）
2. Cloud Scheduler手動実行
3. ログで処理時間・件数を検証
4. 再度Cloud Scheduler手動実行（2回目実行シミュレーション）
5. ログで処理時間短縮を検証

## 📊 成功基準

### 必須基準

1. ✅ 機能性
   - 初回実行で全件処理完了
   - 2回目以降で重複を正しくスキップ
   - 部分重複で正しく動作

2. ✅ パフォーマンス
   - 2回目以降（全て重複）で処理時間が3分以内
   - download link取得が重複分スキップされる

3. ✅ 安全性
   - エラーハンドリングが適切（fail-open戦略維持）
   - ロールバックが容易

### 推奨基準

1. ✅ 処理時間短縮
   - 2回目以降（44件重複）で13分以内
   - 初回実行で900秒以内（タイムアウト延長併用）

2. ✅ ログ可視性
   - 早期重複チェックの結果がログで確認可能
   - 処理時間の内訳がログで確認可能

## 🔄 ロールバック計画

### ロールバック条件

以下のいずれかが発生した場合:
1. 重複検出が正しく動作しない（誤検出または検出漏れ）
2. 新たなエラーが発生
3. 処理時間が改善しない

### ロールバック手順

**Step 1**: Git revert

```bash
# 実装コミットを特定
git log --oneline -10

# コミットをrevert
git revert <commit-hash>

# プッシュ
git push origin main
```

**Step 2**: GitHub Actions自動デプロイ完了を待つ

**Step 3**: 検証

```bash
# Cloud Scheduler手動実行
gcloud scheduler jobs run carewell-class01-task01 --location=asia-northeast1

# ログ確認
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=carewell-file-collector" \
  --project=carewell-automation
```

## 📈 将来の改善案

### Option 1: Firestoreインデックス最適化

**目的**: 早期重複チェックのクエリ性能向上

**方法**:
- `student_id` + `submit_date` の複合インデックス作成
- Firestore consoleまたはfirestore.indexesで設定

### Option 2: キャッシング

**目的**: 同一ジョブ内での重複チェック高速化

**方法**:
- `get_submission_list()` 内でメモリキャッシュを使用
- 同じstudent_id + submit_dateの組み合わせを2回チェックしない

## ✅ チェックリスト

### 実装前
- [ ] コード依存関係を分析
- [ ] 設計ドキュメントをレビュー
- [ ] テスト計画を確認

### 実装中
- [ ] `firestore_service.py`に新メソッド追加
- [ ] `playwright_automation.py`のメソッドシグネチャ拡張
- [ ] `playwright_automation.py`に早期重複チェック統合
- [ ] `main.py`の呼び出しを更新
- [ ] エラーハンドリング実装

### 実装後
- [ ] コード変更をコミット・プッシュ
- [ ] GitHub Actionsデプロイ完了を待つ
- [ ] ユニットテスト実行（ローカル）
- [ ] 統合テスト実行（本番）
  - [ ] 初回実行テスト（cleanup後）
  - [ ] 2回目実行テスト（全て重複）
  - [ ] 処理時間検証
- [ ] ログで検証
  - [ ] 早期重複チェックログ確認
  - [ ] download link取得スキップログ確認
  - [ ] 処理時間短縮確認

## 📝 実施記録

### 実施日時
- **予定日**: 2025-11-04
- **実施日**: _________
- **実施者**: _________

### 実施結果

| ステップ | ステータス | 備考 |
|---------|-----------|------|
| コード変更 | [ ] 完了 / [ ] 失敗 | ファイル数: ____ |
| コミット・プッシュ | [ ] 完了 / [ ] 失敗 | コミットハッシュ: ____ |
| デプロイ完了 | [ ] 完了 / [ ] 失敗 | リビジョン: ____ |
| 初回実行テスト | [ ] 完了 / [ ] 失敗 | 処理時間: ____ 秒 |
| 2回目実行テスト | [ ] 完了 / [ ] 失敗 | 処理時間: ____ 秒 |

### 性能測定

**初回実行**（全件新規）:
- 開始時刻: ____
- 終了時刻: ____
- 処理時間: ____ 秒
- download link取得件数: ____
- アップロード件数: ____

**2回目実行**（全て重複）:
- 開始時刻: ____
- 終了時刻: ____
- 処理時間: ____ 秒
- download link取得件数: ____ （期待: 0）
- スキップ件数: ____ （期待: 149）

### 問題発生時の対応記録
（問題が発生した場合のみ記入）

---

**作成者**: Claude Code
**レビュー**: 要レビュー
**ステータス**: Ready for Implementation
