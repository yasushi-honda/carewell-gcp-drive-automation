# Incident Response Lessons Learned

## 重要：本番問題発生時の対応手順

### 🚨 最優先事項：ドキュメントを先に確認

問題が発生したら、**必ず最初に以下を確認**：

1. **CLAUDE.md の Critical Configuration セクション**
   - 重要な設定値とデザインドキュメント参照
   - 必須パラメータのチェックリスト

2. **CLAUDE.md の Common Mistakes セクション**
   - 過去の同様のインシデント記録
   - 根本原因と最適な解決方法

3. **メモリファイル**
   - `suggested_commands`: 推奨コマンドと検証方法
   - `task_completion_checklist`: 完了チェックリスト

4. **設計ドキュメント（.kiro/specs/）**
   - 該当機能の要件・設計仕様

### 環境の制約を理解する

**ローカル環境の制約**:
- ❌ Firestoreへの直接アクセスは不安定（DNS解決エラーの可能性）
- ✅ Cloud Runログ + Dashboard を優先して使用
- ✅ 本番環境での動作確認を基本とする

**推奨検証方法**:
```bash
# 1. Cloud Runログ（最優先）
gcloud logging read "resource.type=cloud_run_revision AND
  resource.labels.service_name=carewell-file-collector" --limit 50

# 2. Cloud Scheduler状態確認
gcloud scheduler jobs describe JOB_NAME --location=asia-northeast1

# 3. Dashboard（ビジュアル確認）
# https://carewell-automation.web.app/
```

### 実践的な教訓（過去のインシデントから）

#### 🚨 2025-11-06 08:00 JST: デプロイ済みのはずが古いコードが実行されていた

**問題**: コード修正してGitHub Actionsでデプロイしたのに、実際には古いコードが実行され続けていた

**症状**:
- 修正版コードで追加したINFOレベルログが一切出ない
- 古いエラーメッセージ（修正前のもの）が繰り返し出る
- ユーザー報告: 「8:06時点で新たに取得が出来てる状況が無いので、不安です」

**根本原因**:
1. **トラフィックが古いリビジョンに向いたまま**
   ```bash
   # 現在のトラフィック
   carewell-file-collector-00180-j9h  100%  # 古いコード

   # 最新リビジョン
   carewell-file-collector-00183-nb9  True  Retired  # 新しいコードだが無効化
   ```

2. **Dockerイメージダイジェストが同じ** (キャッシュの問題)
   ```bash
   # 00183-nb9 と 00182-78r が同じイメージ
   sha256:ef8d7ff49b0d89feddd7d451222208adac84db51f7a576fc8a32511c5cd2f48d
   ```

3. **GitHub Actionsがデプロイしたが、新リビジョンが有効化されなかった**

**❌ 誤った仮定**:
1. 「GitHub Actionsが成功したから、新しいコードが動いているはず」
2. 「リビジョンが作成されたから、トラフィックも切り替わっているはず」
3. 「ログを見て同じエラーが出ていても、まだ処理中だから様子を見よう」

**✅ 正しい調査ステップ**:

**Step 1: 修正版コードの痕跡をログで確認**
```bash
# 修正版コードで追加したログが出ているか？
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector" \
  --limit 50 --format json | \
  jq -r '.[] | select(.textPayload) | .textPayload' | \
  grep "Found [0-9]+ report links"  # 修正版で追加したINFOログ

# 出ない場合 → 古いコードが実行中
```

**Step 2: トラフィック配分を確認**
```bash
gcloud run services describe carewell-file-collector \
  --region=asia-northeast1 \
  --format="value(status.traffic[0].revisionName,status.traffic[0].percent)"

# 期待: 最新リビジョン名が表示される
# 実際: 古いリビジョン名 → 問題！
```

