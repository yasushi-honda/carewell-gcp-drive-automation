#!/usr/bin/env python3
"""
Verify file_count accuracy across all parent documents.

Usage:
    python scripts/verify_file_count.py
"""

import sys
from google.cloud import firestore
from typing import Dict, List

# Import KNOWN_CLASSES and KNOWN_TASK_IDS
sys.path.insert(0, "src")
from config.classes import KNOWN_CLASSES, KNOWN_TASK_IDS


def verify_file_count() -> Dict:
    """
    Verify file_count accuracy for all parent documents.

    Returns:
        Dict with verification results
    """
    db = firestore.Client(database="carewell-native")

    results = {"total_checked": 0, "mismatches": [], "success": True}

    for class_name in KNOWN_CLASSES:
        for task_id in KNOWN_TASK_IDS:
            # Get parent document
            task_ref = db.collection(class_name).document(task_id)
            task_doc = task_ref.get()

            if not task_doc.exists:
                continue

            task_data = task_doc.to_dict()
            stored_count = task_data.get("file_count", 0)

            # Count actual documents in subcollection
            docs = task_ref.collection("documents").stream()
            actual_count = sum(1 for _ in docs)

            results["total_checked"] += 1

            if stored_count != actual_count:
                results["mismatches"].append(
                    {
                        "class_name": class_name,
                        "task_id": task_id,
                        "stored_count": stored_count,
                        "actual_count": actual_count,
                        "difference": actual_count - stored_count,
                    }
                )
                results["success"] = False

    return results


def main():
    """Main entry point."""
    print("🔍 Verifying file_count accuracy...")

    try:
        results = verify_file_count()

        print(f"\n✅ Checked {results['total_checked']} parent documents")

        if results["mismatches"]:
            print(f"\n❌ Found {len(results['mismatches'])} mismatches:\n")
            for mismatch in results["mismatches"]:
                print(f"  {mismatch['class_name']}/{mismatch['task_id']}:")
                print(f"    Stored: {mismatch['stored_count']}")
                print(f"    Actual: {mismatch['actual_count']}")
                print(f"    Diff:   {mismatch['difference']:+d}\n")

            print("\n💡 To fix mismatches, run:")
            print("   python scripts/fix_file_count.py --execute")

            sys.exit(1)
        else:
            print("✅ All file_count values are accurate!")
            sys.exit(0)

    except Exception as e:
        print(f"\n❌ Error during verification: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
