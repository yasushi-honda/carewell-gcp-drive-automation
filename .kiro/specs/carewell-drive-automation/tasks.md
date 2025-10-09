# 実装計画

- [x] 1. プロジェクト基盤とインフラストラクチャのセットアップ
- [x] 1.1 プロジェクト初期化と依存関係設定
  - Python 3.11+プロジェクト構成を作成
  - requirements.txtに必要なライブラリを定義（playwright, firebase-admin, google-api-python-client, google-auth, google-cloud-secret-manager, google-cloud-logging）
  - Dockerfileを作成してPlaywright + Chromiumをコンテナイメージに含める
  - .gitignoreを設定してシークレット情報の誤コミットを防止
  - _要件: 8.6, 8.7_

- [x] 1.2 Cloud Run Functions用の構成ファイル作成
  - HTTPリクエストハンドラのエントリポイント関数を定義
  - 環境変数とGCPプロジェクト設定を管理
  - メモリ割り当て2GB、タイムアウト540秒の設定を準備
  - _要件: 8.1, 8.6, 8.7_

- [x] 2. 共通基盤層の実装
- [x] 2.1 Secret Manager統合機能の実装
  - Secret ManagerからシークレットIDを指定して値を取得する機能を実装
  - 認証情報（carewell-user-id、carewell-password、service-account-key）を安全に取得
  - シークレット取得失敗時のエラーハンドリングを実装
  - _要件: 1.1, 6.1, 6.2, 6.4_

- [x] 2.2 構造化ロギング機能の実装
  - Cloud Loggingに構造化ログ（JSON形式）を出力する機能を実装
  - 実行ID（UUID）を生成し全ログに含める
  - ログレベル（INFO、WARNING、ERROR）とコンテキスト情報を記録
  - 機密情報（パスワード、APIキー、氏名）をマスキング
  - _要件: 6.5, 6.6, 7.1, 7.6, 9.1, 9.2_

- [x] 2.3 エラーハンドリングとリトライロジックの実装
  - エラー種別に応じたリトライ判定ロジックを実装（最大3回）
  - Exponential backoff（即座、5秒、10秒）を実装
  - リトライ可能エラー/スキップ可能エラー/クリティカルエラーの分類
  - エラーコンテキスト情報（コンポーネント名、操作名、実行ID）の記録
  - _要件: 1.11, 3.9, 4.5, 5.7, 7.2, 7.3_

- [x] 3. データストレージ層の実装
- [x] 3.1 Firestore初期化と接続管理
  - Firebase Admin SDKを初期化してFirestoreクライアントを作成
  - サービスアカウント認証を設定
  - Firestore接続エラーのハンドリング
  - _要件: 4.1, 4.2, 6.3_

- [x] 3.2 重複チェック機能の実装
  - Firestoreで複合キー（日介番号_提出日）の存在チェック機能を実装
  - コレクション階層（{クラス名}/{課題名}/documents）に基づくドキュメント検索
  - 存在チェック結果（true/false）を返す
  - _要件: 2.6, 2.7_

- [x] 3.3 Firestoreメタデータ保存機能の実装
  - ファイルメタデータをFirestoreに保存する機能を実装
  - ドキュメントIDとして複合キーを使用
  - フィールド（composite_key、name、care_number、submitted_at、file_name、file_url、downloaded_at）を保存
  - 書き込み失敗時のリトライロジック（最大3回）
  - _要件: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 4. Google API統合層の実装
- [x] 4.1 サービスアカウント認証基盤の実装
  - Secret Managerからサービスアカウント鍵JSONを取得
  - Google Drive/Sheets APIのスコープを設定
  - サービスアカウント認証情報オブジェクトを生成
  - _要件: 3.6, 5.1, 6.3, 6.4_

- [x] 4.2 Google Driveアップロード機能の実装
  - 一時ファイルをGoogle Driveの指定フォルダにアップロードする機能を実装
  - MediaFileUploadを使用してファイルをアップロード（resumable=True）
  - アップロード後の共有URL（webViewLink）を取得
  - アップロード失敗時のリトライロジック（最大3回）
  - _要件: 3.6, 3.7, 3.8, 3.9_

- [x] 4.3 Google Sheetsデータ記録機能の実装
  - スプレッドシートIDとタスク名からシート存在確認を実装
  - シートが存在しない場合は新規作成してヘッダー行を追加
  - データ行を追記する機能を実装（appendメソッド）
  - カラム順序（複合キー、氏名、日介番号、提出日、ファイル名、ファイルURL、ダウンロード日時）を確保
  - 書き込み失敗時のリトライロジック（最大3回）
  - _要件: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

