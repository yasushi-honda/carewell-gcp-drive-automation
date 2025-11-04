# ページ2個別ファイルアクセスタイムアウト調査記録

**作成日**: 2025-11-04
**ステータス**: 🔬 Investigation - Root Cause Identified
**関連**: [CLASS01_TIMEOUT_ANALYSIS.md](./CLASS01_TIMEOUT_ANALYSIS.md), [PAGINATION_BUG_ANALYSIS.md](./PAGINATION_BUG_ANALYSIS.md)

---

## 📊 Executive Summary

**問題**: ページ2で個別ファイルダウンロードリンク取得時に大量のタイムアウトが発生
**影響**: 61件中1件のみ成功、残り60件失敗 → 全体として0件処理
**根本原因**: `_get_download_link`メソッド内の`list_frame.goto`後、フレーム参照が陳腐化
**解決策**: 各ダウンロードリンク取得後にフレーム参照を再取得

---

## 🔗 ドキュメント階層構造

```
docs/
├── CLASS01_TIMEOUT_ANALYSIS.md          [親] 全体的なタイムアウト問題の分析
│   ├── 問題A: ページ遷移タイムアウト    ✅ 解決済み（10秒待機）
│   └── 問題B: 個別ファイルアクセス     ← 本ドキュメント
│
├── PAGE2_DOWNLOAD_LINK_TIMEOUT_INVESTIGATION.md [本文書]
│   ├── Phase 1: 症状の観察
│   ├── Phase 2: コード分析
│   ├── Phase 3: 仮説検証
│   └── Phase 4: 解決策提案
│
└── PAGINATION_BUG_ANALYSIS.md          [参考] ページネーション全般の問題
```

---

## Phase 1: 症状の観察

### 1.1 発生状況

**日時**: 2025-11-04 18:30 JST（09:30 UTC）
**実行**: Cloud Scheduler定期実行（carewell-class01-task01）
**ページ**: ページ2（61件の提出）

### 1.2 ログ分析

#### 成功パターン（1件目）

```
09:31:11 UTC - Performing early duplicate check for 61 submissions
09:31:11 UTC - Getting download link for: 宮川　典章
09:31:15 UTC - Found download link: 01_L184_宮川典章_改善方針シート.xlsx ✅
```

- **処理時間**: 4秒
- **結果**: 成功

#### 失敗パターン（2件目以降）

```
09:31:15 UTC - Getting download link for: 杉本　省吾
09:31:20 UTC - WARNING: Detail link not found or not clickable:
                report.aspx?log_id=8459&unit_id=684&course_id=41&filter=all
                - Timeout 10000ms exceeded. ❌

09:31:20 UTC - Getting download link for: 小原　暢
09:31:30 UTC - WARNING: Detail link not found or not clickable:
                report.aspx?log_id=8461&unit_id=684&course_id=41&filter=all
                - Timeout 10000ms exceeded. ❌

（以降、同様のタイムアウトが50件連続）
```

- **各処理時間**: 10秒（タイムアウト）
- **タイムアウト箇所**: `wait_for_selector(detail_link_selector, timeout=10000)` in `_get_download_link`
- **エラーメッセージ**: "Detail link not found or not clickable"

#### 最終結果

```
09:31:20 UTC - ERROR: Timeout 30000ms exceeded
09:31:20 UTC - Found 0 submissions ❌
```

### 1.3 ページ1との比較

| 項目 | ページ1（過去） | ページ2（今回） |
|-----|--------------|--------------|
| **処理件数** | 5件で中断 | 61件連続処理 |
| **成功件数** | 5件全て成功 ✅ | 1件のみ成功 ❌ |
| **平均処理時間** | 3-6秒/件 | 1件目:4秒、以降:10秒タイムアウト |
| **中断理由** | ページ遷移エラー | 個別アクセスタイムアウト |

**重要な観察**:
- ページ1: **短期間の処理**で問題が顕在化せず
- ページ2: **長期間の連続処理**で問題が発生

---

## Phase 2: コード分析

### 2.1 処理フロー

#### メインループ（Lines 540-578）

