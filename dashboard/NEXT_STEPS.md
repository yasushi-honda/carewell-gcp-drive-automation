# Carewell Dashboard - 次のステップ

## 🎉 現在の完了状態

**Phase 0: CI/CD構築 - 完了（2025-10-11）**

以下が完了し、本番環境で正常に動作しています：

- ✅ Vue.js 3 + Vite + TypeScript プロジェクト構築
- ✅ Firebase プロジェクト初期化
- ✅ GitHub Actions CI/CDパイプライン構築
- ✅ Firestore Security Rules 自動デプロイ
- ✅ Firebase Hosting 自動デプロイ
- ✅ Hello World ページ公開（https://carewell-automation.web.app）

**デプロイパイプライン動作確認**:
- `dashboard/` 配下の変更を`main`ブランチにプッシュすると、自動的にFirebase Hostingにデプロイされる
- ワークフロー: `.github/workflows/deploy-dashboard.yml`

---

## 📋 Phase 1: 基本機能実装（次のステップ）

### 実装方法の選択肢

#### Option A: TDD（テスト駆動開発）での実装【推奨】

Kiro Spec-Driven Development ワークフローの`spec-impl`コマンドを使用：

```bash
/kiro:spec-impl carewell-dashboard
```

このコマンドは：
1. `.kiro/specs/carewell-dashboard/tasks.md`のタスクを順番に実装
2. 各タスクでテストを先に書き、実装を後で書くTDDアプローチ
3. タスク完了後に自動的に次のタスクに進む

#### Option B: 手動実装

`.kiro/specs/carewell-dashboard/tasks.md`を参照して、以下の順序で実装：

### Task 2: Firestore データアクセス層（優先度：高）

**目的**: Firestoreからデータを取得するComposableを実装

**実装ファイル**:
- `src/composables/useFirestore.ts`
- `src/config/firebase.ts`

**主要機能**:
```typescript
// useFirestore.ts
export function useFirestore() {
  const getClasses = async () => { /* 実装 */ }
  const getTasks = async (className: string) => { /* 実装 */ }
  const getFiles = async (className: string, taskId: string) => { /* 実装 */ }

  return { getClasses, getTasks, getFiles }
}
```

**Firestoreコレクション構造**（既存）:
```
{class_name}/
  └─ {task_id}/
      └─ documents/
          └─ {composite_key}
              ├─ student_id: string
              ├─ student_name: string
              ├─ filename: string
              ├─ submit_date: string
              ├─ score: string
              ├─ result: string
              ├─ status: string
              ├─ drive_file_id: string
              ├─ uploaded_at: timestamp
              └─ sha256: string
```

**環境変数設定**（必須）:

GitHub Secrets/Variablesの設定が必要です。詳細は`SETUP.md`を参照。

### Task 3: クラス一覧表示（優先度：高）

**目的**: 全クラスをカード形式で表示

**実装ファイル**:
- `src/views/ClassListView.vue`
- `src/components/ClassCard.vue`

**画面イメージ**:
```
+----------------------------------+
| Carewell Dashboard               |
+----------------------------------+
| [クラス一覧]                      |
|                                  |
| +-------------+ +-------------+  |
| | №01         | | №02         |  |
| | 課題数: 2   | | 課題数: 2   |  |
| | 提出: 20/25 | | 提出: 18/25 |  |
| +-------------+ +-------------+  |
+----------------------------------+
```

### Task 4: 課題一覧表示（優先度：高）

**目的**: 選択したクラスの課題一覧を表示

**実装ファイル**:
- `src/views/TaskListView.vue`
- `src/components/TaskCard.vue`

**画面イメージ**:
```
+----------------------------------+
| Carewell Dashboard               |
+----------------------------------+
| クラス一覧 > №01                  |
|                                  |
| +-------------+ +-------------+  |
| | 課題①       | | 課題②       |  |
| | 提出: 20/25 | | 提出: 22/25 |  |
| | 未提出: 5   | | 未提出: 3   |  |
| +-------------+ +-------------+  |
+----------------------------------+
```

