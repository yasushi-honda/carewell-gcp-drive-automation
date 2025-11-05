# Dashboard Firestore スキーマ移行ドキュメント

**作成日**: 2025/11/05
**対応者**: Claude Code
**対応理由**: Dashboard が旧スキーマを使用していたため、公式仕様（Steering Document）に合わせて新スキーマに移行

---

## 問題の発見

### 背景

- Backend（src/firestore_service.py）は既に新スキーマ `submissions/{class}/tasks/{task}/files/` を使用
- Dashboard（dashboard/src/composables/）は旧スキーマ `{class}/{task}/documents/` を使用
- 2025/11/05 時点で、Dashboard の実装と公式 Steering Document の仕様が不一致

### 発見のきっかけ

ユーザーが Firestore のデータを削除したにもかかわらず、Dashboard に引き続きデータが表示されていた。調査の結果、Dashboard が旧スキーマから読み取っていたことが判明。

---

## 公式仕様（Steering Document）

参照: `.kiro/steering/firestore-critical-config.md`

### 正しいスキーマ

```
submissions/{class_name}/tasks/{task_id}/files/{composite_key}
```

### 誤った旧スキーマ（使用禁止）

```
❌ {class_name}/{task_id}/documents/{composite_key}
❌ {class_name}/{task_id}/files/{composite_key}
```

---

## 修正内容

### 修正ファイル

#### 1. `dashboard/src/composables/useFirestore.ts` (Line 129)

**修正前:**
```typescript
const docRef = doc(db, className, taskId);
```

**修正後:**
```typescript
const docRef = doc(db, "submissions", className, "tasks", taskId);
```

**理由**: 親ドキュメント（タスクメタデータ）のパスを公式仕様に変更

---

#### 2. `dashboard/src/composables/useTaskList.ts` (Line 61)

**修正前:**
```typescript
const documents = await getDocuments(className, taskId, 'documents');
```

**修正後:**
```typescript
const documents = await getDocuments("submissions", className, "tasks", taskId, 'files');
```

**理由**:
- パス構造を `submissions/{class}/tasks/{task}` に変更
- サブコレクション名を `documents` → `files` に変更

---

#### 3. `dashboard/src/composables/useFileList.ts` (Line 82)

**修正前:**
```typescript
const documents = await getDocuments<FileData>(className, taskId, 'documents');
```

**修正後:**
```typescript
const documents = await getDocuments<FileData>("submissions", className, "tasks", taskId, 'files');
```

**理由**: useTaskList.ts と同じ（パス構造とサブコレクション名を公式仕様に変更）

---

## 対応手順（10フェーズ）

### Phase 1: 現状記録

- スクリプト: `scripts/snapshot-firestore-all-paths.py`
- 目的: 全スキーマパターンのデータ状況を記録
- 結果: 旧スキーマに104件、新スキーマに121件のデータが存在することを確認

### Phase 2-4: Dashboard コード修正

- useFirestore.ts: 親ドキュメントパス変更
- useTaskList.ts: サブコレクションパスとコレクション名変更
- useFileList.ts: サブコレクションパスとコレクション名変更

### Phase 5: 変更内容確認

- TypeScript 文法チェック
- 修正箇所の最終確認

### Phase 6-7: Git commit & ユーザーレビュー

- Commit: `e1e9fe1`
- Commit Message: "fix: Update Dashboard Firestore paths to official schema (submissions/.../tasks/.../files/)"

### Phase 8: デプロイ

- Git push to `origin/main`
- GitHub Actions: 自動デプロイ成功（4m25s）
- Workflow ID: 19100113960

### Phase 9: Dashboard 動作確認

**確認結果:**

| クラス | 課題数 | 提出ファイル数 | 最終更新 | 状態 |
|--------|--------|----------------|----------|------|
| №01 | 0 | 0 | 未更新 | ✅ 予想通り空表示（一時的） |
| №02 | 1 | 40 | 2025/11/05 | ✅ 新スキーマから正常表示 |
| №03 | 1 | 20 | 2025/11/05 | ✅ 新スキーマから正常表示 |
| №04 | 1 | 19 | 2025/11/05 | ✅ 新スキーマから正常表示 |
| №05 | 1 | 8 | 2025/11/04 | ✅ 新スキーマから正常表示 |
| №08 | 0 | 0 | 未更新 | ✅ 予想通り空表示 |
| №09 | 0 | 0 | 未更新 | ✅ 予想通り空表示 |

**結論**: 新スキーマからの正常読み取りを確認

### Phase 10: 旧スキーマデータ削除

