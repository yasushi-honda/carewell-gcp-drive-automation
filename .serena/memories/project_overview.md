# Project Overview

## Purpose
Carewell Webサービスから学生の提出ファイルを自動収集し、Google Driveへ保存、Googleスプレッドシートに記録する自動化システム

## Tech Stack
- **Language**: Python 3.11
- **Web Automation**: Playwright 1.40.0
- **Cloud Platform**: Google Cloud Platform
  - Cloud Run Functions (2nd Gen)
  - Secret Manager
  - Firestore
  - Google Drive API
  - Google Sheets API
  - Artifact Registry
- **Container**: Docker (python:3.11-bookworm)
- **CI/CD**: GitHub Actions + Workload Identity Federation

## Key Components
- `src/main.py`: Cloud Functions entry point
- `src/playwright_automation.py`: Playwright automation engine
- `src/google_drive_service.py`: Google Drive API service
- `src/firestore_service.py`: Firestore duplicate checking service
- `src/sheets_service.py`: Google Sheets API service

## Processing Flow
1. Receive HTTP request on Cloud Functions
2. Login to Carewell (via Secret Manager credentials)
3. Navigate to specified class/task page
4. Retrieve submission list (all students)
5. For each submission file:
   - Check for duplicates in Firestore (SHA256 hash)
   - Download from Carewell to /tmp
   - Upload to Google Drive
   - Record in Firestore
   - Record in Google Sheets
   - Clean up /tmp file
6. Return response with processing summary

## Duplicate Detection
Uses SHA256 hash of: `class_name + task_name + student_id + filename + submit_date`

## Student Data Format
Carewell provides student info as: `森平　直樹 <N9902913>`
System automatically separates into student name and student ID