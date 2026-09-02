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
    # 令和8年度分は「ケアウェル自動化システム/課題レポート/2026年/受講者リスト」に
    # 2025年分と同じ列構成(A:氏名〜L:無効、シート名「統合_受講者リスト」)で新規作成済み。
    # 名簿データ本体の入力は貴団体側の対応待ち（2026-09-02時点、ヘッダー行のみ）。
    "令和8年度": "1PvzMbjhZ4zpLsL6lfljJNHVEkbEkqtGRM4kNyB6ZA2M",
}


def get_current_academic_year_prefix() -> str:
    """KNOWN_CLASSESの先頭クラス名から現在運用中の年度表記（例:「令和8年度」）を取得する"""
    return KNOWN_CLASSES[0].split(" ")[0]


def resolve_student_spreadsheet_id() -> str:
    """
    受講生名簿の同期元スプレッドシートIDを解決する。

    STUDENT_SPREADSHEET_ID環境変数は、対応する年度を示す
    STUDENT_SPREADSHEET_ID_YEAR環境変数が現在年度と一致する場合のみ採用する
    （Cloud Run/実行環境に前年度の値が残ったまま放置され、年度チェックを
    素通りして誤った名簿を同期する事故を防ぐため。年度指定なしの値を無条件に
    信用しない）。一致しない、またはSTUDENT_SPREADSHEET_ID_YEARが未設定の場合は
    ValueErrorを送出する。

    注意（codex review P2指摘）: `.github/workflows/deploy.yml`の通常デプロイは
    `gcloud run deploy --set-env-vars "GCP_PROJECT=..."`のみを指定しており、
    Cloud Runの`--set-env-vars`は既存の環境変数を丸ごと置き換える仕様のため、
    gcloud CLI等で手動設定したSTUDENT_SPREADSHEET_ID/STUDENT_SPREADSHEET_ID_YEAR
    は次回の自動デプロイで消える。恒久的な値はSTUDENT_SPREADSHEET_IDS_BY_YEARに
    コードとして追加すること。環境変数はあくまで一時的な手動オーバーライド用。

    STUDENT_SPREADSHEET_ID自体が未設定の場合は、現在年度
    （KNOWN_CLASSESから動的取得）に対応するIDをSTUDENT_SPREADSHEET_IDS_BY_YEAR
    から引く。対応するIDがなければ、誤った年度のスプレッドシートへ暗黙に
    フォールバックすることを避けるためValueErrorを送出する。
    """
    current_year = get_current_academic_year_prefix()
    env_value = os.environ.get("STUDENT_SPREADSHEET_ID")

    if env_value:
        env_year = os.environ.get("STUDENT_SPREADSHEET_ID_YEAR")
        if env_year != current_year:
            raise ValueError(
                "STUDENT_SPREADSHEET_ID環境変数が設定されていますが、対応する"
                f"年度を示すSTUDENT_SPREADSHEET_ID_YEAR環境変数が現在年度"
                f"（{current_year}）と一致しません（実際の値: {env_year!r}）。"
                "前年度の値が残っている可能性があるため、誤った年度への暗黙"
                f"フォールバックを避けて停止します。STUDENT_SPREADSHEET_ID_YEARを"
                f"{current_year!r}に設定するか、両方の環境変数を削除してください。"
            )
        return env_value

    spreadsheet_id = STUDENT_SPREADSHEET_IDS_BY_YEAR.get(current_year)
    if not spreadsheet_id:
        raise ValueError(
            f"{current_year}の受講生名簿スプレッドシートIDが未設定です。"
            "STUDENT_SPREADSHEET_ID / STUDENT_SPREADSHEET_ID_YEAR環境変数を"
            "設定するか、src/config/classes.pyのSTUDENT_SPREADSHEET_IDS_BY_YEAR"
            "に追加してください。"
        )
    return spreadsheet_id
