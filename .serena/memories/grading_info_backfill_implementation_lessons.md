# 合否情報バックフィル機能 - 実装の教訓

**実装日**: 2025-11-09
**コミット**: `a175783`
**詳細記録**: `docs/grading-info-feature-implementation-2025-11-09.md`

---

## 🎯 実装サマリー

Carewell WebからHTML抽出した合否情報（pass_status, score, grading_status）を：
1. 新規ファイルアップロード時にFirestore metadataに保存
2. 既存ファイル検出時（重複チェック）に自動的にmetadataを更新（バックフィル）
3. Dashboard で表示（デスクトップ・モバイル対応）

**結果**: 講師は提出状況と採点結果を同じ画面で確認可能、作業効率が大幅に向上

---

## 💡 重要な技術的教訓

### 教訓1: 早期重複チェック時の filename 未取得問題

**課題**:
```
早期重複チェック時点では filename が未取得（download linkをクリックする前）
↓
しかし composite_key を生成するには filename が必要
↓
バックフィル処理でどうやって既存ドキュメントを特定する？
```

**解決策**:
```python
# playwright_automation.py: 早期重複チェック時に existing_composite_key を保存
if existing_upload:
    basic["existing_composite_key"] = existing_upload.get("composite_key")  # ← 重要！
    
# main.py: 保存された composite_key を使用
composite_key = submission.get("existing_composite_key")
firestore_service.update_file_metadata(class_name, task_id, composite_key, metadata)
```

**教訓**:
- ✅ 重複チェックで取得した情報を最大限活用する
- ✅ 後続処理に必要な情報を早期に保存しておく
- ✅ filename が取得できないタイミングでも処理可能な設計を考える

**参照**: `docs/grading-info-feature-implementation-2025-11-09.md` - 実装詳細 Section

---

### 教訓2: metadata構造の最適化 - 重複フィールド削除

**問題のあった実装**:
```python
# ❌ 間違い: 親フィールドに既に存在するデータを metadata に重複保存
metadata = {
    "student_id": ...,    # 親フィールドに存在
    "submit_date": ...,   # 親フィールドに存在
    "pass_status": ...,
    "score": ...,
}
```

**最適化後**:
```python
# ✅ 正解: 親フィールドに存在しないデータのみ metadata に保存
metadata = {
    "pass_status": submission.get("pass_status"),
    "score": submission.get("score"),
    "grading_status": submission.get("status"),  # "status"より明確
    "log_no": submission.get("log_no"),
}
# None値をフィルタリング
metadata = {k: v for k, v in metadata.items() if v is not None}
```

**教訓**:
- ✅ データの冗長性を避ける（DRY原則）
- ✅ 既存フィールドを確認してから metadata 設計
- ✅ None値をフィルタリングしてクリーンなデータを保存
- ✅ 明確な命名（"status" → "grading_status"）

**参照**: `src/main.py:183-191`

---

### 教訓3: バックフィル - 常に最新情報で上書き更新

**設計判断**:
```python
# Firestore UPDATE: 既存metadataを常に上書き
doc_ref.update({"metadata": metadata})
```

**理由**:
1. **講師が後から採点結果を変更する可能性**
   - 例: 「不合格」→「合格」に変更
   - 次回Cloud Scheduler実行時に自動的に最新情報に更新される

2. **部分更新しない理由**:
   - 古い情報が残ると混乱を招く
   - 常に最新のHTML情報を完全に反映させる

3. **パフォーマンス**:
   - 毎回上書き更新してもFirestoreの負荷は低い
   - Cloud Schedulerは30分間隔なので頻繁ではない

**教訓**:
- ✅ 「既存データを保持すべきか」vs「最新情報で上書きすべきか」を明確に判断
- ✅ ビジネス要件（講師の採点変更）を技術設計に反映
- ✅ 部分更新のメリット・デメリットを検討

**参照**: `src/firestore_service.py:244`, `docs/grading-info-feature-implementation-2025-11-09.md` - 技術設計 Section

---

### 教訓4: fail-open戦略の一貫した適用

**実装パターン**:
```python
def update_file_metadata(...) -> bool:
    """
    Returns:
        True if successful, False if error occurred (fail-open strategy)
    """
    try:
        doc_ref.update({"metadata": metadata})
        logger.info(f"Backfilled metadata...")
        return True
    except Exception as e:
        logger.error(f"Failed to update metadata: {e}", exc_info=True)
        # fail-open: 例外を伝播せず、Falseを返して処理継続
        return False
```

**main.py での利用**:
```python
success = firestore_service.update_file_metadata(...)
if success:
    logger.info("Successfully backfilled...")
else:
    logger.warning("Failed to backfill...")
# 失敗してもスキップ処理は継続（可用性優先）
```

**教訓**:
- ✅ fail-open戦略を**すべての非クリティカル処理**に適用
- ✅ エラー時も処理を継続（ファイルアップロードが最優先）
- ✅ ログレベルを適切に使い分け（ERROR, WARNING, INFO）
- ✅ 例外を伝播させず、戻り値でエラーを伝える

**参照**: `CLAUDE.md` - Common Mistakes, `.serena/memories/incident_response_lessons.md`

---

### 教訓5: TypeScript型安全 - Optional Chaining の重要性

**Frontend実装**:
```typescript
// 型定義: すべてoptional
export interface FileData {
  metadata?: {
    pass_status?: string;
    score?: string;
    grading_status?: string;
    log_no?: string;
  };
}

// Vue Template: Optional chaining + fallback
{{ file.metadata?.score || '-' }}

<span v-if="file.metadata?.pass_status">
  {{ file.metadata.pass_status }}
</span>
<span v-else class="text-gray-400">-</span>
```

