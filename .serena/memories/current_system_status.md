# Current System Status

**最終更新**: 2025-11-30 13:15 JST

## ⚠️ 一時停止中の Cloud Scheduler

### carewell-class01-task01 (№01 課題①)

**ステータス**: ⏸️ **PAUSED (一時停止中)**

**理由**:
- ページ2以降の学生（99名）がダウンロード失敗
- `page.go_back()` がタイムアウトで例外発生
- 再遷移ロジックに到達しない（例外で関数から抜ける）

**影響範囲**:
- ページ1: 100名 → ✅ 処理可能
- ページ2: 99名 → ❌ 1人目のみ成功、残り98名失敗
- 成功率: 約51% (101/199)

**問題のコード** (revision 00198-4nn):
```python
# Line 1076付近
self.page.go_back(wait_until="load", timeout=30000)  # ← タイムアウト例外
self._wait_for_navigation()

# Re-navigate to target page if not page 1
if current_page > 1:  # ← ここに到達しない
    # 再遷移ロジック
```

**必要な修正**:
```python
# try-except で囲み、タイムアウトでも再遷移ロジックを実行
try:
    self.page.go_back(wait_until="load", timeout=30000)
    self._wait_for_navigation()
except Exception as e:
    self.logger.warning(f"go_back timeout (expected): {e}")

# Re-navigate to target page if not page 1
if current_page > 1:  # ← タイムアウトでも実行される
    # 再遷移ロジック
```

**修正箇所**:
- Line 1076付近: ダウンロード成功時の go_back()
- Line 1181付近: ダウンロード失敗時の go_back()
- Line 1281付近: エラーリカバリー時の go_back()

**再開条件チェックリスト**:
- [ ] `page.go_back()` を try-except で囲む修正完了
- [ ] Black/isort フォーマット完了
- [ ] Git commit & push 完了
- [ ] GitHub Actions デプロイ成功
- [ ] 新リビジョン作成確認
- [ ] トラフィック100%確認（Common Mistake #7）
- [ ] 新コードのログ確認（"go_back timeout (expected)" が出現）
- [ ] 手動テスト実行 → 199件全収集成功確認

**再開コマンド**:
```bash
gcloud scheduler jobs resume carewell-class01-task01 --location=asia-northeast1
```

**検証コマンド**:
```bash
# 現在のステータス確認
gcloud scheduler jobs describe carewell-class01-task01 --location=asia-northeast1 --format="value(state)"
# 出力: PAUSED
```

---

## 🟢 正常稼働中のサービス

### Cloud Scheduler ジョブ

#### carewell-student-sync-daily (学生データ同期)
**ステータス**: ✅ **ENABLED (稼働中)**

- **スケジュール**: 毎日 JST 02:00
- **機能**: Google Sheets → Firestore 学生データ同期 + Backfill
- **リクエストボディ**: `{"backfill": true}`
- **最終更新**: 2025-11-30

**新機能 (2025-11-30追加)**:
- L列「無効」チェックボックス対応 → `status: "inactive"`
- 全ファイル Backfill (スキップ条件削除)
- Dashboard 手動同期ボタン (`?admin=true`)

#### その他のジョブ
- carewell-class01-task01 〜 carewell-class02-task02
- （全14ジョブ）

すべて正常稼働中

---

## 📝 注意事項

**AIエージェント向け**:
1. セッション開始時に必ずこのファイルを読むこと
2. ユーザーが「～は一時停止中」と言った場合、即座にこのファイルを更新
3. 提案・実行前に必ず一時停止状態を考慮すること
4. 修正完了後、このファイルの再開条件チェックリストを更新すること

**最終更新者**: AI Agent (Claude Code)
