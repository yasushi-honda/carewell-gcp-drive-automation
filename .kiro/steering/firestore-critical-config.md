# Firestore Critical Configuration Rules

**IMPORTANT: This steering document is ALWAYS loaded. Read carefully before any Firestore-related changes.**

## Purpose

Prevent configuration mistakes and design specification violations when working with Firestore.

## Critical Rules

### Rule 1: Database Name is IMMUTABLE

**Database name MUST be `carewell-native` in ALL contexts:**

- ✅ Production: `carewell-native`
- ✅ Test (unit): `carewell-native`
- ✅ Test (integration): `carewell-native`
- ✅ Emulator: `carewell-native`
- ❌ NEVER use `(default)` database

**Reference documents:**

- `.kiro/specs/firestore-schema-improvement/requirements.md` (Lines 1-10)
- `docs/firestore-schema-improvement-implementation.md` (Line 529)

**Code locations to verify:**

- `src/firestore_service.py` Line 20: `firestore.Client(database="carewell-native")`
- `tests/conftest.py` Line 20: `firestore.Client(project=project_id, database="carewell-native")`
- `tests/conftest.py` Line 54: `firestore.Client(project=project_id, database="carewell-native")`

### Rule 2: Collection Path Structure is FIXED

**Correct path structure (as per design specification):**

```text
submissions/{class_name}/tasks/{task_id}/files/{composite_key}
```

**Incorrect paths (legacy, DO NOT USE):**

- ❌ `{class_name}/{task_id}/documents/{composite_key}`
- ❌ `{class_name}/{task_id}/files/{composite_key}`

**Reference documents:**

- `.kiro/specs/firestore-schema-improvement/design.md` (Lines 51-75)

**Code locations to verify:**

- `src/firestore_service.py`:
  - Line 67-72: `_update_task_metadata()` method
  - Line 127-133: `check_already_uploaded_by_student_date()` method
  - Line 186-193: `check_already_uploaded()` method
  - Line 270-277: `record_upload()` method

### Rule 3: task_pattern Parameter is REQUIRED

**When calling `record_upload()`, MUST pass `task_pattern` from Cloud Scheduler request.**

**Common mistake:**

```python
# ❌ WRONG: Missing task_pattern parameter
firestore_service.record_upload(
    class_name, task_id, student_name, student_id,
    filename, drive_file_id, drive_folder_id, submit_date,
    metadata=metadata
)
# Result: task_pattern defaults to task_id → incorrect metadata in Firestore

# ✅ CORRECT: Pass task_pattern
firestore_service.record_upload(
    class_name, task_id, student_name, student_id,
    filename, drive_file_id, drive_folder_id, submit_date,
    metadata=metadata,
    task_pattern=task_pattern  # ← This parameter is REQUIRED
)
```

**Reference documents:**

- `.kiro/specs/firestore-schema-improvement/requirements.md` (Lines 98-102)
- `.kiro/specs/firestore-schema-improvement/design.md` (Lines 367-374)

**Code location to verify:**

- `src/main.py` Line 183-194: `firestore_service.record_upload()` call

### Rule 4: Atomic Increment for file_count

**Parent document `file_count` MUST use `firestore.Increment(1)`:**

```python
# ✅ CORRECT: Atomic increment
update_data = {
    "task_id": task_id,
    "task_pattern": task_pattern,
    "file_count": firestore.Increment(1),  # ← Atomic operation
    "last_updated": firestore.SERVER_TIMESTAMP,
}

# ❌ WRONG: Manual increment
doc = task_ref.get()
current_count = doc.to_dict().get("file_count", 0)
update_data = {
    "file_count": current_count + 1  # ← Race condition possible
}
```

**Reference documents:**

- `.kiro/specs/firestore-schema-improvement/design.md` (Lines 403-407)

**Code location to verify:**

- `src/firestore_service.py` Line 78-83: `_update_task_metadata()` method

## Pre-Commit Checklist

Before committing changes to Firestore-related files:

- [ ] Verified database name is `carewell-native` (NOT `(default)`)
- [ ] Verified collection path uses: `submissions/{class_name}/tasks/{task_id}/files/{composite_key}`
- [ ] Verified `task_pattern` is passed to `record_upload()` from Cloud Scheduler request
- [ ] Verified `file_count` uses `firestore.Increment(1)`
- [ ] Read the relevant design document sections
- [ ] Unit tests pass
- [ ] Integration tests pass with Firestore Emulator

## Design Document Reference

**Files that require reading design docs before modification:**

| File | Design Document | Key Sections |
|------|----------------|--------------|
| `src/firestore_service.py` | `.kiro/specs/firestore-schema-improvement/design.md` | Lines 351-430, 493-502 |
| `src/main.py` | `.kiro/specs/firestore-schema-improvement/requirements.md` | Lines 96-104 |
| `tests/conftest.py` | `docs/firestore-schema-improvement-implementation.md` | Lines 520-536 |
| `tests/integration/test_file_upload.py` | `.kiro/specs/firestore-schema-improvement/design.md` | Lines 51-75 |

## Past Incidents (Learn from mistakes)

### Incident 1: Database Name Mistake (2025-11-04)

**What happened:**

- Changed `carewell-native` to `(default)` in `tests/conftest.py`
- Assumption: Firestore Emulator only supports `(default)` database
- Did not check original design documentation

**Impact:**

- Integration tests used wrong database
- Mismatch between test and production environments
- Required revert commit

**Lesson:**

> "Firestoreのデータベースの元々の設計についてちゃんとドキュメントを確認してから対応してくださいね"

### Incident 2: Missing task_pattern Parameter (2025-11-04)

**What happened:**

- `main.py` received `task_pattern` from Cloud Scheduler
- Did not pass `task_pattern` to `record_upload()`
- Result: `task_pattern` defaulted to `task_id`

**Impact:**

- Incorrect metadata in Firestore for ALL pages (1st, 2nd, etc.)
- Dashboard displays simplified task titles
- Example: Expected "課題①業務分析　※～11/3〆切" → Got "課題①"

**Lesson:**

- Always verify ALL required parameters are passed
- Design specifications list required parameters

### Incident 3: Collection Path Mistake (Original bug)

**What happened:**

- Used old path: `{class_name}/{task_id}/documents/{composite_key}`
- Correct path: `submissions/{class_name}/tasks/{task_id}/files/{composite_key}`

**Impact:**

- Duplicate check failed (searching wrong location)
- Files re-downloaded repeatedly
- 156 expected files → 197+ downloaded

**Lesson:**

- Collection path structure is part of design specification
- Must reference design docs when modifying Firestore queries

## When to Reference This Document

**You should review this steering document when:**

- Modifying any file in `src/` that imports `firestore`
- Writing or modifying tests in `tests/` that use Firestore
- Debugging Firestore-related issues
- Adding new Firestore operations
- Reviewing pull requests that touch Firestore code

## Contact for Questions

If unsure about Firestore configuration:

1. Read the design documents listed above
2. Check past incident descriptions in this file
3. Verify against the pre-commit checklist
4. Ask the user for clarification if design docs are ambiguous
