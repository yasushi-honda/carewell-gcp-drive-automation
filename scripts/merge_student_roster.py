#!/usr/bin/env python3
"""
{No}_受講者リスト_出欠管理 の「受講者リスト」タブ(日介番号⇔受講者番号マッピング)を、
クライアント正本({No}リストタブ)と自社管理の申込データ(Team{N}タブ)から
検証ゲート付きで再構築するスクリプト。

背景・設計判断の詳細: ~/.claude/plans/ethereal-meandering-kurzweil.md
(手動転記ミス再発防止のためのスクリプト化。Codex plan-crossreview反映済み)

使い方:
    python scripts/merge_student_roster.py --class 01            # dry-run(検証のみ)
    python scripts/merge_student_roster.py --class 01 --commit   # 実書き込み

注意: --scopesは権限借用時に実効制限として機能しない(src/gcp_sa_auth.py参照)。
実際のアクセス境界はSAのIAM権限とDrive/Sheets共有設定で決まる。
"""

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.gcp_sa_auth import call_with_reauth, get_impersonated_service  # noqa: E402

SA_EMAIL = "carewell-automation-sa@carewell-automation.iam.gserviceaccount.com"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

COLLECTIVE_TRAINING_FOLDER_ID = "1J2h1ZL4MOfKhjVyayJJuRNLovh86rLlu"  # 「集合研修」
APPLICATION_SPREADSHEET_ID = (
    "1ybWm0n0e7Ixk6A_GbLGwmPhixza01PF7Kn0NXv6jXcg"  # 【申込状況】
)

# 既知クラスのスプレッドシートID。未登録クラスはDrive名前検索で解決し、
# 発見したIDをここに追記する運用とする(Codex指摘H4: 名前検索を毎回の識別子にしない)。
KNOWN_ATTENDANCE_FILE_IDS = {
    "01": "10pXxlqzIvWNGt0QZQpgcsgguOvW372RVS2eSkGpMws4",
    "02": "138wCXPyD8JeSbnYhC2-UYi1haJB9OqA61JipwKrm-Uc",
    "03": "1I9t6CzePqaPQxsHfv5r8H2zrBoXRss65flJKZbqk-uU",
    "04": "1rRHdPa5QEuvKG4uI8tKZpocpobzLaubLi1D0cGgWGl4",
    "05": "1F45fZ0-q8-sncS6evRaJ31_hZLaFR3p6Jr5tXq0Byz8",
    "06": "16tpctLo8x_Bn_oLy2sfHv8qyHxGmnqyJufp6-AJJ2Rs",
    "07": "1ooY1O5eurA7MWXN7u8l8A-WytBRTVM62jwBUPSDR62A",
    "09": "1kTR2myJocAeDajT8Tr3Uy6_Kg7pbCVueVgLmJTdSy-U",
}

CLIENT_SOURCE_TAB = "№{class_num}リスト"
ROSTER_TARGET_TAB = "受講者リスト"

CLIENT_SOURCE_HEADER = [
    "グループ",
    "サブ講師",
    "受講者番号",
    "受講者名前",
    "受講者なまえ",
    "サービス種別",
    "備考",
]
APPLICATION_HEADER_PREFIX = ["氏名", "ふりがな", "日介番号"]
ROSTER_HEADER = [
    "氏名",
    "ふりがな",
    "日介番号",
    "会社",
    "事業所",
    "サービス種別",
    "入所・居宅系",
    "グループ",
    "受講者番号",
    "受講者番号（グループ付き）",
]

# グループ→入所・居宅系カテゴリ対応表。
# 出典: クライアントの公式承認ではなく、手動転記時代の「受講者リスト」タブから
# 逆算した推定値(2026-09-11、253/254行で内部矛盾ゼロを確認)。他クラスで同じ
# 規則が成り立つかは未検証のリスクとして明示する(Codex指摘H3、decision-maker
# 承認: 推定値のまま使用しクライアントへの確認は行わない)。
GROUP_CATEGORY_MAP_BY_CLASS = {
    "01": {
        "A": "入所系居住系",
        "B": "入所系居住系",
        "C": "入所系居住系",
        "D": "入所系居住系",
        "E": "入所系居住系",
        "F": "入所系居住系",
        "G": "入所系居住系",
        "H": "入所系居住系",
        "J": "入所系居住系",
        "K": "通所系訪問系",
        "M": "通所系訪問系",
        "N": "通所系訪問系",
        "P": "通所系訪問系",
        "Q": "通所系訪問系",
        "R": "居宅介護支援",
    },
}

