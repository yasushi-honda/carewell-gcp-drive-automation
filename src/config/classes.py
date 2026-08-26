"""
Known classes and task IDs configuration.

This configuration is shared between backend (Cloud Run) and frontend (Dashboard).

Note: This list is NOT read by the Cloud Run collection process itself — that
process is driven directly by each Cloud Scheduler job's message-body
(class_name/task_id/task_pattern/drive_folder_id/spreadsheet_id), independent
of this file. KNOWN_CLASSES/KNOWN_TASK_IDS are used only for Dashboard display
and maintenance/consistency scripts that enumerate classes.
"""

import os

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

# 受講生名簿の同期元スプレッドシートID（年度表記プレフィックスをキーとする）。
# Issue #5: 旧実装は単一のグローバルデフォルト値を持ち、年度概念がなかったため
# 誤った年度の名簿を同期しうるリスクがあった（resolve_student_spreadsheet_id参照）。
STUDENT_SPREADSHEET_IDS_BY_YEAR = {
    "令和7年度": "1AQ12-h3n_NmN2kWxi4Z_g354X0wmUyMKAPeAsXJwu_w",
    # "令和8年度": "<令和8年度の正しい名簿スプレッドシートIDを設定してください>",
}


def get_current_academic_year_prefix() -> str:
    """KNOWN_CLASSESの先頭クラス名から現在運用中の年度表記（例:「令和8年度」）を取得する"""
    return KNOWN_CLASSES[0].split(" ")[0]


def resolve_student_spreadsheet_id() -> str:
    """
    受講生名簿の同期元スプレッドシートIDを解決する。

    STUDENT_SPREADSHEET_ID環境変数が明示設定されていればそれを優先する。
    未設定の場合は現在年度（KNOWN_CLASSESから動的取得）に対応するIDを
    STUDENT_SPREADSHEET_IDS_BY_YEARから引く。どちらも得られない場合は、
    誤った年度のスプレッドシートへ暗黙にフォールバックすることを避けるため
    ValueErrorを送出する。
    """
    env_value = os.environ.get("STUDENT_SPREADSHEET_ID")
    if env_value:
        return env_value

    current_year = get_current_academic_year_prefix()
    spreadsheet_id = STUDENT_SPREADSHEET_IDS_BY_YEAR.get(current_year)
    if not spreadsheet_id:
        raise ValueError(
            f"{current_year}の受講生名簿スプレッドシートIDが未設定です。"
            "STUDENT_SPREADSHEET_ID環境変数を設定するか、"
            "src/config/classes.pyのSTUDENT_SPREADSHEET_IDS_BY_YEARに追加してください。"
        )
    return spreadsheet_id
