#!/usr/bin/env python3
"""
Fix File Count Script

This script detects and fixes file_count mismatches in parent documents.
Use this when file_count becomes inaccurate due to:
- Partial migration failures
- Manual document edits
- System errors

⚠️ KNOWN BUG (found 2026-08-26, unrelated to the 令和8年度 year-string update):
This script targets db.collection(class_name).document(task_id).collection("documents"),
which is the OLD pre-migration schema. The current production writer
(src/firestore_service.py) uses submissions/{class_name}/tasks/{task_id}/files/{...}
instead. This script does NOT operate on current production data for ANY class/year.
--execute performs writes and must NOT be run until fixed. See
docs/SERVICE_SHUTDOWN_AND_RESUME.md "令和8年度（2026年度）再開ステータス" for tracking.

Usage:
    python scripts/fix_file_count.py --dry-run              # Preview mismatches
    python scripts/fix_file_count.py --execute              # Fix all mismatches
    python scripts/fix_file_count.py --execute --class-name "令和8年度 デジタル中核人材養成研修 №01"  # Fix specific class
    python scripts/fix_file_count.py --execute --class-name "令和8年度 デジタル中核人材養成研修 №01" --task-id "課題①"  # Fix specific task
"""

import argparse
import sys
from datetime import datetime
from typing import Dict, List, Optional

# Add src to path
sys.path.insert(0, "src")

from google.cloud import firestore

from config.classes import KNOWN_CLASSES, KNOWN_TASK_IDS


def fix_file_count(
    dry_run: bool = True,
    class_name: Optional[str] = None,
    task_id: Optional[str] = None,
) -> Dict:
    """
    Detect and fix file_count mismatches.

    Args:
        dry_run: If True, preview only without writing
        class_name: Optional class name to filter (None = all classes)
        task_id: Optional task ID to filter (None = all tasks)

    Returns:
        Dict with fix results:
        - success: bool
        - dry_run: bool
        - total_classes: int
        - total_tasks: int
        - checked_documents: int
        - mismatches: List[Dict] (details of mismatches)
        - fixed_documents: int
        - errors: List[Dict]
    """
    db = firestore.Client(database="carewell-native")

    # Determine target classes and tasks
    target_classes = [class_name] if class_name else KNOWN_CLASSES
    target_tasks = [task_id] if task_id else KNOWN_TASK_IDS

    result = {
        "success": True,
        "dry_run": dry_run,
        "total_classes": len(target_classes),
        "total_tasks": 0,
        "checked_documents": 0,
        "mismatches": [],
        "fixed_documents": 0,
        "errors": [],
    }

    print(f"\n{'='*60}")
    print(
        f"{'DRY RUN MODE (--execute to fix)' if dry_run else 'FIX MODE - UPDATING FILE_COUNT'}"
    )
    print(f"{'='*60}\n")

    if class_name:
        print(f"🎯 Target Class: {class_name}")
    if task_id:
        print(f"🎯 Target Task: {task_id}")
    if class_name or task_id:
        print()

    for cls_name in target_classes:
        print(f"📚 Processing class: {cls_name}")

        for tsk_id in target_tasks:
            result["total_tasks"] += 1

            try:
                # Get parent document
                task_ref = db.collection(cls_name).document(tsk_id)
                task_doc = task_ref.get()

                if not task_doc.exists:
                    print(
                        f"  ⏭️  Skipping {tsk_id}: Parent document doesn't exist (use migrate script first)"
                    )
                    continue

                result["checked_documents"] += 1

                # Get stored file_count
                task_data = task_doc.to_dict()
                stored_count = task_data.get("file_count", 0)

                # Count actual documents in subcollection
                docs = task_ref.collection("documents").stream()
                actual_count = sum(1 for _ in docs)

                # Check for mismatch
                if stored_count != actual_count:
                    difference = actual_count - stored_count
                    mismatch = {
                        "class_name": cls_name,
                        "task_id": tsk_id,
                        "stored_count": stored_count,
                        "actual_count": actual_count,
                        "difference": difference,
                    }
                    result["mismatches"].append(mismatch)

                    if dry_run:
                        # Preview mode
                        print(
                            f"  🔍 Mismatch detected in {tsk_id}: "
                            f"stored={stored_count}, actual={actual_count}, diff={difference:+d}"
                        )
                    else:
                        # Fix mode - update file_count
                        task_ref.update(
                            {
                                "file_count": actual_count,
                                "last_updated": firestore.SERVER_TIMESTAMP,
                            }
                        )
                        print(
                            f"  ✅ Fixed {tsk_id}: "
                            f"{stored_count} → {actual_count} (diff={difference:+d})"
                        )
                        result["fixed_documents"] += 1
                else:
                    print(f"  ✅ OK: {tsk_id} - file_count={actual_count} (accurate)")

            except Exception as e:
                error_detail = {
                    "class_name": cls_name,
                    "task_id": tsk_id,
                    "error": str(e),
                }
                result["errors"].append(error_detail)
                result["success"] = False
                print(f"  ❌ Error processing {tsk_id}: {e}")

        print()  # Blank line between classes

    return result


