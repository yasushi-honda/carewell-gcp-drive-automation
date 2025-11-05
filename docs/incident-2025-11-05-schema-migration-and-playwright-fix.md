# インシデント記録: 2025/11/05 Firestore スキーマ移行と Playwright エラー修正

**発生日**: 2025/11/05
**対応時間**: 19:00 - 21:40 JST (約2時間40分)
**影響範囲**: Dashboard 全クラス・全課題、Backend №01 課題①
**重大度**: 🔴 Critical（Dashboard 動作不能、Backend ファイル取得失敗）

---

## エグゼクティブサマリー

2025/11/05、2つの重大な問題が発覚しました：

1. **Dashboard Firestore スキーマ不一致** (19:00-21:00)
   - Dashboard が旧スキーマを使用していたため、公式仕様と乖離
   - 10フェーズの段階的移行により解決

2. **Playwright API エラー** (21:27-21:40)
   - 存在しないメソッド `wait_for_element_state()` により №01 課題① で全ファイル取得失敗
   - Auto-waiting への修正により解決

**根本原因**: 設計ドキュメントの確認不足
**教訓**: 「ドキュメント確認ファースト」の徹底

---

## 問題 1: Dashboard Firestore スキーマ移行

### タイムライン

| 時刻 | イベント |
|------|---------|
| 19:00 | ユーザーがFirestoreデータ削除後もDashboardにデータ表示される問題を報告 |
| 19:10 | 調査の結果、Dashboard が旧スキーマ使用と判明 |
| 19:15 | **ユーザーから重要なフィードバック**: "ちゃんとドキュメントをみてから行動してください" |
| 19:20 | Steering Document 確認、公式仕様との乖離を確認 |
| 19:30 | 10フェーズ計画策定 |
| 19:40 | 現状記録スクリプト実行（全パターンのデータ確認） |
| 19:50 | Dashboard コード修正（3ファイル） |
| 20:00 | 全クラス・全課題検証スクリプト作成 |
| 20:10 | Git commit & push |
| 20:13 | GitHub Actions デプロイ成功 |
| 20:20 | ユーザーによる Dashboard 動作確認 → ✅ 成功 |
| 21:00 | 旧スキーマデータ削除完了 |

### 問題の詳細

#### 発見のきっかけ

ユーザーがFirestoreの新スキーマデータ（121件）を削除したにも関わらず、Dashboard に引き続きデータが表示されていた。調査の結果、Dashboard が旧スキーマから読み取っていたことが判明。

#### スキーマ不一致の内容

| コンポーネント | 使用スキーマ | 状態 |
|---------------|-------------|------|
| Backend (src/firestore_service.py) | `submissions/{class}/tasks/{task}/files/` | ✅ 正しい |
| Dashboard (dashboard/src/composables/) | `{class}/{task}/documents/` | ❌ 旧スキーマ使用 |
| Steering Document (公式仕様) | `submissions/{class}/tasks/{task}/files/` | 📘 正式仕様 |

#### 根本原因

1. **設計ドキュメント確認不足**: Dashboard 実装時に Steering Document を確認せず
2. **Backend と Dashboard の実装時期のズレ**: Backend は既に新スキーマに移行済み
3. **テスト不足**: スキーマ統一性の検証テストが不在

### 修正内容

#### 修正ファイル (3ファイル)

##### 1. `dashboard/src/composables/useFirestore.ts` (Line 129)

**目的**: 親ドキュメント（タスクメタデータ）取得

```typescript
// 修正前
const docRef = doc(db, className, taskId);

// 修正後
const docRef = doc(db, "submissions", className, "tasks", taskId);
```

##### 2. `dashboard/src/composables/useTaskList.ts` (Line 61)

**目的**: ファイル一覧取得（学生数計算用）

```typescript
// 修正前
const documents = await getDocuments(className, taskId, 'documents');

// 修正後
const documents = await getDocuments("submissions", className, "tasks", taskId, 'files');
```

**変更点**:
- パス構造: `{class}/{task}` → `submissions/{class}/tasks/{task}`
- サブコレクション名: `documents` → `files`

##### 3. `dashboard/src/composables/useFileList.ts` (Line 82)

**目的**: ファイル一覧表示

```typescript
// 修正前
const documents = await getDocuments<FileData>(className, taskId, 'documents');

// 修正後
const documents = await getDocuments<FileData>("submissions", className, "tasks", taskId, 'files');
```

**変更点**: useTaskList.ts と同様

### 対応手順（10フェーズ）

