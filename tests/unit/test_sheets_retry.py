"""
Unit tests for append_record_with_retry function in sheets_retry.py.

These tests verify the exponential backoff retry logic for Google Sheets operations.
"""

import sys
from unittest.mock import Mock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, "src")

from sheets_retry import append_record_with_retry


class TestAppendRecordWithRetry:
    """Test suite for append_record_with_retry function."""

    def test_success_on_first_attempt(self):
        """Test successful append on first attempt."""
        mock_sheets_service = Mock()
        mock_sheets_service.append_record.return_value = True

        result = append_record_with_retry(
            mock_sheets_service,
            spreadsheet_id="test-spreadsheet",
            task_id="課題①",
            student_name="テスト太郎",
            student_id="N9902913",
            submit_date="2025-10-12 10:00:00",
            filename="test.pdf",
            drive_file_id="file123",
            max_retries=3,
            base_delay=0.01,  # Short delay for testing
        )

        assert result is True
        assert mock_sheets_service.append_record.call_count == 1

    def test_success_on_second_attempt(self):
        """Test successful append on second attempt after first failure."""
        mock_sheets_service = Mock()
        # First call returns False, second call returns True
        mock_sheets_service.append_record.side_effect = [False, True]

        with patch("sheets_retry.time.sleep") as mock_sleep:
            result = append_record_with_retry(
                mock_sheets_service,
                spreadsheet_id="test-spreadsheet",
                task_id="課題①",
                student_name="テスト太郎",
                student_id="N9902913",
                submit_date="2025-10-12 10:00:00",
                filename="test.pdf",
                drive_file_id="file123",
                max_retries=3,
                base_delay=1.0,
            )

        assert result is True
        assert mock_sheets_service.append_record.call_count == 2
        # Verify sleep was called with exponential backoff (1s for first retry)
        mock_sleep.assert_called_once_with(1.0)

    def test_success_on_third_attempt(self):
        """Test successful append on third attempt after two failures."""
        mock_sheets_service = Mock()
        # First two calls return False, third call returns True
        mock_sheets_service.append_record.side_effect = [False, False, True]

        with patch("sheets_retry.time.sleep") as mock_sleep:
            result = append_record_with_retry(
                mock_sheets_service,
                spreadsheet_id="test-spreadsheet",
                task_id="課題①",
                student_name="テスト太郎",
                student_id="N9902913",
                submit_date="2025-10-12 10:00:00",
                filename="test.pdf",
                drive_file_id="file123",
                max_retries=3,
                base_delay=1.0,
            )

        assert result is True
        assert mock_sheets_service.append_record.call_count == 3
        # Verify exponential backoff: 1s, 2s
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1.0)
        mock_sleep.assert_any_call(2.0)

    def test_failure_after_all_retries(self):
        """Test that function returns False after all retries exhausted."""
        mock_sheets_service = Mock()
        mock_sheets_service.append_record.return_value = False

        with patch("sheets_retry.time.sleep"):
            result = append_record_with_retry(
                mock_sheets_service,
                spreadsheet_id="test-spreadsheet",
                task_id="課題①",
                student_name="テスト太郎",
                student_id="N9902913",
                submit_date="2025-10-12 10:00:00",
                filename="test.pdf",
                drive_file_id="file123",
                max_retries=3,
                base_delay=0.01,
            )

        assert result is False
        assert mock_sheets_service.append_record.call_count == 3

    def test_handles_exception_and_retries(self):
        """Test that exceptions are caught and retries continue."""
        mock_sheets_service = Mock()
        # First call raises exception, second call returns True
        mock_sheets_service.append_record.side_effect = [
            Exception("API error"),
            True,
        ]

        with patch("sheets_retry.time.sleep"):
            result = append_record_with_retry(
                mock_sheets_service,
                spreadsheet_id="test-spreadsheet",
                task_id="課題①",
                student_name="テスト太郎",
                student_id="N9902913",
                submit_date="2025-10-12 10:00:00",
                filename="test.pdf",
                drive_file_id="file123",
                max_retries=3,
                base_delay=0.01,
            )

        assert result is True
        assert mock_sheets_service.append_record.call_count == 2

    def test_exponential_backoff_delays(self):
        """Test that exponential backoff uses correct delay values."""
        mock_sheets_service = Mock()
        mock_sheets_service.append_record.return_value = False

        with patch("sheets_retry.time.sleep") as mock_sleep:
            append_record_with_retry(
                mock_sheets_service,
                spreadsheet_id="test-spreadsheet",
                task_id="課題①",
                student_name="テスト太郎",
                student_id="N9902913",
                submit_date="2025-10-12 10:00:00",
                filename="test.pdf",
                drive_file_id="file123",
                max_retries=4,
                base_delay=1.0,
            )

        # Verify exponential backoff: 1s, 2s, 4s (no sleep after last attempt)
        assert mock_sleep.call_count == 3
        mock_sleep.assert_any_call(1.0)
        mock_sleep.assert_any_call(2.0)
        mock_sleep.assert_any_call(4.0)

    def test_custom_max_retries(self):
        """Test that custom max_retries is respected."""
        mock_sheets_service = Mock()
        mock_sheets_service.append_record.return_value = False

        with patch("sheets_retry.time.sleep"):
            result = append_record_with_retry(
                mock_sheets_service,
                spreadsheet_id="test-spreadsheet",
                task_id="課題①",
                student_name="テスト太郎",
                student_id="N9902913",
                submit_date="2025-10-12 10:00:00",
                filename="test.pdf",
                drive_file_id="file123",
                max_retries=5,
                base_delay=0.01,
            )

        assert result is False
        assert mock_sheets_service.append_record.call_count == 5