def print_summary(result: Dict) -> None:
    """
    Print fix summary report.

    Args:
        result: Fix result dictionary
    """
    print(f"\n{'='*60}")
    print("FIX FILE_COUNT SUMMARY")
    print(f"{'='*60}\n")

    print(f"Mode: {'DRY RUN (--execute to fix)' if result['dry_run'] else 'EXECUTION'}")
    print(f"Total Classes: {result['total_classes']}")
    print(f"Total Tasks Processed: {result['total_tasks']}")
    print(f"Parent Documents Checked: {result['checked_documents']}")
    print(f"Mismatches Found: {len(result['mismatches'])}")
    if not result["dry_run"]:
        print(f"Documents Fixed: {result['fixed_documents']}")
    print(f"Errors: {len(result['errors'])}")
    print(f"Success: {'✅ Yes' if result['success'] else '❌ No'}\n")

    if result["errors"]:
        print("⚠️  ERRORS ENCOUNTERED:\n")
        for error in result["errors"]:
            print(f"  - {error['class_name']}/{error['task_id']}: {error['error']}")
        print()

    if result["mismatches"]:
        print("📊 FILE_COUNT MISMATCHES:\n")
        for mismatch in result["mismatches"]:
            print(f"  {mismatch['class_name']}/{mismatch['task_id']}:")
            print(f"    Stored:  {mismatch['stored_count']}")
            print(f"    Actual:  {mismatch['actual_count']}")
            print(f"    Diff:    {mismatch['difference']:+d}\n")

        if result["dry_run"]:
            print("💡 To fix mismatches, run with --execute flag\n")
    else:
        if result["checked_documents"] > 0:
            print("✅ All file_count values are accurate!\n")


def main():
    """Main entry point for fix_file_count script."""
    parser = argparse.ArgumentParser(
        description="Detect and fix file_count mismatches in parent documents"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview mismatches without fixing (default)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually fix mismatches (writes to Firestore)",
    )
    parser.add_argument(
        "--class-name",
        type=str,
        help="Target specific class (optional, default=all classes)",
    )
    parser.add_argument(
        "--task-id", type=str, help="Target specific task (optional, default=all tasks)"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.task_id and not args.class_name:
        print("❌ Error: --task-id requires --class-name")
        sys.exit(1)

    if args.class_name and args.class_name not in KNOWN_CLASSES:
        print(f"❌ Error: Unknown class name: {args.class_name}")
        print(f"Known classes: {', '.join(KNOWN_CLASSES)}")
        sys.exit(1)

    if args.task_id and args.task_id not in KNOWN_TASK_IDS:
        print(f"❌ Error: Unknown task ID: {args.task_id}")
        print(f"Known task IDs: {', '.join(KNOWN_TASK_IDS)}")
        sys.exit(1)

    # If --execute is specified, override --dry-run
    dry_run = not args.execute

    print(f"\n🔧 Starting File Count Fix...")

    try:
        # Run fix
        result = fix_file_count(
            dry_run=dry_run, class_name=args.class_name, task_id=args.task_id
        )

        # Print summary
        print_summary(result)

        # Exit with appropriate code
        if not result["success"]:
            sys.exit(1)
        elif result["mismatches"] and dry_run:
            # Mismatches found in dry-run, exit with 1 to indicate action needed
            sys.exit(1)
        else:
            sys.exit(0)

    except Exception as e:
        print(f"\n❌ Fatal error during fix: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
