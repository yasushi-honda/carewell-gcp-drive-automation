# Claude Code Spec-Driven Development

Kiro-style Spec Driven Development implementation using claude code slash commands, hooks and agents.

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

Based on past incidents:

1. **Database Name Mistake** (2025-11-04 incident)
   - ❌ Changed from `carewell-native` to `(default)` without checking design docs
   - ✅ Always use `carewell-native` for all environments
   - Lesson: "Firestoreのデータベースの元々の設計についてちゃんとドキュメントを確認してから対応してください"

2. **Missing `task_pattern` Parameter** (2025-11-04 incident)
   - ❌ Forgot to pass `task_pattern` to `record_upload()`
   - ✅ Always pass `task_pattern` from Cloud Scheduler request
   - Impact: Incorrect metadata in Firestore (defaults to `task_id`)

3. **Collection Path Mistake**
   - ❌ Used old path: `{class_name}/{task_id}/documents/{composite_key}`
   - ✅ Use new path: `submissions/{class_name}/tasks/{task_id}/files/{composite_key}`
   - Impact: Duplicate check fails, files re-downloaded repeatedly

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
