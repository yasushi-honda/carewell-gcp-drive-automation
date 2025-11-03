# フレーム参照とURL管理の設計問題

## 📅 発見日
2025-11-04

## 🚨 問題の本質

**`_get_download_link()`メソッドに重大な設計上の矛盾が存在**

### 問題のコード (`src/playwright_automation.py:644-706`)

```python
def _get_download_link(self, detail_url: str, list_url: str) -> dict:
    try:
        # 1. list frameを取得
        list_frame = None
        for frame in self.page.frames:
            if frame.name == CarewellSelectors.FRAME_LIST:
                list_frame = frame
                break

        if not list_frame:
            list_frame = self.page

        # 2. current_url = フレームのURL
        current_url = list_frame.url  # ← フレームのURL
        logger.debug(f"Current list URL: {current_url}")

        # 3. detail linkをクリック（フレーム内で）
        list_frame.click(f'a[href="{detail_url}"]')  # ← フレーム内でクリック
        self._wait_for_navigation(3000)

        # 4. download linkを探す
        download_link = list_frame.locator('a[href^="download.aspx"]').first

        if download_link.count() > 0:
            download_url = download_link.get_attribute("href")
            filename = download_link.text_content().strip()
            logger.info(f"Found download link: {filename}")

            # 5. ★問題箇所★ メインページにフレームのURLをロード
            self.page.goto(current_url, wait_until="networkidle")  # ← self.page（メインページ）
            self._wait_for_navigation()

            return {"url": download_url, "filename": filename}
```

### 矛盾点

| 処理 | 対象 | コード |
|------|------|--------|
| URLを保存 | **フレーム**のURL | `current_url = list_frame.url` |
| detail linkクリック | **フレーム**内 | `list_frame.click(...)` |
| download link検索 | **フレーム**内 | `list_frame.locator(...)` |
| **戻る処理** | **メインページ**にフレームのURLをロード | `self.page.goto(current_url, ...)` ← **矛盾** |

## 🔍 なぜこれが問題なのか

### ASP.NETフレームベースのページ構造

Carewell WebサービスはASP.NETのフレームベース設計：
```
Main Page (index.html)
├── Frame: "menu"
├── Frame: "list"  ← 提出一覧がここにある
└── Frame: "detail"
```

### 期待される動作 vs 実際の動作

**期待される動作**:
1. `list` フレーム内のdetail linkをクリック → detail pageへ遷移
2. detail pageでdownload linkを取得
3. `list` フレームに戻る

**実際の動作**:
1. `list` フレーム内のdetail linkをクリック → detail pageへ遷移
2. detail pageでdownload linkを取得
3. `self.page.goto(フレームのURL)` → **メインページ全体がフレームの内容で置き換わる**
4. 次のdetail linkを探そうとするが、**フレーム構造が壊れている**
5. detail linkが見つからず180秒タイムアウト

### 中島　智洋が成功した理由

**中島　智洋は1件目だった**:
- まだフレーム構造が正常
- detail linkクリック成功
- download link取得成功
- **しかし、戻る処理でフレーム構造が破壊された**

**田中　博明以降（2件目〜）**:
- フレーム構造が既に破壊されている
- detail linkが見つからない
- 180秒タイムアウト

## 📊 実証

### 処理タイムライン

```
17:41:55 - Page 2開始
17:41:55 - 1件目（中島　智洋）: detail link取得開始
  → list_frame.click() 成功（フレーム構造は正常）
  → download link取得成功
  → self.page.goto(フレームURL) ← フレーム構造破壊
  → 17:42:01: 完了

17:42:01 - 2件目（田中　博明）: detail link取得開始
  → list_frame.click() でタイムアウト（フレーム構造が破壊済み）
  → 17:45:01: 180秒タイムアウト

17:45:01 - 3件目: detail link取得開始
  → 同様にタイムアウト
  → 17:48:04: 180秒タイムアウト

17:48:04 - 4件目: detail link取得開始
  → 同様にタイムアウト
  → 17:51:07: 180秒タイムアウト
```

## 🎯 正しい実装

### 修正案1: フレーム内で戻る

```python
# 変更前
self.page.goto(current_url, wait_until="networkidle")

# 変更後
list_frame.goto(current_url, wait_until="load", timeout=30000)
```

### 修正案2: ページ全体のURLを保存して戻る

```python
# 変更前
current_url = list_frame.url  # フレームのURL

# 変更後
current_url = self.page.url  # メインページのURL
```

### 修正案3: 履歴バックを使用

```python
# 変更後
self.page.go_back(wait_until="load", timeout=30000)
```

## 🔄 推奨される修正

**修正案1（フレーム内で戻る）が最も安全**:

```python
def _get_download_link(self, detail_url: str, list_url: str) -> dict:
    """
    Navigate to detail page and extract download link
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

        # Check if detail link exists (10 second timeout)
        detail_link_selector = f'a[href="{detail_url}"]'
        try:
            list_frame.wait_for_selector(detail_link_selector, timeout=10000, state="visible")
        except Exception as e:
            logger.warning(f"Detail link not found: {detail_url} - {e}")
            return {"url": None, "filename": None}

        # Click the detail link
        list_frame.click(detail_link_selector)
        self._wait_for_navigation(3000)

        # Find download link
        download_link = list_frame.locator('a[href^="download.aspx"]').first

        if download_link.count() > 0:
            download_url = download_link.get_attribute("href")
            filename = download_link.text_content().strip()
            logger.info(f"Found download link: {filename}")

            # Navigate back within the frame (FIXED)
            list_frame.goto(current_url, wait_until="load", timeout=30000)
            self._wait_for_navigation()

            return {"url": download_url, "filename": filename}
        else:
            logger.warning(f"No download link found for {detail_url}")
            # Navigate back within the frame (FIXED)
            list_frame.goto(current_url, wait_until="load", timeout=30000)
            self._wait_for_navigation()

            return {"url": None, "filename": None}

    except Exception as e:
        logger.error(f"Error getting download link from {detail_url}: {e}", exc_info=True)
        # Try to go back within the frame (FIXED)
        try:
            if list_frame and current_url:
                list_frame.goto(current_url, wait_until="load", timeout=30000)
                self._wait_for_navigation()
        except:
            pass
        return {"url": None, "filename": None}
```

## 📈 期待される効果

| 項目 | 現在 | 修正後 |
|------|------|--------|
| フレーム構造 | 1件目で破壊 | 維持 |
| 2件目以降のdetail link取得 | 180秒タイムアウト | 成功 |
| 55件の処理時間 | 不可能（タイムアウト） | 約330秒（55件×6秒） |
| Cloud Run 900秒タイムアウト | 到達 | 回避 |
| ファイルDL/UL/スプレッドシート | 未実行 | 実行可能 |

## ✅ 検証方法

1. 修正を実装
2. class01-task01でテスト実行
3. 以下を確認:
   - ✅ 2件目以降もdetail link取得成功
   - ✅ 55件全てdownload link取得完了
   - ✅ ファイルダウンロード開始
   - ✅ Google Driveアップロード成功
   - ✅ スプレッドシート記録成功

---

**作成者**: Claude Code
**レビュー**: 要レビュー
**ステータス**: 🚨 Critical Design Flaw Identified
