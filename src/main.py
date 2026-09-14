"""
Carewell File Collector - Cloud Functions Entrypoint
"""

import json
import logging
import os
import time  # ✅ 追加: 診断ログで使用（将来の拡張用に追加）

from flask import Request

import auth
from config.classes import (
    ATTENDANCE_ROSTER_FILE_IDS,
    KNOWN_CLASSES,
    KNOWN_TASK_IDS,
    get_current_academic_year_prefix,
    resolve_student_spreadsheet_id,
)
from firestore_service import FirestoreService
from google_drive_service import GoogleDriveService
from playwright_automation import PlaywrightAutomationEngine
from sheets_retry import append_record_with_retry
from sheets_service import SheetsService

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main(request):
    """
    Cloud Functions HTTP entrypoint

    Expected request body:
    {
        "class_name": "令和8年度 デジタル中核人材養成研修 №01",
        "task_id": "課題①",
        "task_pattern": "課題①",
        "drive_folder_id": "1abc...xyz",
        "spreadsheet_id": "1def...uvw"
    }

    Returns:
    {
        "status": "success",
        "message": "File collection completed",
        "submissions_found": 12,
        "processed": 10,
        "skipped": 2,
        "failed": 0,
        "total_count_from_ui": 12,
        "count_verified": true
    }
    """
    try:
        # Parse request
        request_json = request.get_json(silent=True)
        if not request_json:
            return {"error": "Request body must be JSON"}, 400

        # Validate required parameters
        required_params = [
            "class_name",
            "task_id",
            "task_pattern",
            "drive_folder_id",
            "spreadsheet_id",
        ]
        missing_params = [p for p in required_params if p not in request_json]
        if missing_params:
            return {
                "error": f"Missing required parameters: {', '.join(missing_params)}"
            }, 400

        class_name = request_json["class_name"]
        task_id = request_json["task_id"]
        task_pattern = request_json["task_pattern"]
        drive_folder_id = request_json["drive_folder_id"]
        spreadsheet_id = request_json["spreadsheet_id"]

        logger.info(
            f"Starting file collection for class={class_name}, task_id={task_id}, task_pattern={task_pattern}"
        )

        # Initialize services with class/task context for better log identification
        engine = PlaywrightAutomationEngine(class_name=class_name, task_id=task_id)
        drive_service = GoogleDriveService()
        firestore_service = FirestoreService()
        sheets_service = SheetsService()

        try:
            # Navigate to task page
            page = engine.navigate_to_task(class_name, task_pattern)

            # If class or task not found (likely not yet created), return success with zero counts
            if page is None:
                logger.info(
                    f"Class or task not yet created, skipping: {class_name}/{task_pattern}"
                )
                return {
                    "status": "success",
                    "message": "Task not yet created",
                    "submissions_found": 0,
                    "processed": 0,
                    "skipped": 0,
                    "failed": 0,
                }, 200

            logger.info(f"Successfully navigated to task page: {page.url}")

            # Get submission list with early duplicate checking
            submission_data = engine.get_submission_list(
                class_name=class_name,
                task_id=task_id,
                firestore_service=firestore_service,
            )
            submissions = submission_data["submissions"]
            total_count = submission_data.get("total_count")
            verified = submission_data.get("verified", False)

            logger.info(f"Found {len(submissions)} submissions")
            if total_count is not None:
                logger.info(f"Total count from UI: {total_count}, Verified: {verified}")

            # Process all submissions
            downloaded_count = 0
            skipped_count = 0
            failed_count = 0

            for submission in submissions:
                file_path = None
                try:
                    # Check early duplicate flag first (set during get_submission_list)
                    if submission.get("is_duplicate", False):
                        # Backfill grading info if available
                        grading_metadata = {
                            "pass_status": submission.get("pass_status"),
                            "score": submission.get("score"),
                            "grading_status": submission.get("status"),
                            "log_no": submission.get("log_no"),
                        }
                        # Remove None values
                        grading_metadata = {
                            k: v for k, v in grading_metadata.items() if v is not None
                        }

                        # Only update if we have grading info to backfill
                        if grading_metadata:
                            # Get composite_key from early duplicate check result
                            composite_key = submission.get("existing_composite_key")

                            if composite_key:
                                logger.info(
                                    f"Backfilling grading info for existing file: student_id={submission.get('student_id')}, submit_date={submission.get('submit_date')}, composite_key={composite_key}"
                                )

                                success = firestore_service.update_file_metadata(
                                    class_name, task_id, composite_key, grading_metadata
                                )

                                if success:
                                    logger.info(
                                        f"Successfully backfilled grading info: {composite_key}"
                                    )
                                else:
                                    logger.warning(
                                        f"Failed to backfill grading info: {composite_key}"
                                    )
                            else:
                                logger.warning(
                                    "Cannot backfill: existing_composite_key not available"
                                )

                        logger.info(
                            f"Skipping already uploaded file (early check): student_id={submission.get('student_id')}, submit_date={submission.get('submit_date')}"
                        )
                        skipped_count += 1
                        continue

                    # ✅ 診断ログ: Phase 2条件チェック（download_url/filename/detail_url の有無確認）
                    logger.info(
                        f"[PHASE 2] Checking submission: {submission.get('student_name', 'UNKNOWN')} - "
                        f"download_url={'SET' if submission.get('download_url') else 'NONE'}, "
                        f"filename={'SET' if submission.get('filename') else 'NONE'}, "
                        f"detail_url={'SET' if submission.get('detail_url') else 'NONE'}"
                    )

                    if (
                        submission.get("download_url")
                        and submission.get("filename")
                        and submission.get("detail_url")
                    ):
                        # For non-early-duplicates, perform full check with filename
                        # (defense-in-depth: catch any edge cases)
                        existing_upload = firestore_service.check_already_uploaded(
                            class_name,
                            task_id,
                            submission.get("student_id", ""),
                            submission["filename"],
                            submission.get("submit_date", ""),
                        )

                        if existing_upload:
                            logger.info(
                                f"Skipping already uploaded file (filename check): {submission['filename']} (Drive ID: {existing_upload.get('drive_file_id')})"
                            )
                            skipped_count += 1
                            continue

                        # Download file
                        logger.info(f"Downloading: {submission['filename']}")
                        file_path = engine.download_file(
                            submission["download_url"],
                            submission["filename"],
                            submission["detail_url"],
                        )
                        logger.info(f"Downloaded to: {file_path}")

                        # Upload to Google Drive
                        drive_file_id = drive_service.upload_file(
                            file_path, submission["filename"], drive_folder_id
                        )
                        logger.info(f"Uploaded to Drive: {drive_file_id}")

                        # Get student data for denormalization (Phase 3: Student metadata integration)
                        student_id = submission.get("student_id", "")
                        student = None
                        student_furigana = ""
                        student_group = "未分類"
                        student_status = "active"
                        student_company = ""
                        student_office = ""
                        student_service_type = ""
                        student_serial_number = 0
                        student_number = ""

                        if student_id:
                            student = firestore_service.get_student(student_id)
                            if student:
                                student_furigana = student.get("furigana", "")
                                student_group = student.get("group", "未分類")
                                student_status = student.get("status", "active")
                                student_company = student.get("company", "")
                                student_office = student.get("office", "")
                                student_service_type = student.get("service_type", "")
                                student_serial_number = student.get("serial_number", 0)
                                student_number = student.get("student_number", "")
                            else:
                                logger.warning(
                                    f"Student not found in students collection: {student_id}"
                                )

                        # Record upload in Firestore
                        # Build metadata with grading information (excluding fields already in parent doc)
                        metadata = {
                            "pass_status": submission.get("pass_status"),
                            "score": submission.get("score"),
                            "grading_status": submission.get(
                                "status"
                            ),  # Renamed from "status" for clarity
                            "log_no": submission.get("log_no"),
                        }
                        # Remove None values to keep metadata clean
                        metadata = {k: v for k, v in metadata.items() if v is not None}

                        firestore_service.record_upload(
                            class_name,
                            task_id,
                            submission["student_name"],
                            student_id,
                            submission["filename"],
                            drive_file_id,
                            drive_folder_id,
                            submission.get("submit_date", ""),
                            metadata=metadata,
                            task_pattern=task_pattern,
                            # Denormalized student fields (Phase 3)
                            student_furigana=student_furigana,
                            student_group=student_group,
                            student_status=student_status,
                            student_company=student_company,
                            student_office=student_office,
                            student_service_type=student_service_type,
                            student_serial_number=student_serial_number,
                            student_number=student_number,
                        )

                        # Record in Google Sheets with retry
                        sheets_success = append_record_with_retry(
                            sheets_service,
                            spreadsheet_id,
                            task_id,
                            submission["student_name"],
                            submission.get("student_id", ""),
                            submission.get("submit_date", ""),
                            submission["filename"],
                            drive_file_id,
                        )

                        # Update sheets_sync_status in Firestore
                        if sheets_success:
                            firestore_service.update_sheets_sync_status(
                                class_name,
                                task_id,
                                student_id,
                                submission["filename"],
                                submission.get("submit_date", ""),
                                status="success",
                            )
                        else:
                            firestore_service.update_sheets_sync_status(
                                class_name,
                                task_id,
                                student_id,
                                submission["filename"],
                                submission.get("submit_date", ""),
                                status="failed",
                                error_message="All retry attempts failed",
                            )
                            logger.error(
                                f"SHEETS_SYNC_FAILED: {submission['student_name']} "
                                f"({student_id}) - {submission['filename']}"
                            )

                        downloaded_count += 1
                    else:
                        logger.warning(
                            f"No download link for {submission['student_name']}"
                        )
                        failed_count += 1
                except Exception as e:
                    logger.error(
                        f"Failed to download {submission.get('filename', 'unknown')}: {e}"
                    )
                    failed_count += 1
                finally:
                    # Clean up temporary file
                    if file_path and os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            logger.info(f"Cleaned up temporary file: {file_path}")
                        except Exception as cleanup_error:
                            logger.warning(
                                f"Failed to clean up {file_path}: {cleanup_error}"
                            )

            response = {
                "status": "success",
                "message": "File collection completed",
                "submissions_found": len(submissions),
                "processed": downloaded_count,
                "skipped": skipped_count,
                "failed": failed_count,
            }

            # Add count verification info if available
            if total_count is not None:
                response["total_count_from_ui"] = total_count
                response["count_verified"] = verified
                if not verified:
                    response["warning"] = (
                        f"Count mismatch: UI shows {total_count} but found {len(submissions)}"
                    )

            return response, 200

        finally:
            engine.close()

    except Exception as e:
        logger.error(f"Error during execution: {str(e)}", exc_info=True)
        return {"status": "error", "error": str(e)}, 500