**Step 3: リビジョン一覧とイメージダイジェスト確認**
```bash
gcloud run revisions list \
  --service=carewell-file-collector \
  --region=asia-northeast1 \
  --limit 5 \
  --format="table(metadata.name,status.conditions[0].status,status.conditions[0].reason,status.imageDigest)" \
  --sort-by="~metadata.creationTimestamp"

# 同じダイジェストのリビジョンが複数ある場合 → Dockerキャッシュの問題
```

**Step 4: 最新リビジョンのステータス確認**
```bash
gcloud run revisions describe LATEST_REVISION \
  --region=asia-northeast1 \
  --format="value(status.conditions[0].status,status.conditions[0].reason)"

# "Retired" と表示される場合 → 無効化されている
```

**解決方法**:

**Option 1: トラフィックを手動で最新リビジョンに切り替え** (有効なリビジョンがある場合)
```bash
gcloud run services update-traffic carewell-file-collector \
  --region=asia-northeast1 \
  --to-revisions LATEST_REVISION=100
```

**Option 2: GitHub Actionsを再実行** (Dockerキャッシュ問題を回避)
```bash
# ワークフローを手動トリガー
gh workflow run deploy.yml

# 進捗監視
gh run watch RUN_ID
```

**Option 3: Dockerキャッシュを無視して再ビルド**
```yaml
# .github/workflows/deploy.yml で --no-cache オプション追加
docker build --no-cache -t ${IMAGE_TAG} .
```

**検証方法**:
```bash
# 1. 新しいリビジョンが作成されたか
gcloud run revisions list --service=carewell-file-collector \
  --region=asia-northeast1 --limit 1

# 2. トラフィックが100%新リビジョンに向いているか
gcloud run services describe carewell-file-collector \
  --region=asia-northeast1 \
  --format="value(status.traffic[0].revisionName,status.traffic[0].percent)"

# 3. ログに修正版コードの痕跡があるか
gcloud logging read "..." --limit 20 | grep "修正版で追加したログ"
```

**重要な教訓**:
- ❌ **「GitHub Actions成功 = 新コード稼働」ではない**
- ✅ **デプロイ後は必ず3点確認**: ①リビジョン作成 ②トラフィック配分 ③ログで新コード確認
- ✅ **修正版コードの痕跡をログで確認** - 新しいログメッセージが出ているか
- ✅ **イメージダイジェストの重複に注意** - 同じダイジェスト = 同じコード
- ✅ **ユーザーの「不安」は重要なシグナル** - 期待した動作がない = 調査すべき

**繰り返し発生しているパターン**:
> ユーザー: 「今回のような新しくしたが、実行は実は古いままだった。という失敗は以前から有りました。」

**恒久対策**:
1. **デプロイ後検証スクリプトを作成** - 3点確認を自動化
2. **GitHub Actionsに検証ステップ追加** - デプロイ後に新リビジョン確認
3. **Dockerビルドに--no-cacheオプション検討** - キャッシュ問題を回避

**参考**: 今回は08:13 JSTにGitHub Actions再実行で解決（予定）

---

#### 2025-11-06: Cloud Run Timeout 設定ミス

**問題**: №01 課題① が Firestore/Drive/Spreadsheet に**一切データ保存されない**

**根本原因**: タイムアウト設定が **2箇所** にあることを見落とし

```
Cloud Scheduler attemptDeadline: 1500秒 (25分) ✅ 延長済み（2025-11-04）
Cloud Run timeoutSeconds:        900秒 (15分)  ❌ 未延長（見落とし）
                                               ↑ ここで先にタイムアウト
```

**症状**:
- Cloud Run ログで処理途中で終了
- HTTP レスポンス: `504 Gateway Timeout`、latency: 900秒
- Firestore/Drive にデータが一切なし

**❌ 誤った仮定**:
1. `docs/CLASS01_TIMEOUT_ANALYSIS.md` で「タイムアウト問題は解決済み」と思い込んだ
2. Cloud Scheduler の設定だけ確認、Cloud Run を見落とし
3. 「全て」タブクリックの問題と誤認（実際は成功していた）