- [x] 5. ブラウザ自動化層の実装
- [x] 5.1 Playwright初期化とブラウザ起動
  - Playwrightを使用してChromiumをヘッドレスモードで起動
  - 起動オプション（--no-sandbox、--disable-dev-shm-usage）を設定
  - ページタイムアウトを60秒に設定
  - ブラウザ起動失敗時のエラーハンドリング
  - _要件: 1.2_

- [x] 5.2 Carewellログイン機能の実装
  - Carewell Webサービス（https://jaccw-carewel.study.jp/）にアクセス
  - フォーム要素（ctl00$masterMain$txtUserID、ctl00$masterMain$txtPassword）に認証情報を入力
  - ログインボタン（ctl00$masterMain$btnSubmit）をクリック
  - ログイン成功/失敗の判定とエラーハンドリング
  - _要件: 1.2, 1.3, 1.4, 1.5, 1.11_

- [x] 5.3 クラス・課題選択ナビゲーション機能の実装
  - フレーム内の「クラス管理」リンクをクリック
  - 「教科クラス一覧」リンク（target="list"のframe内）をクリック
  - 動的読み込み完了待機（3-10秒）
  - パラメータで指定されたクラス名に一致するリンクを検索してクリック
  - クラス詳細画面の「レポート採点」リンクをクリック
  - パラメータで指定された課題名に一致するリンクを検索してクリック
  - 「全て」タブリンクをクリック
  - ナビゲーション失敗時のエラーハンドリングとリトライ
  - _要件: 1.5, 1.6, 1.7, 1.8, 1.9, 1.10, 1.11, 2.1_

- [x] 6. 提出者データ収集とファイル処理の実装
- [x] 6.1 提出者一覧テーブル解析機能の実装
  - データベースからのデータ取得完了を待機
  - 提出者一覧テーブル（standard_grid_item クラス）を検索
  - 各行から氏名、日介番号、提出日（ctl00_masterMain_gvwMain_ctl*_lblStudyDate）、リンクURLを抽出
  - 日介番号と提出日を連結して複合キーを生成（例: N9903754_20251002095045）
  - 日介番号形式（正規表現 `^N\d{7}$`）と提出日時形式（YYYYMMDDHHMMSS）を検証
  - _要件: 2.2, 2.3, 2.4, 2.5_

- [x] 6.2 ページネーション処理の実装
  - ページネーションセレクト要素（ctl00$masterMain$dpgMain$dpgMain$ctl00$ddlPage）の存在確認
  - 次のページが存在する場合はページ番号を選択して遷移
  - 全ページを巡回して未処理提出者リストを構築
  - _要件: 2.9, 2.10, 2.11_

- [x] 6.3 ファイルダウンロード機能の実装
  - 提出者の氏名リンク（例: ctl00_masterMain_gvwMain_ctl*_hplLoginID）をクリック
  - 提出者詳細画面のフレーム内でダウンロードリンク（download.aspx?id=*）を検索
  - リンクテキストからファイル名を取得
  - ダウンロードリンクをクリックして一時ディレクトリ（/tmp/）に保存
  - ダウンロード失敗時のエラーハンドリングとリトライ
  - ファイル情報（ファイルパス、ファイル名、ファイルサイズ、MIME型）を記録
  - _要件: 3.1, 3.2, 3.3, 3.4, 3.5, 3.11_

- [x] 6.4 「レポート選択」へ戻るナビゲーションの実装
  - 各提出者の処理完了後に「レポート選択」へ戻るリンク（list.aspx?course_id=*&unit_id=*&filter=*）をクリック
  - 一覧画面への遷移確認
  - _要件: 3.12_

- [x] 7. メイン処理フローの統合
- [x] 7.1 Function Entrypointの実装
  - HTTPリクエストをトリガーとして受け付けるエントリポイント関数を実装
  - リクエストボディから必須パラメータ（class_name、task_name、drive_folder_id、spreadsheet_id）を抽出
  - パラメータ検証とHTTP 400エラーレスポンス
  - 実行ID（UUID）を生成して全処理に紐付け
  - _要件: 8.1, 8.2, 8.3, 9.1_

- [x] 7.2 ファイル処理ループの実装
  - 未処理提出者リストを順次処理
  - 各ファイルについて: ダウンロード → Driveアップロード → Firestoreメタデータ保存 → Sheets行追加 → 一時ファイル削除
  - 処理成功/スキップ/失敗の件数をカウント
  - 個別ファイル処理失敗時は次のファイルへ進む
  - _要件: 3.1, 3.10, 6.7_

