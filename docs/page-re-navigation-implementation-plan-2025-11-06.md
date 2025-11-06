# ページ再遷移アプローチ実装計画（修正版）

## 📅 作成日時
2025-11-06 19:00 JST

## 📝 更新履歴
- 2025-11-06 19:00 JST: 初版作成
- 2025-11-06 19:30 JST: Playwright API仕様に基づき修正（`Frame.go_back()` は存在しない）

## 🔗 関連ドキュメント
- [ViewState問題の解決計画](./pagination-viewstate-solution-2025-11-06.md) ← **修正済み**
- [CLASS01タイムアウト分析](./CLASS01_TIMEOUT_ANALYSIS.md)
- [トラブルシューティング方法論](../.serena/memories/timeout_troubleshooting_methodology.md)

---

## 🎯 実装の目的

**問題**: `page.go_back()` 実行後、ASP.NET ViewStateの仕様により必ずページ1に戻ってしまう

**解決策**: ページ2以降の処理では、詳細ページから戻った後に**必要なページへ再遷移**する

## ⚠️ 重要な技術的制約（2025-11-06 19:30 判明）

**Playwright API制約**:
- ❌ `Frame.go_back()` メソッドは**存在しない**
- ✅ `Page.go_back()` メソッドのみ利用可能
- 参照: https://playwright.dev/python/docs/api/class-frame

**ASP.NET ViewState制約**:
- `page.go_back()` は常にページ1に戻る（手動確認済み）
- これは避けられない動作

---

## 📊 過去の失敗から学んだ教訓

### 教訓1: タイムアウトの根本原因パターン

```
タイムアウトエラー発生
  ↓
1. フレーム参照は有効か？
   NO → フレーム再取得を追加（リトライロジック）
   YES → 次へ
  ↓
2. 待機時間は十分か？
   NO → 待機時間を延長（ただし最後の手段）
   YES → 他の要因を調査
```

### 教訓2: フレーム取得のベストプラクティス

**❌ 悪い例**（リトライなし）:
```python
list_frame = None
for frame in self.page.frames:
    if frame.name == "list":
        list_frame = frame
        break
```

**✅ 良い例**（リトライあり - Common Mistake #6で実装済み）:
```python
max_frame_retries = 5 if current_page == 1 else 3

for retry in range(max_frame_retries):
    for frame in self.page.frames:
        if frame.name == "list":
            try:
                _ = frame.url  # フレームが detached していないか確認
                list_frame = frame
                break
            except Exception:
                continue

    if list_frame:
        break

    time.sleep(2)  # リトライ前に待機
```

### 教訓3: 待機時間の設定

| 操作 | 推奨待機時間 | 根拠 |
|------|-------------|------|
| ページ遷移後（`select_option`） | **15秒** | Common Mistake #6で15秒に延長済み |
| フレーム再取得リトライ間隔 | **2秒** | Common Mistake #6で実装済み |
| 詳細ページからの戻り（`go_back`） | **30秒** | Playwright default timeout |

---

## 🔍 現在のコード分析

### 現在の_get_download_link()シグネチャ

```python
def _get_download_link(self, detail_url: str, list_url: str) -> dict:
```

**問題点**:
- `current_page` パラメータがない
- ページ2から戻った後、ページ1にいることを認識できない
- 再遷移ロジックが実装されていない

### 現在のページ遷移処理

**場所**: Lines 856-898

```python
# ページ遷移
pagination_select.select_option(str(next_page))
time.sleep(15)  # ✅ 15秒待機（適切）

# フレーム再取得
list_frame = None
for frame in self.page.frames:
    if frame.name == CarewellSelectors.FRAME_LIST:
        list_frame = frame
        break

# ⚠️ リトライロジックなし
```

---

## 💡 実装設計

### 設計方針

1. **シンプルさ優先**: 複雑なロジックを避け、確実に動作する実装
2. **既存パターンの活用**: Common Mistake #6のリトライロジックを再利用
3. **段階的な実装**: まず動作させ、その後最適化

### 変更箇所

#### 変更1: _get_download_link() シグネチャ

```python
# Before
def _get_download_link(self, detail_url: str, list_url: str) -> dict:

# After
def _get_download_link(
    self,
    detail_url: str,
    list_url: str,
    current_page: int = 1  # デフォルト値でページ1
) -> dict:
```

#### 変更2: go_back() 後の再遷移ロジック

**場所**: _get_download_link() の3箇所
- Line 1072: ダウンロードリンク発見後
- Line 1104: ダウンロードリンク未発見時
- Line 1139: エラーリカバリー時

```python
# Navigate back to list using browser history (page level)
# Note: Always returns to page 1 due to ASP.NET ViewState behavior
self.page.go_back(wait_until="load", timeout=30000)
self._wait_for_navigation()

# Re-navigate to target page if not page 1
if current_page > 1:
    self.logger.info(f"Re-navigating to page {current_page} after go_back()")

    # Get frame reference with retry logic (from Common Mistake #6 pattern)
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

#### 変更3: 呼び出し側の修正

**場所**: Line 753-755

```python
# Before
download_info = self._get_download_link(
    basic["detail_url"], list_url
)

