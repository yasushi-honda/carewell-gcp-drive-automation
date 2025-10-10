# Cloud Scheduler Jobs Backup

バックアップ日時: $(date '+%Y-%m-%d %H:%M:%S')

## 旧ジョブ情報

これらは旧システム（carewell-automation）向けのジョブです。
フェーズ11移行に伴い、新システム（carewell-file-collector）向けに再作成します。

### 旧システムの特徴
- URL: https://carewell-automation-61759806259.asia-northeast1.run.app/run
- パラメータ: target_training, sheet_name, spreadsheet_id, environment

### 新システムの特徴
- URL: https://carewell-file-collector-imczapxkba-an.a.run.app
- パラメータ: class_name, task_id, task_pattern, drive_folder_id, spreadsheet_id

## バックアップファイル

- pattern1.yaml
- pattern2.yaml
- pattern3.yaml
- pattern4.yaml
- pattern5.yaml
- pattern8.yaml
- pattern9.yaml

## 復元方法

万が一ロールバックが必要な場合は、これらのYAMLファイルを参照して
gcloud scheduler jobs create コマンドで再作成してください。
