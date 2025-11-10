#!/usr/bin/env python3
"""
Manual student sync script - Sync Google Sheets K column (class_name) to Firestore
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sheets_service import SheetsService
from firestore_service import FirestoreService

def main():
    print("🔄 Starting manual student sync...")

    # Initialize services
    sheets_service = SheetsService()
    firestore_service = FirestoreService()

    # Spreadsheet ID (from environment or hardcoded)
    spreadsheet_id = os.environ.get(
        "STUDENT_SPREADSHEET_ID", "1AQ12-h3n_NmN2kWxi4Z_g354X0wmUyMKAPeAsXJwu_w"
    )

    print(f"📊 Reading student data from Google Sheets: {spreadsheet_id}")

    # Read student data from Google Sheets (includes K column: class_name)
    students = sheets_service.get_student_data(spreadsheet_id, "統合_受講者リスト")

    if not students:
        print("❌ No student data found in Google Sheets")
        return

    print(f"✅ Found {len(students)} students in Google Sheets")

    # Sync to Firestore
    print("💾 Syncing to Firestore...")

    created_count = 0
    updated_count = 0

    for student in students:
        student_id = student['student_id']

        # Check if student exists
        existing = firestore_service.db.collection('students').document(student_id).get()

        # Prepare student data
        student_data = {
            'name': student['name'],
            'furigana': student['furigana'],
            'group': student['group'],
            'company': student['company'],
            'office': student['office'],
            'service_type': student['service_type'],
            'serial_number': student['serial_number'],
            'student_number': student['student_number'],
            'class_name': student['class_name'],  # K column
            'status': student['status'],
        }

        if existing.exists:
            # Update existing student
            firestore_service.db.collection('students').document(student_id).update(student_data)
            updated_count += 1
            print(f"  ✏️  Updated: {student_id} - {student['name']} (class: {student['class_name']})")
        else:
            # Create new student
            firestore_service.db.collection('students').document(student_id).set(student_data)
            created_count += 1
            print(f"  ➕ Created: {student_id} - {student['name']} (class: {student['class_name']})")

    print(f"\n✅ Sync completed!")
    print(f"   Created: {created_count}")
    print(f"   Updated: {updated_count}")
    print(f"   Total: {len(students)}")

if __name__ == '__main__':
    main()
