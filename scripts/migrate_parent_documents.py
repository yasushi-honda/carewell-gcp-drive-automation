#!/usr/bin/env python3
"""
Migrate Parent Documents Script

This script creates parent documents for existing file uploads in Firestore.
It scans all known classes and tasks, counts files in subcollections,
and creates parent documents with metadata.

Usage:
    python scripts/migrate_parent_documents.py --dry-run   # Preview only
    python scripts/migrate_parent_documents.py --execute   # Actually migrate
"""

import argparse
import json
import sys
from datetime import datetime
from typing import Dict, List

# Add src to path
sys.path.insert(0, "src")

from google.cloud import firestore

from config.classes import KNOWN_CLASSES, KNOWN_TASK_IDS


def validate_migration() -> Dict:
    """
    Validate that file_count matches actual document count in subcollections.

    Returns:
        Dict with validation results:
        - success: bool (True if no mismatches)
        - total_checked: int
        - mismatches: List[Dict] (details of any mismatches)
    """
    db = firestore.Client(database="carewell-native")

    result = {
        "success": True,
        "total_checked": 0,
        "mismatches": [],
    }

    print(f"\n{'='*60}")
    print("VALIDATING MIGRATION")
    print(f"{'='*60}\n")

    for class_name in KNOWN_CLASSES:
        for task_id in KNOWN_TASK_IDS:
            try:
                # Get parent document
                task_ref = db.collection(class_name).document(task_id)
                task_doc = task_ref.get()

                if not task_doc.exists:
                    # Parent doesn't exist, skip validation
                    continue

                result["total_checked"] += 1

                # Get file_count from parent
                task_data = task_doc.to_dict()
                stored_count = task_data.get("file_count", 0)

                # Count actual documents in subcollection
                docs = task_ref.collection("documents").stream()
                actual_count = sum(1 for _ in docs)

                # Check for mismatch
                if stored_count != actual_count:
                    mismatch = {
                        "class_name": class_name,
                        "task_id": task_id,
                        "stored_count": stored_count,
                        "actual_count": actual_count,
                        "difference": actual_count - stored_count,
                    }
                    result["mismatches"].append(mismatch)
                    result["success"] = False
                    print(
                        f"  ❌ Mismatch: {class_name}/{task_id} - "
                        f"stored={stored_count}, actual={actual_count}"
                    )
                else:
                    print(f"  ✅ OK: {class_name}/{task_id} - count={actual_count}")

            except Exception as e:
                print(f"  ⚠️  Error validating {class_name}/{task_id}: {e}")

    print(f"\n{'='*60}")
    print("VALIDATION SUMMARY")
    print(f"{'='*60}\n")
    print(f"Total Parent Documents Checked: {result['total_checked']}")
    print(f"Mismatches Found: {len(result['mismatches'])}")
    print(f"Validation {'✅ PASSED' if result['success'] else '❌ FAILED'}\n")

    if result["mismatches"]:
        print("⚠️  FILE_COUNT MISMATCHES:\n")
        for mismatch in result["mismatches"]:
            print(f"  {mismatch['class_name']}/{mismatch['task_id']}:")
            print(f"    Stored:  {mismatch['stored_count']}")
            print(f"    Actual:  {mismatch['actual_count']}")
            print(f"    Diff:    {mismatch['difference']:+d}\n")

        print("💡 Run scripts/fix_file_count.py to fix mismatches\n")

    return result


def migrate_parent_documents(dry_run: bool = True) -> Dict:
    """
    Migrate parent documents for all known classes and tasks.

    Args:
        dry_run: If True, preview only without writing

    Returns:
        Dict with migration results:
        - success: bool
        - dry_run: bool
        - total_classes: int
        - total_tasks: int
        - created_documents: int
        - skipped_documents: int
        - errors: List[Dict]
        - preview: List[Dict] (if dry_run)
    """
    db = firestore.Client(database="carewell-native")

    result = {
        "success": True,
        "dry_run": dry_run,
        "total_classes": len(KNOWN_CLASSES),
        "total_tasks": 0,
        "created_documents": 0,
        "skipped_documents": 0,
        "errors": [],
        "preview": [] if dry_run else None,
    }

    print(f"\n{'='*60}")
    print(f"{'DRY RUN MODE' if dry_run else 'MIGRATION MODE'}")
    print(f"{'='*60}\n")

    for class_name in KNOWN_CLASSES:
        print(f"📚 Processing class: {class_name}")

        for task_id in KNOWN_TASK_IDS:
            result["total_tasks"] += 1

            try:
                # Check if parent document exists
                task_ref = db.collection(class_name).document(task_id)
                task_doc = task_ref.get()

                if task_doc.exists:
                    print(f"  ⏭️  Skipping {task_id}: Parent document already exists")
                    result["skipped_documents"] += 1
                    continue

                # Count files in documents subcollection
                docs = task_ref.collection("documents").stream()
                file_count = sum(1 for _ in docs)

                if file_count == 0:
                    print(
                        f"  ⏭️  Skipping {task_id}: No files in documents subcollection"
                    )
                    result["skipped_documents"] += 1
                    continue

                # Prepare parent document data
                parent_data = {
                    "task_id": task_id,
                    "task_pattern": task_id,  # Default to task_id
                    "file_count": file_count,
                    "created_at": firestore.SERVER_TIMESTAMP,
                    "last_updated": firestore.SERVER_TIMESTAMP,
                }

                if dry_run:
                    # Preview mode
                    print(f"  🔍 Would create {task_id}: file_count={file_count}")
                    result["preview"].append(
                        {
                            "class_name": class_name,
                            "task_id": task_id,
                            "file_count": file_count,
                        }
                    )
                    result["created_documents"] += 1
                else:
                    # Actually create parent document
                    task_ref.set(parent_data)
                    print(f"  ✅ Created {task_id}: file_count={file_count}")
                    result["created_documents"] += 1

            except Exception as e:
                error_detail = {
                    "class_name": class_name,
                    "task_id": task_id,
                    "error": str(e),
                }
                result["errors"].append(error_detail)
                result["success"] = False
                print(f"  ❌ Error processing {task_id}: {e}")

        print()  # Blank line between classes

    return result


