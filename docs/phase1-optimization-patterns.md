# Phase 1最適化ベストプラクティスガイド

**最終更新**: 2025-11-09
**対象**: Phase 1（URL収集フェーズ）の処理時間最適化

---

## 📖 このドキュメントの目的

Phase 1最適化時の**正しいアプローチ**と**禁止パターン**を明確化し、過去のインシデント（go_backスキップによる全員失敗）の再発を防止する。

---

## 🏗️ Phase 1アーキテクチャ理解（必読）

### Phase 1とPhase 2の分離

本システムは2フェーズ処理を採用：

```mermaid
graph LR
    A[Cloud Scheduler] --> B[Phase 1: URL収集]
    B --> C[Phase 2: ファイル処理]
    C --> D[完了]

    style B fill:#e1f5ff
    style C fill:#d4edda
```

**Phase 1（URL収集）**:
- Playwrightでブラウザ自動操作
- 各学生の詳細ページでURL・ファイル名を取得
- **go_back()でリストページに戻る** ← 次の学生処理の前提条件
- `submissions[]`配列に格納

**Phase 2（ファイル処理）**:
- `submissions[]`をループ
- ファイルダウンロード・Drive保存・Firestore記録

**重要**: Phase 1が完全に終了してから、Phase 2が開始

---

### go_back()の役割（最重要）

**go_back()は詳細ページからリストページに戻る唯一の手段**

```
# 処理フロー
詳細ページ（report.aspx?log_id=8559）
  ↓ go_back()で戻る
リストページ（list.aspx）← STEP 2の前提条件
  ↓ STEP 2: pagination control検索
元のページ（Page 2）
```

**代替手段は存在しない**:
- ❌ `frame.goto(list_url)` → ViewState情報が失われる
- ❌ ブラウザリロード → セッション切れの可能性
- ✅ `page.go_back()` → 唯一の正しい方法

**Reference**: `docs/playwright-page-navigation-flow.md` Lines 182-185

---

## ✅ 最適化の3大原則

### 原則1: スキップではなく短縮

```python
# ❌ Wrong: 必須処理をスキップして時間削減
if current_page > 1:
    # Skip go_back() → 詳細ページに留まる → 次の学生失敗
    pass
else:
    self.page.go_back(...)

# ✅ Correct: タイムアウトを短縮して時間削減
try:
    self.page.go_back(wait_until="load", timeout=30000)  # 180秒 → 30秒
except Exception as e:
    self.logger.warning(f"go_back timeout expected: {e}")
```

**効果**:
- 処理時間: 180秒/件 → 30秒/件（150秒削減、83%削減）
- 成功率: 維持（go_backは必ずタイムアウトするが、正常動作）

### 原則2: ドキュメント確認必須

ナビゲーション処理を変更する前に、必ず以下を確認：

1. `docs/playwright-page-navigation-flow.md` Lines 182-185
2. `docs/pagination-viewstate-solution-2025-11-06.md` Lines 136-139, 170-171
3. `CLAUDE.md` Common Mistakes（特に#9, #11）

### 原則3: 1人目=2人目以降で同じ挙動

**テスト時の確認ポイント**:
- ✅ 1人目と2人目で同じフローを通るか確認
- ✅ 条件分岐で挙動が変わる場合、両方テスト
- ❌ 1人目のみ成功・2人目以降失敗 = 状態引き継ぎミス

---

## ❌ 禁止パターン（絶対に避ける）

### 禁止1: 必須処理のスキップ

```python
# ❌ Forbidden
if current_page > 1:
    # Skip go_back() to avoid timeout
    self.logger.info("Skipping go_back()")
    # → 詳細ページに留まる
    # → 次の学生処理時にpagination control見つからず失敗
```

**影響**: 2人目以降全員失敗（1/200成功 = 0.5%成功率）

**Incident**: 2025-11-08、コミット bbd61ab

### 禁止2: frame.goto()でのリストページ遷移

```python
# ❌ Forbidden
list_frame.goto(list_url)
# → ViewState情報が失われる
# → STEP 2のpagination control操作が失敗

# ✅ Correct
self.page.go_back(wait_until="load", timeout=30000)
```

