# タイムアウト延長計画

## 📅 作成日
2025-11-03

## 🔗 関連ドキュメント
- [問題分析レポート](./PAGINATION_BUG_ANALYSIS.md)
- [ページネーション修正計画](./PAGINATION_FIX_PLAN.md)

## 🎯 延長の目的

carewell-class01-task01（149件）の処理を完了するため、Cloud SchedulerおよびCloud Runのタイムアウト設定を延長します。

## 📋 現状と問題

### 現在の設定

| 項目 | 現在の値 | 問題 |
|------|---------|------|
| Cloud Scheduler attemptDeadline | 540秒（9分） | ❌ 149件処理には不足 |
| Cloud Run timeout | 540秒（推定） | ❌ 確認・延長が必要 |

### 処理時間の実測データ

**2025-11-03 19:03 JST実行**（タイムアウトで中断）:
- データ取得（149件）: 約14秒
- download link取得（100件）: 約438秒（7分18秒）
- **平均処理時間**: 約4.4秒/件
- **推定必要時間**: 約11-15分
  - download link取得: 149件 × 4.4秒 = 約656秒（10分56秒）
  - ファイルダウンロード・アップロード: 約2-4分（推定）
  - **合計**: 約13-15分

### 問題の詳細

**タイムアウトにより以下が未完了**:
- ✅ ページネーション処理: 成功
- ✅ 1ページ目データ取得: 100件
- ✅ 2ページ目データ取得: 49件
- ❌ ファイルダウンロード: 0件
- ❌ Google Driveアップロード: 0件
- ❌ Firestore記録: 0件
- ❌ Sheets記録: 0件

## 🎯 延長計画

### Phase 1: class01-task01のみタイムアウト延長

**対象**: carewell-class01-task01（149件ケース）のみ

**変更内容**:

| 項目 | 変更前 | 変更後 | 理由 |
|------|--------|--------|------|
| Cloud Scheduler attemptDeadline | 540秒 | **900秒（15分）** | 149件処理に十分な時間を確保 |
| Cloud Run timeout | 540秒 | **900秒（15分）** | Scheduler延長に合わせて延長 |

**安全性**:
- ✅ コード変更なし（設定変更のみ）
- ✅ 他のジョブに影響なし（class01-task01のみ変更）
- ✅ ロールバックが容易（設定を元に戻すだけ）
- ✅ 十分な余裕（推定15分 < 設定15分）

### Phase 2: 他のジョブの評価（将来）

**対象**: 残り6ジョブ

**方針**:
1. 各ジョブの提出件数を監視
2. 100件超えが常態化したジョブから順次延長
3. 現時点では変更不要（全て100件未満）

## 📝 実装手順

### Step 1: Cloud Run timeout設定の確認

```bash
# 現在のCloud Run timeout設定を確認
gcloud run services describe carewell-file-collector \
  --region=asia-northeast1 \
  --format="value(spec.template.spec.timeoutSeconds)"
```

**期待値**: 540（現在の設定）

### Step 2: Cloud Scheduler attemptDeadlineの延長

```bash
# class01-task01のattemptDeadlineを900秒に延長
gcloud scheduler jobs update http carewell-class01-task01 \
  --location=asia-northeast1 \
  --attempt-deadline=900s
```

**確認**:
```bash
# 変更を確認
gcloud scheduler jobs describe carewell-class01-task01 \
  --location=asia-northeast1 \
  --format="value(attemptDeadline)"
```

**期待値**: 900s

### Step 3: Cloud Run timeoutの延長（必要な場合）

**判断基準**: Step 1で540秒未満の場合のみ実施

```bash
# Cloud Run timeoutを900秒に延長
gcloud run services update carewell-file-collector \
  --region=asia-northeast1 \
  --timeout=900
```

**確認**:
```bash
# 変更を確認
gcloud run services describe carewell-file-collector \
  --region=asia-northeast1 \
  --format="value(spec.template.spec.timeoutSeconds)"
```

**期待値**: 900

### Step 4: ドキュメント更新

- README.md: Cloud Scheduler設定セクションを更新
- この計画書: 実施日時と結果を記録

### Step 5: テスト実行

```bash
# class01-task01を手動実行
gcloud scheduler jobs run carewell-class01-task01 \
  --location=asia-northeast1
```

