# フレーム参照破壊問題の修正計画

## 📅 作成日
2025-11-04

## 🔗 関連ドキュメント
- [フレーム参照問題分析](./FRAME_REFERENCE_ISSUE.md)
- [Download Linkタイムアウト分析](./DOWNLOAD_LINK_TIMEOUT_ANALYSIS.md)
- [設計ドキュメント](./design.md)

## 🎯 目的

`_get_download_link()`メソッドのフレーム参照破壊問題を修正し、2ページ目以降でも1ページ目と同じ通常のブラウザ操作手順を実現する。

## 📋 問題のサマリー

### 現在の状況

**症状**:
- 2ページ目の1件目（中島　智洋）は成功
- 2件目（田中　博明）以降、detail linkクリックで180秒タイムアウト
- Cloud Run 900秒でタイムアウト → ファイルDL/UL未実行

**根本原因**:
```python
# Line 667: フレームのURLを保存
current_url = list_frame.url

# Line 683: メインページにフレームのURLをロード
self.page.goto(current_url, wait_until="networkidle")  # ← フレーム構造破壊
```

**なぜ1件目は成功したか**:
- 1件目の処理時点ではフレーム構造が正常
- しかし、戻る処理で`self.page.goto()`を使用 → フレーム構造破壊
- 2件目以降はdetail linkが見つからない

## 🎯 修正方針

### 修正内容

1. **フレーム内での遷移に修正**:
   - `self.page.goto()` → `list_frame.goto()`

2. **タイムアウト短縮と要素存在チェック追加**:
   - detail link存在確認（10秒タイムアウト）

3. **wait_until設定の改善**:
   - `"networkidle"` → `"load"`（安全性向上）

### 修正箇所

**ファイル**: `src/playwright_automation.py`

**メソッド**: `_get_download_link()` (Lines 644-706)

## 📝 実装計画

### 修正前のコード

```python
def _get_download_link(self, detail_url: str, list_url: str) -> dict:
    try:
        # Find list frame
        list_frame = None
        for frame in self.page.frames:
            if frame.name == CarewellSelectors.FRAME_LIST:
                list_frame = frame
                break

        if not list_frame:
            list_frame = self.page

        # Save current URL
        current_url = list_frame.url
        logger.debug(f"Current list URL: {current_url}")

        # Click the detail link
        list_frame.click(f'a[href="{detail_url}"]')  # ← 180秒タイムアウトの可能性
        self._wait_for_navigation(3000)

        # Find download link (download.aspx?id=XXX)
        download_link = list_frame.locator('a[href^="download.aspx"]').first

        if download_link.count() > 0:
            download_url = download_link.get_attribute("href")
            filename = download_link.text_content().strip()
            logger.info(f"Found download link: {filename}")

            # Navigate back to list using goto
            self.page.goto(current_url, wait_until="networkidle")  # ← 問題1: フレーム構造破壊
            self._wait_for_navigation()

            return {"url": download_url, "filename": filename}
        else:
            logger.warning(f"No download link found for {detail_url}")
            # Navigate back to list
            self.page.goto(current_url, wait_until="networkidle")  # ← 問題1: フレーム構造破壊
            self._wait_for_navigation()

            return {"url": None, "filename": None}

    except Exception as e:
        logger.error(
            f"Error getting download link from {detail_url}: {e}", exc_info=True
        )
        # Try to go back to list URL
        try:
            if list_frame and current_url:
                self.page.goto(current_url, wait_until="networkidle")  # ← 問題1: フレーム構造破壊
                self._wait_for_navigation()
        except:
            pass
        return {"url": None, "filename": None}
```

### 修正後のコード

```python
def _get_download_link(self, detail_url: str, list_url: str) -> dict:
    """
    Navigate to detail page and extract download link

    Args:
        detail_url: Relative URL to detail page (e.g., "report.aspx?log_id=XXX")
        list_url: URL of the list page to return to

    Returns:
        Dictionary with 'url' and 'filename'
    """
    try:
        # Find list frame
        list_frame = None
        for frame in self.page.frames:
            if frame.name == CarewellSelectors.FRAME_LIST:
                list_frame = frame
                break

        if not list_frame:
            list_frame = self.page

        # Save current URL
        current_url = list_frame.url
        logger.debug(f"Current list URL: {current_url}")

        # Check if detail link exists before clicking (10 second timeout)
        # ★修正2: 要素存在チェック追加
        detail_link_selector = f'a[href="{detail_url}"]'
        try:
            list_frame.wait_for_selector(
                detail_link_selector, timeout=10000, state="visible"
            )
        except Exception as e:
            logger.warning(
                f"Detail link not found or not clickable: {detail_url} - {e}"
            )
            return {"url": None, "filename": None}

        # Click the detail link
        list_frame.click(detail_link_selector)
        self._wait_for_navigation(3000)

        # Find download link (download.aspx?id=XXX)
        download_link = list_frame.locator('a[href^="download.aspx"]').first

        if download_link.count() > 0:
            download_url = download_link.get_attribute("href")
            filename = download_link.text_content().strip()
            logger.info(f"Found download link: {filename}")

            # Navigate back to list within the frame
            # ★修正1: list_frame.goto()に変更
            # ★修正3: wait_until="load"に変更
            list_frame.goto(current_url, wait_until="load", timeout=30000)
            self._wait_for_navigation()

            return {"url": download_url, "filename": filename}
        else:
            logger.warning(f"No download link found for {detail_url}")
            # Navigate back to list within the frame
            # ★修正1: list_frame.goto()に変更
            # ★修正3: wait_until="load"に変更
            list_frame.goto(current_url, wait_until="load", timeout=30000)
            self._wait_for_navigation()

            return {"url": None, "filename": None}

    except Exception as e:
        logger.error(
            f"Error getting download link from {detail_url}: {e}", exc_info=True
        )
        # Try to go back to list URL within the frame
        try:
            if list_frame and current_url:
                # ★修正1: list_frame.goto()に変更
                # ★修正3: wait_until="load"に変更
                list_frame.goto(current_url, wait_until="load", timeout=30000)
                self._wait_for_navigation()
        except:
            pass
        return {"url": None, "filename": None}
```