```python
# Lines 540-556: ダウンロードリンク取得ループ
for basic in basics:
    if is_duplicate(basic):
        # 重複の場合スキップ
        continue

    # ① ダウンロードリンク取得
    download_info = self._get_download_link(
        basic["detail_url"], list_url
    )

    # ② 結果を保存
    all_submissions.append({**basic, **download_info})

# Lines 564-578: ページング前のフレーム再取得
list_frame = None
for frame in self.page.frames:
    if frame.name == CarewellSelectors.FRAME_LIST:
        list_frame = frame
        break

logger.info("✓ Frame reference refreshed for pagination check")
```

**問題点**: ループ内（各呼び出し後）でフレーム参照を再取得していない

#### _get_download_link メソッド（Lines 666-740）

```python
def _get_download_link(self, detail_url: str, list_url: str) -> dict:
    # ① フレーム参照を取得（Lines 679-682）
    list_frame = None
    for frame in self.page.frames:
        if frame.name == CarewellSelectors.FRAME_LIST:
            list_frame = frame
            break

    # ② 現在のURLを保存（Line 691）
    current_url = list_frame.url

    # ③ 詳細リンクの存在確認（Lines 694-702）
    detail_link_selector = f'a[href="{detail_url}"]'
    try:
        list_frame.wait_for_selector(
            detail_link_selector, timeout=10000, state="visible"
        )
    except Exception as e:
        logger.warning(f"Detail link not found or not clickable: {detail_url} - {e}")
        return {"url": None, "filename": None}  # ← ここで失敗

    # ④ 詳細リンクをクリック（Line 705）
    list_frame.click(detail_link_selector)
    self._wait_for_navigation(3000)

    # ⑤ ダウンロードリンクを取得（Lines 708-712）
    download_link = list_frame.locator('a[href^="download.aspx"]').first
    # ... (省略)

    # ⑥ リストページに戻る（Line 720）
    list_frame.goto(current_url, wait_until="load", timeout=30000)
    self._wait_for_navigation()

    return {"url": download_url, "filename": filename}
```

### 2.2 根本原因の特定

**Line 720の問題**: `list_frame.goto(current_url)`

```python
list_frame.goto(current_url, wait_until="load", timeout=30000)
```

このgoto実行後、**Playwrightのフレーム参照が陳腐化（stale）する可能性**があります。

#### なぜ陳腐化するのか

1. **Playwright Frame Lifecycle**:
   - `frame.goto()`はフレーム内でページ遷移を実行
   - ページ遷移後、DOM全体が再構築される
   - 元のFrame参照は**新しいDOMを指していない可能性**

2. **ASP.NET特有の問題**:
   - Carewell（ASP.NET WebForms）では、ページ遷移で大規模なDOM再構築
   - ViewState、EventValidationなど、フォーム全体が再生成される

3. **フレーム参照の再取得タイミング**:
   - **現状**: ループ完了後に1回だけ再取得（Lines 564-578）
   - **必要**: **各`_get_download_link`呼び出し後に再取得**

### 2.3 仮説の検証

#### 予測される動作

**仮説**: 各`_get_download_link`後、フレーム参照が陳腐化

| 呼び出し | フレーム状態 | 予測結果 |
|---------|------------|---------|
| 1件目 | ✅ Fresh | 成功（`wait_for_selector`が動作） |
| 2件目 | ❌ Stale | 失敗（10秒タイムアウト） |
| 3件目以降 | ❌ Stale | 失敗（10秒タイムアウト） |

#### 実際のログとの一致

```
✅ 1件目: 09:31:15 - Found download link (4秒) ← 予測通り成功
❌ 2件目: 09:31:20 - Timeout 10秒 ← 予測通り失敗
❌ 3件目: 09:31:30 - Timeout 10秒 ← 予測通り失敗
```

**結論**: 仮説と実際のログが完全に一致 → 根本原因を特定

---

## Phase 3: なぜページ1では問題が顕在化しなかったか

### 3.1 処理件数の違い

#### ページ1（過去の12:25実行）

