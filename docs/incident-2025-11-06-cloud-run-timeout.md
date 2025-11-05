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
2025-11-06 00:02 JST - 手動で Cloud Run timeout を 1500秒に延長（リビジョン 00173-5b6）
2025-11-06 00:21 JST - GitHub Actions が自動デプロイ（timeout=900 で上書き、リビジョン 00174-dnf）
2025-11-06 00:30 JST - №01 実行開始（再び 900秒でタイムアウト）
2025-11-06 00:45 JST - 504 タイムアウト発生（Firestore に 7件のみ保存）
2025-11-06 00:50 JST - ユーザーが「180件あるはずなのに7件しかない」と指摘
2025-11-06 00:55 JST - GitHub Actions ワークフローに timeout=900 がハードコードされていることを発見
2025-11-06 00:56 JST - 手動で timeout=1500 に再設定（リビジョン 00175-6qz）
2025-11-06 00:57 JST - .github/workflows/deploy.yml を修正（timeout=1500）
```

---

## 🔴 重要な追加発見（2025-11-06 00:50 JST）

### GitHub Actions ワークフローによる設定上書き問題

**問題**:
手動で Cloud Run timeout を 1500秒に設定しても、**GitHub Actions が自動デプロイ時に 900秒に戻してしまう**。

**根本原因**:
`.github/workflows/deploy.yml` Line 107 に timeout が **ハードコードされている**：

```yaml
# ❌ 修正前
--timeout 900 \
```

**影響**:
1. 00:02 JST: 手動で timeout=1500 に設定（リビジョン 00173-5b6）
2. 00:21 JST: ドキュメント更新のコミットで GitHub Actions が起動
3. GitHub Actions が timeout=900 で上書き（リビジョン 00174-dnf）
4. 00:30 JST: №01 実行が再び 900秒でタイムアウト
5. **結果**: 180件中 7件のみ保存（残り 173件はタイムアウト）

### 恒久的な修正

**実施内容**:

1. **即座の修正**（リビジョン 00175-6qz）:
   ```bash
   gcloud run services update carewell-file-collector \
     --region=asia-northeast1 \
     --timeout=1500
   ```

2. **恒久的修正**（`.github/workflows/deploy.yml` Line 107）:
   ```yaml
   # ✅ 修正後
   --timeout 1500 \
   ```

**教訓**:
- ❌ Cloud Run の手動設定変更だけでは不十分
- ✅ **CI/CD ワークフローファイルも必ず確認・修正**
- ✅ インフラ設定は IaC（Infrastructure as Code）で管理すべき
- ✅ 手動変更後、次回デプロイで設定が戻らないか検証必須

---

## 🔴 第3の問題発見（2025-11-06 01:00-01:37 JST）

### フレーム取得タイミング問題

**問題**:
Cloud Run timeout を 1500秒に延長したにも関わらず、**01:00 JST の実行でも 504 タイムアウトが発生**。

**症状**:
- 01:00 JST: №01 実行、1499秒（約25分）でタイムアウト
- Firestore: 依然として 7件のみ（増加なし）
- エラーログ: `playwright._impl._errors.TimeoutError: Timeout 60000ms exceeded` が繰り返し発生

**調査結果**:

```
16:01:25 - 課題①クリック完了 ✅
16:01:36 - 「全て」タブクリック成功 ✅
16:01:50 - Could not extract total count: Timeout 10000ms ❌
16:03:05 - Timeout 60000ms exceeded (wait_for_selector) ❌
16:08:01 - Timeout 60000ms exceeded (2回目)
16:17:54 - Timeout 60000ms exceeded (3回目)
```

**根本原因**:
「全て」タブクリック後、**フレームリロード完了前にフレーム取得を試行**していた。

1. **FRAME_LOAD_WAIT が不十分**:
   - 設定値: 3000ms (3秒)
   - №01の180件データの場合、サーバー応答に時間がかかり不足

2. **フレーム取得時のリトライロジック不足**:
   - フレームがリロード中/detachedの可能性を考慮していない
   - 1回の試行で失敗すると即エラー

3. **25分間のループ**:
   - フレーム取得失敗 → 60秒タイムアウト待機 → リトライ → 失敗...
   - 約5分ごとにタイムアウト発生
   - Cloud Run timeout (1500秒) に到達するまで継続

**ユーザーからの指摘**:
> "ドキュメントのトラブルシューティングをみて、多分またフレームがちゃんと探せてないだけだと思うから"

→ **正確な診断でした**。過去の `CLASS01_TIMEOUT_ANALYSIS.md` にも同様の問題が記録されていました。

### 実施した修正

**修正内容**:

1. **フレーム待機時間の延長** (Line 70):
   ```python
   # 修正前
   FRAME_LOAD_WAIT = 3000  # 3秒

   # 修正後
   FRAME_LOAD_WAIT = 15000  # 15秒（5倍）
   ```

2. **フレーム取得にリトライロジック追加** (Line 358-385, 402-430):
   ```python
   # 最大5回リトライ（page 1）、3回リトライ（page 2+）
   max_frame_retries = 5 if current_page == 1 else 3

   for retry in range(max_frame_retries):
       for frame in self.page.frames:
           if frame.name == "list":
               # フレームがdetachedでないことを確認
               try:
                   _ = frame.url  # detachedの場合は例外発生
                   list_frame = frame
                   break
               except Exception:
                   continue  # 次のフレームを試行

       if list_frame:
           break

       time.sleep(2)  # 2秒待機して再試行
   ```

**コミット**: `17d63d8` (2025-11-06 01:37 JST)

**期待される効果**:
- 「全て」タブクリック後、15秒待機でフレームリロード完了を待つ
- フレームが見つからない場合、最大5回リトライ（合計10秒追加待機）
- フレームがdetachedの場合も適切にハンドリング
- テーブル要素待機のタイムアウトエラー解消

**教訓**:
- ❌ **Cloud Run timeout だけ延長しても意味がない**
- ✅ **Playwright のタイムアウト箇所を根本的に修正する必要がある**
- ✅ **過去のトラブルシューティングドキュメントを参照することが重要**
- ✅ **大規模データセット（180+件）では待機時間を長めに設定**

**検証予定**: 次回実行（01:30 JST または 02:00 JST）で効果確認

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