### Task 5: ファイル一覧表示（優先度：高）

**目的**: 選択した課題の提出ファイル一覧をテーブル形式で表示

**実装ファイル**:
- `src/views/FileListView.vue`
- `src/components/FileTable.vue`

**画面イメージ**:
```
+------------------------------------------------+
| Carewell Dashboard                             |
+------------------------------------------------+
| クラス一覧 > №01 > 課題①                        |
|                                                |
| +--------------------------------------------+ |
| | 学生名 | 提出日時 | ファイル名 | Drive    | |
| |--------|---------|-----------|----------| |
| | 山田太郎| 10/01   | report.pdf| [Open]   | |
| | 佐藤花子| 10/02   | report.pdf| [Open]   | |
| +--------------------------------------------+ |
+------------------------------------------------+
```

### Task 6-8: 検索・フィルタ・ソート（優先度：中）

**実装内容**:
- 学生名・学生IDによる部分一致検索
- 提出日時でのソート（昇順・降順）
- フィルタリング機能

---

## 🔧 開発環境セットアップ

### 1. 依存関係のインストール

```bash
cd dashboard
npm install
```

### 2. 環境変数の設定

```bash
cp .env.example .env
# .envファイルを編集してFirebase設定を入力
```

Firebase設定の取得方法は`SETUP.md`を参照。

### 3. 開発サーバー起動

```bash
npm run dev
```

http://localhost:5173 でアプリケーションが起動します。

### 4. 実装 → コミット → デプロイ

```bash
# 実装後
git add dashboard/
git commit -m "feat: Implement Task 2 - Firestore data access layer"
git push origin main

# GitHub Actionsが自動的にデプロイ
# https://carewell-automation.web.app で確認
```

---

## 📚 参考ドキュメント

- **仕様書**: `.kiro/specs/carewell-dashboard/requirements.md`
- **設計書**: `.kiro/specs/carewell-dashboard/design.md`
- **タスク詳細**: `.kiro/specs/carewell-dashboard/tasks.md`
- **セットアップ手順**: `dashboard/SETUP.md`
- **プロジェクトREADME**: `dashboard/README.md`

---

## ⚠️ 注意事項

### セキュリティ（Phase 1）

現在の実装は**認証なし**です：

- ✅ Firestore Security Rules: `allow read: if true` （全員読み取り可能）
- ✅ 書き込み: `allow write: if false` （フロントエンドからの書き込み禁止）
- ⚠️ URLを知っている人なら誰でもアクセス可能

Phase 2で Firebase Authentication を実装予定。

### データ構造

Firestoreのデータ構造は、既存の`carewell-file-collector` Cloud Run Functionsが生成したものを使用します。データ構造の変更が必要な場合は、バックエンド側の修正も必要です。

### パフォーマンス目標

Phase 1実装時に以下を意識してください：

| メトリック | 目標値 |
|-----------|--------|
| 初回表示時間 | 3秒以内 |
| 画面遷移時間 | 1秒以内 |
| バンドルサイズ（gzipped） | 200KB以下 |

---

## 🎯 マイルストーン

### Phase 0: CI/CD構築【完了】
- ✅ 2025-10-11: CI/CDパイプライン構築完了
- ✅ 2025-10-11: Hello Worldページ公開

### Phase 1: 基本機能実装【次】
- ⬜ Task 2: Firestore データアクセス層
- ⬜ Task 3: クラス一覧表示
- ⬜ Task 4: 課題一覧表示
- ⬜ Task 5: ファイル一覧表示
- ⬜ Task 6-8: 検索・フィルタ・ソート

### Phase 2: 認証・セキュリティ【計画中】
- ⬜ Firebase Authentication 統合
- ⬜ 講師別クラスフィルタリング
- ⬜ Firestore Security Rules 更新

---

## 🚀 実装開始

準備ができたら、以下のコマンドで実装を開始してください：

```bash
# TDD方式（推奨）
/kiro:spec-impl carewell-dashboard

# または手動で
cd dashboard
npm run dev
# Task 2から順番に実装
```

Good luck! 🎉