def cleanup_firestore(request):
    """
    Firestore cleanup endpoint for administrative operations

    Expected request body:
    {
        "class_name": "令和8年度 デジタル中核人材養成研修 №01",
        "task_id": "課題①",
        "confirm": true
    }
    """
    try:
        # Parse request
        request_json = request.get_json(silent=True)
        if not request_json:
            return {"error": "Request body must be JSON"}, 400

        # Validate required parameters
        required_params = ["class_name", "task_id", "confirm"]
        missing_params = [p for p in required_params if p not in request_json]
        if missing_params:
            return {
                "error": f"Missing required parameters: {', '.join(missing_params)}"
            }, 400

        class_name = request_json["class_name"]
        task_id = request_json["task_id"]
        confirm = request_json.get("confirm", False)

        if not confirm:
            return {"error": "Set 'confirm': true to execute cleanup"}, 400

        logger.warning(
            f"Starting Firestore cleanup for class={class_name}, task_id={task_id}"
        )

        # Initialize Firestore service
        firestore_service = FirestoreService()

        # Get document count first (NEW SCHEMA)
        collection_ref = (
            firestore_service.db.collection("submissions")
            .document(class_name)
            .collection("tasks")
            .document(task_id)
            .collection("files")
        )
        docs = list(collection_ref.stream())
        doc_count = len(docs)

        logger.info(f"Found {doc_count} documents to delete")

        if doc_count == 0:
            return {
                "status": "success",
                "message": "No documents found to delete",
                "deleted_count": 0,
            }, 200

        # Delete all documents
        deleted_count = 0
        failed_count = 0

        for doc in docs:
            try:
                doc.reference.delete()
                deleted_count += 1
                if deleted_count % 10 == 0:
                    logger.info(f"Deleted {deleted_count}/{doc_count} documents")
            except Exception as e:
                logger.error(f"Failed to delete document {doc.id}: {e}")
                failed_count += 1

        logger.warning(
            f"Cleanup completed: deleted={deleted_count}, failed={failed_count}"
        )

        # Verify cleanup
        remaining_docs = list(collection_ref.stream())
        remaining_count = len(remaining_docs)

        return {
            "status": "success",
            "message": f"Deleted {deleted_count} documents",
            "deleted_count": deleted_count,
            "failed_count": failed_count,
            "remaining_count": remaining_count,
        }, 200

    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}", exc_info=True)
        return {"status": "error", "error": str(e)}, 500


