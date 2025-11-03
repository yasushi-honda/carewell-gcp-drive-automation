# ページネーション処理バグ分析レポート

## 📅 作成日
2025-11-03

## 🎯 問題の概要

Cloud Scheduler実行時に、145件の提出ファイル（2ページ分）を処理する際、以下のエラーが発生し、処理が完了しない問題が発生しました。

```
ERROR: DEADLINE_EXCEEDED - URL_TIMEOUT-TIMEOUT_WEB (HTTP 504)
```

本ドキュメントでは、ページネーション処理の技術的な問題に焦点を当てて分析します。

## 🔍 問題の詳細分析

### 発生環境

| 項目 | 値 |
|------|-----|
| 実行日時 | 2025-11-03 08:00:00 - 08:09:02 |
| ジョブ名 | carewell-class01-task01 |
| クラス | 令和7年度 デジタル中核人材養成研修 №01 |
| 課題 | 課題① |
| 総提出件数 | 145件（UIから取得） |
| ページ数 | 2ページ（100件/ページ） |

### 実際の処理フロー

```
08:00:31.757 - ✓ Total submission count from UI: 145
08:00:31.757 - Processing page 1
08:00:36.777 - Found 100 submission rows on page 1
08:00:46.625 - Extracted basic info for 100 submissions on page 1
08:00:46.625 - Getting download link for: 川久保　晃 (1/100)
08:00:52.494 - Added: 川久保　晃
...
08:01:20.677 - Getting download link for: 淺倉　教江 (14/100)
08:01:22.202 - ERROR: Timeout 30000ms exceeded
                File "/app/src/playwright_automation.py", line 400
                list_frame.wait_for_selector("tr.standard_grid_item", timeout=30000)
08:01:22.203 - Found 0 submissions ← 最終結果は0件！
```

**結果：100件中14件のみ処理完了、残り86件は未処理**

### 根本原因

#### 原因1：フレーム参照の固定化

```python
# src/playwright_automation.py: 343-349行目（現在の実装）

# ループの外でlist_frameを1回のみ取得
list_frame = None
for frame in self.page.frames:
    if frame.name == CarewellSelectors.FRAME_LIST:
        list_frame = frame
        break

# ループの外でlist_urlを1回のみ取得
list_url = list_frame.url  # 382行目

while True:  # ページネーションループ（385行目）
    # 問題：古いlist_frame、古いlist_urlを使い続ける
    rows = list_frame.locator("tr.standard_grid_item").all()  # 400行目

    for basic in submission_basics:
        download_info = self._get_download_link(basic["detail_url"], list_url)  # 457行目
```

**問題点：**
1. `list_frame`はループの外で1回だけ取得され、ページ遷移後も更新されない
2. `list_url`も1ページ目のURLが固定される
3. `_get_download_link`内で`self.page.goto(list_url)`が実行されると、常に1ページ目に戻る

#### 原因2：ページ遷移による参照の破綻

```python
# _get_download_link の処理（586行目）

# 詳細ページから戻る処理
self.page.goto(current_url, wait_until="networkidle")  # current_url = 1ページ目のURL
self._wait_for_navigation()
```

**発生メカニズム：**
```
1. 1ページ目の100件をsubmission_basicsリストに格納 ✅
2. download link取得ループ開始
   ├─ 1人目：詳細ページ → 1ページ目に戻る ✅
   ├─ 2人目：詳細ページ → 1ページ目に戻る ✅
   ├─ ...
   ├─ 14人目：詳細ページ → 1ページ目に戻る ✅
   └─ ❌ ここでフレーム参照が壊れる
3. ループ先頭（400行目）で wait_for_selector実行
4. 古いlist_frame参照により要素が見つからない
5. 30秒タイムアウト → 例外発生
6. except節でall_submissions = []を返す → 0件として終了
```

#### 原因3：ページネーション処理に到達していない

ログを確認すると、以下のログが一切出力されていません：
- "Total pages available"
- "Navigating to page 2"
- "Reached last page"

つまり、**ページネーション処理（481-514行目）に到達する前にエラー発生**しています。

### コード上の問題箇所

#### 問題箇所1: フレーム参照の取得位置

```python
# src/playwright_automation.py: 343-349行目

# ❌ ループの外で1回のみ取得
list_frame = None
for frame in self.page.frames:
    if frame.name == CarewellSelectors.FRAME_LIST:
        list_frame = frame
        break
```

**正しい実装：**
```python
# ✅ ループ内で毎回取得
while True:
    list_frame = None
    for frame in self.page.frames:
        if frame.name == CarewellSelectors.FRAME_LIST:
            list_frame = frame
            break
```

#### 問題箇所2: list_urlの取得位置

```python
# src/playwright_automation.py: 382行目

# ❌ ループの外で1回のみ取得
list_url = list_frame.url

while True:  # ページネーションループ
    # 古いURLを使い続ける
    for basic in submission_basics:
        download_info = self._get_download_link(basic["detail_url"], list_url)
```

**正しい実装：**
```python
while True:
    # ✅ ループ内で毎回取得
    list_url = list_frame.url

    for basic in submission_basics:
        download_info = self._get_download_link(basic["detail_url"], list_url)
```