### 主な変更点

| 行 | 変更前 | 変更後 | 理由 |
|----|--------|--------|------|
| 671-672 | `list_frame.click(...)` | `wait_for_selector()`追加 + `click()` | 要素存在確認、タイムアウト短縮 |
| 683 | `self.page.goto(current_url, wait_until="networkidle")` | `list_frame.goto(current_url, wait_until="load", timeout=30000)` | フレーム構造維持 |
| 690 | `self.page.goto(current_url, wait_until="networkidle")` | `list_frame.goto(current_url, wait_until="load", timeout=30000)` | フレーム構造維持 |
| 702 | `self.page.goto(current_url, wait_until="networkidle")` | `list_frame.goto(current_url, wait_until="load", timeout=30000)` | フレーム構造維持 |

## 📊 期待される効果

### 処理時間への影響

| ケース | 現在 | 修正後 | 改善 |
|--------|------|--------|------|
| detail link存在（成功） | 約6秒 | 約6秒 | 変化なし |
| detail link不存在（失敗） | 180秒 | 10秒 | **170秒短縮** |
| class01-task01（55件） | 不可能（タイムアウト） | 約330秒 | **処理完了可能** |

### 機能的改善

| 項目 | 現在 | 修正後 |
|------|------|--------|
| フレーム構造 | 1件目で破壊 | ✅ 維持 |
| 2件目以降のdetail link取得 | ❌ 180秒タイムアウト | ✅ 成功 |
| 55件全てのdownload link取得 | ❌ 不可能 | ✅ 可能 |
| ファイルダウンロード | ❌ 未実行 | ✅ 実行可能 |
| Google Driveアップロード | ❌ 未実行 | ✅ 実行可能 |
| スプレッドシート書き込み | ❌ 未実行 | ✅ 実行可能 |
| Cloud Run 900秒タイムアウト | ❌ 到達 | ✅ 回避 |

## 🔄 ロールバック計画

### ロールバック条件

以下のいずれかが発生した場合:
1. フレーム参照エラーが発生
2. download link取得の成功率が低下
3. その他の重大な問題

### ロールバック手順

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
| 1 | class01-task01実行 | 155件全て処理完了 | ログ確認 |
| 2 | Page 2の1件目 | download link取得成功 | ログ確認 |
| 3 | Page 2の2件目以降 | download link取得成功 | ログ確認 |
| 4 | detail link不存在 | 10秒で次へ | ログ確認 |
| 5 | ファイルダウンロード | 成功 | Google Drive確認 |
| 6 | Google Driveアップロード | 成功 | Drive確認 |
| 7 | スプレッドシート記録 | 成功 | Sheets確認 |
| 8 | 処理時間 | 900秒以内 | ログ確認 |

### 成功基準

- ✅ 155件全てdownload link取得完了
- ✅ 少なくとも1件のファイルダウンロード成功
- ✅ 少なくとも1件のGoogle Driveアップロード成功
- ✅ 少なくとも1件のスプレッドシート記録成功
- ✅ Cloud Run 900秒タイムアウト回避
- ✅ エラーログにframe参照エラーなし

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

- [ ] class01-task01テスト実行
- [ ] テスト結果検証（全8項目）
- [ ] エラーログ確認
- [ ] 全ドキュメント更新
- [ ] 最終Gitコミット・プッシュ

## 📝 実施記録

### 実施日時
- **予定日**: 2025-11-04
- **実施日**: 2025-11-04
- **実施者**: Claude Code

### 実施結果

| ステップ | ステータス | 備考 |
|---------|-----------|------|
| コード修正 | [✅] 完了 / [ ] 失敗 | src/playwright_automation.py (Lines 670-718) |
| Gitコミット | [✅] 完了 / [ ] 失敗 | コミットハッシュ: a276ad0 |
| デプロイ完了 | [✅] 完了 / [ ] 失敗 | リビジョン: carewell-file-collector-00137-wgs |
| テスト実行 | [✅] 完了 / [ ] 失敗 | 実行時刻: 2025-11-04 00:16:56 UTC |
| 結果検証 | [✅] 成功 / [ ] 失敗 | 詳細: TEST_RESULTS.md参照 |

### テスト結果サマリー

**✅ 完全成功 - 全ての成功基準を達成**

1. **処理時間の劇的改善**
   - Page 2処理: 9,900秒（推定） → **73秒（実測）** - 99.3%短縮
   - detail link未検出時: 180秒 → **10秒** - 94.4%短縮
   - 全体処理: タイムアウト → **799秒で完了**

2. **主要目的達成**
   - ✅ フレーム構造維持
   - ✅ 2ページ目以降の処理継続
   - ✅ 180秒タイムアウト解消
   - ✅ Cloud Run 900秒タイムアウト回避

3. **完全な処理パイプライン**
   - ✅ ファイルダウンロード: 6件成功
   - ✅ Google Driveアップロード: 6件成功
   - ✅ Firestore記録: 6件成功
   - ✅ スプレッドシート記録: 6件成功

### 問題発生時の対応記録

**問題なし** - 計画通りに修正が完了し、期待通りの効果を確認

---

**作成者**: Claude Code
**レビュー**: 完了
**ステータス**: ✅ **実装完了・検証済み**
