# 🚨 Incident Report: Cloud Run Timeout Misconfiguration (2025-11-06)

**発生日時**: 2025-11-06 00:00 JST
**影響範囲**: №01 課題① のみ
**重大度**: 🔴 HIGH (データ取得完全停止)
**ステータス**: ✅ RESOLVED

---

## 📋 目次

1. [概要](#概要)
2. [症状](#症状)
3. [根本原因](#根本原因)
4. [調査プロセス](#調査プロセス)
5. [解決策](#解決策)
6. [教訓](#教訓)
7. [再発防止策](#再発防止策)

---

## 概要

### 問題

**№01 課題①** が Firestore / Google Drive / Google Spreadsheet に**一切データが保存されない**。

### 根本原因

```
Cloud Run timeout:        900秒 (15分)  ← ボトルネック
Cloud Scheduler deadline: 1500秒 (25分)

№01 処理時間: > 15分 (180件の提出データ、2ページ処理)
  ↓
15分で Cloud Run が強制終了 → 504 Gateway Timeout
  ↓
Firestore/Drive/Spreadsheet への保存処理に到達せず
```

### 影響

- **№01 課題①**: 2025-11-05 23:00 JST 実行が 504 タイムアウト
- **他のクラス**: 正常動作（処理時間 < 15分）

---

## 症状

### ユーザー報告

> carewell-class01-task01について、FirestoreやGoogleドライブやスプレッドシートへの処理。Playwrightの構文など大丈夫でしたか？

### 確認結果

```bash
# Firestore データ確認
python3 scripts/check-all-classes-firestore.py

# 結果
№01 / 課題①: ⭕ データなし (0件)
№04 / 課題①: ✅ 新スキーマ: 19件
№09 / 課題①: ✅ 新スキーマ: 100件
```

### Cloud Scheduler ログ

```
2025-11-05 14:00:01 UTC - 開始
2025-11-05 14:15:01 UTC - 504 Gateway Timeout (900秒)
```

### HTTP レスポンス

```json
{
  "timestamp": "2025-11-05T14:00:01.884140Z",
  "latency": "899.999845311s",
  "status": 504,
  "requestSize": "1710",
  "userAgent": "Google-Cloud-Scheduler"
}
```

---

## 根本原因

### タイムアウト設定の不整合

| 設定項目 | 値 | 状態 |
|---------|---|------|
| Cloud Scheduler `attemptDeadline` | 1500秒 (25分) | ✅ OK |
| Cloud Run `timeoutSeconds` | **900秒 (15分)** | ❌ 不足 |

### №01 の処理特性

```
提出データ数: 180件 (Carewell Web で確認)
ページ数: 2ページ (100件 + 80件)
処理時間: > 15分 (推定 20-25分)
```

**なぜ №01 だけ時間がかかるのか**:
- 他のクラス: 19-100件 → 1ページで完結 → < 15分
- №01 のみ: 180件 → **2ページ処理** → > 15分

### 見落とし箇所

`docs/CLASS01_TIMEOUT_ANALYSIS.md` では：
- ✅ Cloud **Scheduler** の `attemptDeadline` を 15分 → 25分に延長
- ❌ Cloud **Run** の `timeoutSeconds` を確認・延長せず

**結果**: Cloud Run が先に 15分でタイムアウト

---

## 調査プロセス

### ステップ1: 初期調査（誤った方向）

**実施内容**:
```bash
gcloud logging read "resource.type=cloud_scheduler_job AND ..."
```

**誤り**: `course_id=47` のログを №01 と誤認
- №01 は `course_id=41`
- course_id=47 は別のクラス

**教訓**: course_id で明確に識別する必要がある

### ステップ2: ユーザーからの訂正

> しかしcarewell-class01-task01についてFirestoreもドライブもスプレッドシートも全て何も取得も記入もできていません。

**気づき**: 重複チェックの問題ではなく、**データが一切保存されていない**

### ステップ3: ドキュメント確認

**読んだドキュメント**:
1. `docs/troubleshooting.md` - トラブルシューティングフロー
2. `docs/CLASS01_TIMEOUT_ANALYSIS.md` - タイムアウト問題の履歴

**発見**:
```
Lines 488-489:
"⚠️ 検証状況: 1ページのみで実行されたため、ページ2処理は未検証"
```

→ 180件 = 初めて2ページ処理が本番実行される

### ステップ4: ユーザーからHTMLデータ提供

**Carewell Web の実際のHTML**:
```html
<!-- 課題リストページ -->
5件 / 188件

<!-- 提出リストページ（全て タブ選択後） -->
<tr class="standard_grid_item">...</tr>  <!-- 100+ rows -->
```

**確認事項**:
- ✅ 180件のデータが存在
- ✅ HTML構造は正しい
- ✅ セレクタ `tr.standard_grid_item` は有効

### ステップ5: 「全て」タブクリック確認

```bash
gcloud logging read "... textPayload=~\"全て\""
```

**結果**:
```
14:01:19.547 - Clicking '全て tab'
14:01:29.662 - Clicked '全て tab' in frame: list
14:01:30.961 - Clicked '全て tab' in frame: list
14:01:31.285 - Clicked '全て tab' in frame: list
```

✅ **「全て」タブは正常にクリックされている**

### ステップ6: course_id=41 のログ検索

```bash
gcloud logging read "... textPayload=~\"course_id=41\""
```

**結果**: ログなし（ここで異常に気づく）

### ステップ7: №01 のフロー追跡

```
14:00:01.894 - Starting file collection for №01
14:00:43.172 - Selecting class: №01
14:00:53.283 - Clicked 'class "№01"'
14:01:07.389 - Selecting task: 課題①業務分析
14:01:17.546 - Clicked 'task "課題①業務分析"'
[その後ログなし]
```

→ 課題選択後にログが途絶える

### ステップ8: HTTP レスポンス確認（決定的証拠）

```bash
gcloud logging read "... httpRequest.status>=200 ..."
```

**発見**:
```json
{
  "timestamp": "2025-11-05T14:00:01.884140Z",
  "latency": "899.999845311s",  // ← 900秒 = 15分
  "status": 504,  // ← Gateway Timeout
  "requestSize": "1710"  // ← 他より大きい（task_pattern が長い）
}
```

### ステップ9: タイムアウト設定確認

```bash
# Cloud Scheduler
gcloud scheduler jobs describe carewell-class01-task01 \
  --format="value(attemptDeadline)"
→ 1500s ✅

# Cloud Run (決定的発見)
gcloud run services describe carewell-file-collector \
  --format="value(spec.template.spec.timeoutSeconds)"
→ 900s ❌
```

**根本原因確定**: Cloud Run timeout = 900秒が不足

---

## 解決策

### 実施した修正

```bash
gcloud run services update carewell-file-collector \
  --region=asia-northeast1 \
  --timeout=1500 \
  --project carewell-automation
```

### 変更内容

| 項目 | 変更前 | 変更後 |
|------|-------|-------|
| Cloud Run timeout | 900秒 (15分) | 1500秒 (25分) |
| リビジョン | 00172-w9r | 00173-5b6 |

### 検証

```bash
gcloud run services describe carewell-file-collector \
  --format="value(spec.template.spec.timeoutSeconds)"
→ 1500 ✅
```

### エンドポイント確認

```
Cloud Run URL: https://carewell-file-collector-imczapxkba-an.a.run.app
Cloud Scheduler URL: https://carewell-file-collector-imczapxkba-an.a.run.app/
```

✅ エンドポイントは変更なし（リビジョン更新のみ）

---

## 教訓

### 1. タイムアウトは2箇所ある

```
Cloud Scheduler → Cloud Run → Backend Processing
       ↓              ↓
  attemptDeadline  timeoutSeconds
    (1500s)          (900s)  ← ここで先にタイムアウト！
```

**重要**: **両方を一致させる**必要がある

### 2. ドキュメントの見落とし

`docs/CLASS01_TIMEOUT_ANALYSIS.md` では Cloud Scheduler のみ延長：
- ✅ `attemptDeadline` 900s → 1500s に延長
- ❌ Cloud Run `timeoutSeconds` は未確認

**原因**: タイムアウト設定が Cloud Run にも存在することを認識していなかった

### 3. 調査時の誤認

**最初の誤り**:
- `course_id=47` のログを №01 と誤認
- →「19件全て重複」という誤った結論

**正しい調査方法**:
- Cloud Scheduler のリクエストペイロードから `task_pattern` で識別
- または HTTP リクエストの `requestSize` で推定（№01 = 1710 bytes が最大）

### 4. 2ページ処理の未検証リスク

`docs/CLASS01_TIMEOUT_ANALYSIS.md` Line 488:
> "⚠️ 検証状況: 1ページのみで実行されたため、ページ2処理は未検証"

**リスク**:
- 180件（2ページ）は初めて本番実行
- テストでカバーできていない

**対策**:
- 定期的に高負荷シナリオのテスト実行
- または Cloud Run ログで処理時間をモニタリング

---

## 再発防止策

### 1. タイムアウト設定チェックリスト

**変更時の必須確認項目**:
- [ ] Cloud Scheduler `attemptDeadline`
- [ ] Cloud Run `timeoutSeconds`
- [ ] 両者が一致している

### 2. ドキュメント更新

- [x] `docs/troubleshooting.md` に調査ステップ追加
- [x] `docs/CLASS01_TIMEOUT_ANALYSIS.md` に Cloud Run timeout 見落とし記録
- [x] `CLAUDE.md` Common Mistakes に追加
- [x] `.serena/memories/incident_response_lessons.md` 更新

### 3. モニタリング追加（今後の課題）

```bash
# Cloud Monitoring アラート設定（推奨）
- Cloud Run 処理時間 > 20分 → 警告
- Cloud Run 504 エラー → 即座に通知
```

### 4. 定期検証スクリプト

```bash
# scripts/check-timeout-config.sh (提案)
scheduler_deadline=$(gcloud scheduler jobs describe ... --format="value(attemptDeadline)")
cloudrun_timeout=$(gcloud run services describe ... --format="value(timeoutSeconds)")

if [ "$scheduler_deadline" != "${cloudrun_timeout}s" ]; then
  echo "⚠️ Timeout mismatch detected!"
fi
```

---

## タイムライン

```
2025-11-05 23:00 JST - №01 課題① 実行開始
2025-11-05 23:15 JST - Cloud Run timeout (900秒)、504 エラー
2025-11-06 00:00 JST - ユーザーが問題報告
2025-11-06 00:00-00:30 JST - 調査・根本原因特定
2025-11-06 00:30 JST - Cloud Run timeout を 1500秒に延長
2025-11-06 00:30 JST - 次回実行で検証予定
```

---

## 関連ドキュメント

- **CLAUDE.md Lines 224-308**: Common Mistakes (このインシデント追加済み)
- **docs/CLASS01_TIMEOUT_ANALYSIS.md**: タイムアウト問題の履歴
- **docs/troubleshooting.md**: トラブルシューティングガイド（調査ステップ追加済み）
- **.serena/memories/incident_response_lessons.md**: 教訓とチェックリスト

---

**作成日**: 2025-11-06
**最終更新**: 2025-11-06
**作成者**: Claude Code
**レビュー**: Pending (次回実行での検証後)
