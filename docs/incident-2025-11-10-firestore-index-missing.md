# Incident Report: Firestore Index Missing After Phase 2 Deployment

**Date**: 2025-11-10
**Severity**: 🔴 High
**Status**: ✅ Resolved
**Duration**: ~12 hours (13:00 JST - next successful run)

---

## Executive Summary

Phase 2 Dashboard deployment on 2025-11-10 13:00 JST triggered automatic deletion of manually created Firestore indexes, causing backend duplicate check queries to fail. This resulted in all files being treated as "new", leading to infinite download loops and 25-minute timeouts. The issue was resolved by adding the missing composite index definition to `dashboard/firestore.indexes.json` and removing the `(default)` database configuration.

**Impact**: Cloud Scheduler timeouts affecting all classes and tasks for 12 hours
**Root Cause**: Infrastructure as Code (IaC) gap - manually created indexes were not documented in code
**Resolution Time**: 1.5 hours (investigation + fix + deployment + verification)

---

## Timeline

| Time (JST) | Event | Evidence | Impact |
|------------|-------|----------|--------|
| **2025-11-04 17:55** | Dashboard initial setup | `git show 3bd76ea:dashboard/firestore.indexes.json` | `indexes: []` created (empty) |
| **2025-11-04 - 2025-11-10** | Normal operation period | Cloud Run logs | Manual indexes working (created in Firestore console) |
| **2025-11-10 13:00:42** | Phase 2: collectionGroup index added | `git show 1ff3401` | `firebase deploy --only firestore` executed |
| **2025-11-10 13:00** | 🔥 Manual indexes deleted | GitHub Actions logs | `indexes: []` applied, existing indexes removed |
| **2025-11-10 13:00** | ❌ Timeout started | Cloud Run logs "DEADLINE_EXCEEDED" | Duplicate check failed, infinite loop |
| **2025-11-10 13:30+** | ❌ Continued timeouts | Recurring every 30 mins | 12-hour service degradation |

---

## Problem Description

### Symptoms

1. **Cloud Scheduler Timeout**
   - Jobs timing out at exactly 25 minutes (1500 seconds)
   - Error: `DEADLINE_EXCEEDED`
   - All classes and tasks affected

2. **Expected vs Actual Behavior**
   - **User verification**: 0 new files (all duplicates)
   - **Actual**: System downloading files indefinitely (infinite loop)
   - **Logs**: "Performing early duplicate check for 100 submissions" present
   - **Missing**: "Duplicate detected" logs completely absent

3. **Performance Degradation**
   - Normal execution: 2-3 minutes
   - After incident: 25 minutes → timeout
   - Efficiency: 0% (no files saved before timeout)

### User Report

> "目視で取得対象は0件（すべて重複のはず）なのに、延々とファイルをダウンロードし続けている"

---

## Root Cause Analysis

### Primary Cause: Missing Firestore Composite Index

**Backend Query** (`src/firestore_service.py:136-139`):
```python
docs = (
    collection_ref.where("student_id", "==", student_id)
    .where("submit_date", "==", submit_date)  # 2 equality operators → composite index required
    .limit(1)
    .stream()
)
```

**Required Index**:
```json
{
  "collectionGroup": "files",
  "queryScope": "COLLECTION_GROUP",
  "fields": [
    {"fieldPath": "student_id", "order": "ASCENDING"},
    {"fieldPath": "submit_date", "order": "ASCENDING"}
  ]
}
```

**Without Index**: Query returns empty results (fail-open behavior)
**Impact**: All files treated as "new" → infinite download loop

### Secondary Cause: `(default)` Database in firebase.json

**Problem**: `dashboard/firebase.json` defined TWO databases:
```json
{
  "firestore": [
    {
      "database": "(default)",  // ← Datastore Mode (collectionGroup indexes not supported)
      "indexes": "firestore.indexes.json"
    },
    {
      "database": "carewell-native",  // ← Firestore Native Mode (Backend uses this)
      "indexes": "firestore.indexes.json"
    }
  ]
}
```

**Error during deployment**:
```
Error: Request to https://firestore.googleapis.com/v1/projects/carewell-automation/databases/(default)/collectionGroups/files/indexes
had HTTP Error: 400, ANY_API ApiScope is not supported for Datastore Mode databases.
```

### Contributing Factors

1. **IaC Gap**
   - Manual index creation in Firestore console (not documented in code)
   - `dashboard/firestore.indexes.json` initialized with `indexes: []`
   - No documentation of manual indexes

