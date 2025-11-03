# ページネーション処理バグ修正計画

## 📅 作成日
2025-11-03

## 🔗 関連ドキュメント
- [問題分析レポート](./PAGINATION_BUG_ANALYSIS.md)

## 🎯 修正の目的

`get_submission_list`メソッドにおいて、2ページ目以降の処理時にフレーム参照が古くなり、処理が途中で中断される問題を修正します。

## 📋 修正内容の詳細

### 修正1: フレーム参照の定期更新

**対象ファイル**: `src/playwright_automation.py`
**対象メソッド**: `PlaywrightAutomationEngine.get_submission_list`
**対象行**: 385行目付近（whileループの先頭）

#### 現在のコード

```python
# 343-349行目: ループの外でフレーム取得
list_frame = None
for frame in self.page.frames:
    if frame.name == CarewellSelectors.FRAME_LIST:
        list_frame = frame
        break

if not list_frame:
    logger.warning("'list' frame not found, using main page")
    list_frame = self.page

# 382行目: ループの外でURL取得
list_url = list_frame.url

# 385行目: ページネーションループ
while True:
    logger.info(f"Processing page {current_page}")

    # Wait for table to be fully rendered after frame reload or page transition
    if current_page == 1:
        # Frame reload after "全て" tab click
        logger.info("Waiting for table to render after frame reload...")
        time.sleep(5)
    elif current_page > 1:
        # Page transition via ASP.NET __doPostBack
        logger.info("Waiting for table to render after page navigation...")
        time.sleep(3)

    # Wait for data to load
    logger.info("Waiting for submission table rows...")
    list_frame.wait_for_selector("tr.standard_grid_item", timeout=30000)
    # ...
```

#### 修正後のコード

```python
# 343-349行目: 初回のフレーム取得（削除はしない、変更なし）
list_frame = None
for frame in self.page.frames:
    if frame.name == CarewellSelectors.FRAME_LIST:
        list_frame = frame
        break

if not list_frame:
    logger.warning("'list' frame not found, using main page")
    list_frame = self.page

# 382行目: 初回のURL取得（削除）
# list_url = list_frame.url  ← この行を削除

# 385行目: ページネーションループ
while True:
    logger.info(f"Processing page {current_page}")

    # 🆕 フレーム参照を毎回更新
    list_frame = None
    for frame in self.page.frames:
        if frame.name == CarewellSelectors.FRAME_LIST:
            list_frame = frame
            break

    if not list_frame:
        logger.warning("'list' frame not found, using main page")
        list_frame = self.page

    # 🆕 現在のページURLを保存（各ページで更新）
    list_url = list_frame.url
    logger.debug(f"Current list URL for page {current_page}: {list_url}")

    # Wait for table to be fully rendered after frame reload or page transition
    if current_page == 1:
        # Frame reload after "全て" tab click
        logger.info("Waiting for table to render after frame reload...")
        time.sleep(5)
    elif current_page > 1:
        # Page transition via ASP.NET __doPostBack
        logger.info("Waiting for table to render after page navigation...")
        time.sleep(3)

    # Wait for data to load
    logger.info("Waiting for submission table rows...")
    list_frame.wait_for_selector("tr.standard_grid_item", timeout=30000)
    # ...
```

#### 修正のポイント

1. **フレーム参照の更新頻度**: ループの外 → ループの内（毎ページ）
2. **URL取得の更新頻度**: ループの外 → ループの内（毎ページ）
3. **デバッグログの追加**: `list_url`の値を確認できるログを追加

#### 期待される効果

- ✅ ページ遷移後も常に最新のフレームオブジェクトを参照
- ✅ 各ページの正しいURLを保存
- ✅ download link取得後、正しいページに戻れる
- ✅ 100件全てのdownload link取得が完了
- ✅ 2ページ目以降の処理に進める

### 修正2: ページ遷移後のフレーム更新確認（オプション）

**対象行**: 506-508行目付近（ページ選択後）

#### 現在のコード

```python
# Select next page by value (page numbers are 1-indexed)
pagination_select.select_option(str(next_page))

current_page = next_page
```

#### 修正後のコード（オプション）

```python
# Select next page by value (page numbers are 1-indexed)
pagination_select.select_option(str(next_page))
logger.info(f"✓ Selected page {next_page}")

current_page = next_page

# Note: Frame reference will be refreshed at the top of the loop
```

**注記**: 修正1で対応されるため、この修正は必須ではありません。ログの明確化のみ。

## 📝 コード変更サマリー

### 変更ファイル

```
src/playwright_automation.py
```

### 変更内容