# 自動正規化(NFKC/カタカナ→ひらがな変換)では解決できない名寄せ例外のみ登録する。
# 日介番号は別途人間が確認済みのものに限る。
MATCH_EXCEPTIONS_BY_CLASS = {
    "01": {
        # 植田隆介: クライアント側ふりがな「りゆうすけ」/ 申込データ側「リュウスケ」(拗音表記ゆれ)
        "K165": "N9905863",
    },
}

# クラスごとの正しい受講者総数(人間が別途確認した値のみ登録する)。
# 受講者番号の連番検証(validate_student_number_sequence)は取得できた行数から
# 期待値を逆算するため、取得自体が途中で欠落しても内部的には無矛盾に見えてしまう
# (Codex指摘: 2026-09-11)。この定数と突き合わせることで、取得漏れによる
# サイレントな名簿破損(既存の正しいマッピングを空行で上書きしてしまう事故)を防ぐ。
EXPECTED_STUDENT_COUNT_BY_CLASS = {
    "01": 254,
}


class ValidationError(RuntimeError):
    """検証ゲートで1つ以上失敗した"""


def normalize_key(name: str, kana: str) -> tuple[str, str]:
    """氏名+ふりがなの照合キーを正規化する(マッチングキー専用。保存値には適用しない)。

    NFKC正規化 + 全角/半角問わず全空白除去 + カタカナ→ひらがな変換。
    拗音(小さい「ゅ」と大きい「ゆ」等)の差異は正規化しても解決できないため、
    そのケースはMATCH_EXCEPTIONS_BY_CLASSで個別に救済する。
    """

    def _norm(s: str) -> str:
        s = unicodedata.normalize("NFKC", s or "")
        s = "".join(s.split())
        return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)

    return (_norm(name), _norm(kana))


def _require_header(actual: list[str], expected_prefix: list[str], label: str) -> None:
    actual_prefix = actual[: len(expected_prefix)]
    if actual_prefix != expected_prefix:
        raise ValidationError(
            f"{label}のヘッダーが想定と異なります。期待={expected_prefix} 実際={actual_prefix}"
        )


def parse_client_source(rows: list[list[str]], label: str) -> list[dict]:
    if not rows:
        raise ValidationError(f"{label}が空です")
    _require_header(rows[0], CLIENT_SOURCE_HEADER, label)
    parsed = []
    for line_no, row in enumerate(rows[1:], start=2):
        row = row + [""] * (7 - len(row))
        required = [
            row[0],
            row[2],
            row[3],
            row[4],
            row[5],
        ]  # group/student_number/name/kana/service_type
        if not any(v.strip() for v in required):
            continue  # 完全に空白の行はスキップ(末尾の余白行等)
        if not all(v.strip() for v in required):
            raise ValidationError(
                f"{label} {line_no}行目が部分的にしか入力されていません: {row}"
            )
        parsed.append(
            {
                "group": row[0].strip(),
                "sub_teacher": row[1].strip(),
                "student_number": row[2].strip(),
                "name": row[3].strip(),
                "kana": row[4].strip(),
                "service_type": row[5].strip(),
            }
        )
    return parsed


def parse_application_data(rows: list[list[str]], label: str) -> list[dict]:
    if not rows:
        raise ValidationError(f"{label}が空です")
    _require_header(rows[0], APPLICATION_HEADER_PREFIX, label)
    header = rows[0] + [""] * (12 - len(rows[0]))
    company_col, office_col = header[10], header[11]
    if (company_col, office_col) != ("勤務先法人名称", "勤務先名称"):
        raise ValidationError(
            f"{label}の会社/事業所列(K/L列)が想定と異なります。"
            f"期待=('勤務先法人名称', '勤務先名称') 実際=({company_col!r}, {office_col!r})"
        )
    parsed = []
    for line_no, row in enumerate(rows[1:], start=2):
        row = row + [""] * (12 - len(row))
        required = [
            row[0],
            row[1],
            row[2],
        ]  # name/kana/nichikai(company/officeは正当に空欄になりうる)
        if not any(v.strip() for v in required):
            continue  # 完全に空白の行はスキップ(末尾の余白行等)
        if not all(v.strip() for v in required):
            raise ValidationError(
                f"{label} {line_no}行目が部分的にしか入力されていません: {row}"
            )
        parsed.append(
            {
                "name": row[0].strip(),
                "kana": row[1].strip(),
                "nichikai": row[2].strip(),
                "company": row[10].strip(),
                "office": row[11].strip(),
            }
        )
    return parsed


