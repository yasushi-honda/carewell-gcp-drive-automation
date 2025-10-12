#!/usr/bin/env python3
"""
Rollback Parent Documents Script

This script deletes parent documents created by migration.
Use this when migration fails or when rolling back a deployment.

IMPORTANT: This script only deletes parent documents.
Subcollections (documents) are preserved.

Usage:
    python scripts/rollback_parent_documents.py                 # Preview only
    python scripts/rollback_parent_documents.py --confirm       # Actually delete
"""

import argparse
import sys
from datetime import datetime
from typing import Dict, List

# Add src to path
sys.path.insert(0, "src")

from google.cloud import firestore

from config.classes import KNOWN_CLASSES, KNOWN_TASK_IDS


def rollback_parent_documents(confirm: bool = False) -> Dict:
    """
    Delete parent documents for all known classes and tasks.

    Args:
        confirm: If True, actually delete. If False, preview only.

    Returns:
        Dict with rollback results:
        - success: bool
        - confirm_required: bool
        - deleted_documents: int
        - skipped_documents: int
        - errors: List[Dict]
        - preview: List[Dict] (if not confirmed)
    """
    db = firestore.Client(database="carewell-native")

    result = {
        "success": True,
        "confirm_required": not confirm,
        "total_classes": len(KNOWN_CLASSES),
        "total_tasks": 0,
        "deleted_documents": 0,
        "skipped_documents": 0,
        "errors": [],
        "preview": [] if not confirm else None,
    }

    print(f"\n{'='*60}")
    print(
        f"{'PREVIEW MODE (--confirm required to delete)' if not confirm else 'ROLLBACK MODE - DELETING PARENT DOCUMENTS'}"
    )
    print(f"{'='*60}\n")

    if not confirm:
        print("⚠️  This is a PREVIEW. No documents will be deleted.")
        print("⚠️  Use --confirm flag to actually delete parent documents.\n")

    for class_name in KNOWN_CLASSES:
        print(f"📚 Processing class: {class_name}")

        for task_id in KNOWN_TASK_IDS:
            result["total_tasks"] += 1

            try:
                # Check if parent document exists
                task_ref = db.collection(class_name).document(task_id)
                task_doc = task_ref.get()

                if not task_doc.exists:
                    print(f"  ⏭️  Skipping {task_id}: Parent document doesn't exist")
                    result["skipped_documents"] += 1
                    continue

                # Get parent document data for preview
                task_data = task_doc.to_dict()
                file_count = task_data.get("file_count", 0)

                if not confirm:
                    # Preview mode
                    print(
                        f"  🔍 Would delete {task_id}: file_count={file_count} (subcollections preserved)"
                    )
                    result["preview"].append(
                        {
                            "class_name": class_name,
                            "task_id": task_id,
                            "file_count": file_count,
                        }
                    )
                    result["deleted_documents"] += 1
                else:
                    # Actually delete parent document
                    task_ref.delete()
                    print(
                        f"  ✅ Deleted {task_id}: file_count={file_count} (subcollections preserved)"
                    )
                    result["deleted_documents"] += 1

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


def print_summary(result: Dict) -> None:
    """
    Print rollback summary report.

    Args:
        result: Rollback result dictionary
    """
    print(f"\n{'='*60}")
    print("ROLLBACK SUMMARY")
    print(f"{'='*60}\n")

    print(
        f"Mode: {'PREVIEW (--confirm required to delete)' if result['confirm_required'] else 'EXECUTION'}"
    )
    print(f"Total Classes: {result['total_classes']}")
    print(f"Total Tasks Processed: {result['total_tasks']}")
    print(
        f"Parent Documents {'Would Be ' if result['confirm_required'] else ''}Deleted: {result['deleted_documents']}"
    )
    print(f"Parent Documents Skipped: {result['skipped_documents']}")
    print(f"Errors: {len(result['errors'])}")
    print(f"Success: {'✅ Yes' if result['success'] else '❌ No'}\n")

    if result["errors"]:
        print("⚠️  ERRORS ENCOUNTERED:\n")
        for error in result["errors"]:
            print(f"  - {error['class_name']}/{error['task_id']}: {error['error']}")
        print()

    if result["confirm_required"] and result["preview"]:
        print("🔍 PREVIEW OF DOCUMENTS TO BE DELETED:\n")
        for item in result["preview"]:
            print(
                f"  - {item['class_name']}/{item['task_id']}: file_count={item['file_count']}"
            )
        print()
        print("⚠️  IMPORTANT NOTES:")
        print("  - Parent documents will be deleted")
        print("  - Subcollections (documents) will be PRESERVED")
        print("  - This operation is IRREVERSIBLE\n")

    if result["confirm_required"]:
        print("💡 To execute rollback, run with --confirm flag\n")


def main():
    """Main entry point for rollback script."""
    parser = argparse.ArgumentParser(
        description="Rollback parent documents (delete parent documents, preserve subcollections)"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm deletion (required to actually delete)",
    )

    args = parser.parse_args()

    print(f"\n🔙 Starting Parent Documents Rollback...")

    try:
        # Run rollback
        result = rollback_parent_documents(confirm=args.confirm)

        # Print summary
        print_summary(result)

        # Exit with appropriate code
        if not result["success"]:
            sys.exit(1)
        else:
            sys.exit(0)

    except Exception as e:
        print(f"\n❌ Fatal error during rollback: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