2. **Multi-Service Firestore Sharing**
   - Dashboard and Backend share same Firestore
   - Index definitions only in Dashboard repository
   - Backend index requirements not considered during Dashboard setup

3. **Declarative Deployment Behavior**
   - `firebase deploy --only firestore` maintains ONLY defined indexes
   - Undefined indexes are deleted (by design)
   - Team unaware of this Firebase CLI behavior

---

## Investigation Process

### Step 1: Symptom Analysis
```bash
# Cloud Run logs showed timeout
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  severity>=ERROR" --limit 10

# Result: DEADLINE_EXCEEDED at exactly 1500 seconds
```

### Step 2: Log Pattern Analysis
- ✅ "Performing early duplicate check for 100 submissions" present
- ❌ "Duplicate detected" logs ABSENT
- 🔍 Hypothesis: Duplicate check query failing silently

### Step 3: Firestore Query Investigation
```python
# src/firestore_service.py:136-139
docs = (
    collection_ref.where("student_id", "==", student_id)
    .where("submit_date", "==", submit_date)  # 2 equality operators
    .limit(1)
    .stream()
)
```
→ Requires composite index for 2 equality operators

### Step 4: Firestore Console Check
- **Finding**: No composite index for `files` collection group
- **Expected**: `student_id` + `submit_date` composite index
- **Status**: Missing

### Step 5: Git History Analysis
```bash
git log --all --oneline --grep="firestore.indexes"
# Result: firebase.indexes.json created with "indexes": []
```

### Step 6: Deployment Timeline Correlation
- Phase 2 deployment: 2025-11-10 13:00:42 JST
- First timeout: 2025-11-10 13:00 JST
- **Conclusion**: Deployment triggered index deletion

---

## Solution

### Fix 1: Add Backend Composite Index

**File**: `dashboard/firestore.indexes.json`

**Change**:
```diff
 {
-  "indexes": [],
+  "indexes": [
+    {
+      "collectionGroup": "files",
+      "queryScope": "COLLECTION_GROUP",
+      "fields": [
+        {
+          "fieldPath": "student_id",
+          "order": "ASCENDING"
+        },
+        {
+          "fieldPath": "submit_date",
+          "order": "ASCENDING"
+        }
+      ]
+    }
+  ],
   "fieldOverrides": [
     {
       "collectionGroup": "files",
       "fieldPath": "student_id",
       "indexes": [
         {
           "order": "ASCENDING",
           "queryScope": "COLLECTION_GROUP"
         }
       ]
     }
   ]
 }
```

**Commit**: `eb9f4b2`

### Fix 2: Remove `(default)` Database Configuration

**File**: `dashboard/firebase.json`

**Change**:
```diff
-  "firestore": [
-    {
-      "database": "(default)",
-      "rules": "firestore.rules",
-      "indexes": "firestore.indexes.json"
-    },
-    {
-      "database": "carewell-native",
-      "rules": "firestore.rules",
-      "indexes": "firestore.indexes.json"
-    }
-  ],
+  "firestore": {
+    "database": "carewell-native",
+    "rules": "firestore.rules",
+    "indexes": "firestore.indexes.json"
+  },
```

**Commit**: `1a56352`

### Deployment

1. **GitHub Actions** (Run ID: 19226772176)
   - Status: ✅ Success (2m38s)
   - Steps: Build → Deploy Firestore Security Rules → Deploy Hosting

2. **Firestore Index Creation**
   - Status: Building → Enabled (2-5 minutes)
   - Index ID: `CICAgJlUpoMK`
   - Verified in Firestore Console

3. **Verification**
   - Cloud Scheduler execution: 2m37s (vs 25min timeout)
   - Duplicate detection: 200/200 files correctly identified
   - Performance: 90% execution time reduction

---

## Verification Results

### Before Fix
```
❌ Duplicate check query: FAILED (index missing)
❌ Files processed: 0/200 (timeout before completion)
❌ Execution time: 25 minutes (DEADLINE_EXCEEDED)
❌ Duplicate detection: 0/200 (all treated as "new")
```

### After Fix
```
✅ Duplicate check query: SUCCESS (index enabled)
✅ Files processed: 200/200 (all duplicates correctly identified)
✅ Execution time: 2m37s (90% reduction)
✅ Duplicate detection: 200/200 (100% accuracy)
```

