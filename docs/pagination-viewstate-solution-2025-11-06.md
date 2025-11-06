# ASP.NET ViewState方式ページネーション問題の解決計画

## 📅 作成日時
2025-11-06 18:00 JST

## 🔗 関連ドキュメント
- [インシデント記録](./incident-2025-11-06-pagination-url-update-delay.md)
- [Class01タイムアウト分析](./CLASS01_TIMEOUT_ANALYSIS.md)

---

## 🎯 問題の再発見

### 当初の誤った仮説（commit 9330a23）

**仮説**: ASP.NET `__doPostBack` 後、Frame URLの更新が遅延する

**対策**: URL変更を明示的に待機（最大20秒ポーリング）

**結果**: 効果なし → revert（commit ccc5fdf）

---

## 🔍 真の根本原因（2025-11-06 18:00判明）

### 手動確認結果

```
ページ1のURL: https://jaccw-carewel.study.jp/
ページ2のURL: https://jaccw-carewel.study.jp/  ← 同じ！
```

### ASP.NET WebフォームのViewState方式

**重要な発見**:
- ページネーション状態はURLではなく**ViewState**（POSTデータ）で管理
- URLは全ページで同一
- `pagination_select.select_option("2")` はViewStateを更新するが、URLは変更しない

### なぜ9330a23がrevertされたのか（確定）

```python
# 9330a23の修正ロジック
old_url = list_url  # "https://jaccw-carewel.study.jp/"
for retry in range(10):
    current_frame_url = list_frame.url  # "https://jaccw-carewel.study.jp/" (変わらない)
    if current_frame_url != old_url:
        break  # ← 永遠に実行されない
    time.sleep(2)  # 毎回20秒タイムアウト
```

**結論**: URL監視は**意味がない** → パフォーマンス悪化のみ → revert

---

## 💥 実際の問題メカニズム（詳細フロー）

### シナリオ：ページ2の学生100名を処理

```python
# --- ページ2に遷移 ---
Line 861: pagination_select.select_option("2")
          ↓
          ViewState: page=2 に更新
          DOM: ページ2の学生（101-200名）のテーブル表示
          URL: "https://jaccw-carewel.study.jp/" (変わらず)

Line 892: list_url = list_frame.url  # "https://jaccw-carewel.study.jp/"

# --- ページ2の学生A（101番目）のファイルをダウンロード ---
Line 753: download_info = self._get_download_link(basic["detail_url"], list_url)

    # _get_download_link 内
    Line 963: current_url = list_url  # "https://jaccw-carewel.study.jp/"

    Line 969: if list_frame.url != current_url:  # False（同じURL）
              # このチェックは通過（URLが同じなので問題ないと判断）

    Line 1035: link.click()  # detail pageに遷移
               ↓
               詳細ページでダウンロードリンク取得
               ↓
    Line 1070: list_frame.goto(current_url)  # ❌ 問題発生！
               ↓
               goto("https://jaccw-carewel.study.jp/") を実行
               → ブラウザは「最初の状態」をロード
               → ViewState: page=1 にリセット
               → DOM: ページ1の学生（1-100名）のテーブル表示

    Line 1088-1090: wait_for_selector("tr.standard_grid_item")
                    # ページ1のテーブルを待機（成功）

# --- ページ2の学生B（102番目）のファイルをダウンロード ---
Line 753: download_info = self._get_download_link(basic["detail_url"], list_url)

    # _get_download_link 内（frameはページ1の状態）
    Line 991: report_links = list_frame.locator('a[href*="report.aspx"]').all()
              # ❌ ページ1のDOMで「学生B（102番目）」を検索
              # → 見つからない！（ページ1には1-100名しかいない）

    Line 994-996: if not report_links:
                      return {"url": None, "filename": None}
                  # ダウンロード失敗
```

### 結果

- **ページ2の最初の学生（101番目）**: ダウンロード成功
- **ページ2の残り99名（102-200番目）**: 全て失敗

**実際のログ証拠**（リビジョン 00193-sxw）:
```json
{
  "submissions_found": 199,
  "processed": 115,
  "failed": 84
}
```
→ ページ1（100名）+ ページ2の最初（15名）= 115名成功

---

## ❌ 誤った解決策：`list_frame.go_back()` への変更（存在しないメソッド）

### 検証結果（2025-11-06 19:30）

**Playwright API確認**:
- ❌ `Frame.go_back()` メソッドは**存在しない**
- ✅ `Page.go_back()` メソッドのみ利用可能
- 参照: https://playwright.dev/python/docs/api/class-frame

### 実際の動作

**`page.go_back()` を使用した場合**:
```python
self.page.go_back(wait_until="load", timeout=30000)
# → ページ全体の履歴を戻す
# → ASP.NET ViewStateの性質により、常にページ1に戻る
```

**手動確認結果**（ユーザー検証）:
> 「戻る」操作をすると必ず1ページ目に遷移する

