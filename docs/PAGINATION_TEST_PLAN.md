# ページネーション処理バグ修正 - テスト計画

## 📅 作成日
2025-11-03

## 🔗 関連ドキュメント
- [問題分析レポート](./PAGINATION_BUG_ANALYSIS.md)
- [修正計画](./PAGINATION_FIX_PLAN.md)

## 🎯 テストの目的

ページネーション処理のバグ修正が正しく動作し、以下を確認する：
1. 2ページ目以降の処理が正常に動作すること
2. 既存の単一ページケースに影響がないこと
3. フレーム参照とURL更新が正しく機能すること

## 📋 テストケース

### テストケース1: 単一ページ（<100件）- 後方互換性確認

**目的**: 既存動作を壊さないことを確認

**テストデータ**:
- クラス: 他のクラス（提出件数が100件未満のもの）
- 提出件数: 約13-50件程度

**実行方法**:
```bash
# Cloud Schedulerジョブを手動実行（例: class02-task01など）
gcloud scheduler jobs run carewell-class02-task01 \
  --location=asia-northeast1 \
  --project=carewell-automation
```

**確認項目**:

| # | 確認内容 | 確認方法 | 期待結果 |
|---|----------|----------|----------|
| 1.1 | 処理が正常に完了する | Cloud Schedulerログ | ステータス: SUCCESS |
| 1.2 | 全件数が取得される | Cloud Runログ | `Successfully extracted N submissions` |
| 1.3 | 件数検証が成功する | Cloud Runログ | `✓ Count verification passed: N/N` |
| 1.4 | フレーム参照更新ログが出力される | Cloud Runログ | `Current list URL for page 1:` が出力される |
| 1.5 | Firestoreに記録される | Firestoreコンソール | N件のドキュメントが存在 |
| 1.6 | Sheetsに記録される | Google Sheets | N行のデータが存在 |

**成功基準**:
- ✅ 全ての確認項目がPASS
- ✅ 修正前と同じ動作をする

---

### テストケース2: 2ページ（100-200件）- 主要バグ修正確認

**目的**: 2ページ目の処理が正常に動作することを確認

**テストデータ**:
- ジョブ: carewell-class01-task01
- クラス: 令和7年度 デジタル中核人材養成研修 №01
- 課題: 課題①
- 提出件数: 145件（UIから取得）
- ページ数: 2ページ（100件 + 45件）

**実行方法**:
```bash
# Cloud Schedulerジョブを手動実行
gcloud scheduler jobs run carewell-class01-task01 \
  --location=asia-northeast1 \
  --project=carewell-automation

# リアルタイムでログを監視
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=carewell-file-collector" \
  --project=carewell-automation
```

**確認項目**:

| # | 確認内容 | 確認方法 | 期待結果 |
|---|----------|----------|----------|
| 2.1 | UI件数が正しく取得される | Cloud Runログ | `✓ Total submission count from UI: 145` |
| 2.2 | 1ページ目が正しく処理される | Cloud Runログ | `Extracted basic info for 100 submissions on page 1` |
| 2.3 | 1ページ目のURL更新ログ | Cloud Runログ | `Current list URL for page 1: [URL1]` |
| 2.4 | 1ページ目の全download link取得 | Cloud Runログ | `Getting download link for:` が100回出力 |
| 2.5 | ページ数検出 | Cloud Runログ | `Total pages available: 2` |
| 2.6 | 2ページ目への遷移 | Cloud Runログ | `Navigating to page 2/2` |
| 2.7 | 2ページ目の処理開始 | Cloud Runログ | `Processing page 2` |
| 2.8 | 2ページ目のフレーム参照更新 | Cloud Runログ | `Current list URL for page 2: [URL2]` |
| 2.9 | 2ページ目が正しく処理される | Cloud Runログ | `Extracted basic info for 45 submissions on page 2` |
| 2.10 | 2ページ目の全download link取得 | Cloud Runログ | `Getting download link for:` が45回出力 |
| 2.11 | 最終ページ到達 | Cloud Runログ | `Reached last page 2/2` |
| 2.12 | 全件数処理完了 | Cloud Runログ | `Successfully extracted 145 submissions from 2 page(s)` |
| 2.13 | 件数検証成功 | Cloud Runログ | `✓ Count verification passed: 145/145` |
| 2.14 | タイムアウトエラーなし | Cloud Runログ | `TimeoutError` が出力されない |
| 2.15 | Firestoreに145件記録 | Firestoreコンソール | 145件のドキュメントが存在 |
| 2.16 | Sheetsに145件記録 | Google Sheets | 145行のデータが存在 |

**成功基準**:
- ✅ 全ての確認項目がPASS
- ✅ 145件全て処理完了
- ✅ タイムアウトエラーが発生しない

**重要ログパターン**:
```
Processing page 1
Current list URL for page 1: https://jaccw-carewel.study.jp/course/list.aspx?...
Extracted basic info for 100 submissions on page 1
Getting download link for: [学生1]
...
Getting download link for: [学生100]
Total pages available: 2
Navigating to page 2/2
Processing page 2
Current list URL for page 2: https://jaccw-carewel.study.jp/course/list.aspx?...
Extracted basic info for 45 submissions on page 2
Getting download link for: [学生101]
...
Getting download link for: [学生145]
Reached last page 2/2
Successfully extracted 145 submissions from 2 page(s)
✓ Count verification passed: 145/145
```

