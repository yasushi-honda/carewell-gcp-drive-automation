# 新規AIエージェント向けクイックスタートガイド

**対象**: 初めてこのプロジェクトを担当するAIエージェント
**所要時間**: 10分
**最終更新**: 2025-11-18

---

## 🚨 最優先: これを最初に読む

### ステップ1: プロジェクト概要（2分）

**プロジェクト名**: Carewell GCP Drive Automation

**目的**:
- Carewell Webサービスから学生の提出ファイルを自動収集
- Google Driveに保存
- Firestoreにメタデータを記録
- Dashboardで可視化

**主要コンポーネント**:
1. **Cloud Run** (`carewell-file-collector`): ファイル収集バックエンド
2. **Cloud Scheduler**: 定期実行ジョブ
3. **Firestore** (`carewell-native`): メタデータストレージ
4. **Dashboard** (Firebase Hosting): 可視化UI
5. **Google Sheets**: 学生マスターデータ

---

### ステップ2: 必読ドキュメント（8分）

**作業開始前に必ず読むこと**:

| # | ドキュメント | 所要時間 | 優先度 | 内容 |
|---|------------|---------|--------|------|
| 1 | **[CLAUDE.md](../CLAUDE.md)** - CRITICAL セクション | 3分 | 🔴 必須 | インシデント対応ワークフロー、過去の失敗例 |
| 2 | **[docs/QUICKSTART.md](QUICKSTART.md)** | 5分 | 🔴 必須 | システムアーキテクチャ、Firestoreスキーマ |
| 3 | このファイル（QUICKSTART_FOR_NEW_AI.md） | 10分 | 🔴 必須 | 新規AI向けガイド |

**コーディング前に読むべき**:

| ドキュメント | タイミング | 内容 |
|------------|-----------|------|
| [docs/DASHBOARD_CLASS_DISPLAY.md](DASHBOARD_CLASS_DISPLAY.md) | Dashboard修正時 | Dashboardの2つのクラス表示機能 |
| [docs/STUDENT_SYNC_AUTOMATION_HANDOVER.md](STUDENT_SYNC_AUTOMATION_HANDOVER.md) | 学生データ同期関連 | Cloud Scheduler自動同期の運用 |
| [docs/common-mistakes.md](common-mistakes.md) | トラブル発生時 | 過去14件のインシデント詳細 |

---

## 📊 システム構成図（全体像）

```mermaid
graph TB
    subgraph "定期実行"
        A[Cloud Scheduler<br/>carewell-class01-task01<br/>etc.]
        B[Cloud Scheduler<br/>carewell-student-sync-daily<br/>毎日JST 02:00]
    end

    subgraph "Backend (Cloud Run)"
        C[carewell-file-collector<br/>ファイル収集API]
        D[/admin/sync-students-from-sheets<br/>学生データ同期API]
    end

    subgraph "データソース"
        E[Carewell Webサービス<br/>提出ファイル]
        F[Google Sheets<br/>統合_受講者リスト<br/>学生マスターデータ]
    end

    subgraph "ストレージ"
        G[Google Drive<br/>提出ファイル保存]
        H[Firestore carewell-native<br/>submissions/{class}/tasks/{task}/files/<br/>students/{student_id}]
    end

    subgraph "フロントエンド"
        I[Dashboard<br/>Firebase Hosting<br/>https://carewell-automation.web.app/]
    end

    A -->|POST /| C
    B -->|POST /admin/sync-students-from-sheets| D
    C -->|スクレイピング| E
    C -->|保存| G
    C -->|メタデータ記録| H
    D -->|読み取り A:K列| F
    D -->|同期| H
    H -->|リアルタイムリスナー| I
```

---

## 🔑 重要な設定値（暗記推奨）

### Firestore

| 項目 | 値 | 重要度 |
|------|-----|-------|
| **データベース名** | `carewell-native` | 🔴 CRITICAL |
| **提出ファイルパス** | `submissions/{class}/tasks/{task}/files/{composite_key}` | 🔴 CRITICAL |
| **学生データパス** | `students/{student_id}` | 🟡 重要 |

⚠️ **絶対に `(default)` データベースを使用しないこと**

### Google Sheets

| 項目 | 値 |
|------|-----|
| **スプレッドシート ID** | `1AQ12-h3n_NmN2kWxi4Z_g354X0wmUyMKAPeAsXJwu_w` |
| **シート名** | `統合_受講者リスト` |
| **読み取り範囲** | `A:K`（11列） |

### Cloud Run

| サービス名 | リージョン | URL |
|----------|----------|-----|
| `carewell-file-collector` | asia-northeast1 | https://carewell-file-collector-imczapxkba-an.a.run.app/ |

### Dashboard

| 項目 | 値 |
|------|-----|
| **URL** | https://carewell-automation.web.app/ |
| **デプロイ** | GitHub Actions (自動) |

---

## 🚨 絶対にやってはいけないこと

### ❌ 禁止事項

