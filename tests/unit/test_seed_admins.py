"""
Unit tests for scripts/seed_admins.py (Issue #12).

安全設計（DRY_RUN既定true、fail-closedの管理者判定を裏で支える書き込み経路）を
実際に叩いて検証する。本番Firestoreへの書き込みは行わず、db をMockで差し替える。
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

import seed_admins  # noqa: E402


class TestIsDryRun:
    def test_default_is_dry_run(self, monkeypatch):
        monkeypatch.delenv("DRY_RUN", raising=False)
        assert seed_admins.is_dry_run() is True

    def test_dry_run_false_disables_dry_run(self, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "false")
        assert seed_admins.is_dry_run() is False

    def test_dry_run_false_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "False")
        assert seed_admins.is_dry_run() is False

    def test_dry_run_true_explicit(self, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "true")
        assert seed_admins.is_dry_run() is True

    def test_dry_run_arbitrary_value_defaults_to_dry_run(self, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "yes")
        assert seed_admins.is_dry_run() is True


class TestLoadEmailsFromFile:
    def test_json_array(self, tmp_path):
        f = tmp_path / "admins.json"
        f.write_text(json.dumps(["a@example.com", "b@example.com"]))
        assert seed_admins.load_emails_from_file(str(f)) == [
            "a@example.com",
            "b@example.com",
        ]

    def test_line_based(self, tmp_path):
        f = tmp_path / "admins.txt"
        f.write_text("a@example.com\nb@example.com\n\n")
        assert seed_admins.load_emails_from_file(str(f)) == [
            "a@example.com",
            "b@example.com",
        ]

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.json"
        f.write_text("")
        assert seed_admins.load_emails_from_file(str(f)) == []

    def test_json_non_list_raises(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text(json.dumps({"not": "a list"}))
        with pytest.raises(ValueError):
            seed_admins.load_emails_from_file(str(f))


class TestCmdAdd:
    def test_dry_run_does_not_write(self, capsys):
        mock_db = MagicMock()
        seed_admins.cmd_add(
            mock_db, ["Admin@Example.com"], added_by="tester", dry_run=True
        )
        mock_db.collection.assert_not_called()
        assert "ドライラン" in capsys.readouterr().out

    def test_writes_when_not_dry_run(self):
        mock_db = MagicMock()
        seed_admins.cmd_add(
            mock_db, ["Admin@Example.com"], added_by="tester", dry_run=False
        )
        mock_db.collection.assert_called_with(seed_admins.ADMINS_COLLECTION)
        # メールアドレスはlowercase正規化してドキュメントIDにする
        mock_db.collection.return_value.document.assert_called_with("admin@example.com")
        mock_db.collection.return_value.document.return_value.set.assert_called_once()

    def test_dedupes_and_normalizes_case(self):
        mock_db = MagicMock()
        seed_admins.cmd_add(
            mock_db,
            ["Admin@Example.com", "admin@example.com", "  "],
            added_by="tester",
            dry_run=False,
        )
        # 大小文字違い・重複・空文字は1件に集約される
        assert mock_db.collection.return_value.document.call_count == 1

    def test_empty_email_list_no_op(self):
        mock_db = MagicMock()
        seed_admins.cmd_add(mock_db, [], added_by="tester", dry_run=False)
        mock_db.collection.assert_not_called()


class TestCmdRemove:
    def test_dry_run_does_not_delete(self, capsys):
        mock_db = MagicMock()
        seed_admins.cmd_remove(mock_db, ["admin@example.com"], dry_run=True)
        mock_db.collection.assert_not_called()
        assert "ドライラン" in capsys.readouterr().out

    @patch("builtins.input", return_value="yes")
    def test_deletes_when_confirmed(self, mock_input):
        mock_db = MagicMock()
        seed_admins.cmd_remove(mock_db, ["admin@example.com"], dry_run=False)
        mock_db.collection.return_value.document.return_value.delete.assert_called_once()

    @patch("builtins.input", return_value="no")
    def test_does_not_delete_when_not_confirmed(self, mock_input):
        mock_db = MagicMock()
        seed_admins.cmd_remove(mock_db, ["admin@example.com"], dry_run=False)
        mock_db.collection.return_value.document.return_value.delete.assert_not_called()


class TestCmdList:
    def test_lists_existing_admins(self, capsys):
        mock_db = MagicMock()
        mock_doc = MagicMock()
        mock_doc.id = "admin@example.com"
        mock_doc.to_dict.return_value = {"added_by": "tester", "added_at": "2026-08-27"}
        mock_db.collection.return_value.stream.return_value = [mock_doc]

        seed_admins.cmd_list(mock_db)
        output = capsys.readouterr().out
        assert "admin@example.com" in output
        assert "合計: 1件" in output

    def test_empty_admins(self, capsys):
        mock_db = MagicMock()
        mock_db.collection.return_value.stream.return_value = []
        seed_admins.cmd_list(mock_db)
        assert "0件" in capsys.readouterr().out