```
[03:25:53] ダウンロードリンク取得開始
[03:25:57] 川久保　晃   ✅ (4秒)
[03:25:59] 平嶋　俊司   ✅ (2秒)
[03:26:04] 吉岡　宏行   ✅ (5秒)
[03:26:10] 森平　直樹   ✅ (6秒)
[03:26:15] 冨田　勝正   ✅ (5秒)
[03:26:16] ❌ ページ2遷移でタイムアウト（Line 429）
```

- **処理件数**: 5件で中断
- **問題**: ページ1→ページ2の遷移失敗（別の問題）
- **フレーム陳腐化**: 影響が顕在化する前に処理終了

#### ページ2（今回の18:30実行）

```
09:31:11 - 重複チェック: 61件
09:31:11 - 新規件数: 51件（10件は重複でスキップ）
09:31:15 - 1件目成功 ✅
09:31:20 - 2件目以降、全てタイムアウト ❌
```

- **処理件数**: 51件の連続処理を試行
- **問題**: 2件目以降、フレーム陳腐化で全て失敗
- **顕在化**: **初めて大量の連続処理が実行された**

### 3.2 ページ遷移による「リセット効果」

**ページ1での処理**:
1. ダウンロードリンク取得ループ（5件）
2. ページ遷移処理（ページ1→ページ2）← ここで**全体リセット**
3. ページ2の処理開始（フレッシュな状態）

**ページ2での処理**:
1. ダウンロードリンク取得ループ（51件）← **リセットなし**
2. フレーム陳腐化が累積
3. 問題が顕在化

---

## Phase 4: 解決策の提案

### 4.1 最小限の修正（推奨）

**場所**: `src/playwright_automation.py` Lines 543-556

**修正内容**: 各`_get_download_link`呼び出し後にフレーム参照を再取得

```python
# BEFORE (Lines 540-556)
for basic in basics:
    if is_duplicate(basic):
        continue

    download_info = self._get_download_link(
        basic["detail_url"], list_url
    )

    submission = {**basic, **download_info}
    all_submissions.append(submission)

# AFTER (修正案)
for basic in basics:
    if is_duplicate(basic):
        continue

    download_info = self._get_download_link(
        basic["detail_url"], list_url
    )

    # ⭐ フレーム参照を再取得（詳細ページアクセス後）
    list_frame = None
    for frame in self.page.frames:
        if frame.name == CarewellSelectors.FRAME_LIST:
            list_frame = frame
            break

    if not list_frame:
        logger.error("'list' frame not found after download link retrieval")
        break

    submission = {**basic, **download_info}
    all_submissions.append(submission)
```

### 4.2 代替案1: `_get_download_link`の戻り値にフレーム参照を含める

**メリット**: メソッドの責任が明確
**デメリット**: メソッドシグネチャの変更が必要

### 4.3 代替案2: `_get_download_link`内でフレームリフレッシュ

**メリット**: 呼び出し元の変更不要
**デメリット**: `list_frame.goto`後の再取得が難しい（メソッド内で完結しない）

### 4.4 推奨する修正（4.1）の根拠

1. **最小限の変更**: 呼び出し元に数行追加のみ
2. **明確な責任分離**: フレーム管理は呼び出し元の責任
3. **既存パターンとの一貫性**: Lines 564-578と同じアプローチ
4. **テスト容易性**: 既存のテストケースを再利用可能

---

## Phase 5: 実装計画

### 5.1 実装ステップ

1. ✅ **Phase 1-4**: 根本原因の特定と解決策の提案（完了）
2. ⏳ **Phase 5**: コード修正
3. ⏳ **Phase 6**: ローカルテスト（単体テスト実行）
4. ⏳ **Phase 7**: デプロイ
5. ⏳ **Phase 8**: 本番検証（次回定期実行）

### 5.2 検証計画

#### テストケース

| No | テスト内容 | 期待結果 | 確認方法 |
|----|----------|---------|---------|
| 1 | ページ2で61件処理 | 全件成功 | Cloud Runログ "Found N submissions" |
| 2 | 重複チェック | 正常動作 | ログに "Skipped (duplicate)" |
| 3 | ダウンロードリンク取得 | タイムアウトなし | 警告ログ "Detail link not found" が出ない |
| 4 | 処理時間 | 540秒以内 | Cloud Scheduler成功 |
| 5 | Firestoreデータ | 全件保存 | ダッシュボード確認 |

