# Common Mistakes to Avoid - Detailed Reference

過去のインシデントから学んだ教訓の詳細記録

---

## 📋 クイックリファレンス

| # | インシデント | 日付 | 影響 | 根本原因 |
|---|------------|------|------|---------|
| 1 | Database Name Mistake | 2025-11-04 | Firestore接続失敗 | `carewell-native` → `(default)` 変更 |
| 2 | Missing task_pattern | 2025-11-04 | メタデータ不正 | パラメータ渡し忘れ |
| 3 | Collection Path Mistake | - | 重複チェック失敗 | 古いパス使用 |
| 4 | Dashboard Schema Mismatch | 2025-11-05 | Dashboard データ不可視 | 古いスキーマ使用 |
| 5 | Iframe Context Error | 2025-11-08 | Page 2+ 100% 失敗 | Frame context 誤り |
| 6 | Playwright Invalid API | 2025-11-05 | 全学生ダウンロード失敗 | 存在しないメソッド |
| 7 | Cloud Run Timeout | 2025-11-06 | 15分でタイムアウト | 2箇所の設定見落とし |
| 8 | Deployed Code Not Running | 2025-11-06 | 修正が反映されない | トラフィックルーティング |
| 9 | ASP.NET Pagination Delay | 2025-11-06 | 42.2% 収集失敗 | URL更新待機なし |
| 10 | Deleting Critical STEP 1 | 2025-11-07 | 50% 収集失敗 | 誤った前提で削除 |
| 11 | Assuming Parameter Names | 2025-11-08 | Page 2+ 0% 成功 | HTML検証なし |
| 12 | Phase 1 go_back Skip | 2025-11-08 | 2人目以降失敗 | 必須処理スキップ |
| 13 | Firestore Index Missing | 2025-11-10 | 25分タイムアウト | IaC不徹底 |
| 14 | Dashboard Class Display | 2025-11-18 | 誤解による作業 | 機能の混同 |
| 15 | Sheets Sync Silent Failure | 2025-01-28 | 5件データ欠落 | リトライ・ステータス追跡なし |

---

## 1. Database Name Mistake (2025-11-04)

**症状**: Firestoreデータベース接続失敗

**根本原因**: `carewell-native` から `(default)` に変更してしまった

**影響**: 全ての Firestore 操作が失敗

### 詳細

```python
# ❌ Wrong
db = firestore.Client(database="(default)")

# ✅ Correct
db = firestore.Client(database="carewell-native")
```

**なぜ起きたか**:
- 設計ドキュメントを確認せずにコード変更
- デフォルト値を使えば簡単だと思い込んだ

**防止策**:
- [ ] `.kiro/specs/firestore-schema-improvement/requirements.md` Line 1-10 を読む
- [ ] `docs/firestore-schema-improvement-implementation.md` Line 529 を確認
- [ ] 全環境で `carewell-native` を使用

**ユーザーからの教訓**:
> "Firestoreのデータベースの元々の設計についてちゃんとドキュメントを確認してから対応してください"

**参照**:
- `.kiro/specs/firestore-schema-improvement/requirements.md`
- `docs/firestore-schema-improvement-implementation.md`

---

## 2. Missing task_pattern Parameter (2025-11-04)

**症状**: Firestore に不正確なメタデータが保存される

**根本原因**: `record_upload()` に `task_pattern` パラメータを渡し忘れ

**影響**: `task_pattern` が `task_id` にフォールバック（不正確）

### 詳細

**Root Cause**: `scripts/create-scheduler-jobs.sh` Line 84 のバグ

```bash
# ❌ Wrong (Line 84)
"task_pattern": "${task_name}"  # task_id と同じ値

# ✅ Correct
"task_pattern": "${task_pattern}"  # 別パラメータ
```

**なぜ起きたか**:
- Cloud Scheduler リクエストから `task_pattern` を渡すのを忘れた
- `record_upload()` のデフォルト値に頼った

**最適な解決策**:
1. 全14個のCloud Scheduler jobsを一括更新するスクリプトを作成
2. 作成スクリプトの根本原因を先に修正
3. `gcloud scheduler jobs update` で適切な JSON body を使用
4. 手作業での1つずつ修正を避ける

**防止策**:
- [ ] `.kiro/specs/firestore-schema-improvement/requirements.md` Line 98-102 確認
- [ ] Cloud Scheduler リクエスト JSON に全パラメータが含まれているか確認
- [ ] `record_upload()` 呼び出し時に全必須パラメータをチェック

**参照**:
- `.kiro/specs/firestore-schema-improvement/requirements.md` Lines 98-102
- `scripts/create-scheduler-jobs.sh`

---

## 3. Collection Path Mistake

**症状**: 重複チェックが機能せず、ファイルが繰り返しダウンロードされる

**根本原因**: 古いコレクションパスを使用

**影響**: ストレージとFirestoreの無駄な使用

### 詳細

```python
# ❌ Wrong - Old path
path = f"{class_name}/{task_id}/documents/{composite_key}"

# ✅ Correct - New path
path = f"submissions/{class_name}/tasks/{task_id}/files/{composite_key}"
```

**なぜ起きたか**:
- スキーマ変更の周知不足
- 古いコードからのコピー&ペースト

**防止策**:
- [ ] `.kiro/specs/firestore-schema-improvement/design.md` Line 51-75 確認
- [ ] 全てのFirestoreパス参照を新スキーマに更新
- [ ] テストで古いパスが使われていないか検証

**参照**:
- `.kiro/specs/firestore-schema-improvement/design.md` Lines 51-75

---

## 4. Dashboard Schema Mismatch (2025-11-05)

**症状**: Dashboard に新しいデータが表示されない

**根本原因**: Dashboard composables が古いスキーマを使用

**影響**: Dashboard が古いデータのみ表示、新データ不可視

### 詳細

**Root Cause**: `dashboard/src/composables/useFirestore.ts` Line 129

```typescript
// ❌ Wrong (dashboard/src/composables/useFirestore.ts:129)
const docRef = doc(db, className, taskId);

// ✅ Correct
const docRef = doc(db, "submissions", className, "tasks", taskId);
```

