# Phase 11 本番環境テスト計画書

> 📌 このドキュメントの対象・保存先IDは全て令和7年度時点のもの（№10も未収録）。令和8年度でも
> そのまま流用してよいかは未検証（`docs/SERVICE_SHUTDOWN_AND_RESUME.md`「令和8年度再開ステータス」
> 参照）。令和8年度用にこのテスト計画を再利用する場合は、保存先IDを確認・更新してから使うこと。

## テスト概要

### 目的
task_id/task_pattern分離実装（Phase 11）の本番環境における動作検証

### テスト範囲
- 全7クラス × 2課題 = 14パターン
- HTTPリクエスト〜データ保存までのエンドツーエンドテスト

### テスト環境
- **Cloud Run**: https://carewell-file-collector-imczapxkba-an.a.run.app
- **Firestore Database**: carewell-native
- **Google Drive**: 各クラス専用フォルダ
- **Google Sheets**: 各クラス専用スプレッドシート

## テストパターン

### クラス一覧
1. 令和7年度 デジタル中核人材養成研修 №01
2. 令和7年度 デジタル中核人材養成研修 №02
3. 令和7年度 デジタル中核人材養成研修 №03
4. 令和7年度 デジタル中核人材養成研修 №04
5. 令和7年度 デジタル中核人材養成研修 №05
6. 令和7年度 デジタル中核人材養成研修 №08
7. 令和7年度 デジタル中核人材養成研修 №09

### 課題一覧
1. 課題① (検索パターン: "課題①")
2. 課題② (検索パターン: "課題②")

### 設定データ

| クラス | Drive Folder ID | Spreadsheet ID |
|--------|-----------------|----------------|
| №01 | 1gxt-OVloMfJWi73Yjm4v5bjupKL25Pag | 1R1bsr24uyFf67p7_0I0yUA47ap5uIrJE7n89A9NbRYI |
| №02 | 1yJ60hEUHCHGOZNdMbACteoM5C2-pPVmC | 1qmczJQo2f3rSsZxhRWF3XfjCVc5Y3yW7K4wrk7bAcnc |
| №03 | 1IR81q87NIN9PkUAUDZpW9c2XZdkWTM7p | 1kzDATIoQ1hOM9KYuYloCPsbmGn-tSDHSwYxK9pYQkwA |
| №04 | 1OuJk_u1Ig9CfIVXu3n5wQu0Ft6lfr3jQ | 12Xg8Edrtloct-jk_IBVApnqLVz6fPeQFTxxQDPXxi_Q |
| №05 | 1rNnmEJ92smjkcKFOd1L_u1n8SO1LDAC4 | 1CPVDaX4E3AX3xl5I_sm-DjRVr7SfYKz4DjoBSS-h74o |
| №08 | 1kdKwI7nQ8N6j8gD6agZap5FWL-uDTbwg | 1Zm2ePE2gbKm8Yw_4B6vuO8HP3kfN2wZpFCQaNFHfcsk |
| №09 | 1nllFEyyDEV7jiTSEgyBnnNeXhC_4Ttu6 | 1O8S3w3F8RvLJp0LrS-eZtX0sZW5HcjOgMhyWJ_e8YPA |

## テスト項目

### 1. HTTPリクエスト検証
- [ ] リクエストパラメータ受付（task_id, task_pattern）
- [ ] パラメータバリデーション
- [ ] 認証成功

### 2. Playwright自動化検証
- [ ] Carewellログイン成功
- [ ] クラス選択成功
- [ ] 課題検索成功（部分一致）
- [ ] 提出一覧取得成功

### 3. ファイル処理検証
- [ ] ファイルダウンロード成功
- [ ] Google Driveアップロード成功
- [ ] ファイル重複検知動作

### 4. Firestore検証
- [ ] コレクション構造: `{class_name}/{task_id}/documents`
- [ ] ドキュメントID: composite_key形式
- [ ] 必須フィールド存在（task_id, student_id, filename, etc.）

### 5. Google Sheets検証
- [ ] シート名: task_id（"課題①" or "課題②"）
- [ ] ヘッダー行: 課題ID | 複合キー | 氏名 | 日介番号 | 提出日 | ファイル名 | ファイルURL | ダウンロード日時
- [ ] データ行: 全フィールド正常記録

## テスト手順

### 準備フェーズ
1. Cloud Runデプロイ確認（最新コミット反映済み）
2. 認証設定確認（ADC or サービスアカウント）
3. テストデータクリーンアップ（オプション）
   - Firestore: 旧データ削除
   - Sheets: 旧データ削除

### 実行フェーズ
1. テストスクリプト実行（14パターン順次実行）
2. 各リクエスト後30秒待機（ブラウザ操作完了待ち）
3. レスポンスログ記録
4. エラー発生時は詳細ログ取得

### 検証フェーズ
1. HTTPレスポンス確認（200 OK、ダウンロード件数）
2. Cloud Runログ確認（エラー有無）
3. Firestore確認（全14パターンのデータ存在）
4. Sheets確認（全14シートのデータ存在）
5. Drive確認（ファイル存在）

## 成功基準

### 必須条件
- [ ] 全14パターンでHTTP 200レスポンス
- [ ] Firestore: 全14パターンでコレクション作成
- [ ] Sheets: 全14シート（課題①×7、課題②×7）作成
- [ ] エラーログ0件（重複スキップは除く）

### 推奨条件
- [ ] 実行時間: 各パターン3分以内
- [ ] ファイル取得: 各課題で1件以上
- [ ] 重複検知: 2回目実行時に正常動作

## リスクと対策

### リスク
1. **ブラウザタイムアウト**: Carewell画面の読み込みが遅い
   - 対策: timeout設定を180秒に設定済み
2. **並列実行競合**: 同時実行によるブラウザ競合
   - 対策: 順次実行、各リクエスト間に30秒待機
3. **認証エラー**: Secret Manager認証情報の問題
   - 対策: 事前に認証情報確認
4. **課題名変更**: Carewell側で課題名が変更されている
   - 対策: 部分一致検索（:has-text）で対応済み

## ロールバック計画

テスト失敗時:
1. Cloud Runログでエラー原因特定
2. コード修正が必要な場合は修正・再デプロイ
3. データクリーンアップして再テスト

## テスト実施者

- 実施日時: 2025-10-09
- 実施者: Claude Code (with User approval)
- 承認者: User

## テスト結果記録フォーマット

各テストパターンで以下を記録:
```
パターンID: №01-課題①
実行時刻: YYYY-MM-DD HH:MM:SS
HTTPステータス: 200
レスポンス: {"status": "success", "submissions_found": X, "processed": Y, ...}
Firestore確認: ✓ コレクション存在
Sheets確認: ✓ シート「課題①」存在、データX件
Drive確認: ✓ ファイルX件
備考: -
```
