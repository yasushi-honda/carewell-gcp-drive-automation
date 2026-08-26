"""
Unit tests for app(request) routing + auth gate integration (Issue #12).

Flaskを使わず、path/method/headers/get_jsonを持つ最小のFakeRequestでapp()を直接叩き、
既存ハンドラ（main.main等）をunittest.mock.patchで差し替える。

最重要の検証観点: 認証なし・不正な資格情報のリクエストで、既存ハンドラが
一切呼び出されないこと（副作用ゼロで拒否されること）。
"""

import sys
from unittest.mock import patch

# Add src to path for imports
sys.path.insert(0, "src")

import auth  # noqa: E402
import main  # noqa: E402


class FakeRequest:
    """Flask Request の最小互換スタブ"""

    def __init__(self, method, path, bearer_token=None, json_body=None):
        self.method = method
        self.path = path
        self.headers = {}
        if bearer_token is not None:
            self.headers["Authorization"] = f"Bearer {bearer_token}"
        self._json_body = json_body

    def get_json(self, silent=False):
        return self._json_body


class TestAppRoutingWithoutAuth:
    """認証なし・不正資格情報のリクエストが既存ハンドラに到達しないことを検証"""

    @patch("main.sync_students_from_sheets")
    def test_sync_students_no_token_returns_401_and_handler_not_called(
        self, mock_handler
    ):
        request = FakeRequest("POST", "/admin/sync-students-from-sheets")
        body, status, headers = main.app(request)
        assert status == 401
        mock_handler.assert_not_called()

    @patch("main.sync_students_from_sheets")
    def test_sync_students_garbage_token_returns_401(self, mock_handler):
        request = FakeRequest(
            "POST", "/admin/sync-students-from-sheets", bearer_token="garbage"
        )
        body, status, headers = main.app(request)
        assert status in (401, 403)
        mock_handler.assert_not_called()

    @patch("auth.is_admin_email", return_value=False)
    @patch("auth.fb_auth.verify_id_token")
    @patch("main.sync_students_from_sheets")
    def test_sync_students_non_admin_firebase_token_returns_403(
        self, mock_handler, mock_verify, mock_is_admin
    ):
        mock_verify.return_value = {
            "email": "nobody@example.com",
            "email_verified": True,
        }
        request = FakeRequest(
            "POST", "/admin/sync-students-from-sheets", bearer_token="firebase-token"
        )
        body, status, headers = main.app(request)
        assert status == 403
        mock_handler.assert_not_called()

    @patch("auth.is_admin_email", return_value=True)
    @patch("auth.fb_auth.verify_id_token")
    @patch("main.sync_students_from_sheets")
    def test_sync_students_admin_firebase_token_reaches_handler(
        self, mock_handler, mock_verify, mock_is_admin
    ):
        mock_handler.return_value = {"status": "success"}, 200
        mock_verify.return_value = {
            "email": "admin@example.com",
            "email_verified": True,
        }
        request = FakeRequest(
            "POST", "/admin/sync-students-from-sheets", bearer_token="firebase-token"
        )
        body, status, headers = main.app(request)
        assert status == 200
        mock_handler.assert_called_once()

    @patch("auth.ga_id_token.verify_oauth2_token")
    @patch("main.sync_students_from_sheets")
    def test_sync_students_scheduler_token_reaches_handler(
        self, mock_handler, mock_verify
    ):
        mock_handler.return_value = {"status": "success"}, 200
        mock_verify.return_value = {
            "iss": "https://accounts.google.com",
            "aud": auth.CLOUD_RUN_BASE_URL,
            "email": auth.SCHEDULER_SERVICE_ACCOUNT,
            "email_verified": True,
        }
        request = FakeRequest(
            "POST", "/admin/sync-students-from-sheets", bearer_token="oidc-token"
        )
        body, status, headers = main.app(request)
        assert status == 200
        mock_handler.assert_called_once()

    @patch("main.cleanup_firestore")
    def test_cleanup_no_token_returns_401_and_handler_not_called(self, mock_handler):
        """破壊的操作(/cleanup)の回帰テスト: 認証なしでは絶対にハンドラへ到達しない"""
        request = FakeRequest("POST", "/cleanup")
        body, status, headers = main.app(request)
        assert status == 401
        mock_handler.assert_not_called()

    @patch("auth.ga_id_token.verify_oauth2_token")
    @patch("main.cleanup_firestore")
    def test_cleanup_scheduler_token_rejected(self, mock_handler, mock_verify):
        """/cleanup はFirebase管理者専用。SchedulerのOIDCトークンでは通らない"""
        mock_verify.return_value = {
            "iss": "https://accounts.google.com",
            "aud": auth.CLOUD_RUN_BASE_URL,
            "email": auth.SCHEDULER_SERVICE_ACCOUNT,
            "email_verified": True,
        }
        request = FakeRequest("POST", "/cleanup", bearer_token="oidc-token")
        body, status, headers = main.app(request)
        assert status == 401
        mock_handler.assert_not_called()

    @patch("auth.is_admin_email", return_value=True)
    @patch("auth.fb_auth.verify_id_token")
    @patch("main.cleanup_firestore")
    def test_cleanup_admin_firebase_token_reaches_handler(
        self, mock_handler, mock_verify, mock_is_admin
    ):
        mock_handler.return_value = {"status": "success"}, 200
        mock_verify.return_value = {
            "email": "admin@example.com",
            "email_verified": True,
        }
        request = FakeRequest("POST", "/cleanup", bearer_token="firebase-token")
        body, status, headers = main.app(request)
        assert status == 200
        mock_handler.assert_called_once()

    @patch("main.get_duplicate_students")
    def test_duplicate_students_no_token_returns_401(self, mock_handler):
        request = FakeRequest("GET", "/admin/duplicate-students")
        body, status, headers = main.app(request)
        assert status == 401
        mock_handler.assert_not_called()

    @patch("main.main")
    def test_root_no_token_returns_401_and_handler_not_called(self, mock_handler):
        request = FakeRequest("POST", "/")
        body, status, headers = main.app(request)
        assert status == 401
        mock_handler.assert_not_called()

    @patch("auth.is_admin_email", return_value=True)
    @patch("auth.fb_auth.verify_id_token")
    @patch("main.main")
    def test_root_firebase_admin_token_rejected(
        self, mock_handler, mock_verify, mock_is_admin
    ):
        """POST / はScheduler専用。Firebase管理者トークンでも拒否される
        （Dashboardからファイル収集を起動させないための設計）"""
        mock_verify.return_value = {
            "email": "admin@example.com",
            "email_verified": True,
        }
        request = FakeRequest("POST", "/", bearer_token="firebase-token")
        body, status, headers = main.app(request)
        assert status == 401
        mock_handler.assert_not_called()