### 他のメソッドとの比較

`_get_download_link`メソッド（559-564行目）では、**毎回フレームを再取得**する正しい実装がされています：

```python
def _get_download_link(self, detail_url: str, list_url: str) -> dict:
    try:
        # ✅ 毎回フレームを取得
        list_frame = None
        for frame in self.page.frames:
            if frame.name == CarewellSelectors.FRAME_LIST:
                list_frame = frame
                break
```

この実装を`get_submission_list`メソッドにも適用する必要があります。

## 📊 影響範囲

### 現在の影響

1. **提出件数が100件を超えるクラス**: ページネーション処理が必要なケースで、2ページ目以降が処理されない
2. **全7クラス**: 将来的に100件を超える可能性があるため、全クラスが影響を受ける可能性
3. **データの不完全性**: 一部の学生の提出ファイルが取得されない

### 影響を受けないケース

1. **提出件数が100件以下のクラス**: 1ページで完結するため、問題なし
2. **現在のログ**: 13件のケースは正常に動作（08:00:37のログで確認済み）

## 🔧 修正方針

### 修正内容

**修正1: フレーム参照の更新**
- ページネーションループの先頭で、毎回`list_frame`を再取得
- ASP.NET __doPostBackによるページ遷移後も、最新のフレームを参照

**修正2: list_urlの更新**
- ページネーションループの先頭で、毎回`list_url`を更新
- 各ページの正しいURLを保存し、download link取得後に正しいページに戻る

**修正3: ログ追加**
- フレーム参照更新のログを追加（デバッグ用）
- list_url更新のログを追加（トレーサビリティ向上）

### 修正の範囲

- **対象ファイル**: `src/playwright_automation.py`
- **対象メソッド**: `PlaywrightAutomationEngine.get_submission_list`
- **修正行数**: 約10行追加、約5行修正

### 後方互換性

✅ **後方互換性あり**
- 既存の動作（100件以下のケース）に影響なし
- 新たなパラメータ追加なし
- APIインターフェース変更なし

## 📝 検証計画

### テストケース

1. **単一ページ（<100件）**: 既存動作を壊さないことを確認
2. **2ページ（100-200件）**: 2ページ目の処理を確認
3. **3ページ以上（>200件）**: 3ページ以降の処理を確認

### 検証方法

1. **ローカル環境**: テストスクリプトで動作確認
2. **本番環境**: carewell-class01-task01で実際の145件を処理

### 成功基準

- ✅ 145件全て処理完了
- ✅ UI表示件数と処理件数が一致
- ✅ "✓ Count verification passed" のログ出力
- ✅ 2ページ目の処理ログ（"Navigating to page 2"）が出力される

## 📚 参考情報

### 関連コミット

- `7692bc8`: 2ページ目以降のページネーション遷移に3秒待機を追加
  - **注記**: 本番環境での2ページ目以降のテストは未実施
- `ae3cbc4`: Add wait time for table rendering after frame reload

### 関連ドキュメント

- `.kiro/specs/carewell-drive-automation/requirements.md`: 要件2（行135-136）
  - "IF 次のページが存在する THEN システムは次のページ番号を選択してページ遷移し、同じ処理を繰り返さなければならない"
- `.kiro/specs/carewell-drive-automation/design.md`: 設計判断

## 🎯 次のアクション

1. 修正計画ドキュメントの作成
2. コード修正の実装
3. テスト実施
4. デプロイ
5. 本番環境での検証

---

## 📋 更新履歴

### 2025-11-03 09:00 JST - 第1回修正後の検証結果

#### デプロイ状況
- **コミット**: b416e3b
- **デプロイ時刻**: 2025-11-03 08:33:45 JST
- **リビジョン**: carewell-file-collector-00127-gvd

#### 検証結果

**❌ ページネーション処理は依然として動作せず**

検証ログ（2025-11-02 23:41:50 JST）:
```
⚠️ Count mismatch! Extracted 100 submissions but UI shows 140
Successfully extracted 100 submissions from 1 page(s)
WARNING - Pagination navigation failed: Frame was detached, assuming last page
```

#### 判明した真の問題

**第1回修正では不十分：ページネーション判定時点でフレームが再度detachedになる**

```
処理フロー:
1. [385-399行] ページループ先頭でフレーム更新 ✅ 動作OK
2. [468-492行] download link取得（100回のページ遷移）
   → この間にフレームがdetachedになる ❌
3. [494-527行] ページネーション判定処理
   → detachedフレームを使用 ❌
   → Exception: "Frame was detached"
   → except節で「最終ページ」と誤判定
   → ループ終了（2ページ目に進めず）
```

#### 根本原因の詳細

**download link取得処理による副作用：**

`_get_download_link`メソッドは以下を実行：
1. 詳細ページに遷移（`self.page.goto(detail_url)`）
2. download link取得
3. 一覧ページに戻る（`self.page.goto(list_url)`）