def health_check(request):
    """Health check endpoint"""
    return {"status": "healthy", "service": "carewell-file-collector"}, 200


def sync_students_from_sheets(request):
    """
    Admin endpoint for syncing student master data from Google Sheets

    Expected request body:
    {
        "backfill": false  # Optional: Whether to backfill existing files with student data
    }

    Returns:
    {
        "status": "success",
        "students_synced": 2000,
        "students_created": 150,
        "students_updated": 1850,
        "files_backfilled": 4000,  # Only if backfill=true
        "errors": []
    }
    """
    # 令和8年度は出欠名簿経由の同期(/admin/sync-students-from-attendance-rosters)に
    # 統一されている。このガードは_sync_students()ではなく、このHTTPハンドラ自身の
    # 先頭に置く（_sync_students()の戻り値契約はdictのみであり、そちらにタプルを
    # 返すガードを置くと呼び出し元のsync_result.get("status")がAttributeErrorになり
    # 実際には500になる、という実装ミスをplan-crossreviewのcodexレビューで指摘され
    # 修正した経緯がある。2026-09-14）。
    if get_current_academic_year_prefix() == "令和8年度":
        return {
            "status": "disabled",
            "message": (
                "令和8年度は出欠名簿経由の同期"
                "(/admin/sync-students-from-attendance-rosters)に統一されています。"
            ),
        }, 409

    try:
        # Parse request
        request_json = request.get_json(silent=True) or {}
        backfill = request_json.get("backfill", False)

        logger.info(f"Starting student sync from Google Sheets (backfill={backfill})")

        # Initialize services
        sheets_service = SheetsService()
        firestore_service = FirestoreService()

        # Phase 1: Sync students from Google Sheets
        spreadsheet_id = resolve_student_spreadsheet_id()
        sync_result = _sync_students(sheets_service, firestore_service, spreadsheet_id)

        if sync_result.get("status") != "success":
            return sync_result, 500

        response = {
            "status": "success",
            "students_synced": sync_result["students_synced"],
            "students_created": sync_result["students_created"],
            "students_updated": sync_result["students_updated"],
            "errors": sync_result.get("errors", []),
        }

        # Phase 2: Backfill existing files (optional)
        if backfill:
            logger.info("Starting backfill of existing files...")
            backfill_result = _backfill_all_files(firestore_service)

            response["files_backfilled"] = backfill_result.get("files_updated", 0)
            response["files_skipped"] = backfill_result.get("files_skipped", 0)
            response["backfill_errors"] = backfill_result.get("errors", [])

        logger.info(f"Student sync completed: {response}")
        return response, 200

    except ValueError as e:
        # 同期元スプレッドシートID未設定等の設定不備。詳細はログにのみ残し、
        # レスポンスには内部構成の詳細（ファイルパス・環境変数名等）を含めない
        # （silent-failure-hunterレビュー指摘。Issue #12でAuth必須化後も、
        # 多層防御としてこの方針は維持する）。
        logger.error(f"Student sync configuration error: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "error": "受講生名簿の同期設定が未完了です。管理者に連絡してください。",
        }, 500

    except Exception as e:
        logger.error(f"Error during student sync: {str(e)}", exc_info=True)
        return {"status": "error", "error": str(e)}, 500