- スクリプト: `scripts/cleanup-legacy-schema.py`
- 削除対象: `令和7年度 デジタル中核人材養成研修 №01/課題①/documents/`
- 削除件数: 104件（サブコレクション） + 1件（親ドキュメント）
- 削除日時: 2025/11/05

---

## 結果

### 成功ポイント

1. **Backend と Dashboard のスキーマ統一**
   - Backend: 新スキーマ使用済み
   - Dashboard: 新スキーマに移行完了
   - Steering Document: 仕様通り実装

2. **データ整合性の確保**
   - №02-05: 87件のファイルが正常表示（新スキーマから取得）
   - №01: 次回 Backend 実行時に新スキーマに再取得される

3. **旧スキーマの完全削除**
   - 旧データを削除し、新スキーマのみで運用開始

### 教訓

#### 1. **ドキュメント確認の重要性**

> "ちゃんとドキュメントをみてから行動してください。Firestoreのデータについて、重複チェックリストの設計、Hostingへの接続設計などどれも事前に確認してから対応すべき重要な仕様内容です。"

**学んだこと**:
- Steering Document は設計の唯一の真実（Single Source of Truth）
- コード変更前に必ず Steering Document を確認する
- 破壊的操作（削除等）は現状記録スクリプトで全体像を把握してから実施

#### 2. **段階的な変更アプローチ**

> "破壊しないように慎重に深呼吸して。ここまでの議論と確信を持てた本来のドキュメントの設計に合うように修正する対応を段階的にチェックしながら進めて下さい・"

**学んだこと**:
- 10フェーズに分けて段階的に実施
- 各フェーズで検証を実施
- ユーザー確認を挟んで進める

#### 3. **全体影響の事前評価**

> "carewell-class01-task01コレ以外のFirestoreの設計も合わせて正しくすると思いますが、他の表示はこれまで通りの内容でFirestoreの内容をちゃんと反映表示しますか？"

**学んだこと**:
- 1つのクラス・課題だけでなく、全クラス・全課題の影響を評価
- `check-all-classes-firestore.py` で全体検証スクリプトを作成
- 87件のデータが正常表示されることを事前確認

---

## 次回の Backend 実行予定

Cloud Scheduler は毎時 :00 と :30 に実行されます：
- **次回実行**: 2025/11/05 21:00 または 21:30（JST）
- **動作**: №01 課題① のデータが新スキーマに取得される
- **結果**: Dashboard で №01 のデータが表示されるようになる

---

## 関連ドキュメント

- `.kiro/steering/firestore-critical-config.md` - Firestore 公式仕様
- `.kiro/specs/firestore-schema-improvement/design.md` - スキーマ改善設計書
- `docs/firestore-schema-improvement-implementation.md` - 実装ドキュメント
- `CLAUDE.md` - インシデント対応ワークフロー

---

## スクリプト一覧

| スクリプト | 目的 | Phase |
|-----------|------|-------|
| `scripts/snapshot-firestore-all-paths.py` | 全スキーマパターンのデータ記録 | Phase 1 |
| `scripts/check-all-classes-firestore.py` | 全クラス・全課題のデータ検証 | Phase 9 準備 |
| `scripts/cleanup-legacy-schema.py` | 旧スキーマデータ削除 | Phase 10 |

---

## Git コミット履歴

```bash
commit e1e9fe1
Author: Claude Code
Date: 2025-11-05

fix: Update Dashboard Firestore paths to official schema (submissions/.../tasks/.../files/)

修正内容:
- useFirestore.ts: 親ドキュメントパスを正式仕様に変更
- useTaskList.ts: サブコレクションパスとコレクション名を正式仕様に変更
- useFileList.ts: サブコレクションパスとコレクション名を正式仕様に変更

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## 完了日時

- **開始**: 2025/11/05 19:00 (JST)
- **完了**: 2025/11/05 21:00 (JST)
- **所要時間**: 約2時間
- **フェーズ数**: 10フェーズ
- **修正ファイル数**: 3ファイル
- **削除データ数**: 105件（旧スキーマ）

---

## 関連インシデント

### 同日発生: Playwright API エラー (21:27-21:40)

Dashboard スキーマ移行完了後、21:27に別の問題が発覚：

**問題**: №01 課題① でファイル取得失敗
**原因**: `src/playwright_automation.py:840` に存在しないメソッド `wait_for_element_state()` を使用
**影響**: №01 課題① の全学生でファイル取得失敗
**解決**: Playwright Auto-waiting に修正（Line 840削除）

詳細は包括的インシデント記録を参照：
- `docs/incident-2025-11-05-schema-migration-and-playwright-fix.md`

**教訓**: 複数の問題が同時期に発生する可能性がある。1つ解決しても、別の問題が潜んでいないか確認が必要。