**教訓**:
- ✅ 既存データ（metadata未設定）への後方互換性を最優先
- ✅ Optional chaining (`?.`) で null安全
- ✅ フォールバック値（`|| '-'`）で未設定時の表示を明示
- ✅ `v-if` で存在確認してから表示
- ✅ TypeScript型定義でoptionalを明示（`?:`）

**参照**: `dashboard/src/types/models.ts`, `dashboard/src/components/FileTable.vue`

---

## 🛡️ 安全性の保証パターン

### パターン1: 既存フィールド変更禁止

**ルール**:
- ❌ 既存のFirestoreフィールドを削除・型変更してはいけない
- ✅ 既存の `metadata` フィールドを拡張する形で実装

**検証方法**:
```bash
# 実装前に必ず確認
cat .kiro/specs/firestore-schema-improvement/requirements.md | grep -A5 "既存フィールド"
```

**参照**: `.kiro/specs/firestore-schema-improvement/requirements.md:106`

---

### パターン2: 重複チェックロジック不変

**ルール**:
- ❌ `check_already_uploaded()` メソッドを変更してはいけない
- ✅ 重複チェック結果を利用する形で実装（`existing_composite_key` の保存）

**理由**:
- 重複チェックは既に十分にテストされている
- 変更すると意図しない副作用が発生するリスク

**参照**: `src/firestore_service.py:161-207`

---

### パターン3: デプロイ後の3点確認（CLAUDE.md準拠）

**必須チェック**:
1. ✅ 新リビジョンが作成されたか
2. ✅ トラフィックが100%新リビジョンに向いているか
3. ✅ ログで新コードの痕跡があるか

**過去のインシデント**: 2025-11-06 - "デプロイ済みのはずが古いコードが実行されていた"

**教訓**:
- ❌ 「GitHub Actions成功 = 新コード稼働」ではない
- ✅ 必ず3点確認してから「デプロイ成功」と判断

**参照**: `CLAUDE.md` - Common Mistakes #8, `.serena/memories/incident_response_lessons.md`

---

## 📊 実装前のドキュメント確認チェックリスト

今回の実装で**実際に確認したドキュメント**:

- [x] `CLAUDE.md` - "🚨 CRITICAL: READ THIS FIRST" セクション
- [x] `CLAUDE.md` - "Common Mistakes to Avoid" セクション
- [x] `.kiro/specs/firestore-schema-improvement/design.md` - metadataフィールド設計
- [x] `.kiro/specs/firestore-schema-improvement/requirements.md` - 既存フィールド変更禁止
- [x] `.serena/memories/incident_response_lessons.md` - 過去の教訓
- [x] `src/firestore_service.py` - `record_upload()` シグネチャ
- [x] `src/playwright_automation.py` - 既存抽出ロジック
- [x] `src/main.py` - データフロー

**これらを読まずにコーディングを開始していたら**:
- ❌ metadata構造に重複フィールドを含めていた（データ冗長性）
- ❌ 既存フィールドを変更してしまう可能性があった（スキーマ破壊）
- ❌ fail-open戦略を破壊していた（可用性低下）

**教訓**: **ドキュメントドリブンは時間の節約**（読む時間 < 後で修正する時間）

---

## 🔍 監視・デバッグのためのログクエリ

### バックフィル実行確認

```bash
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  textPayload=~'Backfilling grading info'" \
  --limit 50 --format json | \
  jq -r '.[] | select(.textPayload) | .textPayload'
```

### バックフィル成功数カウント

```bash
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  textPayload=~'Successfully backfilled grading info'" \
  --limit 1000 --format json | \
  jq -r '.[] | select(.textPayload) | .textPayload' | wc -l
```

### バックフィル失敗確認

```bash
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  (textPayload=~'Failed to backfill' OR textPayload=~'Cannot backfill')" \
  --limit 50 --format json | \
  jq -r '.[] | select(.textPayload) | .textPayload'
```

---

## 🎓 今後の類似実装への適用

### 類似ケース: 別の情報をmetadataに追加したい場合

**手順**:
1. **ドキュメント確認**（必須）
   - `CLAUDE.md` - Critical Configuration
   - `.kiro/specs/firestore-schema-improvement/` - スキーマ設計
   - 既存コード（`src/main.py`, `src/firestore_service.py`）

2. **metadata構造の設計**
   - 既存フィールドとの重複を避ける
   - 明確な命名（曖昧な名前を避ける）
   - None値のフィルタリング

3. **バックフィル処理の検討**
   - 既存データも更新すべきか？
   - 上書き更新 vs 部分更新の判断
   - fail-open戦略の適用

4. **Frontend型定義**
   - すべてoptional（後方互換性）
   - Optional chaining使用
   - フォールバック値設定

5. **デプロイ後の3点確認**
   - リビジョン作成
   - トラフィック配分
   - ログで新コード確認

**参照**: 本ドキュメント全体

---

## 📚 関連ドキュメント

- **詳細実装記録**: `docs/grading-info-feature-implementation-2025-11-09.md`
- **Firestoreスキーマ設計**: `.kiro/specs/firestore-schema-improvement/design.md`
- **過去のインシデント**: `docs/common-mistakes.md`
- **プロジェクトルール**: `CLAUDE.md`
- **インシデント教訓**: `.serena/memories/incident_response_lessons.md`

---

**最終更新**: 2025-11-09
**レビュー推奨**: 類似の metadata 拡張実装を行う前に必読