def sync_students_from_attendance_rosters(request):
    """
    Admin/Scheduler endpoint: クラス別出欠管理ファイル({No}_受講者リスト_出欠管理)の
    「受講者リスト」タブからFirestore studentsコレクションへ直接同期する。

    令和7年度が使っていたVSTACK/IMPORTRANGE集約スプレッドシート方式のバージョンアップ版。
    全クラスを読込み・検証してから書込む二段階のfail-closed設計（1クラスでも異常が
    あればFirestoreへは一切書き込まない）。

    Expected request body:
    {
        "dry_run": false  # trueの場合フェーズAのみ実行し、Firestoreへは書き込まない
                          # (preflight用。読み取り権限・ヘッダー一致の事前確認に使う)
    }

    Returns:
    {
        "status": "success" | "aborted" | "error",
        "dry_run": false,
        "classes": [{"class_name": "No1", "status": "ok", "synced": 254, ...}, ...],
        "not_configured_classes": ["No8", "No10"],
        "error_classes": [...],
        "malformed_rows": [...],
        "duplicate_student_ids": [...]
    }
    """
    try:
        request_json = request.get_json(silent=True) or {}
        dry_run = bool(request_json.get("dry_run", False))

        logger.info(f"Starting attendance roster student sync (dry_run={dry_run})")

        sheets_service = SheetsService()
        firestore_service = FirestoreService()

        result = _sync_students_from_attendance_rosters(
            sheets_service, firestore_service, dry_run=dry_run
        )

        status_code = 200 if result.get("status") == "success" else 409
        logger.info(f"Attendance roster sync completed: status={result.get('status')}")
        return result, status_code

    except Exception as e:
        logger.error(
            f"Error during attendance roster student sync: {str(e)}", exc_info=True
        )
        return {"status": "error", "error": str(e)}, 500