class TestAppRoutingPublicAndUnknown:
    """認証不要ルート・未知パス・CORS preflightの挙動"""

    @patch("main.health_check")
    def test_health_check_no_token_ok(self, mock_handler):
        mock_handler.return_value = {"status": "healthy"}, 200
        request = FakeRequest("GET", "/health")
        body, status, headers = main.app(request)
        assert status == 200
        mock_handler.assert_called_once()

    def test_options_preflight_returns_204_without_touching_handlers(self):
        request = FakeRequest("OPTIONS", "/admin/sync-students-from-sheets")
        body, status, headers = main.app(request)
        assert status == 204

    def test_unknown_path_returns_404_without_endpoint_list(self):
        request = FakeRequest("GET", "/does-not-exist")
        body, status, headers = main.app(request)
        assert status == 404
        # 旧実装は available_endpoints を列挙していたが、情報漏洩のため削除した
        assert "available_endpoints" not in body

    def test_method_mismatch_returns_404(self):
        """/cleanup は POST のみ。GET は未登録パス扱いで404"""
        request = FakeRequest("GET", "/cleanup")
        body, status, headers = main.app(request)
        assert status == 404

    def test_all_error_responses_include_cors_headers(self):
        """認証エラー応答にもCORSヘッダーが付与されること
        （無いとDashboardには単なるネットワークエラーにしか見えない）"""
        request = FakeRequest("POST", "/admin/sync-students-from-sheets")
        body, status, headers = main.app(request)
        assert status == 401
        assert "Access-Control-Allow-Origin" in headers

    def test_error_response_body_has_no_internal_details(self):
        """認証エラーのレスポンスボディに内部詳細（トークン・claims等）を含めない"""
        request = FakeRequest(
            "POST", "/admin/sync-students-from-sheets", bearer_token="garbage-token-xyz"
        )
        body, status, headers = main.app(request)
        assert "garbage-token-xyz" not in str(body)