**なぜ起きたか**:
- Steering Document を確認せずにコーディング
- バックエンドとフロントエンドのスキーマ不一致
- レガシーコードをそのまま使用

**最適な解決策**:
1. コーディング前に Steering Document を読む
2. 全クラス/タスクの検証スクリプトを作成
3. ユーザー確認付き10段階移行を実施
4. 新スキーマ動作確認後に古いデータを削除

**ユーザーからの教訓**:
> "ちゃんとドキュメントをみてから行動してください。Firestoreのデータについて、重複チェックリストの設計、Hostingへの接続設計などどれも事前に確認してから対応すべき重要な仕様内容です。"

**防止策**:
- [ ] Steering Document 読了確認
- [ ] バックエンドとフロントエンドのスキーマ一致確認
- [ ] 段階的移行計画の作成

**参照**:
- `docs/incident-2025-11-05-schema-migration-and-playwright-fix.md`
- `.kiro/steering/firestore-critical-config.md`

---

## 5. Iframe Context and Missing Error Recovery (2025-11-08)

**症状**: Page 2+ の学生が 100% 失敗

**根本原因**:
1. ダウンロードリンクを間違ったコンテキスト（main page vs iframe）で検索
2. エラー後の go_back() 欠如 → 詳細ページに留まる

**影響**: Page 2+ students (100名) が 100% 失敗率

### 3つの根本原因

#### Cause 1: DOWNLOAD_LINK constant undefined

```python
# ❌ Wrong (src/playwright_automation.py)
# Constant not defined in CarewellSelectors class

# ✅ Correct
class CarewellSelectors:
    DOWNLOAD_LINK = 'a[href^="download.aspx"]'
```

#### Cause 2: Frame context error

詳細ページが iframe に読み込まれるが、main page コンテキストで検索

```python
# ❌ Wrong - searching in main page context
download_link = self.page.wait_for_selector(DOWNLOAD_LINK)

# ✅ Correct - refresh frame reference, search in iframe
# Refresh list_frame reference (detail page loaded in iframe)
list_frame = None
for frame in self.page.frames:
    if frame.name == "list":
        list_frame = frame
        break

download_link = list_frame.wait_for_selector(CarewellSelectors.DOWNLOAD_LINK)
```

#### Cause 3: Missing error recovery

```python
# ❌ Wrong - stays on detail page after error
except TimeoutError:
    self.logger.error("Timeout waiting for download link")
    return {"url": None, "filename": None}

# ✅ Correct - go_back() to list page
except TimeoutError:
    self.logger.error("Timeout waiting for download link")
    try:
        self.page.go_back(wait_until="domcontentloaded")
        time.sleep(15)  # Wait for DOM to stabilize
    except Exception as e:
        self.logger.warning(f"Failed to go_back: {e}")
    return {"url": None, "filename": None}
```

### なぜ起きたか
- ダウンロードページがmain pageに読み込まれると仮定
- マルチページフローでのエラーリカバリー欠如
- 実際のHTML構造を DevTools で確認しなかった

### 重要な教訓
- ❌ **避ける**: ダウンロードページがmain page contextに読み込まれると仮定
- ❌ **避ける**: マルチページフローでのエラーリカバリー欠如
- ✅ **使用**: クリックベースナビゲーション後のフレーム更新
- ✅ **使用**: 全エラーハンドラーに go_back()
- ✅ **検証**: 実際のHTML構造（onclick ではなく text_content() を使用）

### 検証チェックリスト (iframeフィックスデプロイ前)
- [ ] クリックナビゲーション後にフレーム参照を更新？
- [ ] 検索コンテキストを self.page から iframe に変更？
- [ ] TimeoutError ハンドラーに go_back() 追加？
- [ ] Exception ハンドラーに go_back() 追加？
- [ ] DevTools で実際のHTML構造を確認？

**参照**:
- `src/playwright_automation.py` Lines 1227-1463

---

## 6. Playwright Invalid API Call (2025-11-05)

**症状**: №01 課題① 全学生のファイルダウンロード失敗

**根本原因**: 存在しないメソッド `locator.wait_for_element_state("visible")` を使用

**影響**: 全学生のダウンロード失敗

### 詳細

**Root Cause**: `src/playwright_automation.py` Line 840

```python
# ❌ Wrong
link.wait_for_element_state("visible", timeout=10000)

# ✅ Correct - Auto-waiting handles this automatically
link.click()  # Waits for clickable state automatically
```

**なぜテストで検出されなかったか**: テストコードパスがこの行を実行しなかった

### 重要な教訓
- Playwright アクション（click, fill など）は組み込みの Auto-waiting を持つ
- 本当に必要な場合のみ明示的な `wait_for(state="visible")` を使用
- 公式ドキュメントで API メソッドの存在を確認
- エラーパスのテストカバレッジを改善