---

### テストケース3: エラーハンドリング - フレーム取得失敗時

**目的**: フレーム取得失敗時のフォールバック動作を確認

**テストデータ**:
- （通常のケースで確認）

**確認項目**:

| # | 確認内容 | 確認方法 | 期待結果 |
|---|----------|----------|----------|
| 3.1 | フレーム未検出時のログ | Cloud Runログ | `'list' frame not found, using main page` が出力される（該当する場合） |
| 3.2 | main pageへのフォールバック | Cloud Runログ | 処理が継続する |

**成功基準**:
- ✅ エラーが発生せず処理が継続する

---

## 🔍 ログ確認手順

### 1. Cloud Schedulerログの確認

```bash
# ジョブのログを確認
gcloud logging read \
  'resource.type="cloud_scheduler_job" AND resource.labels.job_id="carewell-class01-task01"' \
  --limit 10 \
  --format json \
  --project carewell-automation
```

**確認ポイント**:
- ステータスが `SUCCESS` であること
- `DEADLINE_EXCEEDED` エラーが出ていないこと

### 2. Cloud Runログの確認

```bash
# ページネーション関連のログを確認
gcloud logging read \
  'resource.type=cloud_run_revision
   AND resource.labels.service_name=carewell-file-collector
   AND (
     textPayload=~"Processing page"
     OR textPayload=~"Total pages"
     OR textPayload=~"Current list URL"
     OR textPayload=~"Count verification"
   )' \
  --limit 50 \
  --format json \
  --project carewell-automation
```

**確認ポイント**:
- `Processing page 1` と `Processing page 2` が両方出力されている
- `Current list URL for page 1` と `Current list URL for page 2` が異なるURL
- `✓ Count verification passed: 145/145` が出力されている

### 3. Firestoreデータの確認

```bash
# Firestore内のドキュメント数を確認
gcloud firestore documents list \
  "令和7年度 デジタル中核人材養成研修 №01/課題①/documents" \
  --project carewell-automation \
  | wc -l
```

**確認ポイント**:
- 145行（ヘッダー除く）が出力される

### 4. Google Sheetsの確認

手動で確認：
1. スプレッドシートを開く
2. 「課題①」シートを選択
3. 行数を確認（ヘッダー除いて145行）

---

## 📊 テスト実行記録

### 実行日時

- テストケース1: ____年__月__日 __:__ (JST)
- テストケース2: ____年__月__日 __:__ (JST)
- テストケース3: ____年__月__日 __:__ (JST)

### テスト結果サマリー

| テストケース | ステータス | 備考 |
|-------------|-----------|------|
| TC1: 単一ページ | [ ] PASS / [ ] FAIL | |
| TC2: 2ページ | [ ] PASS / [ ] FAIL | |
| TC3: エラーハンドリング | [ ] PASS / [ ] FAIL | |

### 詳細結果（テストケース2）

| 確認項目 | ステータス | 実測値 | 備考 |
|---------|-----------|--------|------|
| 2.1 | [ ] PASS / [ ] FAIL | | |
| 2.2 | [ ] PASS / [ ] FAIL | | |
| 2.3 | [ ] PASS / [ ] FAIL | | |
| 2.4 | [ ] PASS / [ ] FAIL | | |
| 2.5 | [ ] PASS / [ ] FAIL | | |
| 2.6 | [ ] PASS / [ ] FAIL | | |
| 2.7 | [ ] PASS / [ ] FAIL | | |
| 2.8 | [ ] PASS / [ ] FAIL | | |
| 2.9 | [ ] PASS / [ ] FAIL | | |
| 2.10 | [ ] PASS / [ ] FAIL | | |
| 2.11 | [ ] PASS / [ ] FAIL | | |
| 2.12 | [ ] PASS / [ ] FAIL | | |
| 2.13 | [ ] PASS / [ ] FAIL | | |
| 2.14 | [ ] PASS / [ ] FAIL | | |
| 2.15 | [ ] PASS / [ ] FAIL | | |
| 2.16 | [ ] PASS / [ ] FAIL | | |

---

## 🔄 問題発生時の対応

### ロールバック条件

以下のいずれかが発生した場合、即座にロールバック：

1. テストケース1（単一ページ）がFAIL
2. テストケース2で重大なエラー（データ損失、重複書き込みなど）
3. 新たなタイムアウトエラーが頻発

### ロールバック手順

```bash
# 1. コミットをrevert
cd /Users/yyyhhh/carewell-gcp-drive-automation
git revert HEAD

# 2. 再デプロイ
git push origin main

# 3. GitHub Actionsの完了を待つ

# 4. Cloud Schedulerジョブを一時停止（必要に応じて）
gcloud scheduler jobs pause carewell-class01-task01 \
  --location=asia-northeast1 \
  --project=carewell-automation
```

---

## ✅ 最終チェックリスト

テスト実行前:
- [ ] 修正内容をレビュー
- [ ] テスト計画を確認
- [ ] 必要なアクセス権限を確認

テスト実行:
- [ ] テストケース1を実行
- [ ] テストケース2を実行
- [ ] テストケース3を確認
- [ ] 全ログを保存

テスト完了後:
- [ ] テスト結果を記録
- [ ] 問題があればロールバック
- [ ] 成功すれば次フェーズへ

---

**作成者**: Claude Code
**レビュー**: 要レビュー
**ステータス**: Ready for Execution