| 操作 | 行番号 | 内容 |
|------|--------|------|
| 削除 | 382 | `list_url = list_frame.url` をループ外から削除 |
| 追加 | 385-398 | ループ内でフレーム参照とURLを更新するコードを追加 |
| 追加 | ~393 | デバッグログ追加: `logger.debug(f"Current list URL for page {current_page}: {list_url}")` |

### 変更行数

- **追加**: 約15行
- **削除**: 1行
- **修正**: 0行
- **合計**: 約16行の変更

## 🧪 テスト計画

### テストケース1: 単一ページ（<100件）

**目的**: 既存動作を壊さないことを確認

**手順**:
1. 13件のクラス（例: class02-task01）を実行
2. ログを確認

**期待結果**:
```
✓ Total submission count from UI: 13
Processing page 1
Current list URL for page {current_page}: [URL]
Extracted basic info for 13 submissions on page 1
Getting download link for: [学生名1]
...
Getting download link for: [学生名13]
Successfully extracted 13 submissions from 1 page(s)
✓ Count verification passed: 13/13
```

### テストケース2: 2ページ（100-200件）

**目的**: 2ページ目の処理を確認

**手順**:
1. 145件のクラス（carewell-class01-task01）を実行
2. ログを確認

**期待結果**:
```
✓ Total submission count from UI: 145
Processing page 1
Current list URL for page 1: [URL1]
Extracted basic info for 100 submissions on page 1
Getting download link for: [学生名1]
...
Getting download link for: [学生名100]
Total pages available: 2
Navigating to page 2/2
Processing page 2
Current list URL for page 2: [URL2]
Extracted basic info for 45 submissions on page 2
Getting download link for: [学生名101]
...
Getting download link for: [学生名145]
Reached last page 2/2
Successfully extracted 145 submissions from 2 page(s)
✓ Count verification passed: 145/145
```

### テストケース3: エラーハンドリング

**目的**: フレーム取得失敗時の挙動確認

**手順**:
1. モックでフレーム取得失敗をシミュレート

**期待結果**:
- "list' frame not found, using main page" のログ出力
- main pageをフォールバックとして使用
- 処理継続

## 📊 成功基準

### 必須基準

- ✅ 145件全て処理完了（`Successfully extracted 145 submissions`）
- ✅ UI表示件数と処理件数が一致（`✓ Count verification passed: 145/145`）
- ✅ 2ページ目の処理ログが出力（`Processing page 2`）
- ✅ ページ遷移ログが出力（`Navigating to page 2/2`）

### 推奨基準

- ✅ 各ページで正しいURLが取得されている（`Current list URL for page 2: [URL2]`）
- ✅ タイムアウトエラーが発生しない
- ✅ 既存の単一ページケース（<100件）の動作に影響なし

## 🚀 実装手順

### Step 1: コード修正

1. `src/playwright_automation.py`を開く
2. 382行目の`list_url = list_frame.url`を削除
3. 385行目のwhileループ先頭に、フレーム参照とURL更新のコードを追加
4. デバッグログを追加

### Step 2: ローカルテスト（オプション）

1. テストスクリプトで動作確認
2. モックデータで2ページケースをテスト

### Step 3: コミット

1. 変更をステージング: `git add src/playwright_automation.py`
2. コミット: `git commit`（詳細なコミットメッセージを記述）

### Step 4: デプロイ

1. GitHub Actionsで自動デプロイ
2. Cloud Runへのデプロイ完了を確認

### Step 5: 本番検証

1. Cloud Schedulerでjobを手動実行: `gcloud scheduler jobs run carewell-class01-task01 --location=asia-northeast1`
2. Cloud Loggingでログを確認
3. Firestoreで145件の記録を確認
4. Google Sheetsで145件の記録を確認

## 📚 ドキュメント更新

### 更新対象

1. **design.md** (.kiro/specs/carewell-drive-automation/)
   - 「判断X: ページネーション処理でのフレーム参照更新」セクションを追加
   - 今回の修正内容と判断理由を記録

2. **README.md**
   - トラブルシューティングセクションに追記（必要に応じて）

3. **CHANGELOG.md**（存在する場合）
   - 修正履歴を追加

## 🔄 ロールバック計画

### ロールバック条件

以下のいずれかが発生した場合、即座にロールバック：

1. 単一ページケース（<100件）が正常に動作しない
2. Firestoreへの書き込みエラーが頻発
3. その他の重大なエラー

### ロールバック手順

```bash
# コミットをrevert
git revert HEAD

# 再デプロイ
git push origin main

# GitHub Actionsで自動デプロイされる
```

## 📞 エスカレーション