def get_duplicate_students(request):
    """
    Admin endpoint for getting duplicate student_id information

    Returns:
    {
        "status": "success",
        "duplicates": [
            {
                "student_id": "N9903499",
                "name": "山田太郎",
                "kept_class": "No3",
                "kept_status": "active",
                "ignored_class": "No5",
                "ignored_status": "inactive",
                "resolution": "active_inactive"
            },
            ...
        ],
        "total_duplicates": 23
    }
    """
    try:
        logger.info("Getting duplicate student information from Google Sheets")

        # Initialize service
        sheets_service = SheetsService()

        # Get spreadsheet ID
        spreadsheet_id = resolve_student_spreadsheet_id()

        # Get duplicates (now returns dict with duplicates and class_urls)
        result = sheets_service.get_duplicate_students(spreadsheet_id)

        response = {
            "status": "success",
            "duplicates": result.get("duplicates", []),
            "class_urls": result.get("class_urls", {}),
            "total_duplicates": len(result.get("duplicates", [])),
        }

        return response, 200

    except ValueError as e:
        # 同期元スプレッドシートID未設定等の設定不備。詳細はログにのみ残し、
        # レスポンスには内部構成の詳細（ファイルパス・環境変数名等）を含めない
        # （silent-failure-hunterレビュー指摘。Issue #12でAuth必須化後も、
        # 多層防御としてこの方針は維持する）。
        logger.error(f"Duplicate students configuration error: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "error": "受講生名簿の同期設定が未完了です。管理者に連絡してください。",
        }, 500

    except Exception as e:
        logger.error(f"Error getting duplicate students: {str(e)}", exc_info=True)
        return {"status": "error", "error": str(e)}, 500


def _sync_students(sheets_service, firestore_service, spreadsheet_id):
    """
    Sync student data from Google Sheets to Firestore students collection

    Args:
        sheets_service: SheetsService instance
        firestore_service: FirestoreService instance
        spreadsheet_id: Google Sheets spreadsheet ID

    Returns:
        Dictionary with sync results
    """
    try:
        # Get student data from Google Sheets
        logger.info(f"Reading student data from spreadsheet: {spreadsheet_id}")
        students = sheets_service.get_student_data(spreadsheet_id)

        if not students:
            logger.warning("No student data found in spreadsheet")
            return {
                "status": "success",
                "students_synced": 0,
                "students_created": 0,
                "students_updated": 0,
                "errors": [],
            }

        logger.info(f"Found {len(students)} students in spreadsheet")

        # Batch process students (500 at a time for Firestore batch limit)
        created_count = 0
        updated_count = 0
        error_count = 0
        errors = []

        batch_size = 500
        for i in range(0, len(students), batch_size):
            batch = students[i : i + batch_size]
            logger.info(
                f"Processing student batch {i // batch_size + 1}: {len(batch)} students"
            )

            for student in batch:
                try:
                    # Check if student already exists
                    student_exists = firestore_service.student_exists(
                        student["student_id"]
                    )

                    # Create/update student
                    success = firestore_service.create_student(student)

                    if success:
                        if student_exists:
                            updated_count += 1
                        else:
                            created_count += 1
                    else:
                        error_count += 1
                        errors.append(
                            {
                                "student_id": student["student_id"],
                                "error": "Failed to create/update student",
                            }
                        )

                except Exception as e:
                    error_count += 1
                    error_msg = f"Error syncing student {student.get('student_id', 'unknown')}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(
                        {"student_id": student.get("student_id"), "error": str(e)}
                    )

        logger.info(
            f"Student sync completed: created={created_count}, updated={updated_count}, errors={error_count}"
        )

        return {
            "status": "success",
            "students_synced": created_count + updated_count,
            "students_created": created_count,
            "students_updated": updated_count,
            "errors": errors[:100],  # Limit errors to first 100
        }

    except Exception as e:
        logger.error(f"Error in _sync_students: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "students_synced": 0,
            "students_created": 0,
            "students_updated": 0,
            "errors": [{"error": str(e)}],
        }