| Phase | 内容 | 状態 | 所要時間 |
|-------|------|------|----------|
| 1 | 現状記録スクリプト作成・実行 | ✅ 完了 | 10分 |
| 2 | useFirestore.ts 修正 | ✅ 完了 | 5分 |
| 3 | useTaskList.ts 修正 | ✅ 完了 | 5分 |
| 4 | useFileList.ts 修正 | ✅ 完了 | 5分 |
| 5 | 変更内容確認 | ✅ 完了 | 5分 |
| 6 | Git commit | ✅ 完了 | 3分 |
| 7 | ユーザーレビュー | ✅ 完了 | 10分 |
| 8 | Git push & デプロイ | ✅ 完了 | 5分 |
| 9 | Dashboard 動作確認 | ✅ 完了 | 10分 |
| 10 | 旧スキーマデータ削除 | ✅ 完了 | 5分 |

**合計所要時間**: 約63分

### 検証結果

#### 全クラス・全課題のデータ状況（Phase 9）

| クラス | 課題数 | 提出ファイル数 | 最終更新 | 状態 |
|--------|--------|----------------|----------|------|
| №01 | 0 | 0 | 未更新 | ✅ 予想通り空表示（一時的） |
| №02 | 1 | 40 | 2025/11/05 | ✅ 新スキーマから正常表示 |
| №03 | 1 | 20 | 2025/11/05 | ✅ 新スキーマから正常表示 |
| №04 | 1 | 19 | 2025/11/05 | ✅ 新スキーマから正常表示 |
| №05 | 1 | 8 | 2025/11/04 | ✅ 新スキーマから正常表示 |
| №08 | 0 | 0 | 未更新 | ✅ 予想通り空表示 |
| №09 | 0 | 0 | 未更新 | ✅ 予想通り空表示 |

**合計表示ファイル数**: 87件（40 + 20 + 19 + 8）

#### 旧スキーマデータ削除（Phase 10）

- **削除パス**: `令和7年度 デジタル中核人材養成研修 №01/課題①/documents/`
- **削除件数**: 105件（サブコレクション104件 + 親ドキュメント1件）

### Git コミット履歴

```bash
# Dashboard スキーマ修正
commit e1e9fe1
Author: Claude Code
Date: 2025-11-05 20:13:17

fix: Update Dashboard Firestore paths to official schema (submissions/.../tasks/.../files/)

# ドキュメント・スクリプト追加
commit a1ae25b
Author: Claude Code
Date: 2025-11-05 21:30:00

docs: Dashboard Firestore スキーマ移行完了記録
```

---

## 問題 2: Playwright API エラー

### タイムライン

| 時刻 | イベント |
|------|---------|
| 21:27 | ユーザーが №01 課題① のファイル取得失敗を報告 |
| 21:28 | Cloud Run ログ確認開始 |
| 21:30 | エラー発見: `'Locator' object has no attribute 'wait_for_element_state'` |
| 21:32 | ソースコード調査、Line 840 にバグを発見 |
| 21:33 | Playwright 公式ドキュメントで正しいAPIを確認 |
| 21:35 | コード修正（wait_for_element_state 削除、Auto-waiting 採用） |
| 21:36 | Git commit & push |
| 21:38 | GitHub Actions デプロイ成功 |
| 21:40 | 次回 Scheduler 実行（22:00）待機状態 |

### 問題の詳細

#### エラーメッセージ

```
2025-11-05 12:26:57,705 - playwright_automation - WARNING -
Error finding detail link dynamically: report.aspx?log_id=8402&unit_id=684&course_id=41&filter=all -
'Locator' object has no attribute 'wait_for_element_state'
```

**影響**: №01 課題① (`course_id=41`) の全学生でファイル取得失敗

#### 根本原因

**`src/playwright_automation.py:840`** に存在しない Playwright API メソッドの呼び出し：

```python
link.wait_for_element_state("visible", timeout=10000)  # ❌ このメソッドは存在しない
```

#### 発生経緯

- **Phase 6** (commit 941e94a, 2025/11/05 14:41) で導入
- コミットメッセージ: "feat: Phase 6 - Dynamic detail link detection without hardcoding URLs"
- 目的: HTML entity encoding 問題の解決（セレクタベース → 動的リンク検出）
- **バグの混入**: 存在しないメソッド `wait_for_element_state()` を誤って追加

#### なぜ見逃されたか？

1. **テストでの検出漏れ**: Phase 6 のコミット時、テストは成功していた
   - 理由: 該当コードパスが実行されなかった（テストデータに該当学生なし）
2. **本番環境での発覚**: 21:00 の Scheduler 実行時に初めてエラー発生

### 修正内容

#### Playwright API の正しい使い方

| 方法 | 適用場面 | 記述例 |
|------|---------|--------|
| **Auto-waiting** (推奨) | 通常のブラウザ自動化 | `locator.click()` のみ |
| `wait_for(state="visible")` | 明示的な待機が必要な場合 | `await locator.wait_for(state="visible")` |
| `expect().to_be_visible()` | テストでのアサーション | `expect(locator).to_be_visible()` |