def validate_expected_count(client_rows: list[dict], expected_count: int) -> list[str]:
    """検証ゲート0: 取得できた行数が、人間が別途確認した正しい受講者総数と一致するか。

    取得自体が(APIのレンジ指定ミス・データ移動・一部行の欠落等で)途中で
    欠けていた場合、他の検証ゲート(特に受講者番号連番チェック)は取得できた
    行数を基準に整合性を判定するため、欠落そのものを検出できない
    (Codex指摘: 2026-09-11)。既知の正しい総数との突き合わせでこれを防ぐ。
    """
    if len(client_rows) != expected_count:
        return [
            f"取得した受講者数({len(client_rows)}件)が、確認済みの正しい総数"
            f"({expected_count}件)と一致しません。データ取得が途中で欠落している"
            f"可能性があります。"
        ]
    return []


def validate_student_number_sequence(client_rows: list[dict]) -> list[str]:
    """検証ゲート1: 受講者番号に重複・欠番がないか(数字部分が1..Nの通し番号か)"""
    issues = []
    numbers = [r["student_number"] for r in client_rows]
    if len(numbers) != len(set(numbers)):
        dup = [n for n in numbers if numbers.count(n) > 1]
        issues.append(f"受講者番号に重複があります: {sorted(set(dup))}")
    suffixes = []
    for n in numbers:
        m = re.fullmatch(r"[A-Zー](\d{3})", n)
        if not m:
            issues.append(f"受講者番号の形式が不正です: {n!r}")
            continue
        suffixes.append(int(m.group(1)))
    if suffixes and sorted(suffixes) != list(range(1, len(client_rows) + 1)):
        issues.append(
            f"受講者番号の通し番号に欠番があります(件数={len(client_rows)}、"
            f"番号範囲={min(suffixes)}-{max(suffixes)})"
        )
    return issues


def _find_key_duplicates(rows: list[dict], label: str) -> list[str]:
    keys: dict[tuple, list[str]] = {}
    for r in rows:
        k = normalize_key(r["name"], r["kana"])
        keys.setdefault(k, []).append(r.get("student_number") or r.get("nichikai", ""))
    dups = {k: v for k, v in keys.items() if len(v) > 1}
    if not dups:
        return []
    return [f"{label}で氏名+ふりがなキーが重複しています: {dups}"]


def match_students(
    client_rows: list[dict],
    app_rows: list[dict],
    match_exceptions: dict[str, str],
) -> tuple[list[dict], list[str], list[str], list[str]]:
    """クライアント正本と申込データを氏名+ふりがなキーで突合する。

    Returns:
        merged: マージ済み行(10列相当の辞書)のリスト
        unmatched: 突合できなかった受講者番号のリスト
        exception_usage_issues: 例外テーブル適用時の機械検証で見つかった問題(Codex指摘M3)
        exception_used_for: 例外テーブルが実際に適用された受講者番号のリスト
    """
    app_by_key: dict[tuple, list[dict]] = {}
    for r in app_rows:
        app_by_key.setdefault(normalize_key(r["name"], r["kana"]), []).append(r)

    # 先に通常マッチ(自動正規化キー一致)を確定させ、使用済み日介番号を把握する
    # (例外テーブル適用時に「既に通常マッチで使用済みの日介番号」を検出するため、
    # 通常マッチを全件確定してから例外を解決する。ただし出力順序は client_rows の
    # 元の並び順を保持するため、merged はインデックス位置を保った状態で構築する)
    normally_matched_nichikai: set[str] = set()
    direct_match: dict[int, dict] = {}
    pending_exception: list[tuple[int, dict]] = []
    unmatched_indices: set[int] = set()

    for i, c in enumerate(client_rows):
        key = normalize_key(c["name"], c["kana"])
        candidates = app_by_key.get(key, [])
        if len(candidates) == 1:
            app = candidates[0]
            normally_matched_nichikai.add(app["nichikai"])
            direct_match[i] = app
        elif len(candidates) == 0:
            pending_exception.append((i, c))
        else:
            unmatched_indices.add(i)

    exception_issues = []
    exception_used_for = []
    exception_match: dict[int, dict] = {}

    for i, c in pending_exception:
        expected_nichikai = match_exceptions.get(c["student_number"])
        if expected_nichikai is None:
            unmatched_indices.add(i)
            continue
        nichikai_candidates = [
            r for r in app_rows if r["nichikai"] == expected_nichikai
        ]
        if len(nichikai_candidates) != 1:
            exception_issues.append(
                f"例外テーブル対象 {c['student_number']} の日介番号 {expected_nichikai} が"
                f"申込データ側に一意に存在しません(候補{len(nichikai_candidates)}件)"
            )
            unmatched_indices.add(i)
            continue
        if expected_nichikai in normally_matched_nichikai:
            exception_issues.append(
                f"例外テーブル対象 {c['student_number']} の日介番号 {expected_nichikai} は"
                f"既に別の通常マッチで使用済みです(二重割当の疑い)"
            )
            unmatched_indices.add(i)
            continue
        normally_matched_nichikai.add(expected_nichikai)
        exception_used_for.append(c["student_number"])
        exception_match[i] = nichikai_candidates[0]

    # client_rows の元の並び順を保ったままmergedを構築する
    # (例外テーブル救済分が末尾に回り、以降の全行がずれる事故を防ぐ)
    merged = []
    unmatched = []
    for i, c in enumerate(client_rows):
        app = direct_match.get(i) or exception_match.get(i)
        if app is not None:
            merged.append(_build_merged_row(c, app))
        elif i in unmatched_indices:
            unmatched.append(c["student_number"])

    return merged, unmatched, exception_issues, exception_used_for


