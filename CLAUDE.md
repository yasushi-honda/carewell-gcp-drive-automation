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

11. **Iframe Context and Missing Error Recovery** (2025-11-08 incident)
   - ❌ Downloaded links searched in wrong context (main page vs iframe)
   - ❌ Missing go_back() calls after errors → stayed on detail page
   - ✅ ALWAYS verify iframe navigation and refresh frame references
   - ✅ ALWAYS add error recovery to return to list page
   - Impact: Page 2+ students (100名) failed with 100% failure rate

   **Root Causes**:

   **Cause 1**: DOWNLOAD_LINK constant undefined
   ```python
   # ❌ Wrong (src/playwright_automation.py)
   # Constant not defined in CarewellSelectors class

   # ✅ Correct
   class CarewellSelectors:
       DOWNLOAD_LINK = 'a[href^="download.aspx"]'
   ```

   **Cause 2**: Frame context error - detail page loads in iframe
   ```python
   # ❌ Wrong - searching in main page context
   download_link = self.page.wait_for_selector(DOWNLOAD_LINK)

   # ✅ Correct - refresh frame reference after navigation, search in iframe
   # Refresh list_frame reference (detail page loaded in iframe)
   list_frame = None
   for frame in self.page.frames:
       if frame.name == "list":
           list_frame = frame
           break

   download_link = list_frame.wait_for_selector(CarewellSelectors.DOWNLOAD_LINK)
   ```

   **Cause 3**: Missing error recovery
   ```python
   # ❌ Wrong - stays on detail page after error
   except TimeoutError:
       self.logger.error("Timeout waiting for download link")
       return {"url": None, "filename": None}

   # ✅ Correct - go_back() to list page
   except TimeoutError:
       self.logger.error("Timeout waiting for download link")
       try:
           self.page.go_back(wait_until="domcontentloaded")
           time.sleep(15)  # Wait for DOM to stabilize
       except Exception as e:
           self.logger.warning(f"Failed to go_back: {e}")
       return {"url": None, "filename": None}
   ```

   **Critical Lessons**:
   - ❌ **Avoid**: Assuming download page loads in main page context
   - ❌ **Avoid**: Missing error recovery in multi-page flows
   - ✅ **Use**: Frame refresh after click-based navigation
   - ✅ **Use**: go_back() in ALL error handlers
   - ✅ **Verify**: Actual HTML structure (not onclick, use text_content())

   **Verification Checklist** (before deploying iframe-related fixes):
   - [ ] Frame reference refreshed after click navigation?
   - [ ] Search context changed from self.page to iframe?
   - [ ] go_back() added to TimeoutError handler?
   - [ ] go_back() added to Exception handler?
   - [ ] Actual HTML structure verified in DevTools?

   **Reference**: src/playwright_automation.py:1227-1463

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

