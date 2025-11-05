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
2. **このファイルの Common Mistakes セクション** (Lines 224-308)
   - 過去の5つの重大インシデント

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

Based on past incidents:

1. **Database Name Mistake** (2025-11-04 incident)
   - ❌ Changed from `carewell-native` to `(default)` without checking design docs
   - ✅ Always use `carewell-native` for all environments
   - Lesson: "Firestoreのデータベースの元々の設計についてちゃんとドキュメントを確認してから対応してください"

2. **Missing `task_pattern` Parameter** (2025-11-04 incident)
   - ❌ Forgot to pass `task_pattern` to `record_upload()`
   - ✅ Always pass `task_pattern` from Cloud Scheduler request
   - Impact: Incorrect metadata in Firestore (defaults to `task_id`)

   **Root Cause**: `scripts/create-scheduler-jobs.sh` had bug on Line 84
   ```bash
   # ❌ Wrong (Line 84)
   "task_pattern": "${task_name}"  # Same value as task_id

   # ✅ Correct
   "task_pattern": "${task_pattern}"  # Separate parameter
   ```

   **Optimal Solution**:
   - Create bulk update script for all 14 Cloud Scheduler jobs
   - Fix root cause in creation script first
   - Use `gcloud scheduler jobs update` with proper JSON body
   - Avoid manual one-by-one fixes

3. **Collection Path Mistake**
   - ❌ Used old path: `{class_name}/{task_id}/documents/{composite_key}`
   - ✅ Use new path: `submissions/{class_name}/tasks/{task_id}/files/{composite_key}`
   - Impact: Duplicate check fails, files re-downloaded repeatedly

4. **Dashboard Schema Mismatch** (2025-11-05 incident)
   - ❌ Dashboard used old schema without checking Steering Document
   - ✅ ALWAYS verify Dashboard reads from same schema as Backend
   - Impact: Dashboard showed old data, new data invisible

   **Root Cause**: Dashboard composables used legacy path

   ```typescript
   // ❌ Wrong (dashboard/src/composables/useFirestore.ts:129)
   const docRef = doc(db, className, taskId);

   // ✅ Correct
   const docRef = doc(db, "submissions", className, "tasks", taskId);
   ```

   **Lesson**: "ちゃんとドキュメントをみてから行動してください。Firestoreのデータについて、重複チェックリストの設計、Hostingへの接続設計などどれも事前に確認してから対応すべき重要な仕様内容です。"

   **Optimal Solution**:
   - Read Steering Document BEFORE coding
   - Create verification scripts for all classes/tasks
   - Staged 10-phase migration with user confirmation
   - Delete old data AFTER verifying new schema works

   **Reference**: `docs/incident-2025-11-05-schema-migration-and-playwright-fix.md`

