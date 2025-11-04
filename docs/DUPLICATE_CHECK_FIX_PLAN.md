# 重複チェック機能修正 緊急対応計画

## 📅 作成日
2025-11-04

## 🔗 関連ドキュメント
- [問題分析](./DUPLICATE_CHECK_BUG_ANALYSIS.md)
- [Firestoreスキーマ改善仕様](.kiro/specs/firestore-schema-improvement/)

## 🎯 目的

Firestoreコレクションパスの不整合を修正し、重複チェック機能を正常化する

## 📋 問題のサマリー

### 現在の状況

**症状**:
- 156件のはずが197件取得されている
- 重複ファイルが検出されず繰り返しダウンロード

**根本原因**:
```python
# 間違ったパス
self.db.collection(class_name).document(task_id).collection("documents")

# 正しいパス
self.db.collection("submissions").document(class_name).collection("tasks").document(task_id).collection("files")
```

## 🎯 修正方針

### 修正内容

**ファイル**: `src/firestore_service.py`

**影響を受けるメソッド**: 4つ

1. `check_already_uploaded_by_student_date()` (Lines 121-126)
2. `check_already_uploaded()` (Lines 178-184)
3. `record_upload()` (Lines 260-266)
4. `_update_task_metadata()` (Line 67)

### 修正箇所詳細

#### 1. check_already_uploaded_by_student_date() (Lines 121-126)

**修正前**:
```python
# Collection path: {class_name}/{task_id}/documents
collection_ref = (
    self.db.collection(class_name)
    .document(task_id)
    .collection("documents")
)
```

**修正後**:
```python
# Collection path: submissions/{class_name}/tasks/{task_id}/files
collection_ref = (
    self.db.collection("submissions")
    .document(class_name)
    .collection("tasks")
    .document(task_id)
    .collection("files")
)
```

#### 2. check_already_uploaded() (Lines 178-184)

**修正前**:
```python
# Collection path: {class_name}/{task_id}/documents
doc_ref = (
    self.db.collection(class_name)
    .document(task_id)
    .collection("documents")
    .document(composite_key)
)
```

**修正後**:
```python
# Collection path: submissions/{class_name}/tasks/{task_id}/files
doc_ref = (
    self.db.collection("submissions")
    .document(class_name)
    .collection("tasks")
    .document(task_id)
    .collection("files")
    .document(composite_key)
)
```

#### 3. record_upload() (Lines 260-266)

**修正前**:
```python
# Collection path: {class_name}/{task_id}/documents
doc_ref = (
    self.db.collection(class_name)
    .document(task_id)
    .collection("documents")
    .document(composite_key)
)
```

**修正後**:
```python
# Collection path: submissions/{class_name}/tasks/{task_id}/files
doc_ref = (
    self.db.collection("submissions")
    .document(class_name)
    .collection("tasks")
    .document(task_id)
    .collection("files")
    .document(composite_key)
)
```

#### 4. _update_task_metadata() (Line 67)

**修正前**:
```python
task_ref = self.db.collection(class_name).document(task_id)
```

**修正後**:
```python
task_ref = (
    self.db.collection("submissions")
    .document(class_name)
    .collection("tasks")
    .document(task_id)
)
```

## 📊 期待される効果

| 項目 | 現在 | 修正後 |
|------|------|--------|
| 重複チェック | ❌ 機能していない | ✅ 正常動作 |
| ファイル取得数 | 197件（重複含む） | 156件（重複なし） |
| Firestoreドキュメント数 | 増加し続ける | 156件で安定 |
| 処理時間 | 長い（重複処理あり） | 短い（重複スキップ） |
| Google Drive容量 | 無駄に消費 | 最適化 |

## 📝 実施計画

### ステップ1: コード修正

1. `src/firestore_service.py` の4メソッドを修正
2. コメントも正しいパスに更新

### ステップ2: テスト検証

**テスト方法**:
1. 既存データをクリーンアップ（submissions配下）
2. 少数件でテスト実行（class01-task01の1-2件など）
3. Firestoreで正しいパスに保存されているか確認
4. 2回目実行で重複スキップされるか確認

**確認ポイント**:
- ✅ Firestoreパス: `submissions/{class_name}/tasks/{task_id}/files/`
- ✅ 重複チェックログ: "File already uploaded (early check)"
- ✅ 2回目実行: "Skipping already uploaded file"
- ✅ ファイル数: 増加しない

### ステップ3: デプロイ

1. Gitコミット
2. GitHub Actions自動デプロイ
3. Cloud Run新リビジョン確認

### ステップ4: 実運用テスト

1. 小規模ジョブで確認（class01-task01など）
2. ログとFirestore確認
3. 全ジョブ実行

### ステップ5: 既存データクリーンアップ（オプション）

古いパス `{class_name}/{task_id}/documents/` のデータを削除

**注意**: 新しいパスでデータが正常に保存されていることを確認後に実施

## ⚠️ リスク評価

### 修正によるリスク

| リスク | 発生確率 | 影響度 | 対策 |
|--------|---------|--------|------|
| パス指定ミス | 低 | 高 | テスト検証で確認 |
| 既存データとの不整合 | 中 | 中 | 段階的デプロイ |
| Dashboardとの不整合 | 低 | 中 | Dashboardは既に正しいパス使用 |

### ロールバック計画

**ロールバック条件**:
- Firestore書き込みエラーが発生
- 重複チェックが動作しない
- その他の重大な問題

**ロールバック手順**:
```bash
# コミット履歴を確認
git log --oneline -5

# 該当コミットをrevert
git revert <commit-hash>

# リモートにpush
git push origin main

# GitHub Actionsで自動デプロイ
```

## ✅ テスト計画

### テストケース