**✅ 正しい調査ステップ**:
1. HTTP レスポンスログで latency 確認 → 900秒で終了
2. **タイムアウト設定を2箇所とも確認**:
   ```bash
   # Cloud Scheduler
   gcloud scheduler jobs describe JOB_NAME --format="value(attemptDeadline)"

   # Cloud Run (見落としやすい！)
   gcloud run services describe SERVICE_NAME --format="value(spec.template.spec.timeoutSeconds)"
   ```
3. 短い方（Cloud Run 900秒）が先にタイムアウトすることを特定

**解決方法**:
```bash
gcloud run services update carewell-file-collector \
  --region=asia-northeast1 \
  --timeout=1500
```

**教訓**:
- **タイムアウトチェックリスト**（変更時の必須確認）:
  - [ ] Cloud Scheduler `attemptDeadline` 確認
  - [ ] Cloud Run `timeoutSeconds` 確認
  - [ ] 両者が一致している（または Cloud Run ≥ Scheduler）
  - [ ] 最大処理時間を考慮（2ページ = 20-25分）
  - [ ] **GitHub Actions ワークフローファイル（`.github/workflows/deploy.yml`）も更新**
- **「解決済み」を鵜呑みにしない**: 過去ドキュメントでも実データで検証
- **504 Timeout の調査**: HTTP latency が timeout 値と一致 → そこでタイムアウト

**🔴 重要な追加発見（同日 00:50 JST）**:

**第2の根本原因**: GitHub Actions ワークフローが設定を上書き

```
00:02 JST - 手動修正: timeout=1500 (リビジョン 00173-5b6) ✅
00:21 JST - GitHub Actions デプロイ: timeout=900 で上書き (00174-dnf) ❌
00:30 JST - №01 実行: 再び 504 タイムアウト（180件中 7件のみ保存）
```

**原因**: `.github/workflows/deploy.yml` Line 107 に `--timeout 900` がハードコード

**修正内容**:
1. 即座の修正: `gcloud run services update --timeout=1500`（リビジョン 00175-6qz）
2. 恒久的修正: `.github/workflows/deploy.yml` を `--timeout 1500` に変更

**重要な教訓**:
- ❌ **Cloud Run の手動設定変更だけでは不十分！**
- ✅ **CI/CD ワークフローファイルも必ず更新**（`.github/workflows/deploy.yml`）
- ✅ 手動変更後、次回デプロイで設定が戻らないか検証必須
- ✅ インフラ設定は IaC（Infrastructure as Code）で管理すべき

**参考**: `docs/incident-2025-11-06-cloud-run-timeout.md`

**🔴 追加発見 #2（同日 01:00-01:37 JST）**:

**第3の根本原因**: フレーム取得タイミング問題（大規模データセット）

Cloud Run timeout を 1500秒に延長したのに、**01:00 JST 実行でも 1499秒でタイムアウト**。

**根本原因**: `FRAME_LOAD_WAIT = 3000ms (3秒)` が不十分（№01の180+件データの場合）

```
「全て」タブクリック成功 ✅
  ↓
3秒待機（FRAME_LOAD_WAIT）← 不足！
  ↓
フレーム取得試行 → 失敗（フレームまだリロード中）
  ↓
wait_for_selector → 60秒タイムアウト ❌
  ↓
約5分ごとにリトライ... 25分間ループ
```

**ユーザーの診断**:
> "ドキュメントのトラブルシューティングをみて、多分またフレームがちゃんと探せてないだけだと思うから"

→ **100%正解**。過去の `CLASS01_TIMEOUT_ANALYSIS.md` にも同様の問題が記録されていた。

**修正内容** (commit `17d63d8`):
1. `FRAME_LOAD_WAIT`: 3000ms → 15000ms (5倍)
2. フレーム取得にリトライロジック追加（最大5回、2秒間隔）
3. フレームがdetachedでないことを確認

