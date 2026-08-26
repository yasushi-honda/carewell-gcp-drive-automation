# Current System Status

**最終更新**: 2026-04-03 JST

## 🔴 システム全体ステータス

**サービス停止中（年度区切り課金完全停止）**

詳細: `docs/SERVICE_SHUTDOWN_AND_RESUME.md`

---

## 📊 Cloud Scheduler ジョブ一覧（全25ジョブ PAUSED）

### ファイル収集ジョブ（全16ジョブ）

| クラス | 課題① | 課題② | スケジュール |
|--------|--------|--------|--------------|
| №01 | ⏸ PAUSED | ⏸ PAUSED | 0,30 / 5,35 |
| №02 | ⏸ PAUSED | ⏸ PAUSED | 10,40 / 15,45 |
| №03 | ⏸ PAUSED | ⏸ PAUSED | 20,50 / 25,55 |
| №04 | ⏸ PAUSED | ⏸ PAUSED | 0,30 / 5,35 |
| №05 | ⏸ PAUSED | ⏸ PAUSED | 10,40 / 15,45 |
| №08 | ⏸ PAUSED | ⏸ PAUSED | 20,50 / 25,55 |
| №09 | ⏸ PAUSED | ⏸ PAUSED | 0,30 / 5,35 |
| №10 | ⏸ PAUSED | ⏸ PAUSED | 3,33 / (pattern10) |

### 受講生同期ジョブ

| ジョブ名 | ステータス |
|----------|-----------|
| carewell-student-sync-daily | ⏸ PAUSED |

### パターン自動化ジョブ（全9ジョブ）

| ジョブ名 | ステータス |
|----------|-----------|
| carewell-automation-pattern1〜5,8,9,10 | ⏸ PAUSED |

---

## 🛑 停止済みリソース（2026-04-03）

- **GitHub Actions**: 全5ワークフロー disabled
- **Cloud Scheduler**: 全25ジョブ PAUSED
- **Cloud Run**: min-instances=0のまま（課金ゼロ）
- **Artifact Registry**: latestイメージのみ保持

## ✅ データ保持中（停止後も維持）

- **Firestore** (`carewell-native`): データそのまま保持
- **Firebase Hosting** (`carewell-automation.web.app`): Dashboard閲覧可能
- **Secret Manager**: 2シークレット保持
- **Google Drive / Sheets**: データ保持

---

## 🔄 再開手順

`docs/SERVICE_SHUTDOWN_AND_RESUME.md` の「再開手順（来年度）」を参照:
1. GitHub Actions ワークフロー有効化
2. Cloud Scheduler ジョブ再開
3. 動作確認

---

## 📝 注意事項

**AIエージェント向け**:
1. セッション開始時に必ずこのファイルを読むこと
2. **サービスは停止中**。再開前に `docs/SERVICE_SHUTDOWN_AND_RESUME.md` を確認
3. ジョブ状態変更時はこのファイルを更新すること
4. 新クラス追加時は以下を確認:
   - Cloud Scheduler ジョブ
   - `dashboard/src/config/classes.ts` (KNOWN_CLASSES, CLASS_NAME_MAPPING)
   - Google Sheets 受講生データ → 同期実行

**最終更新者**: Claude Code