7. **🚨 Deployed Code Not Running** (2025-11-06 08:00 JST - RECURRING PATTERN)
   - ❌ Deployed new code via GitHub Actions, but old code kept running
   - ✅ **ALWAYS verify 3 points after deployment**: ①Revision created ②Traffic routed ③New code logs visible
   - Impact: Fixed code not applied → users confused → wasted time debugging

   **User Feedback**: _"今回のような新しくしたが、実行は実は古いままだった。という失敗は以前から有りました。"_
   **This is a RECURRING pattern that MUST be prevented.**

   **Symptoms**:
   - New INFO-level logs added in fix don't appear
   - Old error messages (pre-fix) keep appearing
   - User reports: "8:06時点で新たに取得が出来てる状況が無いので、不安です"

   **Root Causes**:
   1. **Traffic still routed to old revision**
      ```bash
      # Current traffic
      carewell-file-collector-00180-j9h  100%  # Old code

      # Latest revision
      carewell-file-collector-00183-nb9  Retired  # New code but inactive
      ```

   2. **Same Docker image digest** (caching issue)
      ```bash
      # 00183-nb9 and 00182-78r share same image
      sha256:ef8d7ff49b0d89feddd7d451222208adac84db51f7a576fc8a32511c5cd2f48d
      ```

   3. **GitHub Actions deployed but new revision not activated**

   **Investigation Steps** (MANDATORY after deployment):

   **Step 1: Verify new code traces in logs**
   ```bash
   # Check if logs added in fix appear
   gcloud logging read "resource.type=cloud_run_revision AND \
     resource.labels.service_name=carewell-file-collector" \
     --limit 50 --format json | \
     jq -r '.[] | select(.textPayload) | .textPayload' | \
     grep "YOUR_NEW_LOG_MESSAGE"  # Log added in fix

   # If not found → old code running
   ```

   **Step 2: Check traffic routing**
   ```bash
   gcloud run services describe carewell-file-collector \
     --region=asia-northeast1 \
     --format="value(status.traffic[0].revisionName,status.traffic[0].percent)"

   # Expected: Latest revision name
   # If old revision → PROBLEM!
   ```

   **Step 3: Check image digest**
   ```bash
   gcloud run revisions list \
     --service=carewell-file-collector \
     --region=asia-northeast1 \
     --limit 5 \
     --format="table(metadata.name,status.conditions[0].status,status.conditions[0].reason,status.imageDigest)" \
     --sort-by="~metadata.creationTimestamp"

   # Same digest across revisions → Docker cache issue
   ```

   **Solutions**:

   **Option 1: Manually route traffic** (if valid revision exists)
   ```bash
   gcloud run services update-traffic carewell-file-collector \
     --region=asia-northeast1 \
     --to-revisions LATEST_REVISION=100
   ```

   **Option 2: Re-run GitHub Actions** (bypass Docker cache)
   ```bash
   gh workflow run deploy.yml
   gh run watch RUN_ID
   ```

   **Option 3: Add --no-cache to Docker build**
   ```yaml
   # .github/workflows/deploy.yml
   docker build --no-cache -t ${IMAGE_TAG} .
   ```

   **Post-Deployment Verification Checklist** (MANDATORY):
   - [ ] New revision created? (`gcloud run revisions list --limit 1`)
   - [ ] Traffic routed 100% to new revision? (`status.traffic[0]`)
   - [ ] New code logs visible? (grep for new log messages)
   - [ ] Image digest different from previous revision?

   **Critical Lessons**:
   - ❌ **"GitHub Actions success ≠ new code running"**
   - ✅ **Always verify 3 points**: revision, traffic, logs
   - ✅ **User's "unease" is important signal** - investigate immediately
   - ✅ **Check image digest for duplication** - same digest = same code

   **Permanent Solutions**:
   1. Create post-deployment verification script (automate 3-point check)
   2. Add verification step to GitHub Actions workflow
   3. Consider --no-cache for Docker builds to avoid cache issues

   **Reference**: `.serena/memories/incident_response_lessons.md` Line 46-177

8. **ASP.NET Pagination URL Update Delay** (2025-11-06 14:45 JST)
   - ❌ Used `frame.url` property without verifying URL changed after pagination
   - ✅ **Explicitly verify state changes** - don't blindly trust property values
   - Impact: №01 課題① - 84/199 files (42.2%) not collected (Page 2+ students)

   **Root Cause**: ASP.NET `__doPostBack` pagination delay

   ```python
   # ❌ Wrong (src/playwright_automation.py:892)
   list_url = list_frame.url  # Retrieves stale Page 1 URL even after Page 2 transition

   # Result: Page 2 student links searched using Page 1 URL → Not found → Download failed
   ```

   **Why it happened**:
   - ASP.NET `__doPostBack` is async - DOM update ≠ URL update
   - Playwright `frame.url` is sync property - no auto-wait for updates
   - Fixed `sleep(15)` waited for time but didn't verify URL changed

   **Solution** (commit `9330a23`):

   ```python
   # ✅ Correct - Explicit URL change verification
   old_url = list_url
   url_updated = False
   for retry in range(10):
       current_frame_url = list_frame.url
       if current_frame_url != old_url:
           list_url = current_frame_url
           url_updated = True
           self.logger.info(f"✓ URL changed after {retry * 2}s: {list_url}")
           break
       time.sleep(2)

   if not url_updated:
       self.logger.warning(
           f"URL did not change after 20s, using current frame URL: {list_frame.url}"
       )
       list_url = list_frame.url
   ```

   **Key Features**:
   - **Explicit verification**: Compare old vs new URL
   - **Adaptive wait**: Max 20s, early exit when change detected
   - **Detailed logging**: Record timing for debugging (`✓ URL changed after Xs`)
   - **Fail-safe**: Use current frame URL if no change after timeout

   **Critical Lessons**:
   - ❌ **Avoid**: Blind property access after state changes
   - ❌ **Avoid**: Fixed `sleep()` without state verification
   - ✅ **Use**: Polling + explicit comparison + timeout
   - ✅ **Use**: Detailed logs for timing analysis

   **Playwright Limitations**:
   - Auto-waiting works for actions (`click`, `fill`)
   - Property access (`frame.url`) has NO auto-waiting
   - → Always verify property updates explicitly

   **ASP.NET Webforms Specific**:
   - `__doPostBack` completion ≠ DOM/URL update completion
   - Always poll for state changes, never assume timing

   **Verification Checklist** (for Playwright property access):
   - [ ] Property value compared before/after state change?
   - [ ] Polling logic with timeout implemented?
   - [ ] Early exit when change detected (not just fixed sleep)?
   - [ ] Logs show timing of state change?
   - [ ] Fail-safe for timeout case?

   **Reference**: `docs/incident-2025-11-06-pagination-url-update-delay.md`