def _build_merged_row(client_row: dict, app_row: dict) -> dict:
    return {
        "name": client_row["name"],
        "kana": client_row["kana"],
        "nichikai": app_row["nichikai"],
        "company": app_row["company"],
        "office": app_row["office"],
        "service_type": client_row["service_type"],
        "group": client_row["group"],
        "student_number": client_row["student_number"],
    }


def validate_required_fields(merged: list[dict]) -> list[str]:
    issues = []
    for r in merged:
        # company/officeは申込データ原本にも空欄がありうる正当なデータのため必須対象外
        # (実データで確認済み)。日介番号とサービス種別のみ必須とする。
        missing = [k for k in ("nichikai", "service_type") if not r.get(k)]
        if missing:
            issues.append(f"受講者番号{r['student_number']}で必須列が欠損: {missing}")
    return issues


def validate_group_mapping(
    client_rows: list[dict], category_map: dict[str, str]
) -> list[str]:
    groups = {r["group"] for r in client_rows}
    unknown = groups - set(category_map)
    if unknown:
        return [
            f"入所・居宅系マッピングに存在しないグループがあります: {sorted(unknown)}"
        ]
    return []


def validate_student_number_uniqueness(merged: list[dict]) -> list[str]:
    numbers = [r["student_number"] for r in merged]
    if len(numbers) != len(set(numbers)):
        dup = sorted({n for n in numbers if numbers.count(n) > 1})
        return [f"マージ後の受講者番号(グループ付き)に重複があります: {dup}"]
    return []


def validate_nichikai_uniqueness(merged: list[dict]) -> list[str]:
    """氏名+ふりがなキーが別でも、申込データ側の日介番号自体が重複していれば
    2名の受講者が同一の日介番号にマッピングされうる(Codex指摘、直接マッチ経路の
    重複はキー重複チェックだけでは検出できない)。"""
    nichikai_to_numbers: dict[str, list[str]] = {}
    for r in merged:
        nichikai_to_numbers.setdefault(r["nichikai"], []).append(r["student_number"])
    dup = {k: v for k, v in nichikai_to_numbers.items() if len(v) > 1}
    if not dup:
        return []
    return [f"日介番号が複数の受講者にマッピングされています: {dup}"]


