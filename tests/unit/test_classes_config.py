"""
Unit tests for src/config/classes.py's year-aware student spreadsheet ID resolution.

Issue #5: STUDENT_SPREADSHEET_ID was a single global env var with no year concept,
risking a silent sync against the wrong academic year's roster spreadsheet.
codex review (P1, effort=high) additionally flagged that an unscoped env var
override would still silently win even when it held a stale prior-year value,
so the override now requires a matching STUDENT_SPREADSHEET_ID_YEAR companion.
"""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, "src")

from config import classes as classes_config  # noqa: E402

CURRENT_YEAR_PREFIX = classes_config.KNOWN_CLASSES[0].split(" ")[0]


class TestGetCurrentAcademicYearPrefix:
    def test_derives_prefix_from_known_classes(self):
        assert classes_config.get_current_academic_year_prefix() == CURRENT_YEAR_PREFIX


class TestResolveStudentSpreadsheetId:
    def test_env_var_takes_priority_when_year_matches(self):
        with patch.dict(
            os.environ,
            {
                "STUDENT_SPREADSHEET_ID": "env-override-id",
                "STUDENT_SPREADSHEET_ID_YEAR": CURRENT_YEAR_PREFIX,
            },
        ):
            assert classes_config.resolve_student_spreadsheet_id() == "env-override-id"

    def test_env_var_rejected_when_year_missing(self):
        with patch.dict(os.environ, {"STUDENT_SPREADSHEET_ID": "stale-prior-year-id"}):
            os.environ.pop("STUDENT_SPREADSHEET_ID_YEAR", None)
            with pytest.raises(ValueError, match="STUDENT_SPREADSHEET_ID_YEAR"):
                classes_config.resolve_student_spreadsheet_id()

    def test_env_var_rejected_when_year_mismatches(self):
        with patch.dict(
            os.environ,
            {
                "STUDENT_SPREADSHEET_ID": "stale-prior-year-id",
                "STUDENT_SPREADSHEET_ID_YEAR": "令和7年度",
            },
        ):
            with pytest.raises(ValueError, match="STUDENT_SPREADSHEET_ID_YEAR"):
                classes_config.resolve_student_spreadsheet_id()

    def test_falls_back_to_year_dict_when_env_var_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.dict(
                classes_config.STUDENT_SPREADSHEET_IDS_BY_YEAR,
                {CURRENT_YEAR_PREFIX: "current-year-id"},
                clear=True,
            ):
                assert (
                    classes_config.resolve_student_spreadsheet_id() == "current-year-id"
                )

    def test_raises_when_neither_env_var_nor_year_entry_exists(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.dict(
                classes_config.STUDENT_SPREADSHEET_IDS_BY_YEAR, {}, clear=True
            ):
                with pytest.raises(ValueError, match=CURRENT_YEAR_PREFIX):
                    classes_config.resolve_student_spreadsheet_id()

    def test_empty_string_env_var_is_treated_as_unset(self):
        with patch.dict(os.environ, {"STUDENT_SPREADSHEET_ID": ""}):
            with patch.dict(
                classes_config.STUDENT_SPREADSHEET_IDS_BY_YEAR, {}, clear=True
            ):
                with pytest.raises(ValueError):
                    classes_config.resolve_student_spreadsheet_id()


class TestResolveFirestoreDatabaseId:
    """
    2026-09-14: 令和7年度・令和8年度が同一Firestore DBを共有していたため、
    令和8年度ダッシュボードに令和7年度の受講者が混在表示される事故が発生した。
    以降DBを年度ごとに分離する。resolve_student_spreadsheet_id()と異なり、
    誤ったDBへの誤接続の被害が大きいため環境変数上書きは持たせない
    （/plan-crossreviewでのcodex指摘）。
    """

    def test_resolves_current_year_database_id(self):
        with patch.dict(
            classes_config.FIRESTORE_DATABASE_IDS_BY_YEAR,
            {CURRENT_YEAR_PREFIX: "current-year-db"},
            clear=True,
        ):
            assert classes_config.resolve_firestore_database_id() == "current-year-db"

    def test_raises_when_current_year_entry_missing(self):
        with patch.dict(classes_config.FIRESTORE_DATABASE_IDS_BY_YEAR, {}, clear=True):
            with pytest.raises(ValueError, match=CURRENT_YEAR_PREFIX):
                classes_config.resolve_firestore_database_id()

    def test_environment_variable_has_no_override_effect(self):
        """
        DB選択には意図的にenv var上書き機構を持たせていない回帰テスト。
        STUDENT_SPREADSHEET_IDと同名の慣習(FIRESTORE_DATABASE_ID)を環境変数に
        設定しても、辞書引きの結果に一切影響しないこと。
        """
        with patch.dict(os.environ, {"FIRESTORE_DATABASE_ID": "should-be-ignored"}):
            with patch.dict(
                classes_config.FIRESTORE_DATABASE_IDS_BY_YEAR,
                {CURRENT_YEAR_PREFIX: "current-year-db"},
                clear=True,
            ):
                assert (
                    classes_config.resolve_firestore_database_id() == "current-year-db"
                )

    def test_production_dict_has_no_duplicate_database_ids_across_years(self):
        """
        本番のFIRESTORE_DATABASE_IDS_BY_YEAR自体を対象にした回帰テスト（他のテストは
        辞書をpatch.dictで差し替えているため、実際の値そのものは検証していなかった）。
        2つの年度が同じDB名を指す設定は、まさに今回の事故（令和7年度・令和8年度が
        carewell-nativeを共有）そのものであり、これを機械的に検知する。
        """
        values = list(classes_config.FIRESTORE_DATABASE_IDS_BY_YEAR.values())
        assert len(values) == len(set(values)), (
            "FIRESTORE_DATABASE_IDS_BY_YEARの複数年度が同じDB名を指しています: "
            f"{classes_config.FIRESTORE_DATABASE_IDS_BY_YEAR!r}"
        )

    def test_production_dict_resolves_current_year_to_expected_database(self):
        """
        本番のFIRESTORE_DATABASE_IDS_BY_YEAR（未patch）を対象に、現在年度が
        期待するDB名に解決されることを固定検証する。
        """
        assert (
            classes_config.FIRESTORE_DATABASE_IDS_BY_YEAR.get(CURRENT_YEAR_PREFIX)
            == "carewell-2026"
        )
        assert classes_config.resolve_firestore_database_id() == "carewell-2026"