9. **Phase B: Deleting Critical STEP 1 Based on False Premise** (2025-11-07 incident)
   - ❌ Deleted STEP 1 (118 lines) assuming commit 3bd3399 was correct
   - ❌ Added ineffective URL check code (Lines 988-1019) based on false premise that "URL changes after pagination"
   - ✅ **Always verify assumptions against documentation before deleting critical code**
   - Impact: Page 2+ students (100 out of 200 reports) failed to collect

   **Root Cause**: Commit 672afc9 assumed `list_frame.url` changes after pagination, but it always equals the original `list_url`

   ```python
   # Lines 988-1019 (Phase B ineffective code - DELETED in fix)
   if list_frame.url != list_url:  # ❌ Always FALSE
       # This condition NEVER executes
       # URL remains "carewel.dk-lab.jp" regardless of page number
   ```

   **Evidence**:
   - `docs/pagination-viewstate-solution-2025-11-06.md` Line 251: "このチェックは常にFalse" (This check is always False)
   - `docs/playwright-page-navigation-flow.md` Lines 182-185: Official specification that Phase B violated

   **Why it happened**:
   - Misinterpreted git history without verifying against current documentation
   - Assumed newer commit (672afc9) was correct without testing the premise
   - Deleted STEP 1 (the ONLY way to navigate to Page 2+ before detail link search)
   - Added 43 lines of URL polling code based on false assumption

   **Impact Chain**:
   ```
   STEP 1 deleted → No navigation to Page 2 before detail link search
   → Page 2 students processed on Page 1's DOM
   → Detail links not found (students are on different page)
   → 100 out of 200 reports failed to collect
   ```

   **Solution** (commit `00a87be`):

   **Part 1: Delete ineffective code**
   ```python
   # Deleted Lines 988-1019 (32 lines)
   # - frame.url != list_url check (always False)
   # - Unnecessary frame.goto() logic
   # - URL polling code based on false premise
   ```

   **Part 2: Restore STEP 1 with pagination control**
   ```python
   # Added 48 lines (Lines 986-1032)
   # STEP 1: Navigate to correct page BEFORE detail link search
   if current_page > 1:
       pagination_select = list_frame.locator("#ctl00_masterMain_ddlPage")
       if pagination_select.count() > 0:
           pagination_select.select_option(str(current_page))
           time.sleep(15)  # Page transition wait

           # Frame refresh with retry logic
           for retry in range(3):
               # ... frame refresh code ...
   ```

   **Critical Lessons**:
   - ❌ **"Newer commit ≠ Correct approach"** - Always verify against specifications
   - ❌ **Don't delete code without understanding WHY it existed**
   - ✅ **Read specification documents BEFORE making architectural changes**
   - ✅ **Test critical assumptions** (e.g., "Does URL actually change?")
   - ✅ **Document-driven verification**: Compare implementation against `docs/playwright-page-navigation-flow.md`

   **Verification Checklist** (before deleting critical code):
   - [ ] Read specification documents that describe this code's purpose?
   - [ ] Understand WHY the code was added (check git history AND docs)?
   - [ ] Test assumptions in newer commits (e.g., URL change behavior)?
   - [ ] Identify alternative approaches if this code is removed?
   - [ ] Consider impact on multi-page processing (Page 2+ scenarios)?

   **User Quote**: _"ちゃんとドキュメントをみてから行動してください"_ (Please check documentation properly before taking action)

   **References**:
   - `docs/playwright-page-navigation-flow.md` Lines 182-185 (official specification)
   - `docs/pagination-viewstate-solution-2025-11-06.md` Line 251 (evidence URL never changes)
   - `docs/incident-2025-11-06-pagination-url-update-delay.md` (related ASP.NET behavior)