def run_validation_gates(
    client_rows: list[dict],
    app_rows: list[dict],
    category_map: dict[str, str],
    match_exceptions: dict[str, str],
    expected_count: int,
) -> tuple[list[dict], dict[str, list[str]]]:
    """全検証ゲートを実行し、(マージ結果, ゲート名->issuesのdict) を返す。

    issuesが空のゲートはPASS、1件以上あればFAIL。
    """
    results: dict[str, list[str]] = {}

    results["0_受講者総数"] = validate_expected_count(client_rows, expected_count)
    results["1_受講者番号連番"] = validate_student_number_sequence(client_rows)
    results["2_氏名ふりがなキー重複"] = _find_key_duplicates(
        client_rows, "クライアント正本"
    ) + _find_key_duplicates(app_rows, "申込データ")

    merged, unmatched, exception_issues, exception_used_for = match_students(
        client_rows, app_rows, match_exceptions
    )
    match_issues = []
    if unmatched:
        match_issues.append(f"突合できなかった受講者番号: {sorted(unmatched)}")
    results["3_氏名ふりがなキー突合率"] = match_issues
    results["7_例外テーブル機械検証"] = exception_issues
    if exception_used_for:
        print(f"  [情報] 例外テーブルが適用された受講者番号: {exception_used_for}")

    results["4_必須列欠損"] = validate_required_fields(merged)
    results["5_グループマッピング完全性"] = validate_group_mapping(
        client_rows, category_map
    )
    results["6_受講者番号重複"] = validate_student_number_uniqueness(merged)
    results["8_日介番号重複"] = validate_nichikai_uniqueness(merged)

    return merged, results


def build_target_matrix(
    merged: list[dict], category_map: dict[str, str]
) -> list[list[str]]:
    rows = []
    for r in merged:
        rows.append(
            [
                r["name"],
                r["kana"],
                r["nichikai"],
                r["company"],
                r["office"],
                r["service_type"],
                category_map.get(r["group"], ""),
                r["group"],
                r["student_number"],
                r["student_number"],
            ]
        )
    return rows


def _rstrip_blank_rows(rows: list[list[str]]) -> list[list[str]]:
    """末尾の完全空行を除去する(Sheets APIのvalues.get()が返す形と正規化を揃えるため)"""
    trimmed = list(rows)
    while trimmed and not any(c.strip() for c in trimmed[-1]):
        trimmed.pop()
    return trimmed


def _content_hash(rows: list[list[str]]) -> str:
    return hashlib.sha256(
        json.dumps(rows, ensure_ascii=False, sort_keys=False).encode()
    ).hexdigest()


def _col_letter(n: int) -> str:
    """1-indexed列番号をA1記法の列文字に変換する(J=10までしか使わないため簡易実装)"""
    letters = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _build_drive_service():
    return get_impersonated_service("drive", "v3", SA_EMAIL, SCOPES)


def _build_sheets_service():
    return get_impersonated_service("sheets", "v4", SA_EMAIL, SCOPES)


