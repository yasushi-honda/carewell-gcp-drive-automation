# Carewell Automation Project

**プロジェクト全体の実績・経緯・システム構成をまとめたポータルページ**

---

## 📋 プロジェクト概要

### システム名
**Carewell File Automation System**

### 目的
Carewell Webサービスから学生の提出ファイルを自動取得し、Google Driveに保存、Firestoreにメタデータを記録。講師向けDashboardで提出状況を可視化。

### 主要URL
| サービス | URL |
|---------|-----|
| **Dashboard**（令和8年度） | https://carewell-dashboard-2026.web.app/ |
| **Dashboard (管理者)** | https://carewell-dashboard-2026.web.app/?admin=true |
| **Dashboard（令和7年度・凍結アーカイブ）** | https://carewell-automation.web.app/（今後デプロイしない） |
| **GitHub** | https://github.com/yasushi-honda/carewell-gcp-drive-automation |
| **Cloud Run** | carewell-file-collector (asia-northeast1) |

---

## 📊 システム構成図

```mermaid
graph TB
    subgraph "Data Sources"
        GS[("Google Sheets<br/>統合_受講者リスト")]
        CW["Carewell Web<br/>jaccw-carewel.study.jp"]
    end

    subgraph "Cloud Scheduler"
        direction TB
        CS1["carewell-class01-task01<br/>毎時 :00, :30"]
        CS2["carewell-class01-task02<br/>毎時 :00, :30"]
        CS3["... 全14ジョブ"]
        CS4["carewell-student-sync-daily<br/>毎日 JST 02:00"]
    end

    subgraph "Cloud Run: carewell-file-collector"
        MAIN["main.py<br/>エントリーポイント"]
        PA["playwright_automation.py<br/>Webスクレイピング"]
        FS["firestore_service.py<br/>データ保存"]
        SS["sheets_service.py<br/>Sheets読み取り"]
    end

    subgraph "Storage"
        GD[("Google Drive<br/>ファイル保存")]
        FB[("Firestore<br/>carewell-native")]
    end

    subgraph "Frontend"
        FH["Firebase Hosting<br/>carewell-dashboard-2026.web.app"]
        VUE["Vue.js 3 Dashboard"]
    end

    CS1 & CS2 & CS3 -->|HTTP POST| MAIN
    CS4 -->|HTTP POST| MAIN
    MAIN --> PA
    MAIN --> SS
    PA <-->|Playwright| CW
    SS <-->|API| GS
    PA --> FS
    FS -->|Upload| GD
    FS -->|Metadata| FB
    VUE <-->|Read/Write| FB
    FH --> VUE

    style MAIN fill:#4285f4,color:#fff
    style FB fill:#ff9800,color:#fff
    style GD fill:#0f9d58,color:#fff
    style VUE fill:#42b883,color:#fff
```

---

## 📅 プロジェクトタイムライン

### 2025年11月 主要マイルストーン

```mermaid
gantt
    title Carewell Automation 開発タイムライン (2025年11月)
    dateFormat  YYYY-MM-DD

    section Phase 1: 基盤構築
    Firestore スキーマ改善           :done, p1a, 2025-11-04, 2d
    Playwright タイムアウト修正       :done, p1b, 2025-11-05, 1d
    Cloud Run タイムアウト延長        :done, p1c, 2025-11-06, 1d

    section Phase 2: ページネーション対応
    ASP.NET ViewState 対応          :done, p2a, 2025-11-06, 2d
    ページ再遷移ロジック実装          :done, p2b, 2025-11-07, 2d
    go_back タイムアウト修正          :done, p2c, 2025-11-08, 1d

    section Phase 3: Dashboard強化
    グループビュー機能               :done, p3a, 2025-11-09, 2d
    受講生管理機能                   :done, p3b, 2025-11-10, 1d
    Firestore Index修正             :done, p3c, 2025-11-10, 1d

    section Phase 4: 受講生同期
    Google Sheets 連携              :done, p4a, 2025-11-17, 1d
    Cloud Scheduler 自動同期        :done, p4b, 2025-11-18, 1d
    L列 論理削除対応                 :done, p4c, 2025-11-30, 1d
    手動同期ボタン                   :done, p4d, 2025-11-30, 1d

    section 運用
    本番運用開始                     :active, ops, 2025-11-10, 20d
```

