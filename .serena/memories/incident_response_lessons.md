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

### 実践的な教訓（2025-11-04 インシデントから）

#### ❌ 避けるべきアプローチ
1. ドキュメント確認をスキップして調査開始
2. ローカル環境からFirestoreへの直接アクセスを試行
3. 14個のジョブを1つずつ手動で修正
4. 手動実行テストを複数回試行
5. 失敗が予測される操作でバックグラウンドプロセスを多数起動

#### ✅ 推奨されるアプローチ
1. CLAUDE.md と過去のインシデントを確認
2. 根本原因をコード/設定から特定
3. 一括更新スクリプトを作成（手動作業を避ける）
4. Cloud Runログとダッシュボードで検証
5. 自動実行スケジュールを待つ（手動実行は不安定）

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

- [ ] CLAUDE.md の Critical Configuration を確認
- [ ] CLAUDE.md の Common Mistakes を確認
- [ ] メモリファイル（suggested_commands等）を確認
- [ ] 設計ドキュメントを確認
- [ ] 環境の制約を理解（ローカルFirestoreは不安定）
- [ ] 根本原因をコードから特定
- [ ] 一括処理スクリプトを作成（繰り返し作業を避ける）
- [ ] Cloud Runログ/Dashboardで検証
- [ ] 教訓をドキュメント化
- [ ] バックグラウンドプロセスをクリーンアップ

### 参考ドキュメント

- **CLAUDE.md**: Lines 81-126 (Incident Response Workflow)
- **CLAUDE.md**: Lines 155-229 (Common Mistakes)
- **docs/CLASS01_TIMEOUT_ANALYSIS.md**: Lines 689-797 (対応の振り返りと最適解)

最終更新: 2025-11-04
コミット: a20d9b7