### Cloud Run Logs (Post-Fix)
```
2025-11-10 09:33:03,568 - Duplicate detected (early check): 川久保 晃 (student_id=N9903754, ...)
2025-11-10 09:33:03,596 - Duplicate detected (early check): 平嶋 俊司 (student_id=N9903080, ...)
2025-11-10 09:33:03,621 - Duplicate detected (early check): 吉岡 宏行 (student_id=N9903083, ...)
...
2025-11-10 09:34:09,394 - [PHASE 1] Complete. Download links obtained: 0/200
2025-11-10 09:34:09,394 - ✓ Count verification passed: 200/200
2025-11-10 09:34:13,283 - Closing browser
```

**Total execution time**: 09:31:36 → 09:34:13 = **2 minutes 37 seconds** ✅

---

## Lessons Learned

### 1. Infrastructure as Code (IaC) Discipline

**Problem**: Manual Firestore index creation without code documentation

**Consequences**:
- Indexes deleted during declarative deployment
- No audit trail of manual changes
- Difficult to reproduce in other environments

**Solution**:
- ✅ ALL Firestore indexes MUST be defined in `firestore.indexes.json`
- ✅ NEVER create indexes manually in console without immediately documenting in code
- ✅ Treat `firebase deploy --only firestore` as destructive operation

### 2. Multi-Service Resource Sharing

**Problem**: Dashboard and Backend share Firestore, but index definitions only in Dashboard

**Consequences**:
- Backend index requirements not considered during Dashboard setup
- Cross-service dependencies not visible

**Solution**:
- ✅ Document ALL service query patterns before adding indexes
- ✅ Create unified index definition covering all services
- ✅ Add comments in `firestore.indexes.json` indicating which service uses each index

### 3. Declarative Deployment Understanding

**Problem**: Team unaware that `firebase deploy --only firestore` deletes undefined indexes

**Consequences**:
- Unexpected index deletion
- Production incident

**Solution**:
- ✅ Document Firebase CLI declarative behavior in project docs
- ✅ Always review `firestore.indexes.json` before deployment
- ✅ Verify indexes in Firestore Console after deployment
- ✅ Monitor Cloud Run logs for "index required" errors

### 4. Silent Query Failures

**Problem**: Firestore queries without indexes return empty results (no error thrown)

**Consequences**:
- Difficult to diagnose (no explicit error message)
- Wrong behavior instead of error logs

**Solution**:
- ✅ Add explicit logging when duplicate check returns no results
- ✅ Monitor metrics: "Expected duplicates vs Actual duplicates"
- ✅ Alert when duplicate detection rate drops significantly

---

## Prevention Checklist

### When Adding New Firestore Query

- [ ] Check if query uses 2+ equality operators (`==`) or range operators
- [ ] Define required composite index in `dashboard/firestore.indexes.json`
- [ ] Add comment indicating which service/function uses this index
- [ ] Test query with Firestore Emulator (note: indexes optional in emulator)
- [ ] Test query in production Firestore after index creation

### Before Firestore Deployment

- [ ] Review `dashboard/firestore.indexes.json` contents
- [ ] Verify Backend index (`student_id` + `submit_date`) exists
- [ ] Verify Dashboard index (`student_id` single field) exists
- [ ] Check for any manually created indexes in Firestore Console
- [ ] Document any manual indexes in `firestore.indexes.json` BEFORE deploying

### After Firestore Deployment

- [ ] Verify indexes in Firestore Console: https://console.firebase.google.com/project/carewell-automation/firestore/indexes
- [ ] Wait for index creation to complete (Status: Building → Enabled)
- [ ] Monitor Cloud Run logs for "index required" or "FAILED_PRECONDITION" errors
- [ ] Trigger Cloud Scheduler job manually to verify functionality
- [ ] Verify duplicate detection logs appear in Cloud Run

### Multi-Service Environment

- [ ] List ALL services using shared Firestore
- [ ] Document query patterns for each service
- [ ] Create unified `firestore.indexes.json` covering all services
- [ ] Test impact on ALL services after index changes

---

## Emergency Recovery Procedure

### Symptoms Recognition
- Cloud Scheduler timing out at 25 minutes
- "Duplicate detected" logs absent
- Page 1 infinite loop (same students repeatedly processed)

### Diagnosis
```bash
# 1. Check Cloud Run logs for index errors
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=carewell-file-collector AND \
  (textPayload=~'index' OR textPayload=~'FAILED_PRECONDITION')" \
  --limit 50 --format=json

# 2. Check Firestore Console indexes
# URL: https://console.firebase.google.com/project/carewell-automation/firestore/indexes
# Expected: Composite index for "files" collection group

# 3. Check firebase.indexes.json
cat dashboard/firestore.indexes.json | jq '.indexes'
# Expected: Non-empty array with composite index definition
```