**監視**:
```bash
# リアルタイムでログ監視
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=carewell-file-collector" \
  --project=carewell-automation
```

### Step 6: 検証

**確認項目**:
1. ✅ タイムアウトエラーが発生しない
2. ✅ 149件全件処理完了（"Successfully extracted 149 submissions"）
3. ✅ 件数検証成功（"✓ Count verification passed: 149/149"）
4. ✅ Firestoreに149件記録
5. ✅ Google Drive フォルダ `1gxt-OVloMfJWi73Yjm4v5bjupKL25Pag` に149ファイル
6. ✅ Google Sheetsに149行記録

## 📊 成功基準

### 必須基準

- ✅ タイムアウトエラー（504）が発生しない
- ✅ 149件全件処理完了
- ✅ UI表示件数と処理件数が一致
- ✅ "✓ Count verification passed: 149/149" ログ出力

### 推奨基準

- ✅ 処理時間が900秒未満（十分な余裕）
- ✅ 全ファイルが正しいDriveフォルダにアップロード
- ✅ Firestore・Sheetsへの記録が正常完了

## 🔄 ロールバック計画

### ロールバック条件

以下のいずれかが発生した場合:
1. 新たなエラーが発生
2. 他のジョブに影響
3. その他の重大な問題

### ロールバック手順

```bash
# Cloud Scheduler attemptDeadlineを元に戻す
gcloud scheduler jobs update http carewell-class01-task01 \
  --location=asia-northeast1 \
  --attempt-deadline=540s

# Cloud Run timeoutを元に戻す（延長した場合のみ）
gcloud run services update carewell-file-collector \
  --region=asia-northeast1 \
  --timeout=540
```

## 📈 将来の改善案

### Option 1: パフォーマンス最適化（推奨）

**目的**: 処理時間の短縮

**方法**:
1. download link取得処理の効率化
2. 待機時間の最適化
3. 並列処理の導入（要検討）

**メリット**:
- タイムアウトを元に戻せる
- 全ジョブのパフォーマンス向上

**デメリット**:
- 実装コストが高い
- テストが必要
- リスクが中～高

### Option 2: さらなるタイムアウト延長

**目的**: 提出件数増加への対応

**条件**:
- 200件超えのケースが発生
- パフォーマンス最適化が困難

**変更内容**:
- 900秒 → 1200秒（20分）

## ✅ チェックリスト

### 実施前
- [ ] 問題分析ドキュメントをレビュー
- [ ] 延長計画をレビュー
- [ ] バックアップ・ロールバック手順を確認

### 実施中
- [ ] Cloud Run timeout設定を確認
- [ ] Cloud Scheduler attemptDeadlineを延長
- [ ] Cloud Run timeoutを延長（必要な場合）
- [ ] 変更を確認

### 実施後
- [ ] ドキュメントを更新（README.md）
- [ ] 計画書に実施日時と結果を記録
- [ ] テスト実行
- [ ] ログで検証
- [ ] Firestoreで検証
- [ ] Google Driveで検証
- [ ] Google Sheetsで検証

## 📝 実施記録

### 実施日時
- **予定日**: 2025-11-03
- **実施日**: 2025年11月03日 23:30 (JST)
- **実施者**: Claude Code

### 実施結果

| ステップ | ステータス | 備考 |
|---------|-----------|------|
| Cloud Run timeout確認 | [x] 完了 / [ ] スキップ | 結果: 540秒 |
| Scheduler延長 | [x] 完了 / [ ] 失敗 | 540s → 900s（成功） |
| Cloud Run延長 | [x] 完了 / [ ] スキップ | 540s → 900s（新リビジョン: 00129-bfb） |
| テスト実行 | [ ] 完了 / [ ] 失敗 | 実行時刻: ______ |
| 検証 | [ ] 成功 / [ ] 失敗 | 処理件数: ____ |

### 設定変更詳細

**実施前**:
- Cloud Scheduler attemptDeadline: 540秒
- Cloud Run timeout: 540秒

**実施後**:
- Cloud Scheduler attemptDeadline: 900秒 ✅
- Cloud Run timeout: 900秒 ✅
- Cloud Run 新リビジョン: carewell-file-collector-00129-bfb

### 問題発生時の対応記録
（問題が発生した場合のみ記入）

---

**作成者**: Claude Code
**レビュー**: 要レビュー
**ステータス**: Ready for Implementation