def resolve_attendance_spreadsheet_id(class_num: str) -> str:
    if class_num in KNOWN_ATTENDANCE_FILE_IDS:
        return KNOWN_ATTENDANCE_FILE_IDS[class_num]

    print(f"[情報] クラス{class_num}は未登録のため、Driveフォルダを名前検索します")
    folders = call_with_reauth(
        _build_drive_service,
        lambda svc: svc.files()
        .list(
            q=(
                f"'{COLLECTIVE_TRAINING_FOLDER_ID}' in parents and "
                f"name = '№{class_num}' and mimeType = 'application/vnd.google-apps.folder'"
            ),
            fields="files(id,name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute(),
    ).get("files", [])
    if len(folders) != 1:
        raise ValidationError(
            f"「集合研修」フォルダ配下に№{class_num}フォルダが{len(folders)}件見つかりました(1件である必要があります)"
        )
    folder_id = folders[0]["id"]

    files = call_with_reauth(
        _build_drive_service,
        lambda svc: svc.files()
        .list(
            q=f"'{folder_id}' in parents and name = '№{class_num}_受講者リスト_出欠管理'",
            fields="files(id,name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute(),
    ).get("files", [])
    if len(files) != 1:
        raise ValidationError(
            f"№{class_num}_受講者リスト_出欠管理ファイルが{len(files)}件見つかりました(1件である必要があります)"
        )
    file_id = files[0]["id"]
    print(
        f"[情報] 発見したファイルID={file_id} をKNOWN_ATTENDANCE_FILE_IDSに追記してください"
    )
    return file_id


def _verify_single_tab(spreadsheet_id: str, tab_name: str) -> None:
    meta = call_with_reauth(
        _build_sheets_service,
        lambda svc: svc.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets.properties.title")
        .execute(),
    )
    titles = [s["properties"]["title"] for s in meta.get("sheets", [])]
    matches = [t for t in titles if t == tab_name]
    if len(matches) != 1:
        raise ValidationError(
            f"タブ「{tab_name}」が{len(matches)}件見つかりました(1件である必要があります)。実在タブ={titles}"
        )


def _get_values(spreadsheet_id: str, range_: str) -> list[list[str]]:
    result = call_with_reauth(
        _build_sheets_service,
        lambda svc: svc.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet_id,
            range=range_,
            valueRenderOption="UNFORMATTED_VALUE",
        )
        .execute(),
    )
    return [[str(c) for c in row] for row in result.get("values", [])]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--class", dest="class_num", required=True, help="クラス番号(例: 01)"
    )
    parser.add_argument(
        "--commit", action="store_true", help="実際にSheetsへ書き込む(省略時はdry-run)"
    )
    args = parser.parse_args()
    class_num = args.class_num

    if class_num not in GROUP_CATEGORY_MAP_BY_CLASS:
        print(
            f"[エラー] クラス{class_num}の入所・居宅系マッピングが未登録です。中断します。"
        )
        return 1
    if class_num not in EXPECTED_STUDENT_COUNT_BY_CLASS:
        print(
            f"[エラー] クラス{class_num}の確認済み受講者総数が未登録です。"
            f"人間が正しい総数を確認してEXPECTED_STUDENT_COUNT_BY_CLASSに登録してから"
            f"実行してください。中断します。"
        )
        return 1
    if class_num not in MATCH_EXCEPTIONS_BY_CLASS:
        print(f"[情報] クラス{class_num}の名寄せ例外テーブルは空です")
    category_map = GROUP_CATEGORY_MAP_BY_CLASS[class_num]
    match_exceptions = MATCH_EXCEPTIONS_BY_CLASS.get(class_num, {})
    expected_count = EXPECTED_STUDENT_COUNT_BY_CLASS[class_num]

    spreadsheet_id = resolve_attendance_spreadsheet_id(class_num)
    client_tab = CLIENT_SOURCE_TAB.format(class_num=class_num)
    _verify_single_tab(spreadsheet_id, client_tab)
    _verify_single_tab(spreadsheet_id, ROSTER_TARGET_TAB)
    roster_header = _get_values(spreadsheet_id, f"'{ROSTER_TARGET_TAB}'!A1:J1")
    if not roster_header or roster_header[0] != ROSTER_HEADER:
        raise ValidationError(
            f"「{ROSTER_TARGET_TAB}」のヘッダーが想定と異なります。"
            f"列順・見出しが変更されている可能性があります。"
            f"期待={ROSTER_HEADER} 実際={roster_header[0] if roster_header else None}"
        )

    client_raw = _get_values(spreadsheet_id, f"'{client_tab}'!A1:G1000")
    client_rows = parse_client_source(client_raw, client_tab)

    app_tab = f"Team{int(class_num)}"
    app_raw = _get_values(APPLICATION_SPREADSHEET_ID, f"'{app_tab}'!A1:L1000")
    app_rows = parse_application_data(app_raw, app_tab)

    merged, gate_results = run_validation_gates(
        client_rows, app_rows, category_map, match_exceptions, expected_count
    )

    print(f"=== クラス{class_num} 検証ゲート結果 ===")
    all_passed = True
    for gate_name, issues in gate_results.items():
        status = "PASS" if not issues else "FAIL"
        if issues:
            all_passed = False
        print(f"  [{status}] {gate_name}")
        for issue in issues:
            print(f"      - {issue}")

    if not all_passed:
        print("[中断] 検証ゲートに失敗があるため書き込みを行いません。")
        return 1

    new_matrix = build_target_matrix(merged, category_map)

    current_raw = _get_values(spreadsheet_id, f"'{ROSTER_TARGET_TAB}'!A2:J100000")
    current_hash = _content_hash(current_raw)

    scratch_dir = Path.home() / ".claude" / "scratch" / "merge_student_roster"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = scratch_dir / f"backup_class{class_num}_{timestamp}.json"
    backup_path.write_text(json.dumps(current_raw, ensure_ascii=False, indent=2))
    print(f"[バックアップ] {backup_path}")

    diff_count = sum(
        1
        for i in range(max(len(current_raw), len(new_matrix)))
        if (current_raw[i] if i < len(current_raw) else None)
        != (new_matrix[i] if i < len(new_matrix) else None)
    )
    print(
        f"[差分レポート] 現状{len(current_raw)}行 → 新規{len(new_matrix)}行、実質変更{diff_count}行"
    )

    if not args.commit:
        print("[DRY-RUN] --commitが指定されていないため書き込みは行いません。")
        return 0

    reread_raw = _get_values(spreadsheet_id, f"'{ROSTER_TARGET_TAB}'!A2:J100000")
    if _content_hash(reread_raw) != current_hash:
        print(
            "[中断] 検証時点からシート内容が変更されています(楽観ロック)。再実行してください。"
        )
        return 1

    max_rows = max(len(current_raw), len(new_matrix))
    padded_matrix = [
        (new_matrix[i] if i < len(new_matrix) else [""] * 10) for i in range(max_rows)
    ]
    end_row = 1 + max_rows  # ヘッダーが1行目
    write_range = f"'{ROSTER_TARGET_TAB}'!A2:{_col_letter(10)}{end_row}"

    manifest = {
        "timestamp": timestamp,
        "class": class_num,
        "spreadsheet_id": spreadsheet_id,
        "write_range": write_range,
        "input_client_rows": len(client_rows),
        "input_app_rows": len(app_rows),
        "output_rows": len(new_matrix),
        "content_hash_before": current_hash,
    }

    write_error: Exception | None = None
    try:
        call_with_reauth(
            _build_sheets_service,
            lambda svc: svc.spreadsheets()
            .values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=write_range,
                valueInputOption="RAW",
                body={"values": padded_matrix},
            )
            .execute(),
        )
    except (
        Exception
    ) as e:  # noqa: BLE001 - 意図的に広く捕捉し、下で読み戻し検証にフォールバックする
        write_error = e

    # タイムアウト等でクライアント側は例外を検知しても、書き込み自体は
    # サーバー側で成功している可能性がある(Codex指摘)。盲目的に「失敗」と
    # 記録せず、必ず対象範囲を再読込して実際の結果で判定する。
    try:
        verify_raw = _get_values(spreadsheet_id, write_range)
    except Exception as read_error:
        manifest["result"] = "failed_unknown_state"
        manifest["error"] = (
            f"write_error={write_error}; readback_error={read_error}"
            if write_error
            else f"readback_error={read_error}"
        )
        _write_manifest(scratch_dir, class_num, timestamp, manifest)
        print(
            "[エラー] 書き込み後の状態確認に失敗しました。実際に書き込まれたか不明です。"
            "手動でシートを確認してください(盲目的な再試行はしないこと)。"
        )
        return 1

    # Sheets APIは末尾の完全空行を読み取り結果から自動的に省くため、比較前に
    # 両者の末尾空行を除去して正規化する(Codex指摘: これをしないと更新成功時も
    # 常に不一致になり誤ってverification_mismatchを記録してしまう)
    verify_trimmed = _rstrip_blank_rows(
        [[c.strip() for c in row] for row in verify_raw]
    )
    expected_trimmed = _rstrip_blank_rows(
        [[c.strip() for c in row] for row in padded_matrix]
    )
    if verify_trimmed != expected_trimmed:
        manifest["result"] = (
            "failed_unknown_state" if write_error else "verification_mismatch"
        )
        if write_error:
            manifest["error"] = str(write_error)
        _write_manifest(scratch_dir, class_num, timestamp, manifest)
        print(
            "[エラー] 書き込み後の読み戻し検証で不一致が見つかりました。手動確認してください。"
        )
        return 1

    if write_error:
        manifest["result"] = "success_despite_client_error"
        manifest["client_error"] = str(write_error)
        _write_manifest(scratch_dir, class_num, timestamp, manifest)
        print(
            f"[成功(要注意)] 書き込みAPI呼び出しは例外({write_error})を報告しましたが、"
            f"読み戻し検証では{write_range}の内容が意図通りであることを確認しました。"
        )
        return 0

    manifest["result"] = "success"
    _write_manifest(scratch_dir, class_num, timestamp, manifest)
    print(
        f"[成功] {write_range} へ{len(new_matrix)}行を書き込み、読み戻し検証も一致しました。"
    )
    return 0


def _write_manifest(
    scratch_dir: Path, class_num: str, timestamp: str, manifest: dict
) -> None:
    manifest_path = scratch_dir / f"manifest_class{class_num}_{timestamp}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"[実行記録] {manifest_path}")


if __name__ == "__main__":
    sys.exit(main())