**重要な教訓**:
- ❌ **Cloud Run timeout だけ延長しても Playwright timeout は解決しない**
- ✅ **コード内の実際のタイムアウト箇所を特定して修正**
- ✅ **過去のトラブルシューティングドキュメントを参照する重要性**
- ✅ **大規模データセット（180+件）では待機時間を長めに設定**

**フレーム問題のチェックリスト**:
- [ ] `FRAME_LOAD_WAIT` が十分か（大規模: 15秒推奨）
- [ ] フレーム取得にリトライロジックがあるか
- [ ] フレームがdetachedでないことを確認しているか
- [ ] ログで「全て」タブクリック成功を確認
- [ ] ログでフレーム取得成功/失敗を確認

**参考**: `docs/incident-2025-11-06-cloud-run-timeout.md` (Section: 第3の問題発見)

#### 🚨 2025-11-06 19:30 JST: Playwright API 検証を怠り、存在しないメソッドをドキュメント・実装に記載

**問題**: `Frame.go_back()` という存在しないメソッドをドキュメントに記載し、実装計画まで作成してしまった

**症状**:
- ドキュメント `pagination-viewstate-solution-2025-11-06.md` に `list_frame.go_back()` の使用を推奨
- 実装計画 `page-re-navigation-implementation-plan-2025-11-06.md` も誤った API に基づく
- ユーザーから指摘を受けて初めて気づく

**ユーザーからの厳しいフィードバック**:
> "なぜ同じ間違いを繰り返しましたか？ドキュメントへの書き込みとコードの改変やエラーの分析などするときは必ずドキュメントを参照してから対応をするようにしてください。"

**根本原因**:
1. **Playwright API ドキュメントを確認しなかった**
   - Frame クラスに `go_back()` メソッドが存在するか検証せず
   - 公式ドキュメント: https://playwright.dev/python/docs/api/class-frame
   - 実際には `Page.go_back()` のみ存在（Frame には存在しない）

2. **既存ドキュメントを盲目的に信頼**
   - 自分が作成したドキュメントであっても技術的正確性を再確認しなかった
   - ドキュメントの内容が API 仕様と一致するか検証を怠った

3. **繰り返しパターン**
   - ユーザー: "なぜ同じ間違いを繰り返しましたか？"
   - 過去にも類似の問題があったことを示唆

**❌ 誤った行動パターン**:
1. API の存在を検証せずにドキュメントに記載
2. 実装計画を作成（存在しないメソッドに基づく）
3. コードを実装（`page.go_back()` は存在するが、フレームレベルでは使えない）
4. ユーザーの指摘で初めて気づく

**✅ 正しいアプローチ**:

**Step 1: API メソッドの検証**
```python
# 使用する前に Playwright 公式ドキュメントで確認
# https://playwright.dev/python/docs/api/class-frame
# → Frame.go_back() は存在しない ❌
# → Page.go_back() のみ存在 ✅
```

**Step 2: 正しい API を使用**
```python
# ✅ Correct - Page レベルでのみ利用可能
self.page.go_back(wait_until="load", timeout=30000)

# ❌ Wrong - Frame レベルでは存在しない
list_frame.go_back()  # AttributeError になる
```

**Step 3: ASP.NET の制約を理解**
- `page.go_back()` は常にページ1に戻る（ViewState の仕様）
- ページ2以降の処理では、go_back() 後に再遷移が必要

**修正内容**:
1. **ドキュメントの即座の修正**:
   - `pagination-viewstate-solution-2025-11-06.md` に「❌ 誤った解決策」セクション追加
   - Playwright API 検証結果を明記
   - 正しいアプローチ（`page.go_back()` + 再遷移）を文書化

2. **実装計画の修正**:
   - `page-re-navigation-implementation-plan-2025-11-06.md` に更新履歴追加
   - 「⚠️ 重要な技術的制約」セクション追加
   - API 制約を明示