- [x] 7.3 処理サマリーとHTTPレスポンスの実装
  - 処理完了後にサマリーログ（総処理時間、処理ファイル数、スキップ数、成功数、失敗数）を出力
  - HTTP 200ステータスと処理結果サマリーをJSONで返す
  - エラー発生時はHTTP 500ステータスとエラー詳細をJSONで返す
  - ブラウザインスタンスを確実にクローズ
  - _要件: 7.7, 8.8, 8.9, 9.7_

- [ ] 8. エラー通知機能の実装（オプション：Gmail API調査後）
- [ ] 8.1 Gmail API統合の調査と実装判断
  - サービスアカウントでのGmail API送信可否を調査
  - Domain-wide Delegation設定の要否を確認
  - 代替案（SendGrid、SMTP）の検討
  - _要件: 7.4_

- [ ] 8.2 エラー通知メール送信機能の実装
  - クリティカルエラー発生時にhy.unimail.11@gmail.comへメール送信
  - メール本文にエラー種別、発生時刻、影響範囲、スタックトレース、実行パラメータを含める
  - 認証失敗、Secret Manager接続失敗、連続ファイルダウンロード失敗、Firestore/Sheets API接続失敗時に通知
  - _要件: 7.4, 7.5_

- [ ] 9. テストの実装
- [ ] 9.1 ユニットテストの作成
  - 重複チェックロジックのテスト（Firestoreモック使用）
  - 複合キー生成ロジックのテスト
  - エラーハンドリングとリトライロジックのテスト
  - Secret Manager取得のテスト（モック使用）
  - pytestとunittest.mockを使用
  - _要件: 全要件のロジック検証_

- [ ] 9.2 統合テストの作成
  - Carewell認証→ナビゲーションフローのテスト（テストアカウント使用）
  - ファイルダウンロード→Driveアップロード→Firestore保存フローのテスト
  - 重複チェック→スキップフローのテスト（Firestore Emulator使用）
  - エラーリトライ→通知フローのテスト
  - GCP testing projectでの全体フローテスト
  - _要件: 全要件の統合動作検証_

- [x] 10. デプロイと本番環境設定
- [x] 10.1 GCP環境のセットアップ
  - GCPプロジェクト（carewell-automation）の作成
  - 必要なAPI有効化（Cloud Functions、Secret Manager、Firestore、Drive、Sheets、Gmail）
  - サービスアカウント作成とIAMロール付与
  - _要件: 8.1_

- [x] 10.2 Secret Managerへのシークレット登録
  - carewell-user-id、carewell-password、service-account-key、gmail-api-credentials（要調査）を登録
  - サービスアカウントに適切なアクセス権限を付与
  - _要件: 6.1, 6.2_

- [x] 10.3 Cloud Run Functionsへのデプロイ
  - Dockerfileとrequirements.txtをリポジトリにコミット
  - gcloud functions deployコマンドでデプロイ
  - メモリ2GB、タイムアウト540秒を設定
  - デプロイ成功確認とログ確認
  - _要件: 8.6, 8.7_

- [ ] 10.4 Cloud Schedulerジョブの設定と運用基盤構築
- [ ] 10.4.1 Schedulerジョブ作成準備
  - ジョブ命名規則の確認（carewell-class{番号}-task{番号}）
  - Cron式とオフセット設計（5分刻みで14ジョブ配置）
  - HTTPターゲットURL確認（Cloud Run FunctionsエンドポイントURL取得）
  - OIDC認証用サービスアカウント確認（cloud-scheduler@carewell-automation.iam.gserviceaccount.com）
  - _要件: 10.1, 10.2, 10.3, 10.4_
- [ ] 10.4.2 初期Schedulerジョブ作成（現在の7クラス×2課題=14ジョブ）
  - クラス01・課題01-02のジョブ作成（Cron: 0,30と5,35）
  - クラス02・課題01-02のジョブ作成（Cron: 10,40と15,45）
  - クラス03・課題01-02のジョブ作成（Cron: 20,50と25,55）
  - クラス04-07・課題01-02のジョブ作成（以降5分刻み）
  - 各ジョブのHTTPリクエストボディ設定（class_name、task_name、drive_folder_id、spreadsheet_id）
  - 全ジョブのタイムゾーン設定（Asia/Tokyo）
  - _要件: 10.1, 10.5_
