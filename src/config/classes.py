"""
Known classes and task IDs configuration.

This configuration is shared between backend (Cloud Run) and frontend (Dashboard).

Note: This list is NOT read by the Cloud Run collection process itself — that
process is driven directly by each Cloud Scheduler job's message-body
(class_name/task_id/task_pattern/drive_folder_id/spreadsheet_id), independent
of this file. KNOWN_CLASSES/KNOWN_TASK_IDS are used only for Dashboard display
and maintenance/consistency scripts that enumerate classes.
"""

# Known class names
# Note: In Phase 1, this list is maintained manually.
# In Phase 2, this could be dynamically managed via Firestore metadata collection.
KNOWN_CLASSES = [
    "令和8年度 デジタル中核人材養成研修 №01",
    "令和8年度 デジタル中核人材養成研修 №02",
    "令和8年度 デジタル中核人材養成研修 №03",
    "令和8年度 デジタル中核人材養成研修 №04",
    "令和8年度 デジタル中核人材養成研修 №05",
    "令和8年度 デジタル中核人材養成研修 №06",
    "令和8年度 デジタル中核人材養成研修 №07",
    "令和8年度 デジタル中核人材養成研修 №08",
    "令和8年度 デジタル中核人材養成研修 №09",
    "令和8年度 デジタル中核人材養成研修 №10",
]

# Known task IDs
# Note: Firestore subcollections exist even without parent documents,
# so we maintain this list to query documents subcollections directly.
# Corresponds to Cloud Scheduler task IDs.
KNOWN_TASK_IDS = ["課題①", "課題②"]