### 問題発生時の連絡先

- **開発者**: [連絡先]
- **システム管理者**: system@jaccw.or.jp

### 緊急時の対応

1. Cloud Scheduler jobを一時停止
2. 問題を調査
3. 必要に応じてロールバック

## ✅ チェックリスト

実装前:
- [ ] 問題分析ドキュメントをレビュー
- [ ] 修正計画をレビュー
- [ ] テスト計画を確認

実装時:
- [ ] コード修正を実装
- [ ] デバッグログを追加
- [ ] コードレビュー（セルフレビュー）

実装後:
- [ ] コミットメッセージを記述
- [ ] design.mdを更新
- [ ] デプロイ実施
- [ ] ログ確認
- [ ] Firestore確認
- [ ] Google Sheets確認

## 📝 備考

### 参考にしたコード

`_get_download_link`メソッド（559-564行目）では、正しくフレーム参照を毎回更新しています：

```python
def _get_download_link(self, detail_url: str, list_url: str) -> dict:
    try:
        # 毎回フレームを取得
        list_frame = None
        for frame in self.page.frames:
            if frame.name == CarewellSelectors.FRAME_LIST:
                list_frame = frame
                break
```

この実装パターンを`get_submission_list`にも適用しました。

### 将来の改善案

1. **フレーム取得の共通化**: フレーム取得ロジックを`_get_list_frame()`のようなヘルパーメソッドに抽出
2. **リトライロジックの追加**: フレーム取得失敗時のリトライ
3. **ページ遷移完了の確認**: `wait_for_load_state`での明示的な待機

---

## 📋 第1回修正の検証結果と追加修正

### 第1回修正の結果

**実装日**: 2025-11-03 08:30 JST
**コミット**: b416e3b
**ステータス**: ❌ 不完全 - 追加修正が必要

**検証結果**:
- フレーム参照更新コードは正しくデプロイされた
- しかし、100回のdownload link取得後、ページネーション判定時点でフレームが再度detachedになる
- エラー: "Pagination navigation failed: Frame was detached"
- 結果: 140件中100件のみ処理、2ページ目に進めず

### 第2回修正計画

#### 修正内容: ページネーション判定前のフレーム参照更新

**対象ファイル**: `src/playwright_automation.py`
**対象行**: 493行目（download linkループの直後）

**追加するコード**:
```python
# Refresh frame reference before pagination check
# (frame may be detached after 100 page navigations in download link loop)
list_frame = None
for frame in self.page.frames:
    if frame.name == CarewellSelectors.FRAME_LIST:
        list_frame = frame
        break

if not list_frame:
    logger.warning(
        "'list' frame not found for pagination check, using main page"
    )
    list_frame = self.page

logger.info("✓ Frame reference refreshed for pagination check")
```

**挿入位置**:
- 現在の493行目（`# Check for pagination and navigate to next page`コメントの直前）
- download linkループ（468-492行）の直後

#### 修正の効果

- ✅ download link取得による100回のページ遷移後も、最新のフレームを参照
- ✅ ページネーション判定処理で "Frame was detached" エラーが発生しない
- ✅ 2ページ目への遷移が正常に実行される
- ✅ 140件全件の処理が完了

#### 実装手順

1. `src/playwright_automation.py` を編集
2. 493行目の直前に、フレーム参照更新コードを追加（約14行）
3. ローカルでコード確認
4. git add, commit, push
5. GitHub Actionsでデプロイ
6. 本番環境で再検証

#### テスト計画

**テストケース**: 140件クラス（令和7年度 デジタル中核人材養成研修 №？、課題①）

**期待ログ**:
```
Processing page 1
Extracted basic info for 100 submissions on page 1
Getting download link for: [学生1]
...
Getting download link for: [学生100]
✓ Frame reference refreshed for pagination check
Total pages available: 2
Navigating to page 2/2
Processing page 2
Extracted basic info for 40 submissions on page 2
Getting download link for: [学生101]
...
Getting download link for: [学生140]
✓ Frame reference refreshed for pagination check
Reached last page 2/2
Successfully extracted 140 submissions from 2 page(s)
✓ Count verification passed: 140/140
```

#### 成功基準

- ✅ "Frame was detached" エラーが発生しない
- ✅ "Total pages available: 2" ログが出力される
- ✅ "Processing page 2" ログが出力される
- ✅ 140件全件処理完了（"Successfully extracted 140 submissions"）
- ✅ 件数検証成功（"✓ Count verification passed: 140/140"）

---

**作成者**: Claude Code
**レビュー**: 要レビュー
**ステータス**: Ready for 2nd Implementation
