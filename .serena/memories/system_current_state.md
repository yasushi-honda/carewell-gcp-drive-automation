# システム現在状態 (MUST READ FIRST)

**最終更新**: 2025-11-07 23:00 JST
**更新者**: AI Agent

---

## 🚨 CRITICAL: Cloud Scheduler 状態

### 現在の状態
- **ステータス**: ⚠️ **1ジョブのみ停止中 (PAUSED)**
- **停止ジョブ**: `carewell-class01-task01` のみ
- **停止理由**: エラー修正完了まで手動停止
- **停止日時**: 2025-11-06
- **再開条件**: 失敗率が5%未満に改善されるまで

### 影響
- ❌ **`carewell-class01-task01` は自動実行されません**
- ✅ **`carewell-class01-task01` のテストは手動実行が必須**
- ✅ **他の13ジョブは通常通り自動実行されます**

### 停止中のジョブ
- `carewell-class01-task01` (PAUSED) ← **これのみ**

### 稼働中のジョブ（自動実行継続中）
- carewell-class01-task02 (ENABLED)
- carewell-class02-task01 (ENABLED)
- carewell-class02-task02 (ENABLED)
- carewell-class03-task01 (ENABLED)
- carewell-class03-task02 (ENABLED)
- carewell-class04-task01 (ENABLED)
- carewell-class04-task02 (ENABLED)
- carewell-class05-task01 (ENABLED)
- carewell-class05-task02 (ENABLED)
- carewell-class08-task01 (ENABLED)
- carewell-class08-task02 (ENABLED)
- carewell-class09-task01 (ENABLED)
- carewell-class09-task02 (ENABLED)

---

## 📊 現在の問題

### STEP 1 Pagination Control 検出失敗
- **検出率**: 0% (Revision 00221-qnf時点)
- **失敗件数**: 49/200 (24.5%)
- **根本原因**: Frame Context Temporal Degradation
  - 2分前に取得したFrameオブジェクトが古くなる
  - Pagination control検索時にはFrameが無効化されている

### 実装済みの修正 (Revision 00223-6mx)
- ✅ STEP 1: Frame refresh FIRST + 15秒待機 + 診断ログ
- ✅ STEP 2: 診断ログ追加 (go_back後の状態記録)
- ✅ 学生ループ: 診断ログ追加 (学生情報記録)
- ✅ デプロイ完了: 2025-11-07 22:26 JST
- ⏳ テスト実行: 未実施

---

## 🎯 次のアクション

### 手動テスト実行 (最優先)
`carewell-class01-task01` のCloud Schedulerが停止中のため、**手動テストが必須**です。

```bash
curl -s -w "\nHTTP_CODE:%{http_code}\n" \
  -X POST https://carewell-file-collector-imczapxkba-an.a.run.app \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -d '{
  "class_name": "令和7年度 デジタル中核人材養成研修 №01",
  "task_id": "課題①",
  "task_pattern": "課題①業務分析　※～11/3〆切",
  "drive_folder_id": "1gxt-OVloMfJWi73Yjm4v5bjupKL25Pag",
  "spreadsheet_id": "1R1bsr24uyFf67p7_0I0yUA47ap5uIrJE7n89A9NbRYI"
}' 2>&1 | head -30
```

### テスト後のログ確認
```bash
# STEP 1ログ確認
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  resource.labels.revision_name=carewell-file-collector-00223-6mx" \
  --limit 500 --format json | \
  jq -r '.[] | select(.textPayload) | .textPayload' | \
  grep -E "\[STEP 1|Frame refreshed|Pagination control\]"
```

---

## 📌 重要なリマインダー

### 新しいAIエージェントへ
1. ✅ **このMemory Fileを最初に読んでください**
2. ✅ **`carewell-class01-task01` のみ停止中 - このジョブは手動テストが必須**
3. ✅ **№01 課題① の自動実行を待つ選択肢はありません**
4. ✅ **デプロイ後は必ず手動テスト実行（№01 課題①の場合）**

### デプロイ後の必須確認事項
1. [ ] 新しいリビジョンが作成されたか
2. [ ] トラフィックが100%新リビジョンに向いているか
3. [ ] イメージダイジェストが前のリビジョンと異なるか
4. [ ] **手動テストを実行したか** ← `carewell-class01-task01` 停止中のため必須
5. [ ] 新しいコードのログが出力されているか

---

## 🔗 関連ドキュメント

- `docs/QUICKSTART.md` - システム概要
- `docs/test-analysis-2025-11-07-revision-00221-step1-retry-logic.md` - 最新テスト分析
- `.serena/memories/incident_response_lessons.md` - 過去のインシデント教訓