- [ ] 10.4.3 Schedulerジョブ初回実行検証
  - 各ジョブの手動トリガーテスト（gcloud scheduler jobs run）
  - 実行ログ確認（Cloud Logging）
  - 実行結果確認（Firestore、Drive、Sheets）
  - エラー発生時の修正と再実行
  - _要件: 10.10_
- [ ] 10.4.4 監視・アラート設定
  - Cloud Loggingログベースメトリクス作成（file_processed_count、file_skipped_count、file_failed_count、execution_time_ms）
  - Cloud Monitoringアラートポリシー作成（エラー率20%超過、連続3回失敗、実行時間8分超過）
  - 通知チャネル設定（hy.unimail.11@gmail.com）
  - ダッシュボード作成（実行成功率、処理ファイル数推移、平均実行時間、エラー発生状況）
  - _要件: 10.11, 10.12_
- [ ] 10.4.5 運用手順書作成
  - ジョブライフサイクル管理手順（新規作成・一時停止・再開・パラメータ更新・削除）
  - 日常運用タスク一覧（ジョブ実行状況確認、エラーログ確認、ダッシュボード確認）
  - トラブルシューティングフロー図
  - 緊急時対応手順（全ジョブ連続失敗、API quota超過、Function OOM）
  - コスト分析レポート（24時間 vs 6-22時、現在14ジョブ vs 最大40ジョブ）
  - _要件: 10.6, 10.7, 10.8, 10.9, 10.13, 10.14, 10.15_
- [ ] 10.4.6 1週間監視期間
  - 全Schedulerジョブの定期実行監視
  - エラー率・処理ファイル数・実行時間の記録
  - 異常検知時の対応とログ記録
  - 監視期間完了後のレビューと改善
  - _要件: 全運用要件の検証_

- [x] 10.5 手動テスト実行と本番稼働開始
  - テスト用パラメータでFunction手動トリガー
  - Firestore、Drive、Sheetsにデータが正しく保存されているか確認
  - エラーログとメトリクスの確認
  - 定期実行が成功するか1週間監視
  - _要件: 全要件の本番動作検証_

- [ ] 11. task_id導入とパラメータ構造改善
- [ ] 11.1 HTTPパラメータ仕様変更
  - main.pyでtask_idとtask_patternパラメータを追加
  - リクエスト検証ロジックを更新（task_id、task_pattern必須）
  - 既存task_nameパラメータを削除
  - パラメータバリデーションエラーメッセージ更新
  - _要件: 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

- [ ] 11.2 Playwright課題検索の部分一致対応
  - playwright_automation.pyのnavigate_to_task()メソッド修正
  - task_patternパラメータを受け取るように変更
  - 課題リンク検索を完全一致から部分一致（:has-text）に変更
  - 検索失敗時のエラーログにtask_patternを含める
  - _要件: 8.4, 1.10_

- [ ] 11.3 Firestoreコレクション構造変更
  - firestore_service.pyのコレクションパス生成をtask_id使用に変更
  - check_duplicate()メソッドでtask_idを使用（{class_name}/{task_id}/documents）
  - save_metadata()メソッドでtask_idをドキュメントフィールドに追加
  - save_metadata()メソッドのコレクションパスをtask_id使用に変更
  - _要件: 8.5, 4.1, 4.2, 4.3_

- [ ] 11.4 Google Sheetsカラム構造変更
  - sheets_service.pyのシート名をtask_id使用に変更
  - ヘッダー行を更新（A: 課題ID、B: 複合キー、C: 氏名、...）
  - append_row()メソッドでtask_idをカラムAに追加
  - 既存シート互換性チェックロジック追加（ヘッダー行確認）
  - _要件: 8.6, 8.7, 5.3, 5.4, 5.5_

- [ ] 11.5 test_request.json更新
  - test_request.jsonにtask_idパラメータ追加
  - test_request.jsonにtask_patternパラメータ追加
  - 既存task_nameパラメータを削除
  - _要件: 8.2_

- [ ] 11.6 テストデータクリーンアップと検証
  - Firestoreテストデータ削除（旧コレクション構造）
  - Sheetsテストデータ削除（旧カラム構造）
  - 新パラメータでFunction手動テスト実行
  - Firestore新コレクション構造確認（{class_name}/{task_id}/documents）
  - Sheets新カラム構造確認（A: 課題ID、B: 複合キー、...）
  - ログ出力確認（task_id、task_pattern含む）
  - _要件: 全要件の新仕様検証_