def save_report_json(result: Dict, validation_result: Dict = None) -> str:
    """
    Save migration report as JSON file.

    Args:
        result: Migration result dictionary
        validation_result: Validation result dictionary (optional)

    Returns:
        Filename of saved report
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"migration_report_{timestamp}.json"

    report = {
        "timestamp": timestamp,
        "migration": result,
        "validation": validation_result,
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return filename


def print_summary(result: Dict, validation_result: Dict = None) -> None:
    """
    Print migration summary report.

    Args:
        result: Migration result dictionary
        validation_result: Validation result dictionary (optional)
    """
    print(f"\n{'='*60}")
    print("MIGRATION SUMMARY")
    print(f"{'='*60}\n")

    print(f"Mode: {'DRY RUN (Preview Only)' if result['dry_run'] else 'EXECUTION'}")
    print(f"Total Classes: {result['total_classes']}")
    print(f"Total Tasks Processed: {result['total_tasks']}")
    print(
        f"Parent Documents {'Would Be ' if result['dry_run'] else ''}Created: {result['created_documents']}"
    )
    print(f"Parent Documents Skipped: {result['skipped_documents']}")
    print(f"Errors: {len(result['errors'])}")
    print(f"Success: {'✅ Yes' if result['success'] else '❌ No'}\n")

    if result["errors"]:
        print("⚠️  ERRORS ENCOUNTERED:\n")
        for error in result["errors"]:
            print(f"  - {error['class_name']}/{error['task_id']}: {error['error']}")
        print()

    if result["dry_run"] and result["preview"]:
        print("🔍 PREVIEW OF DOCUMENTS TO BE CREATED:\n")
        for item in result["preview"]:
            print(
                f"  - {item['class_name']}/{item['task_id']}: file_count={item['file_count']}"
            )
        print()

    if validation_result:
        print(f"\n{'='*60}")
        print("VALIDATION RESULTS")
        print(f"{'='*60}\n")
        print(
            f"Validation: {'✅ PASSED' if validation_result['success'] else '❌ FAILED'}"
        )
        print(f"Total Checked: {validation_result['total_checked']}")
        print(f"Mismatches: {len(validation_result['mismatches'])}\n")

    if result["dry_run"]:
        print("💡 To execute migration, run with --execute flag\n")


def main():
    """Main entry point for migration script."""
    parser = argparse.ArgumentParser(
        description="Migrate parent documents for Firestore file uploads"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview migration without writing (default)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually execute migration (writes to Firestore)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only run validation without migration",
    )

    args = parser.parse_args()

    # If --validate-only is specified, only run validation
    if args.validate_only:
        print(f"\n🔍 Starting Validation Only...")
        try:
            validation_result = validate_migration()

            if not validation_result["success"]:
                sys.exit(1)
            else:
                sys.exit(0)
        except Exception as e:
            print(f"\n❌ Fatal error during validation: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(1)

    # If --execute is specified, override --dry-run
    dry_run = not args.execute

    print(f"\n🚀 Starting Firestore Parent Documents Migration...")

    try:
        # Run migration
        result = migrate_parent_documents(dry_run=dry_run)

        # If migration was executed (not dry-run), run validation
        validation_result = None
        if not dry_run and result["success"]:
            print("\n🔍 Running post-migration validation...")
            validation_result = validate_migration()

        # Print summary
        print_summary(result, validation_result)

        # Save JSON report
        if not dry_run:
            report_file = save_report_json(result, validation_result)
            print(f"📄 Report saved to: {report_file}\n")

        # Exit with appropriate code
        if not result["success"]:
            sys.exit(1)
        elif validation_result and not validation_result["success"]:
            print("⚠️  Migration succeeded but validation found mismatches")
            sys.exit(1)
        else:
            sys.exit(0)

    except Exception as e:
        print(f"\n❌ Fatal error during migration: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