### 開発履歴サマリー

| 日付 | マイルストーン | 主な成果 |
|------|--------------|---------|
| **2025-11-04** | Firestore スキーマ改善 | `submissions/{class}/tasks/{task}/files/` 構造採用 |
| **2025-11-05** | Playwright 修正 | iframe コンテキスト問題解決、タイムアウト改善 |
| **2025-11-06** | Cloud Run 最適化 | タイムアウト 15分→25分、ページネーション対応開始 |
| **2025-11-07** | ページ再遷移 | ASP.NET ViewState 対応、Page 2+ 処理成功 |
| **2025-11-08** | go_back 修正 | try-except でタイムアウト耐性強化 |
| **2025-11-09** | Dashboard Phase 2 | グループビュー、受講生管理機能追加 |
| **2025-11-10** | Index 修正 | Firestore Index IaC 徹底、25分タイムアウト解消 |
| **2025-11-17** | 受講生同期 | Google Sheets → Firestore 自動同期 |
| **2025-11-18** | 自動化完成 | Cloud Scheduler による毎日自動同期 |
| **2025-11-30** | L列対応 | 論理削除機能、手動同期ボタン追加 |

---

## 📁 ドキュメント一覧

### クイックスタート
- [QUICKSTART.md](QUICKSTART.md) - 新規AIエージェント向け5分ガイド
- [QUICKSTART_FOR_NEW_AI.md](QUICKSTART_FOR_NEW_AI.md) - AI向け詳細オンボーディング

### 機能引き継ぎ
- [STUDENT_SYNC_FEATURE_HANDOVER.md](STUDENT_SYNC_FEATURE_HANDOVER.md) - 受講生同期機能（図表付き）
- [STUDENT_SYNC_AUTOMATION_HANDOVER.md](STUDENT_SYNC_AUTOMATION_HANDOVER.md) - 自動同期設定ガイド
- [DASHBOARD_CLASS_DISPLAY.md](DASHBOARD_CLASS_DISPLAY.md) - Dashboard クラス表示機能

### トラブルシューティング
- [troubleshooting.md](troubleshooting.md) - 問題解決フローチャート
- [common-mistakes.md](common-mistakes.md) - 過去13の重大インシデント記録
- [EMERGENCY_RESPONSE.md](EMERGENCY_RESPONSE.md) - 緊急対応ガイド

### 設計・アーキテクチャ
- [architecture-overview.md](architecture-overview.md) - システム詳細アーキテクチャ
- [design.md](design.md) - 設計方針

### インシデント記録
- [incident-2025-11-05-schema-migration-and-playwright-fix.md](incident-2025-11-05-schema-migration-and-playwright-fix.md)
- [incident-2025-11-06-cloud-run-timeout.md](incident-2025-11-06-cloud-run-timeout.md)
- [incident-2025-11-06-pagination-url-update-delay.md](incident-2025-11-06-pagination-url-update-delay.md)
- [incident-2025-11-08-phase1-go-back-skip-bug.md](incident-2025-11-08-phase1-go-back-skip-bug.md)
- [incident-2025-11-10-firestore-index-missing.md](incident-2025-11-10-firestore-index-missing.md)

---

## 🗂️ Firestore スキーマ

