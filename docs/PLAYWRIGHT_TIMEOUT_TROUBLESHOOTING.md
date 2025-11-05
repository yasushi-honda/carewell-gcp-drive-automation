# Playwright タイムアウトエラー トラブルシューティングガイド

## 概要

Playwright自動化で`TimeoutError`が発生した場合の診断と解決方法を記載します。

**重要**: タイムアウトエラーは「待機時間が足りない」問題ではなく、**フレーム参照の問題**であることが多いです。

## 目次

1. [基本的な診断フロー](#基本的な診断フロー)
2. [フレーム再取得の重要性](#フレーム再取得の重要性)
3. [具体的なチェックポイント](#具体的なチェックポイント)
4. [実例: CLASS01タイムアウト問題の解決](#実例-class01タイムアウト問題の解決)
5. [ベストプラクティス](#ベストプラクティス)

## 基本的な診断フロー

### ❌ よくある誤った対応

```python
# ❌ 悪い例: 単に待機時間を増やす
try:
    frame.wait_for_selector("tr.standard_grid_item", timeout=60000)  # 10s → 60s に変更
except TimeoutError:
    # リトライ回数を増やす
    pass
```

**問題点**: タイムアウトエラーの**根本原因**は待機時間ではなく、フレーム参照が無効（detached/stale）になっているケースが多い。

### ✅ 正しい診断フロー

1. **エラー発生箇所を特定**
   - スタックトレースから正確な行番号を確認
   - どのメソッド・どの処理ステップで失敗しているか

2. **フレーム再取得の有無を確認**
   - エラー発生箇所の**直前**でフレームを再取得しているか
   - `time.sleep()`など長時間待機の**後**にフレーム再取得しているか

3. **ログでフレーム再取得を検証**
   - `✓ Frame refreshed` メッセージがログに出力されているか
   - フレーム再取得が成功していても、**タイミング**が適切か

## フレーム再取得の重要性

### なぜフレームがdetachedになるのか

Playwrightでは、以下の操作後にフレーム参照が無効になります：

1. **`frame.goto()` によるページ遷移**
2. **`__doPostBack()` によるASP.NET ポストバック**
3. **`time.sleep()` など長時間の待機中にDOMが再構築**

### フレーム再取得のパターン

```python
# ✅ 正しいパターン
def some_operation_with_navigation():
    # 1. フレームを取得
    list_frame = None
    for frame in self.page.frames:
        if frame.name == CarewellSelectors.FRAME_LIST:
            list_frame = frame
            break

    # 2. ページ遷移
    list_frame.goto(url, wait_until="load")

    # 3. 【重要】フレームを再取得
    list_frame = None
    for frame in self.page.frames:
        if frame.name == CarewellSelectors.FRAME_LIST:
            list_frame = frame
            break

    if not list_frame:
        logger.error("Frame not found after navigation")
        return

    logger.debug("✓ Frame refreshed after navigation")

    # 4. フレームを使用
    list_frame.wait_for_selector("tr.standard_grid_item", timeout=30000)
```

### 特に注意が必要なケース

#### ケース1: `time.sleep()` の後

```python
# ❌ 悪い例
list_frame = get_list_frame()
time.sleep(15)  # テーブルレンダリング待機
list_frame.wait_for_selector("tr.standard_grid_item")  # ← ここでタイムアウト

# ✅ 良い例
list_frame = get_list_frame()
time.sleep(15)  # テーブルレンダリング待機

# sleep後にフレーム再取得
list_frame = None
for frame in self.page.frames:
    if frame.name == CarewellSelectors.FRAME_LIST:
        list_frame = frame
        break

logger.debug("✓ Frame refreshed after sleep")
list_frame.wait_for_selector("tr.standard_grid_item")  # ← 成功
```

#### ケース2: ページネーション遷移

```python
# ✅ 良い例
for page_num in range(1, total_pages + 1):
    # ページ遷移前にフレーム取得
    list_frame = get_list_frame()

    # ページ遷移（__doPostBack）
    if page_num > 1:
        navigate_to_page(page_num)
        time.sleep(15)  # レンダリング待機

        # 【重要】ページ遷移後にフレーム再取得
        list_frame = get_list_frame()
        logger.debug(f"✓ Frame refreshed for page {page_num}")

    # フレーム使用
    list_frame.wait_for_selector("tr.standard_grid_item")
```

## 具体的なチェックポイント

### 1. エラー発生箇所の特定

```bash
# ログからスタックトレースを確認
grep -A 10 "TimeoutError" /tmp/logs.txt
```

出力例：
```
File "/app/src/playwright_automation.py", line 433, in get_submission_list
  list_frame.wait_for_selector("tr.standard_grid_item", timeout=30000)
playwright._impl._errors.TimeoutError: Timeout 30000ms exceeded.
```

→ **433行目**で失敗していることが確認できる

### 2. フレーム再取得の確認

**チェック項目**:
- [ ] エラー発生箇所（433行）の**直前**でフレーム再取得しているか
- [ ] その前に`time.sleep()`など長時間待機があるか（413-429行）
- [ ] sleep後にフレーム再取得しているか

### 3. ログでの検証

```bash
# フレーム再取得ログを確認
grep "Frame refreshed" /tmp/logs.txt
```

**期待される出力**:
```
2025-11-04 12:00:20 - DEBUG - ✓ Frame refreshed after sleep (page 1)
2025-11-04 12:00:35 - DEBUG - ✓ Frame refreshed after navigation back
```

**ログがない場合** → フレーム再取得が実装されていない → 追加が必要

## 実例: CLASS01タイムアウト問題の解決

### 問題の経緯

**Phase 1-2**: リトライロジック実装 → **失敗**
- 待機時間を10秒→60秒に延長
- リトライ回数を3回に増加
- 結果: 改善せず

**Phase 3**: `_get_download_link`内のフレーム再取得 → **部分的成功**
- リスト画面復帰後のフレーム再取得を追加
- 結果: Phase 3のコードは正しく動作したが、**その前段階で失敗**

**Phase 3.5**: `get_submission_list`内のフレーム再取得 → **成功**
- `time.sleep(15秒)`後のフレーム再取得を追加
- 結果: タイムアウトエラー解消

### 根本原因の発見

```python
# src/playwright_automation.py (旧コード)

def get_submission_list():
    # 400-407行: フレーム取得
    list_frame = get_list_frame()

    # 413-429行: 15秒sleep
    if current_page == 1:
        time.sleep(15)

    # 433行: wait_for_selector ← ❌ ここでタイムアウト
    list_frame.wait_for_selector("tr.standard_grid_item", timeout=30000)
```

**問題**: `time.sleep(15秒)`の間にフレームがdetachedになり、433行で無効な参照を使用

### 解決策（Phase 3.5）

```python
# src/playwright_automation.py (修正後)

def get_submission_list():
    # 400-407行: フレーム取得
    list_frame = get_list_frame()

    # 413-429行: 15秒sleep
    if current_page == 1:
        time.sleep(15)

    # 431-444行: 【Phase 3.5】フレーム再取得
    temp_list_frame = None
    for frame in self.page.frames:
        if frame.name == CarewellSelectors.FRAME_LIST:
            temp_list_frame = frame
            break

    if not temp_list_frame:
        logger.warning("'list' frame not found after sleep, using main page")
        list_frame = self.page
    else:
        list_frame = temp_list_frame
        logger.debug(f"✓ Frame refreshed after sleep (page {current_page})")

    # 448行: wait_for_selector ← ✅ 成功
    list_frame.wait_for_selector("tr.standard_grid_item", timeout=30000)
```

### 学んだ教訓

1. **エラー箇所だけでなく、その前のステップも確認する**
   - Phase 3で`_get_download_link`を修正したが、実際のエラーは`get_submission_list`で発生

2. **`time.sleep()`は危険信号**
   - 長時間待機の後は必ずフレーム再取得が必要

3. **ログで検証する**
   - `✓ Frame refreshed`メッセージでフレーム再取得を確認
   - ログがない = フレーム再取得がない

## ベストプラクティス

### 1. フレーム再取得を関数化

```python
def refresh_list_frame(self, context: str = "") -> Optional[Frame]:
    """
    'list'フレームを再取得する

    Args:
        context: ログ出力用のコンテキスト（例: "after sleep", "after navigation"）

    Returns:
        Frameオブジェクト、または見つからない場合はNone
    """
    list_frame = None
    for frame in self.page.frames:
        if frame.name == CarewellSelectors.FRAME_LIST:
            list_frame = frame
            break

    if list_frame:
        logger.debug(f"✓ Frame refreshed {context}")
    else:
        logger.warning(f"'list' frame not found {context}")

    return list_frame
```

使用例:
```python
# sleep後
time.sleep(15)
list_frame = self.refresh_list_frame("after sleep (page 1)")

# ナビゲーション後
list_frame.goto(url)
list_frame = self.refresh_list_frame("after navigation")
```

### 2. フレーム再取得のタイミング

**必須**:
- [ ] `frame.goto()` の後
- [ ] `time.sleep(5秒以上)` の後
- [ ] ページネーション遷移（`__doPostBack`）の後

**推奨**:
- [ ] ループの各イテレーション開始時
- [ ] 複数のフレーム操作の間

### 3. ログ出力の統一

```python
# ✅ 良い例: コンテキストを明確に
logger.debug(f"✓ Frame refreshed after sleep (page {page_num})")
logger.debug(f"✓ Frame refreshed after navigation back")
logger.debug(f"✓ Frame refreshed after {student_name}")

# ❌ 悪い例: コンテキスト不明
logger.debug("Frame refreshed")
```

### 4. エラーハンドリング

```python
# ✅ 良い例
list_frame = self.refresh_list_frame("after sleep")
if not list_frame:
    logger.error("Critical: Cannot refresh list frame")
    return []

try:
    list_frame.wait_for_selector("tr.standard_grid_item", timeout=30000)
except TimeoutError as e:
    logger.error(f"Timeout waiting for table rows: {e}")
    logger.error(f"Frame URL: {list_frame.url if list_frame else 'N/A'}")
    logger.error(f"Frame name: {list_frame.name if list_frame else 'N/A'}")
    return []
```

## チェックリスト

タイムアウトエラーが発生した場合、以下を順に確認：

1. **エラー箇所の特定**
   - [ ] スタックトレースから正確な行番号を確認
   - [ ] どのメソッド・処理で失敗しているか特定

2. **フレーム再取得の確認**
   - [ ] エラー発生箇所の直前にフレーム再取得があるか
   - [ ] その前に`time.sleep()`があるか
   - [ ] sleep後にフレーム再取得があるか

3. **ログでの検証**
   - [ ] `✓ Frame refreshed`メッセージが出力されているか
   - [ ] タイミングが適切か（エラー直前に出力されているか）

4. **コードレビュー**
   - [ ] フレーム参照が古い変数を使っていないか
   - [ ] ループ内で同じフレーム参照を使い回していないか

5. **修正実装**
   - [ ] 適切な箇所でフレーム再取得を追加
   - [ ] ログ出力を追加（コンテキスト付き）
   - [ ] エラーハンドリングを追加

## 関連ドキュメント

- [CLASS01_TIMEOUT_ANALYSIS.md](./CLASS01_TIMEOUT_ANALYSIS.md) - 具体的な問題分析
- [ARCHITECTURE.md](./ARCHITECTURE.md) - システムアーキテクチャ
- [Playwrightドキュメント](https://playwright.dev/python/docs/frames) - 公式フレームAPI

## Phase 6: 動的リンク検出メカニズムの実装

### 問題の発生

Phase 3.5でのタイムアウト拡張（30秒→60秒）後も、特定の条件下で詳細リンククリックがタイムアウト（60秒）していました。

### 根本原因の特定

ログ分析から、`_get_download_link`メソッド内で詳細リンクを取得する際に以下のCSS selectorを使用していたことが判明：

```python
# 旧方法：CSS selectorに URL文字列をハードコード
f'a[href="{detail_url}"]'
```

問題点：
- HTML 属性は `&` が `&amp;` にエスケープされる
- CSS selector では `&amp;` が正しくマッチしない
- 結果として要素が見つからず、60秒待機後にタイムアウト

**例**:
- 期待する href: `detail.aspx?ClassID=1&TaskID=2`
- HTML 実際の href: `detail.aspx?ClassID=1&amp;TaskID=2`
- CSS selector で直接マッチング不可

### 解決策（Phase 6実装）

CSS selector で URL 文字列を直接マッチするのではなく、**ワイルドカード selector で複数要素を取得してから、プログラムロジックで属性を比較する方式に変更**

src/playwright_automation.py:817-858 での実装:

```python
# ✅ Phase 6: Dynamic link detection without hardcoding URL strings
# Find detail link dynamically by comparing href attributes
detail_link_found = False
try:
    # Step 1: ワイルドカード selector で全レポートリンクを取得
    report_links = list_frame.locator('a[href*="report.aspx"]').all()
    logger.debug(f"Found {len(report_links)} report links in the page")

    if not report_links:
        logger.warning(f"No report links found for {detail_url}")
        return {"url": None, "filename": None}

    # Step 2: 取得した各リンクの href 属性を比較
    # HTML entity encoding の差異（&amp; vs &）を処理
    for link in report_links:
        link_href = link.get_attribute("href")
        if link_href:
            # URL を正規化して比較
            # &amp; → & に置換してマッチングをチェック
            if (link_href == detail_url or
                link_href.replace("&amp;", "&") == detail_url):
                logger.debug(f"✓ Found detail link dynamically: {detail_url}")
                # Step 3: 見つけたリンクをクリック
                link.wait_for_element_state("visible", timeout=10000)
                link.click()
                detail_link_found = True
                break

    if not detail_link_found:
        logger.warning(f"Detail link not found dynamically: {detail_url}")
        found_links = [link.get_attribute("href") for link in report_links[:3]]
        logger.debug(f"Sample found links: {found_links}")
        return {"url": None, "filename": None}

    self._wait_for_navigation(3000)  # Wait for page load

except Exception as e:
    logger.warning(
        f"Error finding detail link dynamically: {detail_url} - {e}"
    )
    return {"url": None, "filename": None}
```

### 利点

1. **CSS selector の限界を回避**: HTML entity encoding に依存しない
2. **柔軟性**: URL パラメータ順序が異なる場合でも対応可能
3. **デバッグ性**: 見つかったリンク一覧をログに出力でき、問題判断が容易
4. **信頼性**: URL 全文マッチではなく部分マッチで堅牢性向上

### テスト結果

Phase 6 の展開後、手動スケジューラー実行で動的リンク検出メカニズムが正常に機能することを確認。

## ベストプラクティス（更新版）

### Playwright での動的要素マッチング

```python
# ❌ 悪い例：CSS selector に値をハードコード
locator = frame.locator(f'a[href="{url_with_special_chars}"]')

# ✅ 良い例：ワイルドカード selector + プログラムロジック
locators = frame.locator('a[href*="search_term"]').all()
for loc in locators:
    href = loc.get_attribute('href')
    # Entity encoding や URL パラメータ順序の差異を処理
    if matches_expected_url(href, expected_url):
        loc.click()
```

### Entity Encoding への対応

```python
# URL 比較時の entity encoding 対応
def normalize_url(url: str) -> str:
    """HTML entity encoding を正規化する"""
    return url.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")

# 使用例
if normalize_url(actual_href) == normalize_url(expected_href):
    # リンククリック
```

## 更新履歴

- 2025-11-05: Phase 6追加（動的リンク検出メカニズム実装）
- 2025-11-05: 初版作成（Phase 3.5対応完了後）