**参照**:
- `docs/incident-2025-11-05-schema-migration-and-playwright-fix.md`
- [Playwright Auto-waiting Documentation](https://playwright.dev/python/docs/actionability)

---

## 7. Cloud Run Timeout Misconfiguration (2025-11-06)

**症状**: №01 課題① が15分でタイムアウト → 504 Gateway Timeout → データ未保存

**根本原因**: Cloud Scheduler deadline を延長したが Cloud Run timeout を忘れた

**影響**: 15分でシャットダウン、Firestore/Drive/Spreadsheet保存操作未到達

### タイムアウト設定が2箇所に存在

```
Cloud Scheduler attemptDeadline: 1500秒 (25分) ✅ Extended
Cloud Run timeoutSeconds:        900秒 (15分)  ❌ Overlooked
                                                ↑ Timeout occurs here first
```

### なぜ起きたか
- №01 は 180 submissions（2ページ処理）→ 15分以上かかる
- Cloud Run が 15分で強制シャットダウン
- Firestore/Drive/Spreadsheet 保存操作に到達せず

### 調査手順（将来のインシデントで重要）

1. Cloud Run ログで HTTP response latency を確認
2. latency = 900s → Cloud Run timeout
3. **常に両方のタイムアウト設定を確認**:

```bash
# Cloud Scheduler
gcloud scheduler jobs describe JOB_NAME --format="value(attemptDeadline)"

# Cloud Run (よく見落とされる!)
gcloud run services describe SERVICE_NAME --format="value(spec.template.spec.timeoutSeconds)"
```

### 解決策

```bash
gcloud run services update carewell-file-collector \
  --timeout=1500 \
  --region=asia-northeast1
```

### タイムアウトチェックリスト
- [ ] Cloud Scheduler `attemptDeadline` を確認
- [ ] Cloud Run `timeoutSeconds` を確認
- [ ] 両方の値が一致（または Cloud Run ≥ Scheduler）
- [ ] 最大処理時間を考慮（2ページ = 20-25分）

### 🔴 CRITICAL Follow-up #1 (same day, 00:50 JST)

**Second Root Cause**: GitHub Actions workflow が timeout=900 をハードコード

手動で timeout を 1500s に修正後、**GitHub Actions が次のデプロイで 900s に上書き**:

```text
00:02 JST - Manual fix: timeout=1500 (revision 00173-5b6) ✅
00:21 JST - GitHub Actions deploy: timeout=900 (revision 00174-dnf) ❌ Overwrote!
00:30 JST - №01 execution: 504 timeout again (only 7/180 files saved)
```

**Root Cause**: `.github/workflows/deploy.yml` Line 107

```yaml
# ❌ Wrong
--timeout 900 \

# ✅ Correct
--timeout 1500 \
```

### 重要な教訓
- ❌ 手動の Cloud Run 設定変更は永続的ではない
- ✅ **常に CI/CD ワークフローファイルも更新** (`.github/workflows/deploy.yml`)
- ✅ 次のデプロイで手動変更が上書きされないか確認
- ✅ インフラ設定はバージョン管理に含めるべき（IaC）
- [ ] **チェックリスト追加**: Cloud Run 設定変更時は GitHub Actions ワークフローも更新

### 🔴 CRITICAL Follow-up #2 (same day, 01:00-01:37 JST)

**Third Root Cause**: Frame retrieval timing issue (大規模データセット)

Cloud Run timeout を 1500s に修正後も、**01:00 JST 実行が 1499秒でタイムアウト**

**症状**:
- 「全て」タブクリック: SUCCESS ✅
- Frame retrieval: FAILED ❌
- `TimeoutError: Timeout 60000ms exceeded` が 5分ごとに繰り返し
- 25分間ループして Cloud Run timeout

**Root Cause**: `FRAME_LOAD_WAIT = 3000ms`（3秒）が №01 の 180+ submissions には不十分

```text
「全て」tab clicked successfully (16:01:36) ✅
  ↓
Wait 3 seconds (FRAME_LOAD_WAIT)
  ↓
Try to get frame → FAILED (frame still reloading)
  ↓
wait_for_selector → 60s timeout ❌
  ↓
Retry... (repeated for 25 minutes)
```

**ユーザーの診断**:
> "ドキュメントのトラブルシューティングをみて、多分またフレームがちゃんと探せてないだけだと思うから"

→ **100% CORRECT**. 同様の問題が `CLASS01_TIMEOUT_ANALYSIS.md` に記録されていた

**Solution** (commit `17d63d8`):

1. Frame wait time を増やす (Line 70):

```python
FRAME_LOAD_WAIT = 15000  # 15s (was 3s)
```

2. Frame retrieval retry logic 追加 (Lines 358-385, 402-430):

```python
max_frame_retries = 5 if current_page == 1 else 3

for retry in range(max_frame_retries):
    for frame in self.page.frames:
        if frame.name == "list":
            try:
                _ = frame.url  # Verify frame not detached
                list_frame = frame
                break
            except Exception:
                continue

    if list_frame:
        break

    time.sleep(2)  # Wait before retry
```

### 重要な教訓
- ❌ **Cloud Run timeout 延長だけでは Playwright timeout は修正されない**
- ✅ **コード内の実際のタイムアウト場所を特定して修正する必要がある**
- ✅ **過去のトラブルシューティング文書を参照**（`CLASS01_TIMEOUT_ANALYSIS.md`）
- ✅ **大規模データセット（180+ items）はより長い待機時間が必要**

### Frame Issue チェックリスト
- [ ] `FRAME_LOAD_WAIT` 十分？（大規模データセットは15秒推奨）
- [ ] Frame retrieval に retry logic？
- [ ] 使用前に frame が detached されていないか確認？
- [ ] ログで「全て」タブクリック成功を表示？
- [ ] ログで frame retrieval 成功/失敗を表示？

**参照**:
- `docs/incident-2025-11-06-cloud-run-timeout.md`
- `docs/CLASS01_TIMEOUT_ANALYSIS.md`

---

## 8. 🚨 Deployed Code Not Running (2025-11-06 08:00 JST)

**症状**: GitHub Actions で新コードデプロイしたが、古いコードが実行され続ける

**根本原因**: トラフィックが依然として古い revision にルーティングされている

**影響**: 修正が適用されない → ユーザー混乱 → デバッグ時間の無駄

**ユーザーフィードバック**:
> "今回のような新しくしたが、実行は実は古いままだった。という失敗は以前から有りました。"

**これは繰り返し発生するパターンであり、防止が必須**

### 症状の詳細
- 修正で追加した INFO レベルログが表示されない
- 古いエラーメッセージ（修正前）が出続ける
- ユーザー報告: "8:06時点で新たに取得が出来てる状況が無いので、不安です"

### 根本原因

1. **Traffic still routed to old revision**
```bash
# Current traffic
carewell-file-collector-00180-j9h  100%  # Old code

# Latest revision
carewell-file-collector-00183-nb9  Retired  # New code but inactive
```

2. **Same Docker image digest** (caching issue)
```bash
# 00183-nb9 and 00182-78r share same image
sha256:ef8d7ff49b0d89feddd7d451222208adac84db51f7a576fc8a32511c5cd2f48d
```

3. **GitHub Actions deployed but new revision not activated**

### 調査手順（デプロイ後必須）

**Step 1: ログで新コードトレースを確認**
```bash
# 修正で追加されたログが表示されるか確認
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector" \
  --limit 50 --format json | \
  jq -r '.[] | select(.textPayload) | .textPayload' | \
  grep "YOUR_NEW_LOG_MESSAGE"  # 修正で追加したログ

# 見つからない → 古いコードが実行中
```

**Step 2: トラフィックルーティングを確認**
```bash
gcloud run services describe carewell-file-collector \
  --region=asia-northeast1 \
  --format="value(status.traffic[0].revisionName,status.traffic[0].percent)"

# 期待値: 最新の revision name
# 古い revision → 問題！
```

**Step 3: Image digest を確認**
```bash
gcloud run revisions list \
  --service=carewell-file-collector \
  --region=asia-northeast1 \
  --limit 5 \
  --format="table(metadata.name,status.conditions[0].status,status.conditions[0].reason,status.imageDigest)" \
  --sort-by="~metadata.creationTimestamp"

# 同じ digest が複数の revision → Docker cache 問題
```

### 解決策

**Option 1: 手動でトラフィックをルーティング** (有効な revision が存在する場合)
```bash
gcloud run services update-traffic carewell-file-collector \
  --region=asia-northeast1 \
  --to-revisions LATEST_REVISION=100
```

**Option 2: GitHub Actions を再実行** (Docker cache をバイパス)
```bash
gh workflow run deploy.yml
gh run watch RUN_ID
```

**Option 3: Docker build に --no-cache を追加**
```yaml
# .github/workflows/deploy.yml
docker build --no-cache -t ${IMAGE_TAG} .
```

### デプロイ後検証チェックリスト（必須）
- [ ] 新しい revision が作成された？ (`gcloud run revisions list --limit 1`)
- [ ] トラフィックが 100% 新 revision にルーティング？ (`status.traffic[0]`)
- [ ] 新コードログが表示される？（新ログメッセージを grep）
- [ ] Image digest が前の revision と異なる？

### 重要な教訓
- ❌ **"GitHub Actions 成功 ≠ 新コード実行中"**
- ✅ **常に3点を確認**: revision, traffic, logs
- ✅ **ユーザーの「不安」は重要なシグナル** - すぐに調査
- ✅ **重複の image digest をチェック** - 同じ digest = 同じコード

### 恒久的な解決策
1. デプロイ後検証スクリプトを作成（3点チェックを自動化）
2. GitHub Actions ワークフローに検証ステップを追加
3. Docker build に --no-cache を検討（cache 問題を回避）

**参照**:
- `.serena/memories/incident_response_lessons.md` Line 46-177

---

## 9. ASP.NET Pagination URL Update Delay (2025-11-06 14:45 JST)

**症状**: №01 課題① - 84/199 files (42.2%) 未収集（Page 2+ students）

**根本原因**: ページネーション後に URL が変更されたか検証せずに `frame.url` プロパティを使用

**影響**: Page 2+ の学生リンクが Page 1 の URL で検索され、見つからず失敗

### 詳細

**Root Cause**: ASP.NET `__doPostBack` ページネーション遅延

```python
# ❌ Wrong (src/playwright_automation.py:892)
list_url = list_frame.url  # Page 2 遷移後も古い Page 1 URL を取得

# Result: Page 2 student links searched using Page 1 URL → Not found → Download failed
```

**なぜ起きたか**:
- ASP.NET `__doPostBack` は非同期 - DOM 更新 ≠ URL 更新
- Playwright `frame.url` は同期プロパティ - 更新の auto-wait なし
- 固定 `sleep(15)` は時間を待つが URL 変更を検証しない

### Solution (commit `9330a23`)

```python
# ✅ Correct - Explicit URL change verification
old_url = list_url
url_updated = False
for retry in range(10):
    current_frame_url = list_frame.url
    if current_frame_url != old_url:
        list_url = current_frame_url
        url_updated = True
        self.logger.info(f"✓ URL changed after {retry * 2}s: {list_url}")
        break
    time.sleep(2)

if not url_updated:
    self.logger.warning(
        f"URL did not change after 20s, using current frame URL: {list_frame.url}"
    )
    list_url = list_frame.url
```

### 主な特徴
- **明示的な検証**: 古い URL vs 新しい URL を比較
- **適応的な待機**: 最大 20秒、変更検出時に早期終了
- **詳細なログ**: デバッグ用にタイミングを記録（`✓ URL changed after Xs`）
- **フェイルセーフ**: タイムアウト時は現在の frame URL を使用

### 重要な教訓
- ❌ **避ける**: 状態変更後のプロパティアクセスを盲目的に信頼
- ❌ **避ける**: 状態検証なしの固定 `sleep()`
- ✅ **使用**: ポーリング + 明示的比較 + タイムアウト
- ✅ **使用**: タイミング分析用の詳細ログ

### Playwright の制限
- Auto-waiting はアクション（`click`, `fill`）で機能
- プロパティアクセス（`frame.url`）には auto-waiting なし
- → 常にプロパティ更新を明示的に検証

### ASP.NET Webforms 固有
- `__doPostBack` 完了 ≠ DOM/URL 更新完了
- 常に状態変更をポーリング、タイミングを仮定しない

### 検証チェックリスト（Playwright プロパティアクセス用）
- [ ] 状態変更前後でプロパティ値を比較？
- [ ] タイムアウト付きポーリングロジック実装？
- [ ] 変更検出時に早期終了？（固定 sleep だけでなく）
- [ ] ログで状態変更のタイミングを表示？
- [ ] タイムアウトケース用のフェイルセーフ？

**参照**:
- `docs/incident-2025-11-06-pagination-url-update-delay.md`

---

## 10. Phase B: Deleting Critical STEP 1 Based on False Premise (2025-11-07)

**症状**: Page 2+ students (100 out of 200 reports) 収集失敗

**根本原因**:
- commit 3bd3399 が正しいと仮定して STEP 1（118行）を削除
- "ページネーション後に URL が変更される"という誤った前提で無効な URL チェックコード（Lines 988-1019）を追加

### 詳細

**Root Cause**: commit 672afc9 がページネーション後に `list_frame.url` が変更されると仮定したが、常に元の `list_url` と等しい

```python
# Lines 988-1019 (Phase B ineffective code - DELETED in fix)
if list_frame.url != list_url:  # ❌ Always FALSE
    # This condition NEVER executes
    # URL remains "carewel.dk-lab.jp" regardless of page number
```

**証拠**:
- `docs/pagination-viewstate-solution-2025-11-06.md` Line 251: "このチェックは常にFalse"
- `docs/playwright-page-navigation-flow.md` Lines 182-185: Phase B が違反した公式仕様

**なぜ起きたか**:
- 現在のドキュメントを確認せずに git history を誤解釈
- 前提をテストせずに新しい commit（672afc9）が正しいと仮定
- STEP 1（詳細リンク検索前に Page 2+ に移動する唯一の方法）を削除
- 誤った仮定に基づいて 43行の URL ポーリングコードを追加

**影響チェーン**:
```
STEP 1 deleted → No navigation to Page 2 before detail link search
→ Page 2 students processed on Page 1's DOM
→ Detail links not found (students are on different page)
→ 100 out of 200 reports failed to collect
```

### Solution (commit `00a87be`)

**Part 1: 無効なコードを削除**
```python
# Deleted Lines 988-1019 (32 lines)
# - frame.url != list_url check (always False)
# - Unnecessary frame.goto() logic
# - URL polling code based on false premise
```

**Part 2: ページネーション制御で STEP 1 を復元**
```python
# Added 48 lines (Lines 986-1032)
# STEP 1: Navigate to correct page BEFORE detail link search
if current_page > 1:
    pagination_select = list_frame.locator("#ctl00_masterMain_ddlPage")
    if pagination_select.count() > 0:
        pagination_select.select_option(str(current_page))
        time.sleep(15)  # Page transition wait

        # Frame refresh with retry logic
        for retry in range(3):
            # ... frame refresh code ...
```

### 重要な教訓
- ❌ **"新しい commit ≠ 正しいアプローチ"** - 常に仕様を確認
- ❌ **なぜそのコードが存在するか理解せずに削除しない**
- ✅ **アーキテクチャ変更前に仕様ドキュメントを読む**
- ✅ **重要な仮定をテスト**（例: "URL は実際に変更されるか？"）
- ✅ **ドキュメント駆動検証**: `docs/playwright-page-navigation-flow.md` と実装を比較

### 検証チェックリスト（重要なコード削除前）
- [ ] このコードの目的を説明する仕様ドキュメントを読んだ？
- [ ] なぜコードが追加されたか理解した？（git history とドキュメントを確認）
- [ ] 新しい commits の仮定をテストした？（例: URL 変更動作）
- [ ] このコードを削除した場合の代替アプローチを特定？
- [ ] マルチページ処理（Page 2+ シナリオ）への影響を考慮？

**ユーザーの引用**:
> "ちゃんとドキュメントをみてから行動してください"（行動前に適切にドキュメントを確認してください）

**参照**:
- `docs/playwright-page-navigation-flow.md` Lines 182-185（公式仕様）
- `docs/pagination-viewstate-solution-2025-11-06.md` Line 251（URL が変更されない証拠）
- `docs/incident-2025-11-06-pagination-url-update-delay.md`（関連する ASP.NET 動作）

---

## 11. Assuming Parameter Names Without Verification (2025-11-08)

**症状**: Page 2+ students が 0% 成功率で失敗（№01 課題①）

**根本原因**: 実際の HTML を確認せずに詳細リンクに `Sid` パラメータが存在すると仮定

### 詳細

**Root Cause**: commit `054614c` が本番 HTML を検証せずに `Sid` パラメータ抽出を導入

```python
# ❌ Wrong (Line 1199 - Assumed parameter name)
sid_match = re.search(r"Sid=(\d+)", detail_url)  # Sid doesn't exist!

# ✅ Correct (Verified from actual HTML)
log_id_match = re.search(r"log_id=(\d+)", detail_url)
```

**Production HTML からの証拠**（2025-11-08 検証済み）:

```html
<!-- Page 1 student -->
<a href="report.aspx?log_id=7451&unit_id=684&course_id=41&filter=all">
  川久保　晃 <N9903754>
</a>

<!-- Page 2 student -->
<a href="report.aspx?log_id=8577&unit_id=684&course_id=41&filter=all">
  杉山　千晶 <N9903321>
</a>
```
→ **Sid パラメータは存在しない。log_id のみ存在。**

**なぜ起きたか**:
- 完全一致（`a[href="{detail_url}"]`）から部分一致への改善を試みた
- 柔軟性のためにパラメータベースの検索に変更
- **実際の HTML を確認せずにパラメータ名 `Sid` を推測**
- 他の ASP.NET システムでの経験に基づいて仮定した可能性
- ブラウザ DevTools でパラメータ名を検証しなかった

**影響チェーン**:
```
Sid extraction fails → return {"url": None, "filename": None}
→ Student download fails → Retry 3 times → Still fails
→ Page 2+ students 0% success rate
```

### Solution (commit `ae5d169`)
- 全ての `Sid` 参照を `log_id` に置換（5箇所、Lines 1196-1217）
- regex が実際の URL パラメータに一致することを確認: `r"log_id=(\d+)"`

### 重要な教訓
- ❌ **検証なしにパラメータ/フィールド名を推測しない**
- ❌ 他のシステムからの仮定に頼らない
- ✅ **常にブラウザ DevTools で実際の本番 HTML を検査**
- ✅ 開発中に実際の URL 値をログに記録してパラメータを検証
- ✅ 抽出されたパラメータ値を表示する診断ログを追加

### 検証チェックリスト（URL/パラメータ解析実装前）
- [ ] ブラウザ DevTools を開いて実際の HTML を検査した？
- [ ] 本番環境でパラメータ名を検証した？
- [ ] コードコメントに実際の URL 例をログに記録した？
- [ ] 抽出失敗時に完全な URL を表示するエラーログを追加した？
- [ ] 全ページからの実データでテストした？（Page 1, Page 2 など）

### 防止策

```python
# ✅ Good practice: Log actual URL for verification
self.logger.debug(f"Extracting from detail_url: {detail_url}")
log_id_match = re.search(r"log_id=(\d+)", detail_url)
if not log_id_match:
    self.logger.error(
        f"Failed to extract log_id from detail_url: {detail_url}"
        # ↑ Full URL logged - easy to spot parameter name issues
    )
```

**参照**:
- Cloud Run logs 2025-11-08 00:10-00:12 JST
- Student: 杉山 千晶 (N9903321, Page 2)
- Commit 054614c（Sid 導入 - 誤った仮定）
- Commit ae5d169（log_id で修正 - HTML から検証）

---

## 12. Phase 1最適化の設計ミス - 必須処理のスキップ禁止 (2025-11-08)

**症状**: 2人目以降の学生全員が処理失敗（1人目のみ成功）

**根本原因**: go_back() をスキップして詳細ページに留まる → 次の学生処理時に詳細ページから抜け出せない

**影響**: 2人目以降の学生全員が処理失敗

### 詳細

**Root Cause**: コミット bbd61ab（Phase 1最適化）

```python
# ❌ Wrong (Lines 1272-1292) - Page 2+でgo_back()スキップ
if current_page > 1:
    self.logger.info(f"[PHASE 1] Skipping go_back() for Page {current_page}")
    # → 詳細ページに留まる
    # → 次の学生処理時にpagination control見つからず失敗
else:
    self.page.go_back(wait_until="load", timeout=30000)

# ✅ Correct - 全ページでgo_back()を30秒で実行
try:
    self.page.go_back(wait_until="load", timeout=30000)
except Exception as e:
    self.logger.warning(f"[PHASE 1] go_back timeout: {e}")
self._wait_for_navigation()
```

**なぜ起きたか**:
- タイムアウト回避を優先しすぎて必須処理（go_back）をスキップ
- 詳細ページからリストページに戻る手段が go_back() しかないことを見落とし
- STEP 2 の pagination control 検索が「リストページに戻った後」を前提としていることを見落とし
- `docs/playwright-page-navigation-flow.md` Lines 182-185 を確認しなかった

**影響チェーン**:
```
学生A: 詳細ページ表示 → go_back()スキップ → 詳細ページ留まる
学生B: STEP 1開始 → 詳細ページのまま → pagination control無し → 失敗
学生C: STEP 1開始 → 詳細ページのまま → pagination control無し → 失敗
...（以降全員失敗）
```

### Solution (commit `6e39cce`)
- 3箇所の go_back() 処理を統一（Success/TimeoutError/Exception Path）
- 全ページで 30秒タイムアウト go_back() を実行（スキップしない）
- 処理時間: 200レポート = 600分 → 100分（500分削減、83%削減）

### 重要な教訓
- ❌ タイムアウト回避のために必須処理をスキップしてはいけない
- ❌ 条件分岐で処理をスキップする前に、スキップ後のフローを検証する
- ❌ ドキュメント確認なしにナビゲーション処理を変更してはいけない
- ✅ タイムアウト短縮で最適化する（スキップではなく短縮）
- ✅ 戻り処理（go_back）は次の処理の前提条件
- ✅ 1人目成功・2人目以降失敗のパターンは処理間の状態引き継ぎミス
- ✅ Common Mistake #10（Phase B）と同じ失敗パターン

### 検証チェックリスト（ナビゲーションスキップ前）
- [ ] `docs/playwright-page-navigation-flow.md` Lines 182-185 を確認したか？
- [ ] STEP 2 の前提条件（リストページに戻る）を理解したか？
- [ ] スキップ後、次の処理の前提条件（ページ状態）は満たされるか？
- [ ] 詳細ページからリストページに戻る代替手段があるか？
- [ ] 1人目成功・2人目失敗のパターンになっていないか？
- [ ] ログで「Frame URL」が詳細ページのまま留まっていないか？
- [ ] STEP 1 の「pagination control not found」が連続発生していないか？

### 🔍 診断手順（1人目成功・2人目以降失敗パターン）

1. **Frame URL確認**:
```bash
gcloud logging read "textPayload=~'Frame URL'" --limit 20 | grep "report.aspx?log_id"
```
→ 詳細ページ（`report.aspx?log_id=XXX`）に留まっている場合、go_back() がスキップされている

2. **go_back()実行確認**:
```bash
gcloud logging read "textPayload=~'Skipping go_back'" --limit 10
```
→ スキップログが出ている場合、条件分岐を確認

3. **STEP 1 FAILEDパターン確認**:
```bash
gcloud logging read "textPayload=~'STEP 1 FAILED'" --limit 20
```
→ 連続発生している場合、pagination control が見つからない（詳細ページにいる証拠）

**詳細診断**: `docs/troubleshooting.md`（Mermaid診断フローチャート参照）

### ✅ 最適化ベストプラクティス

| アプローチ | 処理時間削減 | 成功率 | リスク | 推奨度 |
|----------|------------|-------|-------|--------|
| タイムアウト短縮（30秒） | 83% | 100% | 低 | ⭐⭐⭐⭐⭐ |
| 必須処理スキップ | 理論上91% | 0.5% | **致命的** | ❌ **禁止** |
| 並列処理 | 最大50% | 不明 | 中 | △ 将来検討 |
| Frame待機短縮 | 10-20% | 80-90% | 中 | △ 慎重に |

**推奨アプローチ**: タイムアウト短縮（180秒 → 30秒）

**禁止アプローチ**: 必須処理（go_back）のスキップ

### 📊 参考処理時間

| 学生数 | 元の実装（180秒/件） | 最適化後（30秒/件） | 削減時間 | 削減率 |
|-------|-------------------|------------------|---------|--------|
| 100名 | 300分 (5時間) | 50分 | 250分 | 83% |
| 158名 | 474分 (7.9時間) | 79分 | 395分 | 83% |
| 200名 | 600分 (10時間) | 100分 (1.7時間) | 500分 | 83% |

Cloud Run 25分タイムアウト制限により、元の実装では完了不可 → 最適化必須

### 🎯 デプロイ後の検証コマンド

```bash
# 1. STEP 1失敗確認（0件が期待値）
gcloud logging read "textPayload=~'\[STEP 1 FAILED\]'" --limit 10

# 2. Phase 1完了統計
gcloud logging read "textPayload=~'Download links obtained'" --limit 5

# 3. Phase 2開始確認
gcloud logging read "textPayload=~'Downloading:'" --limit 20

# 4. 2人目の学生が成功しているか確認
gcloud logging read "textPayload=~'Added:.*-'" --limit 5
```

**期待される結果**:
- STEP 1 FAILED: 0件
- Download links obtained: 49/200など（重複除外後の新規ファイル数）
- Downloading: 複数件（Phase 2実行中）
- Added: 全員がファイル名付き（"None"が無い）

**参照**:
- **docs/incident-2025-11-08-phase1-go-back-skip-bug.md** - 詳細なインシデントレポート
- `docs/playwright-page-navigation-flow.md` Lines 182-185（STEP 2 設計）
- `docs/pagination-viewstate-solution-2025-11-06.md` Lines 136-139, 170-171（ASP.NET 動作）
- CLAUDE.md Lines 269-309（Common Mistake #10 - 類似パターン）
- Cloud Run logs 2025-11-08 23:25-23:51 JST
- Revision: carewell-file-collector-00232-wj4（問題発生）, 00234-q22（修正後）
- Commit bbd61ab（バグ導入 - go_back skip）
- Commit 6e39cce（修正 - 30s timeout で go_back 統一）

---

## Incident #13: Firestore Index Missing After Phase 2 Deployment (2025-11-10)

### 📅 発生日時
2025-11-10 13:00 JST

### 🚨 症状
- Cloud Scheduler が25分でタイムアウト（DEADLINE_EXCEEDED）
- ユーザー確認: 目視で取得対象は0件（すべて重複のはず）
- 実際: 延々とファイルをダウンロードし続けている（無限ループ）
- 重複チェックログ「Performing early duplicate check for 100 submissions」は出るが、「Duplicate detected」が一切出ない

### 🔍 根本原因

**Backend用のFirestoreインデックスが未定義**

1. **不完全な `dashboard/firestore.indexes.json`**:
   - 2025-11-04 Dashboard初期セットアップ時、`indexes: []` で作成
   - Backend用の複合インデックスが定義されていない
   - Backend用インデックスはFirestoreコンソールで手動作成（ドキュメント化されず）

2. **Phase 2デプロイがトリガー**:
   - 2025-11-10 13:00:42 JST、コミット `1ff3401` で `firestore.indexes.json` 更新
   - GitHub Actions が `firebase deploy --only firestore` 自動実行
   - `firebase deploy --only firestore` は**宣言的**なため、定義されていないインデックスを削除
   - 手動作成したBackend用インデックスが削除された

3. **重複チェッククエリが失敗**:
   - `src/firestore_service.py:136-139` のクエリ:
     ```python
     docs = (
         collection_ref.where("student_id", "==", student_id)
         .where("submit_date", "==", submit_date)  # 複合インデックス必須
         .limit(1)
         .stream()
     )
     ```
   - インデックスなし → 空の結果を返す
   - すべてのファイルを「新規」と誤判定
   - Page 1の100件を無限ダウンロード
   - 25分でタイムアウト

### ✅ 解決策

**`dashboard/firestore.indexes.json` に Backend用複合インデックスを追加**:

```json
{
  "indexes": [
    {
      "collectionGroup": "files",
      "queryScope": "COLLECTION_GROUP",
      "fields": [
        {
          "fieldPath": "student_id",
          "order": "ASCENDING"
        },
        {
          "fieldPath": "submit_date",
          "order": "ASCENDING"
        }
      ]
    }
  ],
  "fieldOverrides": [...]
}
```

**デプロイ**:

```bash
cd dashboard
firebase deploy --only firestore:indexes --project carewell-native
```

インデックス作成完了まで数分かかる。完了後、次回のCloud Scheduler実行で正常動作確認。

### 🎯 教訓

#### 設計上の問題

1. **Infrastructure as Code (IaC) の不徹底**:
   - 手動作成したインデックスを `firestore.indexes.json` に記録していなかった
   - 手動インデックスはドキュメント化されず、削除された際に気づけなかった

2. **マルチサービスでのリソース共有**:
   - Dashboard と Backend が同じ Firestore を共有
   - インデックス定義は Dashboard側のみ（`dashboard/firestore.indexes.json`）
   - Backend用のインデックスが考慮されていなかった

3. **宣言的デプロイの副作用**:
   - `firebase deploy --only firestore` は定義されたインデックスのみを保持
   - 定義されていないインデックスは削除される
   - この仕様を理解していなかった

#### チェックリスト（今後の予防策）

**インデックス追加時**:
- [ ] Backend と Dashboard の**全て**のクエリパターンを確認
- [ ] 複合クエリ（2つ以上の `==` 演算子）には複合インデックスが必要
- [ ] `dashboard/firestore.indexes.json` にすべてのインデックスを定義
- [ ] 手動作成したインデックスは**即座**に `firestore.indexes.json` に追記

**Firestore デプロイ時**:
- [ ] `firebase deploy --only firestore` は既存インデックスを削除する可能性を認識
- [ ] デプロイ前に `firestore.indexes.json` の内容を確認
- [ ] デプロイ後、Firestoreコンソールでインデックス一覧を確認
- [ ] Cloud Run ログで「index required」エラーを監視

**マルチサービス環境**:
- [ ] Firestore を共有するサービスすべてのクエリパターンを把握
- [ ] 各サービスのインデックス要件を統合した `firestore.indexes.json` を維持
- [ ] インデックス変更時は**全サービス**への影響を検証

### 📊 影響分析

**タイムライン**:
- 2025-11-10 12:30 JST: ✅ 最後の正常実行
- 2025-11-10 13:00 JST: ❌ タイムアウト開始
- 2025-11-10 13:30 JST: ❌ タイムアウト継続（30分ごとに再発）

**データへの影響**:
- ファイルの重複アップロードは発生していない（タイムアウトのため）
- Firestoreデータの整合性は維持
- 収集遅延が発生（約12時間の遅延）

**コスト影響**:
- Cloud Run 実行時間延長（25分 × 複数回実行）
- Firestore読み取り増加（重複チェック失敗 → 再ダウンロード試行）
- 推定追加コスト: $1-2（軽微）

### 🔗 関連ドキュメント
- Backend重複チェック実装: `src/firestore_service.py:105-157`
- Backend呼び出し元: `src/playwright_automation.py:677-710`
- Firestore設定: `.kiro/steering/firestore-critical-config.md`
- 設計仕様: `.kiro/specs/firestore-schema-improvement/design.md` Lines 351-430
- Firestore公式: https://firebase.google.com/docs/firestore/query-data/indexing

### 🚨 緊急度評価
- **重大度**: 🔴 High（本番システムが25分でタイムアウト）
- **影響範囲**: 🔴 全クラス・全課題（重複チェック完全停止）
- **修正難易度**: 🟢 Low（JSON追加のみ、5分で完了）
- **再発リスク**: 🟡 Medium（IaC徹底で予防可能）

### 過去のインシデントとの関連
- Incident #1, #4, #10: ドキュメント確認なしのコード変更（パターン類似）
- Incident #7: 複数箇所の設定見落とし（GitHub Actions + Cloud Run）
- 今回: Infrastructure as Code の不徹底（手動設定 + 自動デプロイの齟齬）

---

## Incident #15: Google Sheets Sync Silent Failure (2025-01-28)

### 📅 発見日時
2025-01-28

### 🚨 症状
- Firestoreにレコードが存在するが、対応するスプレッドシートにエントリがない
- 5件のレコードが複数クラス（No1, No4, No5, No8, No9）で欠落
- ユーザーがDashboardで確認したデータがスプレッドシートに反映されていない

### 🔍 根本原因

**Google Sheets API エラー時のサイレント失敗**

1. **エラーハンドリングの不備**:
   - `sheets_service.append_record()` が失敗時に `False` を返す
   - 呼び出し元（`main.py`）が戻り値をチェックしていない
   - Firestore書き込みは成功 → Sheets書き込み失敗 → 不整合発生

2. **リトライなし**:
   - Google Sheets API の一時的エラー（429, 503等）に対するリトライがない
   - 1回の失敗で永久にデータ欠落

3. **ステータス追跡なし**:
   - Firestore側でSheets同期状態を追跡していない
   - 失敗したレコードを後から特定する手段がなかった

```python
# ❌ Before (サイレント失敗)
sheets_service.append_record(...)  # 戻り値チェックなし
# → 失敗しても処理続行、エラー記録なし

# ✅ After (リトライ + ステータス追跡)
sheets_success = append_record_with_retry(sheets_service, ...)
if sheets_success:
    firestore_service.update_sheets_sync_status(..., status="success")
else:
    firestore_service.update_sheets_sync_status(..., status="failed",
        error_message="All retry attempts failed")
```

### ✅ 解決策

**Phase 1: リトライ + ステータス追跡（実装済み）**

1. **`src/sheets_retry.py`** - 指数バックオフリトライ
   - 最大3回リトライ（1秒, 2秒, 4秒間隔）
   - 一時的APIエラーに対する耐性向上

2. **`sheets_sync_status` フィールド追加**
   - `pending`: 初期状態
   - `success`: Sheets書き込み成功
   - `failed`: 全リトライ失敗

3. **整合性チェックスクリプト**
   - `scripts/check_all_spreadsheets_consistency.py`
   - 全8クラスのFirestore-Spreadsheet不整合を検出

### 🎯 教訓

#### 設計上の問題

1. **サイレント失敗の危険性**:
   - 外部API呼び出しの戻り値は必ずチェック
   - 失敗時は明示的にログ + ステータス更新

2. **リトライの重要性**:
   - 外部APIは一時的エラーが発生しうる
   - 指数バックオフリトライで信頼性向上

3. **ステータス追跡の重要性**:
   - 非同期処理の結果を追跡可能にする
   - 失敗したレコードを後から特定できるようにする

#### チェックリスト（外部API連携実装時）

- [ ] API呼び出しの戻り値/例外をチェックしているか？
- [ ] 一時的エラーに対するリトライロジックがあるか？
- [ ] 処理結果をDB等に記録しているか？
- [ ] 失敗時の通知/アラートがあるか？
- [ ] 定期的な整合性チェックの仕組みがあるか？

### 📊 影響分析

**発見された不整合**:
- No1 課題①: 1件
- No4 課題①: 1件
- No5 課題②: 1件
- No8 課題②: 1件
- No9 課題①: 1件
- **合計: 5件**（全8クラス × 2課題 = 16スプレッドシート中）

**データへの影響**:
- Firestoreデータは正常（Dashboard表示は正常）
- スプレッドシートのみ欠落（講師のExcel作業に影響）
- 手動で5件を修正済み

### 🔗 関連ファイル
- `src/sheets_retry.py` - リトライロジック
- `src/firestore_service.py` - `sheets_sync_status` フィールド追加
- `src/main.py` - リトライ使用 + ステータス更新
- `scripts/check_all_spreadsheets_consistency.py` - 整合性チェック
- `tests/unit/test_sheets_retry.py` - リトライテスト

### 🚨 緊急度評価
- **重大度**: 🟡 Medium（データ欠落だが致命的ではない）
- **影響範囲**: 🟢 Low（5件/数百件）
- **修正難易度**: 🟢 Low（リトライ追加のみ）
- **再発リスク**: 🟢 Low（リトライ + ステータス追跡で予防）

### 今後の改善（Phase 2以降）

1. **アラート通知**: `sheets_sync_status: failed` 時にメール通知
2. **定期リコンシリエーション**: 失敗レコードの定期再同期ジョブ
3. **Slackアラート**: 失敗発生時の即時通知（将来検討）