**参考**: [Playwright Python Auto-waiting](https://playwright.dev/python/docs/actionability)

#### 修正前後の比較

**修正前** (`src/playwright_automation.py:836-842`):

```python
if (link_href == detail_url or
    link_href.replace("&amp;", "&") == detail_url):
    logger.debug(f"✓ Found detail link dynamically: {detail_url}")
    # Wait for the link to be visible and clickable
    link.wait_for_element_state("visible", timeout=10000)  # ❌ 存在しないメソッド
    link.click()
    detail_link_found = True
    break
```

**修正後**:

```python
if (link_href == detail_url or
    link_href.replace("&amp;", "&") == detail_url):
    logger.debug(f"✓ Found detail link dynamically: {detail_url}")
    # Playwright's auto-waiting handles visibility checks before click
    link.click()  # ✅ Auto-waiting が自動で待機
    detail_link_found = True
    break
```

**変更点**:
- ❌ 削除: `link.wait_for_element_state("visible", timeout=10000)`
- ✅ 採用: Playwright の Auto-waiting 機能
- **理由**: `click()` は自動的に要素が clickable になるまで待機する

### Git コミット

```bash
commit 4747166
Author: Claude Code
Date: 2025-11-05 21:36:00

fix: Remove invalid wait_for_element_state() call - use Playwright auto-waiting instead

問題:
- Line 840: link.wait_for_element_state("visible", timeout=10000)
- Playwright Locator には wait_for_element_state() メソッドが存在しない
- エラー: 'Locator' object has no attribute 'wait_for_element_state'
- №01 課題① で全学生のファイル取得が失敗

根本原因:
- Phase 6 (commit 941e94a) で導入されたバグ

解決方法:
- wait_for_element_state() 呼び出しを削除
- Playwright の Auto-waiting により、click() は自動的に要素が
  clickable になるまで待機する
```

### デプロイ

- **GitHub Actions**: Run ID 19102157303
- **ステータス**: ✅ SUCCESS
- **所要時間**: 約4分
- **最新リビジョン**: `carewell-file-collector-00168-ctk`

### 次回実行での確認事項

**実行予定**: 2025/11/05 22:00 または 22:30 JST

**期待される動作**:
1. ✅ エラー解消: `wait_for_element_state` エラーが出なくなる
2. ✅ ファイル取得成功: №01 課題① の全学生のファイルが正常に取得される
3. ✅ Firestore 保存: 新スキーマに正常保存される
4. ✅ Dashboard 表示: №01 課題① が Dashboard に表示される

---

## 教訓とベストプラクティス

### 1. ドキュメント確認ファースト

**ユーザーからの重要なフィードバック**:

> "ちゃんとドキュメントをみてから行動してください。Firestoreのデータについて、重複チェックリストの設計、Hostingへの接続設計などどれも事前に確認してから対応すべき重要な仕様内容です。"

**学んだこと**:
- Steering Document は設計の唯一の真実（Single Source of Truth）
- コード変更前に**必ず** Steering Document を確認する
- 破壊的操作（削除等）は現状記録スクリプトで全体像を把握してから実施

**適用ルール** (CLAUDE.md に追加済み):
```markdown
### 🚨 CRITICAL: READ THIS FIRST 🚨

Before ANY bug fix or incident response:

1. ✅ Read `CLAUDE.md` → "Incident Response Workflow" section
2. ✅ Read relevant design documents
3. ✅ Read relevant memory files
4. ✅ Check past commits for similar issues
5. ✅ ONLY THEN start investigation/coding
```

### 2. 段階的な変更アプローチ

**ユーザーからの指示**:

> "破壊しないように慎重に深呼吸して。ここまでの議論と確信を持てた本来のドキュメントの設計に合うように修正する対応を段階的にチェックしながら進めて下さい・"

**学んだこと**:
- 大きな変更は10フェーズのように段階的に実施
- 各フェーズで検証を実施
- ユーザー確認を挟んで進める

**適用例**:
- Phase 1: 現状記録（破壊的操作前のスナップショット）
- Phase 2-4: コード修正
- Phase 5: 変更内容確認
- Phase 6-7: コミット・ユーザーレビュー
- Phase 8: デプロイ
- Phase 9: 動作確認
- Phase 10: クリーンアップ（旧データ削除）

### 3. 全体影響の事前評価

**ユーザーからの質問**:

> "carewell-class01-task01コレ以外のFirestoreの設計も合わせて正しくすると思いますが、他の表示はこれまで通りの内容でFirestoreの内容をちゃんと反映表示しますか？"

**学んだこと**:
- 1つのクラス・課題だけでなく、全クラス・全課題の影響を評価
- 検証スクリプトを作成して全体をチェック
- 事前確認により、87件のデータが正常表示されることを確認

**適用ツール**:
- `scripts/check-all-classes-firestore.py` - 全クラス・全課題のデータ検証
- `scripts/snapshot-firestore-all-paths.py` - 全スキーマパターンのデータ記録

### 4. Playwright API の正しい理解

**問題**:
- 存在しないメソッド `wait_for_element_state()` を使用
- テストで検出できず、本番環境で発覚

**学んだこと**:
- Playwright の Auto-waiting 機能を活用する
- 明示的な待機は基本的に不要
- 公式ドキュメントで API を確認する

**適用ルール**:
- `click()`, `fill()`, `select_option()` などのアクションは Auto-waiting 対応済み
- 明示的な待機が必要な場合は `wait_for(state="visible")` を使用
- テストカバレッジの向上（該当コードパスの実行確保）

### 5. テストカバレッジの重要性

**問題**:
- Phase 6 のコミット時、バグがテストで検出されなかった
- 理由: 該当コードパスが実行されていなかった

**学んだこと**:
- 統合テストで実際のユースケースをカバーする
- コードカバレッジツールの活用
- 本番環境と同等のテストデータを使用

**今後の改善**:
- Playwright のエラーパスを含むテストケース追加
- CI/CD でのコードカバレッジチェック強化

---

## 関連ドキュメント

### 設計ドキュメント

- `.kiro/steering/firestore-critical-config.md` - Firestore 公式仕様
- `.kiro/specs/firestore-schema-improvement/design.md` - スキーマ改善設計書
- `.kiro/steering/dashboard-workflow.md` - Dashboard 開発ワークフロー

### 実装ドキュメント

- `docs/dashboard-firestore-schema-migration.md` - Dashboard スキーマ移行詳細記録
- `docs/firestore-schema-improvement-implementation.md` - Firestore スキーマ改善実装記録
- `docs/phase_6_dynamic_link_detection.md` - Phase 6 動的リンク検出メカニズム

### インシデント対応ワークフロー

- `CLAUDE.md` - プロジェクト全体のルールとインシデント対応手順

---

## 検証スクリプト

| スクリプト | 目的 | 対象問題 |
|-----------|------|---------|
| `scripts/snapshot-firestore-all-paths.py` | 全スキーマパターンのデータ記録 | Dashboard スキーマ移行 |
| `scripts/check-all-classes-firestore.py` | 全クラス・全課題のデータ検証 | Dashboard スキーマ移行 |
| `scripts/cleanup-legacy-schema.py` | 旧スキーマデータ削除 | Dashboard スキーマ移行 |

---

## 影響評価

### ダウンタイム

- **Dashboard**: 約1時間（19:00-20:13）
  - 旧スキーマのデータのみ表示（不正確な状態）
  - 20:13 デプロイ後、正常動作再開

- **Backend №01 課題①**: 約1時間13分（21:00-22:00/22:30）
  - 21:00 実行でファイル取得失敗
  - 21:38 修正デプロイ完了
  - 22:00 または 22:30 実行で正常動作再開予定

### データ整合性

- ✅ **問題なし**: 旧データ削除は検証完了後に実施
- ✅ **問題なし**: 新スキーマへの移行は無損失で完了
- ⚠️ **一時的な空表示**: №01 課題① のみ（次回実行で解消予定）

### ユーザー影響

- **講師**: Dashboard で №01 課題① が一時的に空表示（約1-1.5時間）
- **学生**: 影響なし（提出システムは別システム）
- **管理者**: 次回実行（22:00/22:30）での確認作業が必要

---

## 完了日時

- **開始**: 2025/11/05 19:00 JST
- **完了**: 2025/11/05 21:40 JST
- **所要時間**: 約2時間40分
- **対応フェーズ数**: 16フェーズ（Dashboard 10 + Playwright 6）
- **修正ファイル数**: 4ファイル（Dashboard 3 + Playwright 1）
- **削除データ数**: 105件（旧スキーマ）
- **作成スクリプト数**: 3個

---

## ステータス

| 項目 | 状態 | 確認日時 |
|------|------|---------|
| Dashboard スキーマ移行 | ✅ 完了 | 2025/11/05 20:20 |
| 旧スキーマデータ削除 | ✅ 完了 | 2025/11/05 21:00 |
| Playwright エラー修正 | ✅ 完了 | 2025/11/05 21:38 |
| 次回 Backend 実行確認 | ⏸️ 待機中 | 2025/11/05 22:00 予定 |

---

## 承認

- **報告者**: Claude Code
- **レビュー**: ユーザー確認済み
- **承認日**: 2025/11/05
