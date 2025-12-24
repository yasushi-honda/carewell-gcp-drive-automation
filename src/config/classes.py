"""
Known classes and task IDs configuration.

This configuration is shared between backend (Cloud Run) and frontend (Dashboard).
"""

# Known class names
# Note: In Phase 1, this list is maintained manually.
# In Phase 2, this could be dynamically managed via Firestore metadata collection.
KNOWN_CLASSES = [
    "令和7年度 デジタル中核人材養成研修 №01",
    "令和7年度 デジタル中核人材養成研修 №02",
    "令和7年度 デジタル中核人材養成研修 №03",
    "令和7年度 デジタル中核人材養成研修 №04",
    "令和7年度 デジタル中核人材養成研修 №05",
    "令和7年度 デジタル中核人材養成研修 №08",
    "令和7年度 デジタル中核人材養成研修 №09",
    "令和7年度 デジタル中核人材養成研修 №10",
]

# Known task IDs
# Note: Firestore subcollections exist even without parent documents,
# so we maintain this list to query documents subcollections directly.
# Corresponds to Cloud Scheduler task IDs.
KNOWN_TASK_IDS = ["課題①", "課題②"]