10. **Assuming Parameter Names Without Verification** (2025-11-08 incident)
   - ❌ Assumed `Sid` parameter exists in detail links without checking actual HTML
   - ✅ **Always verify actual parameter names in production HTML before coding**
   - Impact: Page 2+ students failed with 0% success rate (№01 課題①)

   **Root Cause**: Commit `054614c` introduced `Sid` parameter extraction without verifying production HTML

   ```python
   # ❌ Wrong (Line 1199 - Assumed parameter name)
   sid_match = re.search(r"Sid=(\d+)", detail_url)  # Sid doesn't exist!

   # ✅ Correct (Verified from actual HTML)
   log_id_match = re.search(r"log_id=(\d+)", detail_url)
   ```

   **Evidence from Production HTML** (verified 2025-11-08):

   ```html
   <!-- Page 1 student -->
   <a href="report.aspx?log_id=7451&unit_id=684&course_id=41&filter=all">
     川久保　晃 <N9903754>
   </a>

   <!-- Page 2 student -->
   <a href="report.aspx?log_id=8577&unit_id=684&course_id=41&filter=all">
     杉山　千晶 <N9903321>
   </a>
   ```
   → **Sid parameter does NOT exist. Only log_id exists.**

   **Why it happened**:
   - Tried to improve from exact match (`a[href="{detail_url}"]`) to partial match
   - Changed to parameter-based search for flexibility
   - **Guessed parameter name `Sid` without checking actual HTML**
   - Possibly assumed based on experience with other ASP.NET systems
   - Did not verify parameter names in browser DevTools

   **Impact Chain**:
   ```
   Sid extraction fails → return {"url": None, "filename": None}
   → Student download fails → Retry 3 times → Still fails
   → Page 2+ students 0% success rate
   ```

   **Solution** (commit `ae5d169`):
   - Replace all `Sid` references with `log_id` (5 locations, Lines 1196-1217)
   - Verify regex matches actual URL parameter: `r"log_id=(\d+)"`

   **Critical Lessons**:
   - ❌ **NEVER guess parameter/field names without verification**
   - ❌ Don't rely on assumptions from other systems
   - ✅ **ALWAYS inspect actual production HTML in browser DevTools**
   - ✅ Log actual URL values during development to verify parameters
   - ✅ Add diagnostic logs that show extracted parameter values

   **Verification Checklist** (before implementing URL/parameter parsing):
   - [ ] Opened browser DevTools and inspected actual HTML?
   - [ ] Verified parameter names in production environment?
   - [ ] Logged actual URL examples in code comments?
   - [ ] Added error logs that show full URL when extraction fails?
   - [ ] Tested with real data from all pages (Page 1, Page 2, etc.)?

   **Prevention**:
   ```python
   # ✅ Good practice: Log actual URL for verification
   self.logger.debug(f"Extracting from detail_url: {detail_url}")
   log_id_match = re.search(r"log_id=(\d+)", detail_url)
   if not log_id_match:
       self.logger.error(
           f"Failed to extract log_id from detail_url: {detail_url}"
           # ↑ Full URL logged - easy to spot parameter name issues
       )
   ```

   **Reference**:
   - Cloud Run logs 2025-11-08 00:10-00:12 JST
   - Student: 杉山 千晶 (N9903321, Page 2)
   - Commit 054614c (introduced Sid - wrong assumption)
   - Commit ae5d169 (fixed with log_id - verified from HTML)

