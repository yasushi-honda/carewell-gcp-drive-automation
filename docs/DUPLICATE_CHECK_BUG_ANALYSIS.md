# 重複チェック機能不具合 緊急分析

## 📅 発見日
2025-11-04

## 🚨 問題の概要

**症状**: 156件のはずが197件取得されている - 重複ファイルが検出されず繰り返しダウンロード・アップロードされている

**影響度**: 🔴 **Critical** - 重複チェック機能が完全に機能していない

## 🔍 根本原因

### Firestoreコレクションパスの不整合

`src/firestore_service.py`で、**保存パスと確認パスが異なっている**

#### 現在のコード (Lines 260-266)

```python
# Collection path: {class_name}/{task_id}/documents
doc_ref = (
    self.db.collection(class_name)
    .document(task_id)
    .collection("documents")
    .document(composite_key)
)
```

**実際のパス**:
```
令和7年度 デジタル中核人材養成研修 №01/課題①/documents/{composite_key}
```

#### 正しいパス（Firestoreスキーマ改善後）

```
submissions/{class_name}/tasks/{task_id}/files/{composite_key}
```

### 影響を受けるメソッド

| メソッド | 行番号 | 問題 |
|---------|--------|------|
| `check_already_uploaded_by_student_date()` | 121-126 | ❌ 間違ったパスで検索 |
| `check_already_uploaded()` | 178-184 | ❌ 間違ったパスで検索 |
| `record_upload()` | 260-266 | ❌ 間違ったパスに保存 |
| `_update_task_metadata()` | 67 | ❌ 間違ったパスに保存 |

## 📊 問題の影響

### データフロー

```
1. check_already_uploaded_by_student_date()
   → 間違ったパス: {class_name}/{task_id}/documents で検索
   → 結果: ドキュメントが見つからない（None）

2. ファイルダウンロード・アップロード実行（重複と認識されない）

3. record_upload()
   → 間違ったパス: {class_name}/{task_id}/documents に保存
   → 結果: 新しいドキュメントが作成される

4. 次回実行時
   → 再び同じファイルをダウンロード
   → さらにドキュメントが増える
```

### 実測データ

- **期待**: 156件のファイル
- **実際**: 197件取得
- **重複**: 41件 (197 - 156 = 41)

## 🔬 証拠

### ログ分析

```
2025-11-04 01:46:06 - Skipping already uploaded file (early check): student_id=N9903...
```

ログには "Skipping" メッセージが出力されているが、これは：
- Firestoreクエリが実行されている
- しかし**間違ったパスで検索している**ため、ドキュメントが見つからない
- 結果的にスキップされず、ダウンロードが実行される

## 💡 Firestoreスキーマ改善の経緯

### 以前のスキーマ（Old）

```
{class_name}/
  {task_id}/
    documents/
      {composite_key}
```

### 新しいスキーマ（New - 2025年実装）

```.kiro/specs/firestore-schema-improvement` で実装:

submissions/
  {class_name}/
    tasks/
      {task_id}/
        files/
          {composite_key}
```

**理由**:
- タスク親ドキュメントによる動的課題管理対応
- メタデータの階層的管理
- クラス一覧・課題一覧の効率的な取得

## 🎯 修正方針

### 必要な変更

**ファイル**: `src/firestore_service.py`

**修正箇所**: 4メソッド

1. **`check_already_uploaded_by_student_date()`** (Lines 121-126)
2. **`check_already_uploaded()`** (Lines 178-184)
3. **`record_upload()`** (Lines 260-266)
4. **`_update_task_metadata()`** (Line 67)

### 修正内容

#### 修正前

```python
# 間違ったパス
collection_ref = (
    self.db.collection(class_name)
    .document(task_id)
    .collection("documents")
)
```

#### 修正後

```python
# 正しいパス
collection_ref = (
    self.db.collection("submissions")
    .document(class_name)
    .collection("tasks")
    .document(task_id)
    .collection("files")
)
```

## 📋 修正タスク

### 優先度: 🔴 Critical - 即座に修正が必要

1. ✅ 問題分析完了
2. ⏳ 緊急対応計画策定
3. ⏳ コード修正実装
4. ⏳ テスト検証
5. ⏳ デプロイ
6. ⏳ Firestore既存データクリーンアップ検討

## ⚠️ 注意事項

### 既存データの扱い

修正後も、間違ったパスに保存された既存データは残ります：

```
令和7年度 デジタル中核人材養成研修 №01/
  課題①/
    documents/
      {197件の重複ドキュメント}  ← 古いパス（削除検討）

submissions/
  令和7年度 デジタル中核人材養成研修 №01/
    tasks/
      課題①/
        files/
          {0件}  ← 新しいパス（これから保存される）
```

**対応方針**:
1. まずコードを修正してデプロイ
2. 修正後のテスト実行
3. 古いパスのデータを削除（別タスク）

## 📝 関連ドキュメント

- [Firestoreスキーマ改善仕様](.kiro/specs/firestore-schema-improvement/)
- [Dashboard設計](dashboard/README.md) - 正しいパスを使用している

---

**作成者**: Claude Code
**レビュー**: 要レビュー
**ステータス**: 🔴 **Critical - 即座に修正が必要**
