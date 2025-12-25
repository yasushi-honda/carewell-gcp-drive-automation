# Current System Status

**最終更新**: 2025-12-25 JST

## 🟢 システム全体ステータス

**全 Cloud Scheduler ジョブが正常稼働中 (ENABLED)**

---

## 📊 クラス・ジョブ一覧

### ファイル収集ジョブ（全16ジョブ）

| クラス | 課題① | 課題② | スケジュール |
|--------|--------|--------|--------------|
| №01 | ✅ ENABLED | ✅ ENABLED | 0,30 / 5,35 |
| №02 | ✅ ENABLED | ✅ ENABLED | 10,40 / 15,45 |
| №03 | ✅ ENABLED | ✅ ENABLED | 20,50 / 25,55 |
| №04 | ✅ ENABLED | ✅ ENABLED | 0,30 / 5,35 |
| №05 | ✅ ENABLED | ✅ ENABLED | 10,40 / 15,45 |
| №08 | ✅ ENABLED | ✅ ENABLED | 20,50 / 25,55 |
| №09 | ✅ ENABLED | ✅ ENABLED | 0,30 / 5,35 |
| №10 | ✅ ENABLED | ✅ ENABLED | 3,33 / (pattern10) |

### 受講生同期ジョブ

| ジョブ名 | ステータス | スケジュール |
|----------|-----------|--------------|
| carewell-student-sync-daily | ✅ ENABLED | 毎日 JST 02:00 |

---

## 🆕 №10 クラス追加情報 (2025-12-25)

**追加対応済み**:
- ✅ Cloud Scheduler ジョブ作成 (`carewell-class10-task01`, `carewell-class10-task02`)
- ✅ Dashboard `KNOWN_CLASSES` に追加
- ✅ Dashboard `CLASS_NAME_MAPPING` に `No10` マッピング追加
- ✅ Google Sheets 受講生データ同期完了（257名）
- ✅ 受講生一覧クラスフィルター数値順ソート対応

**現在の状況**:
- Carewell Web に提出物がまだないため、ファイル収集は 0件
- テーブル行待機でタイムアウト（想定内の動作）
- 提出物が増えれば自動収集開始

---

## 📝 注意事項

**AIエージェント向け**:
1. セッション開始時に必ずこのファイルを読むこと
2. ジョブ状態変更時はこのファイルを更新すること
3. 新クラス追加時は以下を確認:
   - Cloud Scheduler ジョブ
   - `dashboard/src/config/classes.ts` (KNOWN_CLASSES, CLASS_NAME_MAPPING)
   - Google Sheets 受講生データ → 同期実行

**最終更新者**: Claude Code