5. **Playwright Invalid API Call** (2025-11-05 incident)
   - ❌ Used non-existent method: `locator.wait_for_element_state("visible")`
   - ✅ Use Playwright's Auto-waiting feature (no explicit wait needed)
   - Impact: №01 課題① file download failed for all students

   **Root Cause**: Line 840 in src/playwright_automation.py

   ```python
   # ❌ Wrong
   link.wait_for_element_state("visible", timeout=10000)

   # ✅ Correct - Auto-waiting handles this automatically
   link.click()  # Waits for clickable state automatically
   ```

   **Why Missed in Tests**: Test code path didn't execute this line

   **Lesson**:
   - Playwright actions (click, fill, etc.) have built-in Auto-waiting
   - Only use explicit `wait_for(state="visible")` when truly needed
   - Verify API methods exist in official documentation
   - Improve test coverage for error paths

   **Reference**:
   - `docs/incident-2025-11-05-schema-migration-and-playwright-fix.md`
   - [Playwright Auto-waiting Documentation](https://playwright.dev/python/docs/actionability)

6. **Cloud Run Timeout Misconfiguration** (2025-11-06 incident)
   - ❌ Extended Cloud Scheduler deadline but forgot Cloud Run timeout
   - ✅ **Both** timeouts must be configured (Scheduler AND Cloud Run)
   - Impact: №01 課題① timed out at 15 minutes → 504 Gateway Timeout → No data saved

   **Root Cause**: Timeout settings exist in **two separate places**

   ```
   Cloud Scheduler attemptDeadline: 1500秒 (25分) ✅ Extended
   Cloud Run timeoutSeconds:        900秒 (15分)  ❌ Overlooked
                                                   ↑ Timeout occurs here first
   ```

   **Why it happened**:
   - №01 has 180 submissions (2-page processing) → takes > 15 minutes
   - Cloud Run forced shutdown at 15 minutes
   - Never reached Firestore/Drive/Spreadsheet save operations

   **Investigation Steps** (critical for future incidents):
   1. Check HTTP response latency in Cloud Run logs
   2. If latency = 900s → Cloud Run timeout
   3. **Always check BOTH timeout settings**:
      ```bash
      # Cloud Scheduler
      gcloud scheduler jobs describe JOB_NAME --format="value(attemptDeadline)"

      # Cloud Run (often overlooked!)
      gcloud run services describe SERVICE_NAME --format="value(spec.template.spec.timeoutSeconds)"
      ```

   **Solution**:
   ```bash
   gcloud run services update carewell-file-collector \
     --timeout=1500 \
     --region=asia-northeast1
   ```

   **Lesson**:
   - **Timeout checklist** (when modifying timeout settings):
     - [ ] Cloud Scheduler `attemptDeadline` checked
     - [ ] Cloud Run `timeoutSeconds` checked
     - [ ] Both values match (or Cloud Run ≥ Scheduler)
     - [ ] Maximum processing time considered (2-page = 20-25 min)
   - Don't trust "timeout fixed" in past docs without verifying ALL timeout settings
   - This was overlooked in `docs/CLASS01_TIMEOUT_ANALYSIS.md` which only extended Scheduler

   **🔴 CRITICAL Follow-up** (same day, 00:50 JST):

   **Second Root Cause**: GitHub Actions workflow hardcoded timeout=900

   After manually fixing timeout to 1500s, **GitHub Actions overwrote it back to 900s** during the next deployment:

   ```text
   00:02 JST - Manual fix: timeout=1500 (revision 00173-5b6) ✅
   00:21 JST - GitHub Actions deploy: timeout=900 (revision 00174-dnf) ❌ Overwrote!
   00:30 JST - №01 execution: 504 timeout again (only 7/180 files saved)
   ```

   **Root Cause**: `.github/workflows/deploy.yml` Line 107
   ```yaml
   # ❌ Wrong
   --timeout 900 \

   # ✅ Correct
   --timeout 1500 \
   ```

   **Critical Lesson**:
   - ❌ Manual Cloud Run config changes are NOT permanent
   - ✅ **ALWAYS update CI/CD workflow files** (`.github/workflows/deploy.yml`)
   - ✅ Verify next deployment doesn't overwrite manual changes
   - ✅ Infrastructure settings should be in version control (IaC)
   - [ ] **Checklist addition**: When changing Cloud Run config, also update GitHub Actions workflow

   **Reference**: `docs/incident-2025-11-06-cloud-run-timeout.md` (Section: GitHub Actions ワークフローによる設定上書き問題)

   **🔴 CRITICAL Follow-up #2** (same day, 01:00-01:37 JST):

   **Third Root Cause**: Frame retrieval timing issue (large datasets)

   Even after fixing Cloud Run timeout to 1500s, **01:00 JST execution still timed out** at 1499 seconds.

   **Symptoms**:
   - 「全て」tab click: SUCCESS ✅
   - Frame retrieval: FAILED ❌
   - Repeated `TimeoutError: Timeout 60000ms exceeded` every ~5 minutes
   - Looped for 25 minutes until Cloud Run timeout

   **Root Cause**: `FRAME_LOAD_WAIT = 3000ms` (3 seconds) was insufficient for №01's 180+ submissions

   ```text
   「全て」tab clicked successfully (16:01:36) ✅
     ↓
   Wait 3 seconds (FRAME_LOAD_WAIT)
     ↓
   Try to get frame → FAILED (frame still reloading)
     ↓
   wait_for_selector → 60s timeout ❌
     ↓
   Retry... (repeated for 25 minutes)
   ```

   **User's Diagnosis**:
   > "ドキュメントのトラブルシューティングをみて、多分またフレームがちゃんと探せてないだけだと思うから"

   → **100% CORRECT**. Similar issue was documented in `CLASS01_TIMEOUT_ANALYSIS.md`.

   **Solution** (commit `17d63d8`):

   1. Increase frame wait time (Line 70):

      ```python
      FRAME_LOAD_WAIT = 15000  # 15s (was 3s)
      ```

   2. Add frame retrieval retry logic (Lines 358-385, 402-430):

      ```python
      max_frame_retries = 5 if current_page == 1 else 3

      for retry in range(max_frame_retries):
          for frame in self.page.frames:
              if frame.name == "list":
                  try:
                      _ = frame.url  # Verify frame not detached
                      list_frame = frame
                      break
                  except Exception:
                      continue

          if list_frame:
              break

          time.sleep(2)  # Wait before retry
      ```

   **Critical Lessons**:
   - ❌ **Extending Cloud Run timeout alone doesn't fix Playwright timeouts**
   - ✅ **Must identify and fix the actual timeout location in code**
   - ✅ **Refer to past troubleshooting docs** (`CLASS01_TIMEOUT_ANALYSIS.md`)
   - ✅ **Large datasets (180+ items) require longer wait times**

   **Frame Issue Checklist**:
   - [ ] `FRAME_LOAD_WAIT` sufficient? (15s recommended for large datasets)
   - [ ] Frame retrieval has retry logic?
   - [ ] Verify frame not detached before use?
   - [ ] Log shows 「全て」tab click success?
   - [ ] Log shows frame retrieval success/failure?

   **Reference**: `docs/incident-2025-11-06-cloud-run-timeout.md` (Section: 第3の問題発見 - フレーム取得タイミング問題)

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
