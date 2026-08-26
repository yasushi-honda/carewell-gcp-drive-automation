"""
Unit tests for src/config/classes.py's year-aware student spreadsheet ID resolution.

Issue #5: STUDENT_SPREADSHEET_ID was a single global env var with no year concept,
risking a silent sync against the wrong academic year's roster spreadsheet.
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
    def test_env_var_takes_priority_over_year_dict(self):
        with patch.dict(os.environ, {"STUDENT_SPREADSHEET_ID": "env-override-id"}):
            assert classes_config.resolve_student_spreadsheet_id() == "env-override-id"

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