| No | テスト内容 | 期待結果 | 確認方法 |
|----|----------|---------|---------|
| 1 | 初回ファイル取得 | Firestoreに正しいパスで保存 | Firestore確認 |
| 2 | 重複ファイル確認 | "File already uploaded" ログ出力 | ログ確認 |
| 3 | 重複ファイルスキップ | ダウンロードされない | ログ確認 |
| 4 | ファイル数 | 156件で安定（増加しない） | Firestore確認 |
| 5 | task親ドキュメント | 正しいパスに作成 | Firestore確認 |
| 6 | Dashboard連携 | クラス一覧・課題一覧表示 | Dashboard確認 |

### 成功基準

- ✅ 全ドキュメントが `submissions/{class_name}/tasks/{task_id}/files/` に保存
- ✅ 重複チェックが正常動作（ログ確認）
- ✅ 2回目実行でファイル数が増加しない
- ✅ Dashboardで正常に表示される
- ✅ エラーログなし

## 📝 実施チェックリスト

### 実施前

- [ ] 問題分析ドキュメント完了
- [ ] 修正計画ドキュメント完了
- [ ] 修正内容レビュー

### 実施中

- [ ] コード修正実装
- [ ] 修正内容をGitコミット
- [ ] GitHub Actionsデプロイ完了確認

### 実施後

- [ ] テスト実行
- [ ] テスト結果検証（全6項目）
- [ ] エラーログ確認
- [ ] 全ドキュメント更新
- [ ] 最終Gitコミット・プッシュ

## 📝 実施記録

### 実施日時
- **予定日**: 2025-11-04
- **実施日**: _________
- **実施者**: Claude Code

### 実施結果

| ステップ | ステータス | 備考 |
|---------|-----------|------|
| コード修正 | [ ] 完了 / [ ] 失敗 | |
| Gitコミット | [ ] 完了 / [ ] 失敗 | コミットハッシュ: ____ |
| デプロイ完了 | [ ] 完了 / [ ] 失敗 | リビジョン: ____ |
| テスト実行 | [ ] 完了 / [ ] 失敗 | 実行時刻: ____ |
| 結果検証 | [ ] 成功 / [ ] 失敗 | 詳細: ____ |

### 問題発生時の対応記録
（問題が発生した場合のみ記入）

---

## 🔧 追加の問題と解決（2025-11-04）

### 問題: テストでのFirestoreデータベース名の誤変更

**発生した問題**:
- テストコード修正時にFirestore Emulatorのデータベース名を`carewell-native`から`(default)`に誤って変更
- コミット `5b7d950` で混入

**原因**:
- Firestore Emulatorのクリーンアップ処理実装時に、元々の設計ドキュメントを確認せずに変更
- Emulator REST APIが`(default)`データベースを使うと誤解

**解決策**:
- コミット `4e5ec4e` でデータベース名を`carewell-native`に revert
- 変更内容:
  - `tests/conftest.py`: `emulator_client`フィクスチャのdatabase引数
  - `tests/integration/test_file_upload.py`: setup内のclear URL
- 両方のファイルで`(default)`を`carewell-native`に戻し
- Emulator REST APIのクリアエンドポイントURLも`carewell-native`に対応

**教訓**:
- コードベース変更時は必ず元々の設計ドキュメントを確認する
- 特にデータベース名のような重要な設定値は安易に変更しない
- 参照: `docs/firestore-schema-improvement-implementation.md` Line 529

**参照コミット**:
- 誤変更: `5b7d950`
- 修正: `4e5ec4e`

---

## 🔧 追加の問題と解決2（2025-11-04）

### 問題: task_patternパラメータがrecord_uploadに渡されていない

**発生した問題**:
- `main.py`でCloud Schedulerから`task_pattern`を受け取っているが、`record_upload`に渡していない
- 結果として、Firestoreに保存される`task_pattern`が常に`task_id`にデフォルトされる
- 例: 本来 "課題①業務分析　※～11/3〆切" → 実際 "課題①"

**影響**:
- 2ページ目以降も含め、全ての提出ファイルのメタデータで`task_pattern`が簡略化される
- Dashboardで課題タイトルが正しく表示されない可能性

**根本原因**:
- `main.py` Line 183-193で`firestore_service.record_upload()`を呼び出す際に、`task_pattern`パラメータを省略
- 設計仕様（`.kiro/specs/firestore-schema-improvement/design.md` Line 367）では`task_pattern`を渡すべき

**解決策**:
- `main.py`の`record_upload`呼び出しに`task_pattern=task_pattern`を追加
- これにより、Cloud Schedulerから送信された正しい`task_pattern`がFirestoreに保存される

**修正内容**:
```python
# Before
firestore_service.record_upload(
    class_name,
    task_id,
    submission["student_name"],
    submission.get("student_id", ""),
    submission["filename"],
    drive_file_id,
    drive_folder_id,
    submission.get("submit_date", ""),
    metadata=metadata,
)

# After
firestore_service.record_upload(
    class_name,
    task_id,
    submission["student_name"],
    submission.get("student_id", ""),
    submission["filename"],
    drive_file_id,
    drive_folder_id,
    submission.get("submit_date", ""),
    metadata=metadata,
    task_pattern=task_pattern,  # ← 追加
)
```

**検証**:
- ✅ Unit tests全て成功（9 passed）
- ✅ 既存の動作に影響なし（後方互換性維持）
- ✅ 2ページ目以降も正しい`task_pattern`が保存される

**参照**:
- 設計仕様: `.kiro/specs/firestore-schema-improvement/design.md` Line 367-374
- 要件: `.kiro/specs/firestore-schema-improvement/requirements.md` Line 98-102

---

**作成者**: Claude Code
**レビュー**: 要レビュー
**ステータス**: Implementation In Progress (Tests Fixed, Database Name Reverted, task_pattern Fixed)