def _sync_students_from_attendance_rosters(
    sheets_service, firestore_service, dry_run: bool = False
):
    """
    クラス別出欠管理ファイルからFirestore studentsへ同期する（フェーズA: 収集・検証
    → フェーズB: 書込み+reconcile の二段階、fail-closed）。

    Args:
        sheets_service: SheetsService instance
        firestore_service: FirestoreService instance
        dry_run: Trueの場合フェーズAのみ実行し、Firestoreへは一切書き込まない

    Returns:
        Dictionary with sync results (status: "success" | "aborted")
    """
    # フェーズA: 全クラス収集
    class_results = {}
    for class_num, spreadsheet_id in ATTENDANCE_ROSTER_FILE_IDS.items():
        class_name = f"No{int(class_num)}"
        logger.info(f"Reading attendance roster for class={class_name}")
        class_results[class_num] = sheets_service.get_attendance_roster_data(
            spreadsheet_id, class_name
        )

    all_class_nums = [f"{i:02d}" for i in range(1, len(KNOWN_CLASSES) + 1)]
    not_configured_classes = [
        f"No{int(n)}" for n in all_class_nums if n not in ATTENDANCE_ROSTER_FILE_IDS
    ]

    error_classes = [
        {"class_name": r.class_name, "status": r.status, "error": r.error_detail}
        for r in class_results.values()
        if r.status in ("read_error", "schema_error")
    ]

    malformed_summary = [
        {"class_name": r.class_name, "rows": r.malformed_rows}
        for r in class_results.values()
        if r.malformed_rows
    ]

    # 日介番号の重複検出（クラス内・クラス横断を区別しない統一処理。
    # クラス内限定の「先勝ち」は行わない — plan-crossreview codex指摘対応）
    student_id_owners: dict = {}
    for r in class_results.values():
        for s in r.students:
            student_id_owners.setdefault(s["student_id"], []).append(r.class_name)
    duplicate_student_ids = [
        {"student_id": sid, "classes": classes}
        for sid, classes in student_id_owners.items()
        if len(classes) > 1
    ]

    diagnostics = {
        "not_configured_classes": not_configured_classes,
        "error_classes": error_classes,
        "malformed_rows": malformed_summary,
        "duplicate_student_ids": duplicate_student_ids,
    }

    can_write = (
        not error_classes and not malformed_summary and not duplicate_student_ids
    )

    class_status_overview = [
        {
            "class_name": r.class_name,
            "status": r.status,
            "student_count": len(r.students),
        }
        for r in class_results.values()
    ]

    if dry_run or not can_write:
        logger.info(
            f"Attendance roster sync phase A only: can_write={can_write} "
            f"dry_run={dry_run}"
        )
        return {
            "status": "success" if can_write else "aborted",
            "dry_run": dry_run,
            "classes": class_status_overview,
            **diagnostics,
        }

    # フェーズB: 書込み（クラス単位で擬似アトミック。1件でも書込みが失敗した
    # クラスは、そのクラスのreconcileをスキップし他クラスの処理は継続する）
    class_summaries = []
    for r in class_results.values():
        created = 0
        updated = 0
        write_error_ids = []

        for student in r.students:
            try:
                exists = firestore_service.student_exists(student["student_id"])
                success = firestore_service.create_student(
                    student,
                    preserve_existing_status=True,
                    sync_source="attendance_roster",
                )
                if success:
                    if exists:
                        updated += 1
                    else:
                        created += 1
                else:
                    write_error_ids.append(student["student_id"])
            except Exception as e:
                write_error_ids.append(student["student_id"])
                logger.error(
                    f"Error syncing student {student.get('student_id')} "
                    f"in class={r.class_name}: {e}",
                    exc_info=True,
                )

        withdrawn = 0
        if not write_error_ids:
            try:
                existing_ids = firestore_service.get_student_ids_by_class_and_source(
                    r.class_name, "attendance_roster"
                )
                current_ids = {s["student_id"] for s in r.students}
                for sid, status in existing_ids.items():
                    if sid not in current_ids and status != "withdrawn":
                        if firestore_service.mark_student_withdrawn(sid):
                            withdrawn += 1
                        else:
                            write_error_ids.append(sid)
            except Exception as e:
                write_error_ids.append("__reconcile__")
                logger.error(
                    f"Error reconciling withdrawals for class={r.class_name}: {e}",
                    exc_info=True,
                )

        class_summaries.append(
            {
                "class_name": r.class_name,
                "status": r.status,
                "synced": created + updated,
                "created": created,
                "updated": updated,
                "withdrawn": withdrawn,
                "write_failed": len(write_error_ids),
            }
        )

    logger.info(f"Attendance roster sync completed: {class_summaries}")

    return {
        "status": "success",
        "dry_run": False,
        "classes": class_summaries,
        **diagnostics,
    }