```mermaid
erDiagram
    SUBMISSIONS {
        string class_name PK "クラス名"
    }

    TASKS {
        string task_id PK "課題ID"
        string task_pattern "課題表示名"
        number file_count "ファイル数"
        timestamp created_at "作成日時"
        timestamp last_updated "更新日時"
    }

    FILES {
        string composite_key PK "複合キー"
        string student_id "受講生ID"
        string student_name "受講生名"
        string student_furigana "ふりがな"
        string student_group "グループ"
        string student_status "ステータス"
        string filename "ファイル名"
        timestamp submit_date "提出日時"
        string drive_file_id "Drive ID"
    }

    STUDENTS {
        string student_id PK "受講生ID"
        string name "氏名"
        string furigana "ふりがな"
        string class_name "クラス"
        string group "グループ"
        string company "法人"
        string office "事業所"
        string status "ステータス"
    }

    SUBMISSIONS ||--o{ TASKS : "tasks/"
    TASKS ||--o{ FILES : "files/"
```

### コレクションパス

```
submissions/
  └── {class_name}/
      └── tasks/
          └── {task_id}/              ← 親ドキュメント (file_count等)
              └── files/
                  └── {composite_key}  ← ファイルメタデータ

students/
  └── {student_id}/                    ← 受講生マスター
```

---

## ⚙️ Cloud Scheduler ジョブ一覧

### ファイル収集ジョブ (令和7年度時点16ジョブ、令和8年度は10クラス計画で20ジョブへ拡大予定。2026-04-03以降は全ジョブPAUSED、詳細は`docs/SERVICE_SHUTDOWN_AND_RESUME.md`)

| ジョブ名 | スケジュール | 対象 |
|---------|-------------|------|
| carewell-class01-task01 | 毎時 :00, :30 | №01 課題① |
| carewell-class01-task02 | 毎時 :00, :30 | №01 課題② |
| carewell-class02-task01 | 毎時 :00, :30 | №02 課題① |
| carewell-class02-task02 | 毎時 :00, :30 | №02 課題② |
| ... | ... | ... |

### 学生同期ジョブ

| ジョブ名 | スケジュール | 機能 |
|---------|-------------|------|
| carewell-student-sync-daily | 毎日 JST 02:00 | Google Sheets → Firestore 同期 + Backfill |

---

## 📈 システム規模

### データ規模 (2025-11-07時点)

| クラス | 課題 | レポート数 | ページ数 | 処理時間 |
|-------|------|-----------|---------|---------|
| №01 | 課題① | 200件 | 2ページ | 約19分 |
| その他 | 各課題 | 100-200件 | 1-2ページ | 10-20分 |

### クラス構成

- **クラス数**: 令和7年度は8クラス (№01, 02, 03, 04, 05, 08, 09, 10)。令和8年度は10クラス (№06・07追加) を計画中
- **課題数**: 各クラス2課題 (課題①, 課題②)
- **受講生総数**: 1,923名

---

## 🔧 技術スタック

### Backend
- **言語**: Python 3.11
- **Webスクレイピング**: Playwright 1.40.0
- **コンテナ**: Docker (python:3.11-bookworm)
- **実行環境**: Cloud Run (2nd Gen)

### Frontend
- **フレームワーク**: Vue.js 3 + TypeScript
- **UIフレームワーク**: Tailwind CSS
- **ホスティング**: Firebase Hosting

### Infrastructure
- **データベース**: Firestore (carewell-native)
- **ファイルストレージ**: Google Drive
- **スケジューラ**: Cloud Scheduler
- **CI/CD**: GitHub Actions + Workload Identity Federation
- **シークレット管理**: Secret Manager

---

## 📞 連絡先・サポート

### ドキュメント参照先
- **設計仕様**: `.kiro/steering/` ディレクトリ
- **過去インシデント**: `docs/incident-*.md`
- **教訓**: `.serena/memories/`

### 重要な確認コマンド

```bash
# Cloud Run ログ確認
gcloud logging read "resource.type=cloud_run_revision AND
  resource.labels.service_name=carewell-file-collector" --limit 50

# Cloud Scheduler 状態確認
gcloud scheduler jobs list --location=asia-northeast1

# 手動同期実行
curl -X POST "https://carewell-file-collector-imczapxkba-an.a.run.app/admin/sync-students-from-sheets" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"backfill": true}'
```

---

**最終更新**: 2025-11-30
**メンテナー**: Claude Code AI Agent
