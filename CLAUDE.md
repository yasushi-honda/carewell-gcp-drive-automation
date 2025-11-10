# Claude Code Spec-Driven Development

Kiro-style Spec Driven Development implementation using claude code slash commands, hooks and agents.

---

## 👋 新しいAIエージェントへ

**このプロジェクトを初めて担当する場合、以下を順番に読んでください（所要時間: 10分）**

### 📖 ステップ1: システムを理解する（5分）

**必読ドキュメント**:
1. **docs/QUICKSTART.md** - 5分でわかるシステム概要
   - システムアーキテクチャ図（Mermaid）
   - Firestoreスキーマ図（Mermaid）
   - 重要な設定値

2. **このファイルの次セクション** - 🚨 CRITICAL: READ THIS FIRST

### 📖 ステップ2: トラブル対応を学ぶ（3分）

**必読ドキュメント**:
1. **docs/troubleshooting.md** - トラブルシューティングフローチャート
2. **docs/common-mistakes.md** - 過去13の重大インシデント詳細記録
3. **このファイルの Common Mistakes セクション** - インシデント要約表

### 📖 ステップ3: 詳細を深掘りする（必要時）

**参照ドキュメント**:
1. **docs/architecture-overview.md** - 詳細アーキテクチャ
2. **.serena/memories/incident_response_lessons.md** - 教訓とチェックリスト
3. **.kiro/steering/** - 設計仕様（Steering Documents）

### ✅ オンボーディング完了の確認

以下の質問に答えられれば、オンボーディング完了です：

- [ ] Firestore のデータベース名は？ → `carewell-native`
- [ ] 正しいコレクションパスは？ → `submissions/{class}/tasks/{task}/files/`
- [ ] 問題発生時に最初にやることは？ → CLAUDE.md CRITICAL を読む
- [ ] Cloud Run ログの確認コマンドは？ → `gcloud logging read ...`
- [ ] Dashboard の URL は？ → `https://carewell-automation.web.app/`

**次のステップ**: 実際の作業を開始する前に、必ず下記の「🚨 CRITICAL」セクションを読んでください。

---

## 🚨 CRITICAL: READ THIS FIRST 🚨

### Before ANY bug fix or incident response:

**MANDATORY CHECKLIST** (complete in this exact order):

1. ✅ Read `CLAUDE.md` → "Incident Response Workflow" section
2. ✅ Read `docs/CLASS01_TIMEOUT_ANALYSIS.md` (if pagination/timeout related)
3. ✅ Read relevant memory files (`incident_response_lessons`, etc.)
4. ✅ Check past commits for similar issues (`git log --grep="keyword"`)
5. ✅ ONLY THEN start investigation/coding

**NEVER skip steps 1-3. EVER.**

If you start coding before completing steps 1-3, **STOP IMMEDIATELY** and read the documents.

**Why this matters**: 同じ問題が既に解決されている可能性が高い。ドキュメントを読まずにコードを書くことは時間の無駄であり、同じ失敗を繰り返すことになる。

---

## Project Context

### Paths
- Steering: `.kiro/steering/`
- Specs: `.kiro/specs/`
- Commands: `.claude/commands/`

### Steering vs Specification

**Steering** (`.kiro/steering/`) - Guide AI with project-wide rules and context
**Specs** (`.kiro/specs/`) - Formalize development process for individual features

### Active Specifications
- **carewell-drive-automation**: Carewell Webサービスからのファイル自動取得・Google Drive保存・スプレッドシート記録システム
- **carewell-dashboard**: Firestore提出ファイルメタ情報可視化ダッシュボード（講師向けWebインターフェース）
- **firestore-schema-improvement**: Firestoreスキーマ改善 - タスク親ドキュメント追加による動的課題管理対応
- Check `.kiro/specs/` for active specifications
- Use `/kiro:spec-status [feature-name]` to check progress

## Development Guidelines
- Think in English, but generate responses in Japanese (思考は英語、回答の生成は日本語で行うように)

## Dashboard Development Workflow

**IMPORTANT: ローカル開発環境を使用しないワークフロー**

Dashboard (`dashboard/`ディレクトリ) の開発では、以下のルールを厳守してください：

### 禁止事項
- ❌ `npm run dev` (ローカル開発サーバー起動)
- ❌ `npm run build` (ローカルビルド実行)
- ❌ `npm install` (dashboardディレクトリでの依存関係インストール)
- ❌ その他、`dashboard/`ディレクトリ内でのnpmコマンド実行

### 必須ワークフロー
1. **コード変更**: コンポーネント・composables・設定ファイル等を編集
2. **Git操作**: `git add` → `git commit` → `git push origin main`
3. **自動デプロイ**: GitHub Actionsが自動実行
   - 依存関係インストール
   - 本番ビルド
   - Firestore Security Rulesデプロイ
   - Firebase Hostingデプロイ
4. **動作確認**: https://carewell-automation.web.app/ で確認

### 理由
- CI/CDパイプラインで全て自動化済み
- ローカル環境のセットアップ不要
- 環境差異によるトラブル回避
- デプロイフローの統一

## Workflow

### Phase 0: Steering (Optional)
`/kiro:steering` - Create/update steering documents
`/kiro:steering-custom` - Create custom steering for specialized contexts

Note: Optional for new features or small additions. You can proceed directly to spec-init.

### Phase 1: Specification Creation
1. `/kiro:spec-init [detailed description]` - Initialize spec with detailed project description
2. `/kiro:spec-requirements [feature]` - Generate requirements document
3. `/kiro:spec-design [feature]` - Interactive: "Have you reviewed requirements.md? [y/N]"
4. `/kiro:spec-tasks [feature]` - Interactive: Confirms both requirements and design review

### Phase 2: Progress Tracking
`/kiro:spec-status [feature]` - Check current progress and phases

## Development Rules
1. **Consider steering**: Run `/kiro:steering` before major development (optional for new features)
2. **Follow 3-phase approval workflow**: Requirements → Design → Tasks → Implementation
3. **Approval required**: Each phase requires human review (interactive prompt or manual)
4. **No skipping phases**: Design requires approved requirements; Tasks require approved design
5. **Update task status**: Mark tasks as completed when working on them
6. **Keep steering current**: Run `/kiro:steering` after significant changes
7. **Check spec compliance**: Use `/kiro:spec-status` to verify alignment

## Incident Response Workflow

### 🚨 When Production Issues Occur

**Follow this checklist BEFORE starting investigation:**

1. **Read Documentation First** (Priority: 🔴 CRITICAL)
   ```bash
   # Step 1: Check this file's Critical Configuration section
   # Step 2: Review past incidents in "Common Mistakes to Avoid"
   # Step 3: Read memory files
   ```

2. **Understand Environment Constraints**
   - ⚠️ Local Firestore access may fail (DNS resolution issues)
   - ✅ Use Cloud Run logs for verification: `gcloud logging read "resource.type=cloud_run_revision..."`
   - ✅ Use Dashboard for visual verification: https://carewell-automation.web.app/
   - ✅ Production environment is the source of truth

3. **Plan Before Executing**
   - 🎯 Identify root cause in code/configuration
   - 🔧 Fix the root cause first (don't apply band-aids)
   - 📝 Create automation scripts for bulk operations
   - ✅ Document the solution and lessons learned

4. **Avoid Common Pitfalls**
   - ❌ DON'T retry operations known to fail in local environment
   - ❌ DON'T manually fix items one-by-one (create bulk scripts instead)
   - ❌ DON'T skip documentation review
   - ❌ DON'T leave hanging background processes
   - ✅ DO clean up test artifacts and processes
   - ✅ DO commit and document your findings

### 📊 Recommended Investigation Tools

```bash
# Cloud Run Logs (PREFERRED for verification)
gcloud logging read "resource.type=cloud_run_revision AND
  resource.labels.service_name=carewell-file-collector" --limit 50

# Cloud Scheduler Status
gcloud scheduler jobs describe JOB_NAME --location=asia-northeast1

# Dashboard (Visual Verification)
# https://carewell-automation.web.app/
```

## Critical Configuration & Design Document Reference

### ⚠️ MUST READ BEFORE ANY CODE CHANGES

**Before modifying ANY code related to the following areas, you MUST:**

1. Read the relevant design documents listed below
2. Verify the current implementation matches the design specifications
3. Document any deviations in the change description

### Critical Configuration Values

**DO NOT CHANGE without consulting design documents:**

#### Firestore Configuration

- **Database Name**: `carewell-native` (NEVER use `(default)`)
  - Reference: `.kiro/specs/firestore-schema-improvement/requirements.md` Line 1-10
  - Reference: `docs/firestore-schema-improvement-implementation.md` Line 529
  - All environments (test, production) MUST use `carewell-native`

- **Collection Path Structure**:

  ```text
  submissions/{class_name}/tasks/{task_id}/files/{composite_key}
  ```

  - Reference: `.kiro/specs/firestore-schema-improvement/design.md` Line 51-75
  - OLD (incorrect): `{class_name}/{task_id}/documents/{composite_key}`
  - NEW (correct): Use path above

- **Parent Document Fields**:
  - `task_id` (string): Task identifier (e.g., "課題①")
  - `task_pattern` (string): Task display name (e.g., "課題①業務分析　※～11/3〆切")
  - `file_count` (number): Atomic increment using `firestore.Increment(1)`
  - `created_at` (timestamp): Document creation time
  - `last_updated` (timestamp): Last update time
  - Reference: `.kiro/specs/firestore-schema-improvement/design.md` Line 493-497

#### Required Parameters for Firestore Operations

**When calling `record_upload()`, ALL parameters are required:**

- `class_name`, `task_id`, `student_name`, `student_id`
- `filename`, `drive_file_id`, `drive_folder_id`, `submit_date`
- `metadata` (optional)
- **`task_pattern`** (MUST pass from Cloud Scheduler request)
  - Reference: `.kiro/specs/firestore-schema-improvement/requirements.md` Line 98-102
  - Common mistake: Forgetting to pass this parameter → defaults to `task_id`

### Design Document Reference Checklist

**Before modifying these files, read the corresponding design docs:**

| File Path | Required Reading | Key Sections |
|-----------|-----------------|--------------|
| `src/firestore_service.py` | `.kiro/specs/firestore-schema-improvement/design.md` | Lines 351-430, 493-502 |
| `src/main.py` | `.kiro/specs/firestore-schema-improvement/requirements.md` | Lines 96-104 |
| `tests/conftest.py` | `docs/firestore-schema-improvement-implementation.md` | Lines 520-536 |
| `tests/integration/test_file_upload.py` | `.kiro/specs/firestore-schema-improvement/design.md` | Lines 51-75 (path structure) |

### Code Change Checklist

Before committing changes to Firestore-related code:

- [ ] Read the design document sections listed above
- [ ] Verify database name is `carewell-native` (NOT `(default)`)
- [ ] Verify collection path uses correct structure
- [ ] Verify all required parameters are passed (especially `task_pattern`)
- [ ] Check if parent document fields match design specification
- [ ] Verify atomic operations use `firestore.Increment(1)` for `file_count`
- [ ] Run unit tests to ensure no regressions
- [ ] Run integration tests with Firestore Emulator

### Common Mistakes to Avoid

**📖 詳細な記録は `docs/common-mistakes.md` を参照してください**

過去のインシデントから学んだ教訓の要約：

| # | インシデント | 日付 | 影響 | 重要な教訓 |
|---|------------|------|------|-----------|
| 1 | Database Name Mistake | 2025-11-04 | Firestore接続失敗 | ✅ 必ず `carewell-native` を使用（`(default)` は不可） |
| 2 | Missing task_pattern | 2025-11-04 | メタデータ不正 | ✅ Cloud Scheduler リクエストから全パラメータを渡す |
| 3 | Collection Path Mistake | - | 重複チェック失敗 | ✅ 新パス: `submissions/{class}/tasks/{task}/files/` を使用 |
| 4 | Dashboard Schema Mismatch | 2025-11-05 | Dashboard データ不可視 | ✅ コーディング前に Steering Document を確認 |
| 5 | Iframe Context Error | 2025-11-08 | Page 2+ 100% 失敗 | ✅ Frame 更新 + 全エラーハンドラーに go_back() |
| 6 | Playwright Invalid API | 2025-11-05 | 全学生失敗 | ✅ Playwright の Auto-waiting を活用 |
| 7 | Cloud Run Timeout | 2025-11-06 | 15分タイムアウト | ✅ Scheduler と Cloud Run の両方のタイムアウトを確認 |
| 8 | Deployed Code Not Running | 2025-11-06 | 修正未反映 | ✅ デプロイ後: revision/traffic/logs の3点確認 |
| 9 | ASP.NET Pagination Delay | 2025-11-06 | 42.2% 未収集 | ✅ プロパティ更新を明示的に検証（auto-wait なし） |
| 10 | Deleting Critical STEP 1 | 2025-11-07 | 50% 収集失敗 | ✅ コード削除前にドキュメントで目的を確認 |
| 11 | Assuming Parameter Names | 2025-11-08 | Page 2+ 0% 成功 | ✅ DevTools で実際の HTML/パラメータを検証 |
| 12 | Phase 1 go_back Skip | 2025-11-08 | 2人目以降失敗 | ✅ 必須処理をスキップせず、タイムアウト短縮で最適化 |
| 13 | Firestore Index Missing | 2025-11-10 | 25分タイムアウト | ✅ **全インデックスを `firestore.indexes.json` で管理（IaC 徹底）** |

### 🚨 最重要パターン

**パターン1: ドキュメント確認なしのコード変更**
- インシデント #1, #4, #10, #12
- 教訓: **コーディング前に必ずドキュメント/仕様を確認**

**パターン2: 検証なしの仮定**
- インシデント #9, #10, #11
- 教訓: **DevTools/ログで実際の動作/値を検証してから実装**

**パターン3: 複数箇所の設定見落とし**
- インシデント #7（Cloud Scheduler + Cloud Run）
- インシデント #7 Follow-up（手動設定 + GitHub Actions）
- 教訓: **設定は2箇所以上に存在する可能性を常に確認**

**パターン4: Infrastructure as Code (IaC) の不徹底**
- インシデント #13（手動作成インデックス + 自動デプロイ）
- 教訓: **手動インフラ変更は必ずコードに記録（"コードにないものは存在しない"）**

**パターン4: デプロイ後の検証不足**
- インシデント #8
- 教訓: **GitHub Actions 成功 ≠ 新コード実行中を忘れずに**

**詳細な教訓・解決策・チェックリストは `docs/common-mistakes.md` を参照**

## Steering Configuration

### Current Steering Files

Managed by `/kiro:steering` command. Updates here reflect command changes.

### Active Steering Files

- `product.md`: Always included - Product context and business objectives
- `tech.md`: Always included - Technology stack and architectural decisions
- `structure.md`: Always included - File organization and code patterns

### Custom Steering Files

<!-- Added by /kiro:steering-custom command -->
<!-- Format:
- `filename.md`: Mode - Pattern(s) - Description
  Mode: Always|Conditional|Manual
  Pattern: File patterns for Conditional mode
-->

- `dashboard-workflow.md`: Conditional - `dashboard/**` - Dashboard開発時のローカル環境使用禁止とGitHub Actions CI/CDワークフロー
- `firestore-critical-config.md`: Always - Firestore設定値・設計仕様参照ルール（データベース名・パス構造・必須パラメータ）

### Inclusion Modes

- **Always**: Loaded in every interaction (default)
- **Conditional**: Loaded for specific file patterns (e.g., "*.test.js")
- **Manual**: Reference with `@filename.md` syntax