**結論**: `go_back()` だけではViewStateを保持できない

---

## ✅ 正しい解決策：再遷移アプローチ

### 方針

**`page.go_back()` でページ1に戻ることを受け入れ、その後対象ページへ再遷移する**

1. `page.go_back()` 実行 → ページ1に戻る（これは避けられない）
2. `current_page > 1` の場合、ページネーション操作で対象ページに再遷移
3. 再遷移時は適切な待機時間とフレーム取得リトライを実装

### 実装計画

#### 修正箇所（3箇所）

**箇所1**: Line 1070（正常系 - ダウンロードリンク取得成功後）
```python
# Before
list_frame.goto(current_url, wait_until="load", timeout=30000)

# After
# Navigate back using browser history (page level)
# Note: Always returns to page 1 due to ASP.NET ViewState behavior
self.page.go_back(wait_until="load", timeout=30000)
self._wait_for_navigation()

# Re-navigate to target page if not page 1
if current_page > 1:
    self.logger.info(f"Re-navigating to page {current_page} after go_back()")

    # Get frame reference with retry logic (Common Mistake #6 pattern)
    list_frame = None
    max_retries = 3

    for retry in range(max_retries):
        for frame in self.page.frames:
            if frame.name == CarewellSelectors.FRAME_LIST:
                try:
                    _ = frame.url  # Verify frame not detached
                    list_frame = frame
                    break
                except Exception:
                    continue

        if list_frame:
            break

        if retry < max_retries - 1:
            self.logger.debug(f"Frame not found, retrying ({retry + 1}/{max_retries})...")
            time.sleep(2)

    if not list_frame:
        self.logger.error("List frame not found after go_back, cannot re-navigate")
        return {"url": None, "filename": None}

    # Navigate to target page
    pagination_select = list_frame.locator("#ctl00_masterMain_ddlPage")

    if pagination_select.count() > 0:
        pagination_select.select_option(str(current_page))
        self.logger.info(f"Waiting for page transition to page {current_page} (15 seconds)...")
        time.sleep(15)  # Same as existing pagination wait time

        # Refresh frame reference after re-navigation
        list_frame = None
        for retry in range(max_retries):
            for frame in self.page.frames:
                if frame.name == CarewellSelectors.FRAME_LIST:
                    try:
                        _ = frame.url
                        list_frame = frame
                        break
                    except Exception:
                        continue

            if list_frame:
                break

            if retry < max_retries - 1:
                time.sleep(2)

        self.logger.info(f"✓ Re-navigated to page {current_page}")
    else:
        self.logger.warning("Pagination control not found after go_back")
```

**箇所2**: Line 1101（異常系 - ダウンロードリンクが見つからない）
```python
# 箇所1と同じ再遷移ロジックを実装
```

**箇所3**: Line 1136（エラーリカバリー - 例外発生時）
```python
# 箇所1と同じ再遷移ロジックを実装
```

#### 変更しない箇所

**Line 973**: ページミスマッチ検出時の修正ナビゲーション
```python
# これは変更しない（意図的に特定ページに戻る処理）
if list_frame.url != current_url:
    list_frame.goto(current_url, wait_until="load", timeout=30000)
```
→ ただし、ViewState方式では**このチェックは常にFalse**（URLが常に同じ）なので、実質的に実行されない

### 副次的な改善

**Line 892の `list_url` 更新は不要になる**
```python
# Before
list_url = list_frame.url
self.logger.info(f"✓ Updated list URL for page {next_page}: {list_url}")

# After
# list_url の更新は不要（go_back()はURLを使わないため）
# ただし、後方互換性とログのために残す
list_url = list_frame.url
self.logger.info(f"✓ Page {next_page} loaded (ViewState-based, URL unchanged)")
```

---

## 🔍 リスク分析

### リスク1: 「全て」タブの状態が失われる

**懸念**: `go_back()` で戻った時、「全て」タブが解除されている可能性

**分析**:
- 「全て」タブクリック後、フレームがリロード（Line 345-346）
- その後のページネーションは同じフレーム内での遷移
- `go_back()` は同じフレーム内の履歴を辿る

**結論**: リスク低（「全て」タブ状態は保持される）

**検証方法**: ログで確認
```python
# go_back() 後にテーブル行数をログ
rows_after_back = list_frame.locator("tr.standard_grid_item").count()
self.logger.info(f"Rows after go_back(): {rows_after_back}")
# 期待: ページ2なら 80-100行（最終ページは端数）
```

### リスク2: ブラウザ履歴が不十分

**懸念**: detail pageに遷移した後、履歴がない可能性

**分析**:
- detail pageへの遷移: `link.click()` → 履歴に追加される
- 戻る操作: `go_back()` → 直前の履歴に戻る

**結論**: リスク低（Playwright/Chromiumの標準動作）

**検証方法**: ログで確認
```python
# go_back() 実行前
self.logger.debug(f"Current URL before go_back: {list_frame.url}")
# go_back() 実行後
self.logger.debug(f"Current URL after go_back: {list_frame.url}")
# 期待: 両方とも "https://jaccw-carewel.study.jp/"
```