# After
download_info = self._get_download_link(
    basic["detail_url"],
    list_url,
    current_page  # 現在のページ番号を渡す
)
```

---

## 🚨 リスク分析（修正版）

### リスク1: 再遷移のタイムアウト

**懸念**: ページ再遷移時にタイムアウトが発生する可能性

**対策**:
- 既存と同じ15秒待機を使用（実績あり）
- フレーム取得にリトライロジック（max 3回）

**確率**: 低（既存のページ遷移処理と同じロジック）

### リスク2: フレーム参照の喪失

**懸念**: `page.go_back()` 後にフレームが detached される可能性

**対策**:
- Common Mistake #6のパターンを使用
- フレーム取得前に `frame.url` で detached を確認
- 3回のリトライ with 2秒間隔

**確率**: 低（実績のあるパターン）

**重要な修正**: `page.go_back()` を使用（`Frame.go_back()` は存在しない）

### リスク3: 処理時間の増加

**懸念**: ページ2以降の各学生で再遷移が発生 → 処理時間増加

**計算**:
- 再遷移時間: 約15秒（select_option + sleep）
- ページ2の学生数: 99名
- 追加時間: 99 × 15秒 = **約25分**

**対策**:
- Cloud Run timeout = 1500秒（25分）で十分
- ただし、№01は199名 → 合計処理時間に注意

**確率**: 高（確実に発生）

**緩和策**:
- 現状、Cloud Run timeout = 1500秒（25分）
- №01の推定処理時間:
  - ページ1: 100名 × 5秒/名 = 8分
  - ページ2: 99名 × (5秒 + 15秒再遷移) = 33分
  - **合計: 約41分** → ❌ タイムアウト超過！

**⚠️ CRITICAL: Cloud Run timeout 延長が必要**

推奨設定: **3000秒（50分）**

### リスク4: ページネーションコントロールの不在

**懸念**: `go_back()` 後、ページネーションコントロールが見つからない可能性

**対策**:
- `pagination_select.count() > 0` でチェック
- 見つからない場合は warning ログ + 処理継続
- エラーにせず、次の学生へ

**確率**: 低（これまで発生していない）

---

## 📋 実装チェックリスト

### Phase 1: コード実装

- [ ] _get_download_link() シグネチャに `current_page` 追加
- [ ] Line 1072付近: ダウンロード成功時の再遷移ロジック追加
- [ ] Line 1104付近: ダウンロード失敗時の再遷移ロジック追加
- [ ] Line 1139付近: エラーリカバリー時の再遷移ロジック追加
- [ ] Line 753-755: 呼び出し側で `current_page` 渡す
- [ ] 再遷移ロジックに Common Mistake #6 のリトライパターン適用

### Phase 2: Cloud Run timeout 延長

- [ ] `.github/workflows/deploy.yml` Line 107: `--timeout 3000` に変更
- [ ] デプロイ後、手動で設定確認

### Phase 3: コード品質

- [ ] Black フォーマット
- [ ] isort インポート整理

### Phase 4: デプロイ・検証

- [ ] コミット・プッシュ
- [ ] GitHub Actions 成功確認
- [ ] リビジョン作成確認
- [ ] トラフィック100%確認（⚠️ Common Mistake #7）
- [ ] 手動テスト実行

### Phase 5: 本番検証

- [ ] ページ2の学生でダウンロード成功
- [ ] 再遷移ログ確認（"Re-navigating to page X"）
- [ ] 199件全収集確認
- [ ] 処理時間確認（50分以内）

---

## 🔄 ロールバック計画

### ロールバック条件

以下のいずれかが発生した場合:

1. 再遷移でタイムアウトが頻発
2. ページ2の学生がダウンロードできない（問題未解決）
3. 処理時間が50分を超える（Cloud Run timeout）
4. リグレッション（ページ1の処理も失敗）

### ロールバック手順

```bash
# トラフィックを前のリビジョンに戻す
gcloud run services update-traffic carewell-file-collector \
  --region=asia-northeast1 \
  --to-revisions PREVIOUS_REVISION=100

# または、revert コミット
git revert HEAD
git push origin main
```

---

## 📊 期待される結果

### ビフォー（現在 - revision 00196-zll）

```
№01 課題①（199名）
- ページ1: 100名（全員処理可能）
- ページ2: 99名（1人目のみ成功、残り98名失敗）
- 成功: 約101名
- 失敗: 約98名
- 成功率: 約51%
```

### アフター（修正後）

```
№01 課題①（199名）
- ページ1: 100名（全員処理）
- ページ2: 99名（全員処理、各人再遷移15秒）
- 成功: 199名
- 失敗: 0名
- 成功率: 100%
- 処理時間: 約41分（Cloud Run timeout = 50分で対応）
```

---

## 📝 実装者ノート

実装時の注意点:

1. **Common Mistake #6のパターンを厳守**
   - フレーム取得はリトライロジック必須
   - `frame.url` で detached 確認

2. **既存の待機時間を変更しない**
   - ページ遷移: 15秒（実績あり）
   - リトライ間隔: 2秒（実績あり）

3. **ログを充実させる**
   - 再遷移開始・完了のログ
   - リトライ回数のログ
   - エラー時の詳細ログ

4. **Cloud Run timeout を先に延長**
   - コード変更より先に timeout 延長
   - デプロイ後に設定確認（Common Mistake #7）

---

**作成者**: AI Agent (Claude Code)
**最終更新**: 2025-11-06 19:00 JST