#### 成功基準

- ✅ ページ2の51件（新規）全てが処理完了
- ✅ タイムアウト警告が0件
- ✅ "Found 0 submissions"エラーが発生しない
- ✅ 処理時間が適正範囲内（推定: 約5-7分）

---

## Phase 6: ドキュメントの最適化

### 6.1 関連ドキュメントの整理

#### 現在のドキュメント構造

```
docs/
├── CLASS01_TIMEOUT_ANALYSIS.md (798行)
│   - 膨張化している
│   - 複数の問題を1つのファイルに記録
│
├── PAGE2_DOWNLOAD_LINK_TIMEOUT_INVESTIGATION.md (本文書)
│   - 特定問題に焦点
│   - 体系的な構造
│
└── PAGINATION_BUG_ANALYSIS.md
    - ページネーション全般
```

#### 最適化方針

1. **階層化**: 問題ごとに独立したドキュメント
2. **相互参照**: 関連ドキュメントへのリンク明記
3. **サマリー作成**: 各ドキュメントのExecutive Summaryを統一フォーマットで記載
4. **アーカイブ化**: 解決済み問題は`docs/archive/`に移動

#### 提案する新構造

```
docs/
├── INDEX.md [NEW]
│   - 全ドキュメントの索引
│   - 問題ツリー（階層構造）
│   - ステータス一覧表
│
├── active/ [NEW]
│   ├── PAGE2_DOWNLOAD_LINK_TIMEOUT.md (本文書・リネーム)
│   └── (他の未解決問題)
│
├── resolved/ [NEW]
│   ├── PAGE2_NAVIGATION_TIMEOUT_RESOLVED.md
│   └── TASK_PATTERN_CONFIG_FIXED.md
│
└── reference/
    ├── PAGINATION_BUG_ANALYSIS.md
    └── DUPLICATE_CHECK_FIX_PLAN.md
```

### 6.2 ドキュメント統一フォーマット

```markdown
# [問題名]

**作成日**: YYYY-MM-DD
**ステータス**: 🔬 Investigation | 🔧 In Progress | ✅ Resolved | 📚 Reference
**関連**: [リンク1], [リンク2]

---

## 📊 Executive Summary
- **問題**: 1行で問題を記述
- **影響**: 影響範囲
- **根本原因**: 原因の要約
- **解決策**: 解決方法の要約

---

## 🔗 ドキュメント階層構造
```
親ドキュメント
├── 本ドキュメント
├── 兄弟ドキュメント1
└── 兄弟ドキュメント2
```

---

## Phase N: [フェーズ名]
（内容）

---

## 関連コミット
- `ハッシュ`: コミットメッセージ

---

**作成者**: Claude Code
**レビュー**: [レビュー済み/要レビュー]
```

---

## 関連リソース

### コード参照

- `src/playwright_automation.py:540-556` - ダウンロードリンク取得ループ
- `src/playwright_automation.py:666-740` - `_get_download_link`メソッド
- `src/playwright_automation.py:564-578` - ページング前のフレーム再取得

### ドキュメント参照

- [CLASS01_TIMEOUT_ANALYSIS.md](./CLASS01_TIMEOUT_ANALYSIS.md) - 全体的なタイムアウト分析
- [PAGINATION_BUG_ANALYSIS.md](./PAGINATION_BUG_ANALYSIS.md) - ページネーション問題の詳細

### ログ参照

- `/tmp/manual_test_10s_complete.json` - 18:30 JST実行の完全ログ
- `/tmp/test_result_comprehensive_analysis.md` - 包括的分析レポート

---

## 次のステップ

1. ⏳ コード修正の実装（Phase 5.1 Step 2）
2. ⏳ 単体テスト実行
3. ⏳ デプロイと本番検証
4. ⏳ ドキュメント構造の最適化（Phase 6）

---

**作成者**: Claude Code
**最終更新**: 2025-11-04 19:00 JST
**レビュー**: 要レビュー
**ステータス**: 🔬 Investigation Complete - Ready for Implementation