### 禁止3: wait_until="domcontentloaded"の使用

```python
# ❌ Forbidden
self.page.go_back(wait_until="domcontentloaded", timeout=10000)
# → DOM読込完了を待つだけ
# → ViewState再構築が未完了

# ✅ Correct
self.page.go_back(wait_until="load", timeout=30000)
# → ページ全体の読込完了を待つ
# → ViewState再構築に対応
```

**Reference**: `docs/pagination-viewstate-solution-2025-11-06.md` Lines 136-139

---

## ✅ 推奨: タイムアウト短縮パターン

### 実装例

```python
# go_back()タイムアウト短縮（3箇所に適用）
# - Success Path
# - TimeoutError Path
# - Exception Path

try:
    self.page.go_back(
        wait_until="load",      # ページ全体の読込完了を待つ
        timeout=30000           # 30秒（180秒から短縮）
    )
except Exception as e:
    self.logger.warning(
        f"[PHASE 1] go_back timeout expected (ASP.NET ViewState behavior): {e}"
    )

# 追加待機（約2秒）でDOM安定化
self._wait_for_navigation()
```

### 効果測定

| 学生数 | 元の実装（180秒/件） | 最適化後（30秒/件） | 削減時間 | 削減率 |
|-------|-------------------|------------------|---------|--------|
| 100名 | 300分 | 50分 | 250分 | 83% |
| 158名 | 474分 | 79分 | 395分 | 83% |
| 200名 | 600分 | 100分 | 500分 | 83% |

---

## 📋 最適化実装チェックリスト

### 実装前

- [ ] ボトルネックを特定（測定ベース）
- [ ] 関連ドキュメント3点を確認済み
- [ ] 必須処理をスキップしていないか確認
- [ ] タイムアウト短縮の方向で検討

### 実装後（デプロイ前）

- [ ] コードレビュー完了
- [ ] 禁止パターンに該当しないか確認
- [ ] 1人目と2人目以降で同じ挙動か確認

### デプロイ後（本番検証）

- [ ] 1人目の学生が成功（download_url取得）
- [ ] **2人目の学生が成功**（最重要）
- [ ] Phase 2（Downloading:）ログが出現
- [ ] STEP 1 FAILEDログが連続していないか確認

### 検証コマンド:

```bash
# STEP 1失敗が連続していないか確認（0件が期待値）
gcloud logging read "textPayload=~'\[STEP 1 FAILED\]'" --limit 10

# Phase 2が実行されているか確認
gcloud logging read "textPayload=~'Downloading:'" --limit 20
```

---

## 📚 関連ドキュメント

- **トラブルシューティング**: `docs/troubleshooting.md`（診断フローチャート）
- **インシデントレポート**: `docs/incident-2025-11-08-phase1-go-back-skip-bug.md`
- **STEP 2設計**: `docs/playwright-page-navigation-flow.md` Lines 182-185
- **ASP.NET behavior**: `docs/pagination-viewstate-solution-2025-11-06.md` Lines 136-139, 170-171
- **Common Mistake #11**: `CLAUDE.md` Lines 909+

---

## 🎯 まとめ

### 最適化の黄金ルール

1. ✅ **スキップではなく短縮** - タイムアウトを短くする
2. ✅ **ドキュメント確認必須** - 変更前に必ず設計仕様を確認
3. ✅ **1人目=2人目以降** - 挙動が異なる場合は状態引き継ぎミス
4. ✅ **必須処理は全ページ実行** - 条件分岐でスキップしない
5. ✅ **go_back()は唯一の手段** - 代替手段は存在しない

### 過去のインシデントから学ぶ

**2025-11-08インシデント**:
- **問題**: go_back()をPage 2+でスキップ
- **影響**: 2人目以降全員失敗（199/200失敗）
- **修正**: go_back()を全ページで30秒実行
- **結果**: 92-94%成功、83%処理時間削減
- **教訓**: タイムアウト回避のために必須処理をスキップしてはいけない

---

**最終更新**: 2025-11-09
**バージョン**: 1.0
**メンテナー**: Claude Code