11. **Phase 1最適化の設計ミス - 必須処理のスキップ禁止** (2025-11-08 incident)
   - ❌ go_back()をスキップして詳細ページに留まる
   - ❌ 次の学生処理時に詳細ページから抜け出せない
   - ✅ タイムアウト短縮で最適化（180秒 → 30秒）
   - Impact: 2人目以降の学生全員が処理失敗（1人目のみ成功）

   **Root Cause**: コミット bbd61ab（Phase 1最適化）

   ```python
   # ❌ Wrong (Lines 1272-1292) - Page 2+でgo_back()スキップ
   if current_page > 1:
       self.logger.info(f"[PHASE 1] Skipping go_back() for Page {current_page}")
       # → 詳細ページに留まる
       # → 次の学生処理時にpagination control見つからず失敗
   else:
       self.page.go_back(wait_until="load", timeout=30000)

   # ✅ Correct - 全ページでgo_back()を30秒で実行
   try:
       self.page.go_back(wait_until="load", timeout=30000)
   except Exception as e:
       self.logger.warning(f"[PHASE 1] go_back timeout: {e}")
   self._wait_for_navigation()
   ```

   **Why it happened**:
   - タイムアウト回避を優先しすぎて必須処理（go_back）をスキップ
   - 詳細ページからリストページに戻る手段がgo_back()しかないことを見落とし
   - STEP 2のpagination control検索が「リストページに戻った後」を前提としていることを見落とし
   - docs/playwright-page-navigation-flow.md Lines 182-185を確認しなかった

   **Impact Chain**:
   ```
   学生A: 詳細ページ表示 → go_back()スキップ → 詳細ページ留まる
   学生B: STEP 1開始 → 詳細ページのまま → pagination control無し → 失敗
   学生C: STEP 1開始 → 詳細ページのまま → pagination control無し → 失敗
   ...（以降全員失敗）
   ```

   **Solution** (commit `6e39cce`):
   - 3箇所のgo_back()処理を統一（Success/TimeoutError/Exception Path）
   - 全ページで30秒タイムアウトgo_back()を実行（スキップしない）
   - 処理時間: 200レポート = 600分 → 100分（500分削減、83%削減）

   **Critical Lessons**:
   - ❌ タイムアウト回避のために必須処理をスキップしてはいけない
   - ❌ 条件分岐で処理をスキップする前に、スキップ後のフローを検証する
   - ❌ ドキュメント確認なしにナビゲーション処理を変更してはいけない
   - ✅ タイムアウト短縮で最適化する（スキップではなく短縮）
   - ✅ 戻り処理（go_back）は次の処理の前提条件
   - ✅ 1人目成功・2人目以降失敗のパターンは処理間の状態引き継ぎミス
   - ✅ Common Mistake #9（Phase B）と同じ失敗パターン

   **Verification Checklist** (before skipping navigation):
   - [ ] docs/playwright-page-navigation-flow.md Lines 182-185を確認したか？
   - [ ] STEP 2の前提条件（リストページに戻る）を理解したか？
   - [ ] スキップ後、次の処理の前提条件（ページ状態）は満たされるか？
   - [ ] 詳細ページからリストページに戻る代替手段があるか？
   - [ ] 1人目成功・2人目失敗のパターンになっていないか？
   - [ ] ログで「Frame URL」が詳細ページのまま留まっていないか？
   - [ ] STEP 1の「pagination control not found」が連続発生していないか？

   **Reference**:
   - **docs/incident-2025-11-08-phase1-go-back-skip-bug.md** - 詳細なインシデントレポート
   - docs/playwright-page-navigation-flow.md Lines 182-185 (STEP 2 design)
   - docs/pagination-viewstate-solution-2025-11-06.md Lines 136-139, 170-171 (ASP.NET behavior)
   - CLAUDE.md Lines 269-309 (Common Mistake #9 - similar pattern)
   - Cloud Run logs 2025-11-08 23:25-23:51 JST
   - Revision: carewell-file-collector-00232-wj4 (問題発生), 00234-q22 (修正後)
   - Student: 齊藤誠（1人目・成功）、林秀明（2人目・失敗）、以降全員失敗
   - Commit bbd61ab (introduced bug - go_back skip)
   - Commit 6e39cce (fixed - unified go_back with 30s timeout)

   ---

   **🔍 診断手順（1人目成功・2人目以降失敗パターン）**:

   1. **Frame URL確認**:
      ```bash
      gcloud logging read "textPayload=~'Frame URL'" --limit 20 | grep "report.aspx?log_id"
      ```
      → 詳細ページ（`report.aspx?log_id=XXX`）に留まっている場合、go_back()がスキップされている

   2. **go_back()実行確認**:
      ```bash
      gcloud logging read "textPayload=~'Skipping go_back'" --limit 10
      ```
      → スキップログが出ている場合、条件分岐を確認

   3. **STEP 1 FAILEDパターン確認**:
      ```bash
      gcloud logging read "textPayload=~'STEP 1 FAILED'" --limit 20
      ```
      → 連続発生している場合、pagination controlが見つからない（詳細ページにいる証拠）

   **詳細診断**: `docs/troubleshooting.md`（Mermaid診断フローチャート参照）

   ---

   **✅ 最適化ベストプラクティス**:

   | アプローチ | 処理時間削減 | 成功率 | リスク | 推奨度 |
   |----------|------------|-------|-------|--------|
   | タイムアウト短縮（30秒） | 83% | 100% | 低 | ⭐⭐⭐⭐⭐ |
   | 必須処理スキップ | 理論上91% | 0.5% | **致命的** | ❌ **禁止** |
   | 並列処理 | 最大50% | 不明 | 中 | △ 将来検討 |
   | Frame待機短縮 | 10-20% | 80-90% | 中 | △ 慎重に |

   **推奨アプローチ**: タイムアウト短縮（180秒 → 30秒）

   **禁止アプローチ**: 必須処理（go_back）のスキップ

   **詳細ガイド**: `docs/phase1-optimization-patterns.md`

   ---

   **📊 参考処理時間**:

   | 学生数 | 元の実装（180秒/件） | 最適化後（30秒/件） | 削減時間 | 削減率 |
   |-------|-------------------|------------------|---------|--------|
   | 100名 | 300分 (5時間) | 50分 | 250分 | 83% |
   | 158名 | 474分 (7.9時間) | 79分 | 395分 | 83% |
   | 200名 | 600分 (10時間) | 100分 (1.7時間) | 500分 | 83% |

   Cloud Run 25分タイムアウト制限により、元の実装では完了不可 → 最適化必須

   ---

   **🎯 デプロイ後の検証コマンド**:

   ```bash
   # 1. STEP 1失敗確認（0件が期待値）
   gcloud logging read "textPayload=~'\[STEP 1 FAILED\]'" --limit 10

   # 2. Phase 1完了統計
   gcloud logging read "textPayload=~'Download links obtained'" --limit 5

   # 3. Phase 2開始確認
   gcloud logging read "textPayload=~'Downloading:'" --limit 20

   # 4. 2人目の学生が成功しているか確認
   gcloud logging read "textPayload=~'Added:.*-'" --limit 5
   ```

   **期待される結果**:
   - STEP 1 FAILED: 0件
   - Download links obtained: 49/200など（重複除外後の新規ファイル数）
   - Downloading: 複数件（Phase 2実行中）
   - Added: 全員がファイル名付き（"None"が無い）

   ---

   **📚 関連ドキュメント**:
   - **トラブルシューティング**: `docs/troubleshooting.md`（診断フローチャート）
   - **最適化ガイド**: `docs/phase1-optimization-patterns.md`（ベストプラクティス）
   - **インシデントレポート**: `docs/incident-2025-11-08-phase1-go-back-skip-bug.md`（詳細記録）
   - **STEP 2設計**: `docs/playwright-page-navigation-flow.md` Lines 182-185
   - **ASP.NET behavior**: `docs/pagination-viewstate-solution-2025-11-06.md` Lines 136-139, 170-171

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