**重要な教訓**:
- ❌ **「このメソッドは存在するはず」という思い込みで実装しない**
- ❌ **自分が書いたドキュメントを無批判に信頼しない**
- ✅ **使用するすべての API を公式ドキュメントで検証**
- ✅ **ドキュメント作成時も技術的正確性を確認**
- ✅ **ユーザーからの指摘を重く受け止める** - "なぜ同じ間違いを繰り返す？"
- ✅ **誤ったドキュメントは即座に修正** - 次に読む人（自分自身を含む）を誤導しない

**恒久対策**:

**API 使用前チェックリスト**:
- [ ] メソッドが公式ドキュメントに存在するか確認
- [ ] 使用例を公式ドキュメントで確認
- [ ] 対象クラス（Page/Frame/Locator）が正しいか確認
- [ ] 自分の記憶・推測だけに頼らない

**ドキュメント品質チェックリスト**:
- [ ] 技術的事実を公式ソースで検証
- [ ] コード例が実際に実行可能か確認
- [ ] API メソッド名が正確か確認
- [ ] 誤った情報を含んでいないか自己レビュー

**Playwright 特有の注意点**:
- `Page` クラスと `Frame` クラスは API が異なる
- `Page.go_back()` は存在するが、`Frame.go_back()` は存在しない
- 使用前に必ずクラスごとの API リファレンスを確認

**参考**:
- Playwright Frame API: https://playwright.dev/python/docs/api/class-frame
- Playwright Page API: https://playwright.dev/python/docs/api/class-page
- 修正されたドキュメント: `docs/pagination-viewstate-solution-2025-11-06.md`
- 修正された実装計画: `docs/page-re-navigation-implementation-plan-2025-11-06.md`

#### 2025-11-04: Cloud Scheduler task_pattern 不一致

**❌ 避けるべきアプローチ**:
1. ドキュメント確認をスキップして調査開始
2. ローカル環境からFirestoreへの直接アクセスを試行
3. 14個のジョブを1つずつ手動で修正
4. 手動実行テストを複数回試行
5. 失敗が予測される操作でバックグラウンドプロセスを多数起動

**✅ 推奨されるアプローチ**:
1. CLAUDE.md と過去のインシデントを確認
2. 根本原因をコード/設定から特定
3. 一括更新スクリプトを作成（手動作業を避ける）
4. Cloud Runログとダッシュボードで検証
5. 自動実行スケジュールを待つ（手動実行は不安定）

#### 2025-11-05: Dashboard Firestore スキーマ移行

**ユーザーからの重要なフィードバック**:
> "ちゃんとドキュメントをみてから行動してください。Firestoreのデータについて、重複チェックリストの設計、Hostingへの接続設計などどれも事前に確認してから対応すべき重要な仕様内容です。"

**問題**: Dashboard が旧スキーマを使用、Steering Document と乖離

**❌ 初期の誤ったアプローチ**:
1. ドキュメント確認せずにFirestoreデータ削除を実施
2. 新スキーマデータを削除したが、Dashboard は旧スキーマ使用で影響なし
3. 破壊的操作を先に実施してしまった

**✅ 最終的な正しいアプローチ**:
1. Steering Document を確認して公式仕様を理解
2. 現状記録スクリプトで全パターンのデータを保存
3. 全クラス・全課題の影響を事前評価
4. 10フェーズの段階的移行（各フェーズで検証）
5. ユーザー確認を挟みながら慎重に進行
6. 旧データ削除は**最後**に実施（検証完了後）

**教訓**:
- **Single Source of Truth**: Steering Document が設計の唯一の真実
- **破壊前に記録**: 削除操作の前に必ず現状をスナップショット
- **段階的実施**: 大きな変更は10フェーズのように細かく分割
- **全体影響評価**: 1つだけでなく全体への影響を事前確認

**参考**: `docs/incident-2025-11-05-schema-migration-and-playwright-fix.md`

#### 2025-11-05: Playwright Invalid API エラー

**問題**: 存在しないメソッド `wait_for_element_state()` 使用