これを100回繰り返すと：
- 100回のページ遷移（詳細 → 一覧 → 詳細 → 一覧...）
- フレーム参照が古くなる（ページ遷移のたびにフレームが再生成される）
- ページループ先頭で取得したフレーム参照は、100回後には無効

#### 必要な追加修正

**ページネーション判定の直前にもフレーム参照を更新する**

対象箇所: `src/playwright_automation.py` 494行目付近

```python
# 現在の実装（修正前）
# Second pass: Get download links for each submission on current page
for basic in submission_basics:
    # ... download link処理 (100回のページ遷移)

# Check for pagination and navigate to next page
try:
    pagination_select = list_frame.locator(...)  # ❌ detachedフレームを使用
```

```python
# 必要な実装（修正後）
# Second pass: Get download links for each submission on current page
for basic in submission_basics:
    # ... download link処理 (100回のページ遷移)

# 🆕 ページネーション判定前にフレーム参照を再更新
list_frame = None
for frame in self.page.frames:
    if frame.name == CarewellSelectors.FRAME_LIST:
        list_frame = frame
        break

if not list_frame:
    logger.warning("'list' frame not found for pagination check, using main page")
    list_frame = self.page

# Check for pagination and navigate to next page
try:
    pagination_select = list_frame.locator(...)  # ✅ 最新のフレームを使用
```

#### 次のステップ

1. 追加修正の実装（ページネーション判定前のフレーム更新）
2. ログレベルをDEBUGに変更してデバッグログを有効化（オプション）
3. 再デプロイ
4. 再検証（140件ケースで2ページ目処理を確認）

---

## 📋 第2回修正後の検証結果とタイムアウト問題

### 2025-11-03 19:03 JST - 第2回修正後の検証結果

#### デプロイ状況
- **コミット**: 5587052
- **デプロイ時刻**: 2025-11-03 18:40 JST
- **リビジョン**: carewell-file-collector-00128-gr4

#### 検証結果（carewell-class01-task01、149件）

**実行時刻**: 2025-11-03 10:03:00 UTC (19:03:00 JST)

| 項目 | 結果 |
|------|------|
| ページネーション処理 | ✅ **成功** |
| 1ページ目データ取得 | ✅ 100件取得 |
| 2ページ目データ取得 | ✅ 49件取得 |
| "Total pages available: 2" | ✅ 出力確認 |
| "Processing page 2" | ✅ 出力確認 |
| "Extracted basic info for 49 submissions on page 2" | ✅ 出力確認 |
| ファイルアップロード | ❌ **0件** |
| 処理完了 | ❌ **タイムアウト** |

**エラー内容**:
```
2025-11-03T10:12:00 - ERROR
HTTP Status: 504 (Gateway Timeout)
Latency: 540.000433943s
Request: POST / (Cloud Scheduler)
```

#### 判明した新たな問題

**ページネーション処理は完全に修正されたが、タイムアウト（540秒）により処理が完了しない**

**処理フロー詳細**:
```
10:03:00 - 処理開始（class01-task01、149件）
10:03:28 - Processing page 1
10:03:42 - Extracted basic info for 100 submissions on page 1
10:03:42～10:11:00 - download link取得（1ページ目、約7分18秒）
10:11:00 - ✓ Frame reference refreshed for pagination check
10:11:00 - Total pages available: 2
10:11:00 - Navigating to page 2/2
10:11:00 - Processing page 2
10:11:07 - Extracted basic info for 49 submissions on page 2
10:11:07～10:12:00 - download link取得開始（2ページ目）
10:12:00 - **DEADLINE_EXCEEDED** (540秒タイムアウト)
           → ファイルダウンロード・アップロード処理に到達せず
```

**時間分析**:
- データ取得（149件）: 約14秒
- download link取得（100件）: 約438秒（7分18秒） = 約4.4秒/件
- download link取得開始（2ページ目）: 約53秒経過時点でタイムアウト
- **推定必要時間**: 約11-12分（149件 × 4.4秒 + ファイル処理時間）
- **現在のタイムアウト**: 540秒（9分）

**結論**:
- ✅ ページネーション問題は**完全に解決**
- ❌ タイムアウト設定が不足（540秒では149件を処理できない）

#### 根本原因：タイムアウト不足

**問題**:
- Cloud Scheduler `attemptDeadline`: 540秒
- Cloud Run Functions `timeout`: 540秒（デフォルト、確認必要）
- 149件の処理には約11-15分必要

**必要な対応**:
タイムアウトの延長（540秒 → 900秒）

### 次のステップ

1. **Phase 1: タイムアウト延長**（推奨）
   - Cloud Scheduler attemptDeadline: 540秒 → 900秒
   - Cloud Run timeout: 540秒 → 900秒（必要に応じて）
   - 対象: carewell-class01-task01のみ
   - リスク: 低
   - 効果: 即座に149件処理可能

2. **Phase 2: パフォーマンス最適化**（将来の改善）
   - download link取得処理の効率化
   - 並列処理の導入
   - 対象: 全ジョブ
   - リスク: 中～高
   - 効果: 処理時間短縮

---

**作成者**: Claude Code
**レビュー**: 要レビュー
**ステータス**: Timeout Issue Identified - Phase 1 Required
