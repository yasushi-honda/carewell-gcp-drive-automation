# Student Sync Feature

**最終更新**: 2025-11-30

## 概要

Google Sheets の学生マスターデータを Firestore に同期し、全ファイルに反映する機能。

## コンポーネント

### Cloud Scheduler Job
- **名前**: `carewell-student-sync-daily`
- **スケジュール**: 毎日 JST 02:00 (`0 17 * * *` UTC)
- **リクエストボディ**: `{"backfill": true}`

### API エンドポイント
- **URL**: `POST /admin/sync-students-from-sheets`
- **認証**: OIDC (Cloud Scheduler) / なし (Dashboard - public)

### Google Sheets
- **ID**: `1AQ12-h3n_NmN2kWxi4Z_g354X0wmUyMKAPeAsXJwu_w`
- **シート名**: `統合_受講者リスト`
- **読み取り範囲**: `A:L`

## L列「無効」フラグ

| L列 | Firestore status |
|-----|-----------------|
| TRUE (チェックあり) | `"inactive"` |
| FALSE / 空 | `"active"` |

## 主要ファイル

```
src/sheets_service.py     # get_student_data() - L列マッピング
src/main.py               # sync_students_from_sheets(), _backfill_all_files()
dashboard/src/App.vue     # 同期ボタン、トースト通知
dashboard/src/composables/useStudentSync.ts  # API呼び出し
```

## Dashboard 手動同期

1. `https://carewell-automation.web.app/?admin=true` でアクセス
2. ヘッダー右上の「データ同期」ボタンをクリック
3. スピナー表示 → トースト通知で結果確認

## 関連ドキュメント

- `docs/STUDENT_SYNC_FEATURE_HANDOVER.md` - 完全引き継ぎドキュメント
- `docs/STUDENT_SYNC_AUTOMATION_HANDOVER.md` - 運用ガイド