**エラーメッセージ**:
```
'Locator' object has no attribute 'wait_for_element_state'
```

**根本原因**:
- Phase 6 (commit 941e94a) で誤ったAPIを導入
- テストで検出されず（該当コードパスが実行されなかった）
- 本番環境で初めて発覚

**❌ 間違ったコード**:
```python
link.wait_for_element_state("visible", timeout=10000)  # 存在しないメソッド
link.click()
```

**✅ 正しいコード**:
```python
# Playwright's Auto-waiting handles visibility checks before click
link.click()  # Auto-waiting が自動で待機
```

**教訓**:
- **Playwright の Auto-waiting**: click(), fill() 等は自動で要素が準備完了まで待機
- **公式ドキュメント確認**: APIメソッドの存在を必ず確認
- **テストカバレッジ向上**: エラーパスを含む実際のユースケースをテスト
- **明示的待機は最小限**: 本当に必要な場合のみ `wait_for(state="visible")` を使用

**参考**:
- `docs/incident-2025-11-05-schema-migration-and-playwright-fix.md`
- https://playwright.dev/python/docs/actionability

### 具体例：Cloud Scheduler一括更新

**問題**: 全14ジョブのtask_patternがtask_idと同じになっている

**❌ 悪い対応**: 1つずつ手動で修正
```bash
gcloud scheduler jobs update http carewell-class01-task01 ...
gcloud scheduler jobs update http carewell-class01-task02 ...
# ... 14回繰り返し
```

**✅ 良い対応**: 一括更新スクリプト作成
```bash
#!/bin/bash
declare -A JOB_CONFIGS=(
  ["carewell-class01-task01"]="課題①:課題①業務分析　※～11/3〆切"
  # ... 全14ジョブ
)

for job_name in "${!JOB_CONFIGS[@]}"; do
  IFS=':' read -r task_id task_pattern <<< "${JOB_CONFIGS[$job_name]}"
  # 一括更新処理
done
```

### チェックリスト：問題発生時

**調査前の必須確認** (CRITICAL - スキップ禁止):
- [ ] CLAUDE.md の Critical Configuration を確認
- [ ] CLAUDE.md の Common Mistakes を確認
- [ ] メモリファイル（suggested_commands等）を確認
- [ ] 設計ドキュメント（Steering Document）を確認
- [ ] 過去の類似インシデント記録を検索

**調査・対応時**:
- [ ] 環境の制約を理解（ローカルFirestoreは不安定）
- [ ] 根本原因をコードから特定
- [ ] 破壊的操作の前に現状を記録（スナップショット）
- [ ] 一括処理スクリプトを作成（繰り返し作業を避ける）
- [ ] 段階的実施（各フェーズで検証）
- [ ] 全体影響を事前評価
- [ ] Cloud Runログ/Dashboardで検証
- [ ] **タイムアウト関連**: Cloud Scheduler AND Cloud Run の両方確認

**完了後**:
- [ ] 教訓をドキュメント化
- [ ] CLAUDE.md の Common Mistakes に追加
- [ ] メモリファイル更新
- [ ] バックグラウンドプロセスをクリーンアップ

### 参考ドキュメント

- **CLAUDE.md**: Lines 11-42 (CRITICAL: READ THIS FIRST)
- **CLAUDE.md**: Lines 81-126 (Incident Response Workflow)
- **CLAUDE.md**: Lines 224-398 (Common Mistakes to Avoid - 6 incidents)
- **docs/CLASS01_TIMEOUT_ANALYSIS.md**: Lines 689-797 (対応の振り返りと最適解)
- **docs/incident-2025-11-06-cloud-run-timeout.md**: Cloud Run timeout 設定ミス
- **docs/incident-2025-11-05-schema-migration-and-playwright-fix.md**: 2025/11/05 包括的インシデント記録
- **docs/troubleshooting.md**: トラブルシューティングガイド（診断フロー・調査ステップ）

最終更新: 2025-11-06