def _backfill_all_files(firestore_service):
    """
    Backfill existing file documents with denormalized student data

    Args:
        firestore_service: FirestoreService instance

    Returns:
        Dictionary with backfill results

    Note:
        This function ALWAYS updates all files with the latest student data,
        ensuring consistency between students/ and files/ collections.
        Previously existing data is overwritten with current master data.
    """
    try:
        logger.info("Starting backfill of existing files with student data...")

        # Get all students first
        all_students = firestore_service.get_all_students()
        if not all_students:
            logger.warning("No students found in Firestore, skipping backfill")
            return {
                "status": "success",
                "files_updated": 0,
                "files_skipped": 0,
                "errors": [],
            }

        # Create student lookup dictionary
        student_lookup = {s["student_id"]: s for s in all_students}
        logger.info(f"Loaded {len(student_lookup)} students for backfill")

        updated_count = 0
        skipped_count = 0
        error_count = 0
        errors = []

        # Iterate through the current academic year's known class/task
        # combinations only (KNOWN_CLASSES/KNOWN_TASK_IDS, from
        # src/config/classes.py). Two reasons this must not be a blind
        # `submissions_ref.stream()` scan:
        # 1. `submissions/{class_name}` parent documents are never written
        #    directly (only their `tasks/{task_id}` descendants are) — see
        #    classes.py's own note that "Firestore subcollections exist even
        #    without parent documents" — so a top-level collection stream
        #    does not reliably enumerate classes at all.
        # 2. Prior academic years' class data is retained in Firestore
        #    (not deleted at year-end), so an unscoped scan would overwrite
        #    prior-year files' denormalized student fields with the current
        #    year's roster data (Issue #5 Phase 2).
        submissions_ref = firestore_service.db.collection("submissions")

        for class_name in KNOWN_CLASSES:
            logger.info(f"Processing class: {class_name}")

            tasks_ref = submissions_ref.document(class_name).collection("tasks")

            for task_id in KNOWN_TASK_IDS:
                logger.info(f"Processing task: {class_name}/{task_id}")

                files_ref = tasks_ref.document(task_id).collection("files")

                for file_doc in files_ref.stream():
                    try:
                        file_data = file_doc.to_dict()
                        student_id = file_data.get("student_id")

                        if not student_id:
                            logger.warning(
                                f"File {file_doc.id} has no student_id, skipping"
                            )
                            skipped_count += 1
                            continue

                        # Get student data
                        student = student_lookup.get(student_id)
                        if not student:
                            logger.warning(
                                f"Student not found: {student_id}, skipping file {file_doc.id}"
                            )
                            skipped_count += 1
                            continue

                        # Update file with denormalized student data (always overwrite)
                        update_data = {
                            "student_furigana": student.get("furigana", ""),
                            "student_group": student.get("group", "未分類"),
                            "student_status": student.get("status", "active"),
                            "student_company": student.get("company", ""),
                            "student_office": student.get("office", ""),
                            "student_service_type": student.get("service_type", ""),
                            "student_serial_number": student.get("serial_number", 0),
                            "student_number": student.get("student_number", ""),
                        }

                        file_doc.reference.update(update_data)
                        updated_count += 1

                        if updated_count % 100 == 0:
                            logger.info(f"Backfilled {updated_count} files so far...")

                    except Exception as e:
                        error_count += 1
                        error_msg = f"Error backfilling file {file_doc.id}: {str(e)}"
                        logger.error(error_msg)
                        errors.append({"file_id": file_doc.id, "error": str(e)})

        logger.info(
            f"Backfill completed: updated={updated_count}, skipped={skipped_count}, errors={error_count}"
        )

        return {
            "status": "success",
            "files_updated": updated_count,
            "files_skipped": skipped_count,
            "errors": errors[:100],  # Limit errors to first 100
        }

    except Exception as e:
        logger.error(f"Error in _backfill_all_files: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "files_updated": 0,
            "files_skipped": 0,
            "errors": [{"error": str(e)}],
        }