### リスク3: go_back() のタイムアウト

**懸念**: `go_back()` が30秒でタイムアウトする可能性

**分析**:
- ブラウザキャッシュから復元 → 通常は高速（1-2秒）
- ネットワークリクエストなし

**結論**: リスク低（goto()より高速）

**対策**: タイムアウト値は30秒のまま維持（十分な余裕）

### リスク4: ASP.NET bfcache無効化

**懸念**: ASP.NETが bfcache（back-forward cache）を無効化している可能性

**分析**:
- もし無効化されていれば、`go_back()` も新しいリクエストを送信
- その場合、`goto()` と同じ問題が再発

**結論**: リスク中（実装後の検証が必須）

**検証方法**: ログで確認
```python
# ページ2の2番目の学生で成功するかチェック
# 成功すれば bfcache は有効
```

---

## 📋 実装チェックリスト

### フェーズ1: コード修正
- [ ] Line 1070: `goto()` → `go_back()` 変更
- [ ] Line 1101: `goto()` → `go_back()` 変更
- [ ] Line 1136: `goto()` → `go_back()` 変更（current_url引数も削除）
- [ ] Line 892-895: ログメッセージ更新（ViewState方式を明記）
- [ ] 追加ログ挿入（検証用）
  - `go_back()` 後のテーブル行数
  - `go_back()` 前後のURL

### フェーズ2: コード品質
- [ ] Black フォーマット
- [ ] isort インポート整理
- [ ] mypy 型チェック
- [ ] flake8 リント

### フェーズ3: コミット・デプロイ
- [ ] 詳細なコミットメッセージ作成（このドキュメント参照）
- [ ] git commit & push
- [ ] GitHub Actions実行確認
- [ ] デプロイ完了確認（リビジョン作成）
- [ ] トラフィック100%確認

### フェーズ4: 本番検証
- [ ] Cloud Runログで以下を確認:
  - `go_back()` 実行ログ
  - ページ2の2番目以降の学生でダウンロード成功
  - エラーログなし
- [ ] Dashboard確認:
  - №01 課題①: 199名全員のファイル表示
- [ ] カウント確認:
  - `processed: 199, failed: 0`

---

## 🔄 ロールバック計画

### ロールバック条件

以下のいずれかが発生した場合:
1. `go_back()` でエラーが発生（タイムアウト等）
2. ページ2の学生がダウンロードできない（問題再発）
3. ページ1の学生もダウンロードできなくなる（リグレッション）

### ロールバック手順

```bash
# 即座に前のリビジョンに戻す
gcloud run services update-traffic carewell-file-collector \
  --region=asia-northeast1 \
  --to-revisions PREVIOUS_REVISION=100

# または、revertコミットをプッシュ
git revert HEAD
git push origin main
```

---

## 📚 学習ポイント（将来の参考）

### ASP.NET Webフォームの特性

1. **ViewState方式**:
   - ページ状態はPOSTデータで管理
   - URLは全ページで同一
   - URLを監視しても意味がない

2. **ページネーション**:
   - `__doPostBack` でサーバーにPOST
   - ViewStateが更新される
   - クライアントサイドルーティングではない

### Playwrightのナビゲーション

1. **`goto(url)`**:
   - 新しいHTTPリクエストを送信
   - サーバーの初期応答を受け取る
   - ViewStateはリセットされる

2. **`go_back()`**:
   - ブラウザ履歴を使用
   - bfcacheから復元（可能な場合）
   - ViewStateは保持される

### トラブルシューティングの教訓

1. **仮説検証の重要性**:
   - 「URLが遅延する」という仮説は誤り
   - 手動確認で真因発見（URLが変わらない）

2. **実装前の調査**:
   - ASP.NETの動作方式を先に調査すべきだった
   - ドキュメントに「ViewState」の記載なし → 知識不足

3. **revertの理由分析**:
   - なぜrevertされたのか？ → 効果なし＋パフォーマンス悪化
   - revert理由を明示すべき（将来の混乱を防ぐ）

---

## 📊 期待される結果

### ビフォー（現在）

```
№01 課題①（199名）
- 成功: 115名（ページ1: 100名、ページ2: 15名）
- 失敗: 84名（ページ2: 85-199番目）
- 成功率: 57.8%
```

### アフター（修正後）

```
№01 課題①（199名）
- 成功: 199名
- 失敗: 0名
- 成功率: 100%
```

---

## 📝 実装者ノート

実装時の注意点をここに記録:
- [ ] `go_back()` のAPIシグネチャ確認（Playwright Pythonドキュメント）
- [ ] 既存の `_wait_for_navigation()` との互換性確認
- [ ] エラーハンドリングの既存パターンに従う

---

**作成者**: AI Agent (Claude Code)
**最終更新**: 2025-11-06 18:00 JST