### Recovery Steps

1. **Add Missing Index** to `dashboard/firestore.indexes.json`:
   ```json
   {
     "indexes": [
       {
         "collectionGroup": "files",
         "queryScope": "COLLECTION_GROUP",
         "fields": [
           {"fieldPath": "student_id", "order": "ASCENDING"},
           {"fieldPath": "submit_date", "order": "ASCENDING"}
         ]
       }
     ]
   }
   ```

2. **Deploy Firestore Indexes**:
   ```bash
   cd dashboard
   firebase deploy --only firestore:indexes --project carewell-automation
   ```

3. **Wait for Index Creation** (2-5 minutes):
   - Monitor Firestore Console
   - Status: Building → Enabled

4. **Verify Recovery**:
   ```bash
   # Trigger Cloud Scheduler manually
   gcloud scheduler jobs run carewell-class01-task01 --location=asia-northeast1

   # Check for duplicate detection logs
   gcloud logging read "textPayload=~'Duplicate detected'" --limit 10
   ```

5. **Confirm Success**:
   - Execution time: 2-3 minutes (not 25 minutes)
   - "Duplicate detected" logs present
   - No timeout errors

---

## Related Documentation

### Primary Documents
- **Incident Summary**: `docs/common-mistakes.md` Incident #13
- **Firestore Configuration**: `.kiro/steering/firestore-critical-config.md`
- **Firestore Schema**: `.kiro/specs/firestore-schema-improvement/design.md`

### Code References
- **Backend Query**: `src/firestore_service.py:105-157` (duplicate check function)
- **Backend Caller**: `src/playwright_automation.py:677-710` (early duplicate check loop)
- **Index Definition**: `dashboard/firestore.indexes.json`
- **Firebase Config**: `dashboard/firebase.json`

### External References
- **Firestore Indexing**: https://firebase.google.com/docs/firestore/query-data/indexing
- **Firebase CLI**: https://firebase.google.com/docs/cli

---

## Impact Assessment

### Service Impact
- **Duration**: ~12 hours (13:00 JST - next successful run)
- **Scope**: All classes, all tasks (100% of scheduled jobs affected)
- **Data Integrity**: No data loss (timeouts prevented incorrect uploads)
- **User Impact**: Collection delay (12-hour lag in file availability)

### Cost Impact
- **Cloud Run**: Extended execution time (25min × multiple runs)
- **Firestore**: Increased read operations (repeated duplicate checks)
- **Estimated Additional Cost**: $1-2 (minor)

### Severity Justification: 🔴 High
- Production system completely unavailable for primary function (file collection)
- All scheduled jobs failing consistently
- Required manual intervention to resolve
- 12-hour service degradation

---

## Action Items

### Immediate (Completed)
- [x] Add composite index to `firestore.indexes.json`
- [x] Remove `(default)` database from `firebase.json`
- [x] Deploy fixes via GitHub Actions
- [x] Verify index creation in Firestore Console
- [x] Verify functionality with Cloud Scheduler test run
- [x] Document incident in `docs/common-mistakes.md`
- [x] Update `.kiro/steering/firestore-critical-config.md`

### Short-term (Recommended)
- [ ] Add monitoring alert for duplicate detection rate < 80%
- [ ] Add explicit logging when duplicate check returns empty results
- [ ] Create pre-deployment checklist for Firestore changes
- [ ] Add automated test for Firestore index existence

### Long-term (Strategic)
- [ ] Implement centralized Firestore configuration management
- [ ] Create automated index validation in CI/CD pipeline
- [ ] Document all cross-service Firestore dependencies
- [ ] Consider separating Dashboard and Backend Firestore databases

---

## Conclusion

This incident highlighted the importance of Infrastructure as Code discipline and comprehensive documentation. The root cause was a gap between manual infrastructure changes (Firestore indexes) and code definitions (`firestore.indexes.json`). By establishing strict IaC practices and improving documentation, similar incidents can be prevented in the future.

**Key Takeaway**: "If it's not in code, it doesn't exist" - all infrastructure must be defined declaratively in version-controlled files.

---

**Report Author**: Claude Code AI Agent
**Report Date**: 2025-11-10
**Last Updated**: 2025-11-10