def _add_cors_headers(response_data, status_code=200):
    """
    Add CORS headers to response for browser requests

    Args:
        response_data: Response data (dict or tuple)
        status_code: HTTP status code

    Returns:
        Tuple of (response_data, status_code, headers)
    """
    headers = {
        "Access-Control-Allow-Origin": "https://carewell-dashboard-2026.web.app",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Max-Age": "3600",
    }
    return response_data, status_code, headers


def _normalize(result):
    """ハンドラの戻り値を (data, status_code) に正規化する。

    ハンドラは dict 単体、または (dict, status) の2-tupleのいずれかを返す。
    """
    if isinstance(result, tuple):
        return result[0], result[1]
    return result, 200


# パスごとのハンドラ名（認証ゲート通過後にのみ呼ばれる）。
# 関数オブジェクトを直接束縛せず名前（文字列）で保持し、呼び出しのたびに
# globals() から解決する（テストで unittest.mock.patch("main.xxx") した際に
# 反映されるようにするため。src/auth.py の _VERIFIER_NAMES と同じ理由）。
_HANDLER_NAMES = {
    "/": "main",
    "/cleanup": "cleanup_firestore",
    "/admin/sync-students-from-sheets": "sync_students_from_sheets",
    "/admin/sync-students-from-attendance-rosters": "sync_students_from_attendance_rosters",
    "/admin/duplicate-students": "get_duplicate_students",
    "/health": "health_check",
}


def app(request):
    """
    Main entrypoint with routing + 認証ゲート（Issue #12）

    Routes:
    - POST /                              → File collection (main) — Scheduler専用
    - POST /cleanup                       → Firestore cleanup (administrative) — Firebase管理者専用
    - POST /admin/sync-students-from-sheets
        → Student sync from Google Sheets(令和7年度以前専用。令和8年度は409) — Scheduler or Firebase管理者
    - POST /admin/sync-students-from-attendance-rosters
        → Student sync from attendance rosters — Scheduler or Firebase管理者
    - GET  /admin/duplicate-students      → Get duplicate student_id info (administrative) — Firebase管理者専用
    - GET  /health                        → Health check — 認証不要
    - OPTIONS /*                          → CORS preflight — 認証不要（実処理なし）

    認証は auth.authorize() が一元的に行う（default-deny）。Cloud Run 自体は
    --allow-unauthenticated のまま運用し、アプリ層でゲートする設計の理由は
    src/auth.py のモジュールdocstring参照。
    """
    path = request.path
    method = request.method

    logger.info(f"Request: {method} {path}")

    # CORS preflight は認証不要・実処理なし（Authorization ヘッダを持てないため）
    if method == "OPTIONS":
        return _add_cors_headers({}, 204)

    try:
        auth.authorize(request, method, path)
    except auth.RouteNotFound:
        # 未知パスの一覧列挙は情報漏洩になるため返さない
        return _add_cors_headers({"error": "Not found"}, 404)
    except auth.AuthError as e:
        return _add_cors_headers({"error": e.public_message}, e.status_code)

    handler = globals()[_HANDLER_NAMES[path]]
    result = handler(request)
    return _add_cors_headers(*_normalize(result))