1. **Firestore `(default)` データベースの使用**
   - 必ず `carewell-native` を使用
   - 参照: [CLAUDE.md - Critical Configuration](../CLAUDE.md#critical-configuration--design-document-reference)

2. **Dashboard ディレクトリでのローカルコマンド実行**
   - `npm run dev` / `npm run build` / `npm install` は禁止
   - 全てGitHub Actions経由でデプロイ
   - 参照: [CLAUDE.md - Dashboard Development Workflow](../CLAUDE.md#dashboard-development-workflow)

3. **ドキュメントを読まずにコーディング**
   - 必ず関連ドキュメントを先に読む
   - 過去14件のインシデントはすべてこれが原因
   - 参照: [CLAUDE.md - Common Mistakes](../CLAUDE.md#common-mistakes-to-avoid)

4. **手動インフラ変更**
   - Firestore Index などは必ず `firestore.indexes.json` に記録
   - "コードにないものは存在しない"原則
   - 参照: インシデント #13

---

## 📖 よくある誤解（FAQ）

### Q1: Dashboard ホームページに新しいクラスを追加したら、すぐに表示されますか？

**A**: いいえ、2つの異なる実装があります。

- ✅ **学生詳細ページ**: Firestoreから自動取得（即座に反映）
- ❌ **ホームページのクラス一覧カード**: `dashboard/src/config/classes.ts` ハードコード（手動更新必要）

詳細: [docs/DASHBOARD_CLASS_DISPLAY.md](DASHBOARD_CLASS_DISPLAY.md)

---

### Q2: `/admin/sync-students-from-sheets` は何度実行しても安全ですか？

**A**: はい、安全です（冪等性保証）。

- `merge=True` による差分更新
- 既存フィールドは保持される
- 2回目実行時は `students_created: 0`

詳細: [docs/STUDENT_SYNC_VERIFICATION_2025_11_18.md](STUDENT_SYNC_VERIFICATION_2025_11_18.md)

---

### Q3: Cloud Scheduler の自動実行はいつですか？

**A**: 2種類あります。

**ファイル収集ジョブ**:
- 30分ごと（複数のクラス・課題で時間をずらして実行）
- 例: `carewell-class01-task01` (0,30 * * * *)

**学生データ同期ジョブ**:
- 毎日 JST 02:00（UTC 17:00）
- ジョブ名: `carewell-student-sync-daily`

詳細: [docs/STUDENT_SYNC_AUTOMATION_HANDOVER.md](STUDENT_SYNC_AUTOMATION_HANDOVER.md)

---

### Q4: トラブルが発生した場合、最初に何をすべきですか？

**A**: 以下の順序で確認してください。

1. **[CLAUDE.md](../CLAUDE.md) の CRITICAL セクションを読む**
2. **過去のインシデント記録を確認** ([docs/common-mistakes.md](common-mistakes.md))
3. **Cloud Run ログを確認**:
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND
     resource.labels.service_name=carewell-file-collector" --limit=50
   ```
4. **Dashboard で状態確認**: https://carewell-automation.web.app/
5. **Firestore Console で確認**: https://console.firebase.google.com/project/carewell-automation/firestore

詳細: [docs/EMERGENCY_RESPONSE.md](EMERGENCY_RESPONSE.md)（次セクション参照）

---

## 🔴 緊急時対応（簡易版）

### Cloud Scheduler Job が失敗している

```bash
# 1. ログ確認
gcloud logging read "resource.type=cloud_scheduler_job AND
  resource.labels.job_id=carewell-student-sync-daily AND
  severity>=ERROR" --limit=10

# 2. 手動実行でテスト
TOKEN=$(gcloud auth print-identity-token)
curl -X POST \
  "https://carewell-file-collector-imczapxkba-an.a.run.app/admin/sync-students-from-sheets" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"

# 3. Job の一時停止（必要に応じて）
gcloud scheduler jobs pause carewell-student-sync-daily --location=asia-northeast1
```

### Dashboard にデータが表示されない

```bash
# 1. Firestore 確認
# https://console.firebase.google.com/project/carewell-automation/firestore

# 2. ブラウザキャッシュクリア
# Cmd+Shift+R (Mac) / Ctrl+Shift+R (Windows)

# 3. GitHub Actions 確認（デプロイ済みか）
# https://github.com/yasushi-honda/carewell-gcp-drive-automation/actions
```

---

## 📚 ドキュメント索引

### プロジェクト全体

| ドキュメント | 内容 |
|------------|------|
| [CLAUDE.md](../CLAUDE.md) | プロジェクトルール、インシデント履歴、禁止事項 |
| [docs/QUICKSTART.md](QUICKSTART.md) | システムアーキテクチャ、Firestoreスキーマ |
| [docs/common-mistakes.md](common-mistakes.md) | 過去14件のインシデント詳細記録 |

### 機能別

| ドキュメント | 内容 |
|------------|------|
| [docs/DASHBOARD_CLASS_DISPLAY.md](DASHBOARD_CLASS_DISPLAY.md) | Dashboardのクラス表示（2つの実装） |
| [docs/STUDENT_SYNC_AUTOMATION_HANDOVER.md](STUDENT_SYNC_AUTOMATION_HANDOVER.md) | 学生データ同期の運用ガイド |
| [docs/class-name-feature-implementation.md](class-name-feature-implementation.md) | クラス名機能の実装詳細 |

### 運用

| ドキュメント | 内容 |
|------------|------|
| [docs/STUDENT_SYNC_VERIFICATION_2025_11_18.md](STUDENT_SYNC_VERIFICATION_2025_11_18.md) | 学生データ同期の検証結果 |
| [docs/EMERGENCY_RESPONSE.md](EMERGENCY_RESPONSE.md) | 緊急時対応マニュアル（詳細版） |
| [docs/troubleshooting.md](troubleshooting.md) | トラブルシューティングフローチャート |

---

## ✅ オンボーディング完了チェックリスト

作業開始前に、以下の質問に答えられることを確認してください：

- [ ] Firestoreのデータベース名は？ → **`carewell-native`**
- [ ] 提出ファイルのコレクションパスは？ → **`submissions/{class}/tasks/{task}/files/`**
- [ ] 学生データ同期APIのエンドポイントは？ → **`POST /admin/sync-students-from-sheets`**
- [ ] Dashboard のクラス表示は何種類ある？ → **2種類（ホームページ/学生詳細ページ）**
- [ ] 問題発生時に最初にやることは？ → **CLAUDE.md の CRITICAL セクションを読む**
- [ ] Dashboard でローカルコマンドを実行できる？ → **いいえ（GitHub Actions のみ）**
- [ ] Cloud Scheduler の学生データ同期は何時？ → **毎日 JST 02:00**

**全て答えられた → オンボーディング完了！**

---

## 🎯 次のステップ

### 新規タスクを受けた場合

1. **タスク内容を理解**
   - 何を修正/追加するのか
   - どのコンポーネントに影響するのか

2. **関連ドキュメントを読む**
   - 上記「ドキュメント索引」から該当ドキュメントを選択
   - 必ず [CLAUDE.md](../CLAUDE.md) の関連セクションを確認

3. **過去のインシデントを確認**
   - [docs/common-mistakes.md](common-mistakes.md) で類似のケースがないか確認

4. **コーディング開始**
   - ドキュメントに基づいた安全な実装
   - 変更内容を記録（コミットメッセージ、ドキュメント更新）

---

## 📞 困ったときは

### 1. ドキュメントを再確認

**「ドキュメントに答えがある」** - 過去のインシデントの90%はドキュメントを読まなかったことが原因

### 2. ログを確認

```bash
# Cloud Run ログ
gcloud logging read "resource.type=cloud_run_revision AND
  resource.labels.service_name=carewell-file-collector" --limit=50

# Cloud Scheduler ログ
gcloud logging read "resource.type=cloud_scheduler_job" --limit=50
```

### 3. Dashboard で確認

https://carewell-automation.web.app/

### 4. Firestore Console で確認

https://console.firebase.google.com/project/carewell-automation/firestore

---

## 🎓 重要な教訓（過去のインシデントより）

### パターン1: ドキュメント確認なしのコード変更

**インシデント**: #1, #4, #10, #12

**教訓**: **コーディング前に必ずドキュメント/仕様を確認**

---

### パターン2: 検証なしの仮定

**インシデント**: #9, #10, #11

**教訓**: **DevTools/ログで実際の動作/値を検証してから実装**

---

### パターン3: 複数箇所の設定見落とし

**インシデント**: #7

**教訓**: **設定は2箇所以上に存在する可能性を常に確認**

例: Cloud Scheduler のタイムアウト設定は以下の2箇所:
- Cloud Scheduler Job 設定
- Cloud Run サービス設定

---

### パターン4: Infrastructure as Code (IaC) の不徹底

**インシデント**: #13

**教訓**: **手動インフラ変更は必ずコードに記録（"コードにないものは存在しない"）**

---

### パターン5: デプロイ後の検証不足

**インシデント**: #8

**教訓**: **GitHub Actions 成功 ≠ 新コード実行中を忘れずに**

確認3点セット:
1. Revision 確認
2. Traffic 確認
3. Logs 確認

---

### パターン6: 複数の類似機能の混同

**インシデント**: #14

**教訓**: **同じ「クラス表示」でも、データソースと更新方法が異なる場合がある**

参照: [docs/DASHBOARD_CLASS_DISPLAY.md](DASHBOARD_CLASS_DISPLAY.md)

---

## まとめ

### 成功の3原則

1. **📖 ドキュメントを読む** - 作業前に必ず関連ドキュメントを確認
2. **🔍 ログで検証** - 仮定せず、実際の動作を確認
3. **📝 記録を残す** - コード変更と同時にドキュメント更新

### この順序を守る

```
ドキュメント確認 → ログ/DevTools検証 → コーディング → テスト → ドキュメント更新 → コミット
```

---

**新規AIエージェントへのメッセージ**:

このプロジェクトは、過去14件のインシデントから多くの教訓を学び、それをドキュメントに記録してきました。

**あなたの役割は、これらの教訓を尊重し、同じ失敗を繰り返さないことです。**

**ドキュメントを読み、理解し、実践してください。**

---

**作成日**: 2025-11-18
**作成者**: Claude Code AI Agent
**対象**: 次世代のAIエージェント
