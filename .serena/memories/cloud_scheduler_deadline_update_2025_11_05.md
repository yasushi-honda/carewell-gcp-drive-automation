# Cloud Scheduler Deadline更新記録（2025-11-05）

## 📅 更新日時
2025-11-05

## 🎯 目的
Cloud Scheduler Deadlineを延長し、タイムアウト率30%を5%未満に改善

## 📊 問題の概要

### 実行統計（2025-11-05 05:00-09:30）
```
成功:        5回 (50.0%)  - 平均実行時間: 約10分
タイムアウト: 3回 (30.0%)  - すべて15分超過
エラー:      1回 (10.0%)  - URL_UNREACHABLE
混合状態:    1回 (10.0%)  - 処理完了(12分)だがSchedulerタイムアウト判定
```

### 根本原因
1. **Deadline設定が短すぎる**: 
   - class01-task01: 900秒（15分）
   - 他のclassジョブ: 540秒（9分）
   
2. **実行時間の実績**:
   - 最短: 23秒
   - 平均: 約10分
   - 最長成功: 14分37秒（余裕わずか23秒）
   
3. **外部依存の影響**:
   - Carewell Webサイトのサーバー応答速度が変動
   - ピーク時にはテーブル読み込みが60秒を超えることがある
   - Phase 1-6の対策でコード側は限界に達している

### スケジュール設計との整合性

各ジョブは30分間隔で実行、開始時刻を5分ずつずらしている：
```
class01-task01:  0,30  (00分, 30分)
class01-task02:  5,35  (05分, 35分)
class02-task01: 10,40  (10分, 40分)
class02-task02: 15,45  (15分, 45分)
class03-task01: 20,50  (20分, 50分)
class03-task02: 25,55  (25分, 55分)
class04-task01:  0,30  (00分, 30分)
class04-task02:  5,35  (05分, 35分)
class05-task01: 10,40  (10分, 40分)
class05-task02: 15,45  (15分, 45分)
class08-task01: 20,50  (20分, 50分)
class08-task02: 25,55  (25分, 55分)
class09-task01:  0,30  (00分, 30分)
class09-task02:  5,35  (05分, 35分)
```

**重要**: 30分間隔のため、Deadlineは30分未満である必要がある
- 30分Deadline → 実行オーバーラップのリスク
- 25分Deadline → 5分のクッションで安全

## ✅ 実施した対応

### 設定変更内容

**変更前**:
```
class01-task01:       900秒（15分）
class01-task02:       540秒（ 9分）
class02-05, 08, 09:   540秒（ 9分）
```

**変更後**:
```
全classジョブ:        1500秒（25分）に統一
```

### Deadline 25分（1500秒）を選択した理由

1. **実行間隔との整合性**:
   - スケジュール: 30分間隔
   - Deadline: 25分
   - クッション: 5分（実行オーバーラップを防止）

2. **実績データとの照合**:
   - 最長成功例: 14分37秒
   - 25分設定: 14分37秒 + 余裕10分23秒 = 十分な余裕
   - 現在の15分: 14分37秒 + 余裕23秒 = ギリギリすぎる

3. **期待される改善**:
   - タイムアウト率: 30% → <5%
   - 成功率: 50% → 95%以上
   - 余裕: 1.67倍（15分→25分）

## 🔧 実装コマンド

```bash
# 全classジョブのDeadlineを25分（1500秒）に更新
for job in carewell-class01-task01 carewell-class01-task02 \
           carewell-class02-task01 carewell-class02-task02 \
           carewell-class03-task01 carewell-class03-task02 \
           carewell-class04-task01 carewell-class04-task02 \
           carewell-class05-task01 carewell-class05-task02 \
           carewell-class08-task01 carewell-class08-task02 \
           carewell-class09-task01 carewell-class09-task02; do
  gcloud scheduler jobs update http "$job" \
    --location=asia-northeast1 \
    --attempt-deadline=1500s
  echo "✓ Updated $job: 1500s (25 min)"
done
```

## 📊 期待される効果

| 項目 | 変更前 | 変更後 | 改善率 |
|------|--------|--------|--------|
| Deadline | 15分 | 25分 | +67% |
| 余裕（最長例基準） | 23秒 | 10分23秒 | +26倍 |
| タイムアウト率 | 30% | <5% | -83% |
| 成功率 | 50% | >95% | +90% |
| 実行オーバーラップリスク | あり（30分設定時） | なし（5分クッション） | - |

## ✅ 検証計画

### 検証方法
1. 次回の自動実行（毎時0分・30分）を待つ
2. Cloud Runログで実行結果を確認
3. Cloud Schedulerステータスで成功/失敗を確認

### 確認コマンド
```bash
# Cloud Schedulerログ確認
gcloud logging read 'resource.type="cloud_scheduler_job" AND 
  resource.labels.job_id="carewell-class01-task01" AND 
  resource.labels.location="asia-northeast1"' --limit 10

# Cloud Runログ確認
gcloud logging read 'resource.type="cloud_run_revision" AND 
  resource.labels.service_name="carewell-file-collector"' --limit 50
```

### 成功基準
- ✅ タイムアウトエラー（DEADLINE_EXCEEDED）が発生しない
- ✅ 全ジョブがHTTP 200で正常完了
- ✅ 実行時間が25分以内
- ✅ 次回実行と5分以上の間隔が空く

## 📝 関連ドキュメント

- `docs/CLASS01_TIMEOUT_ANALYSIS.md`: タイムアウト問題の詳細分析
- `MANDATORY_INCIDENT_CHECKLIST`: インシデント対応手順
- `incident_response_lessons`: 過去のインシデントからの教訓
- `timeout_troubleshooting_methodology`: タイムアウト問題のトラブルシューティング方法

## 💡 今後の課題

### 短期（1週間）
- [ ] 25分Deadline設定後の実行統計を収集（最低10回）
- [ ] タイムアウト率が5%未満になることを確認
- [ ] 他のclassジョブ（class02-05, 08, 09）の動作確認

### 中期（1ヶ月）
- [ ] 提出数増加時の影響を監視
- [ ] 必要に応じてDeadlineの微調整
- [ ] モニタリングアラートの設定

### 長期（検討事項）
- [ ] 非同期レスポンス設計の検討（Cloud Runで即座に202 Acceptedを返却）
- [ ] Carewell Webサイト側のパフォーマンス改善依頼

## 🎓 教訓

1. **スケジュール間隔との整合性を常に考慮する**
   - Deadlineは実行間隔より短く設定する必要がある
   - クッション期間を確保して実行オーバーラップを防止

2. **実績データに基づいた設定を行う**
   - 最長成功例を基準に、十分な余裕を持たせる
   - 外部依存の影響を考慮する

3. **コード側の対策には限界がある**
   - Phase 1-6で十分な対策を実施済み
   - インフラ設定（Deadline）で対応すべき問題もある

---

**更新者**: AI Assistant  
**承認**: ユーザー承認済み  
**実施日**: 2025-11-05  
**ステータス**: 実施完了予定
