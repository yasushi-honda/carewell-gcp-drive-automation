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
