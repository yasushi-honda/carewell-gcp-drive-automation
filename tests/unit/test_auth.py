"""
Unit tests for the application-layer auth gate in src/auth.py (Issue #12).

Cloud Run自体は--allow-unauthenticatedのまま運用するため、これらのテストが
「認証なし/不正な資格情報では既存ハンドラに到達しない」ことを担保する唯一の
機械的な検証になる。
"""

import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, "src")

import auth  # noqa: E402


def _fake_request(bearer_token=None):
    """Authorization ヘッダのみを持つ最小のリクエストスタブ。"""
    request = Mock()
    headers = {}
    if bearer_token is not None:
        headers["Authorization"] = f"Bearer {bearer_token}"
    request.headers = headers
    return request


class TestExtractBearerToken:
    """_extract_bearer_token の境界値テスト"""

    def test_no_header(self):
        request = Mock()
        request.headers = {}
        assert auth._extract_bearer_token(request) is None

    def test_valid_bearer(self):
        request = Mock()
        request.headers = {"Authorization": "Bearer abc123"}
        assert auth._extract_bearer_token(request) == "abc123"

    def test_lowercase_scheme(self):
        request = Mock()
        request.headers = {"Authorization": "bearer abc123"}
        assert auth._extract_bearer_token(request) == "abc123"

    def test_non_bearer_scheme(self):
        request = Mock()
        request.headers = {"Authorization": "Basic abc123"}
        assert auth._extract_bearer_token(request) is None

    def test_bearer_without_token(self):
        request = Mock()
        request.headers = {"Authorization": "Bearer"}
        assert auth._extract_bearer_token(request) is None

    def test_empty_header(self):
        request = Mock()
        request.headers = {"Authorization": ""}
        assert auth._extract_bearer_token(request) is None

    def test_bearer_with_whitespace_only_token(self):
        request = Mock()
        request.headers = {"Authorization": "Bearer   "}
        assert auth._extract_bearer_token(request) is None


class TestVerifySchedulerOidcToken:
    """verify_scheduler_oidc_token: Google OIDC トークンの検証"""

    def _valid_claims(self, **overrides):
        claims = {
            "iss": "https://accounts.google.com",
            "aud": auth.CLOUD_RUN_BASE_URL,
            "email": auth.SCHEDULER_SERVICE_ACCOUNT,
            "email_verified": True,
        }
        claims.update(overrides)
        return claims

    @patch("auth.ga_id_token.verify_oauth2_token")
    def test_valid_token(self, mock_verify):
        mock_verify.return_value = self._valid_claims()
        claims = auth.verify_scheduler_oidc_token("valid-token")
        assert claims["email"] == auth.SCHEDULER_SERVICE_ACCOUNT

    @patch("auth.ga_id_token.verify_oauth2_token")
    def test_invalid_token_raises_401(self, mock_verify):
        mock_verify.side_effect = ValueError("Token expired")
        with pytest.raises(auth.AuthError) as exc_info:
            auth.verify_scheduler_oidc_token("garbage")
        assert exc_info.value.status_code == 401

    @patch("auth.ga_id_token.verify_oauth2_token")
    def test_google_auth_error_raises_401(self, mock_verify):
        """verify_oauth2_tokenはissuerがGoogle既知issuer以外だとValueErrorではなく
        GoogleAuthErrorを送出する（ライブラリ内部実装）。これも401として処理すること。"""
        from google.auth import exceptions as ga_exceptions

        mock_verify.side_effect = ga_exceptions.GoogleAuthError("Wrong issuer")
        with pytest.raises(auth.AuthError) as exc_info:
            auth.verify_scheduler_oidc_token("token-with-bad-issuer")
        assert exc_info.value.status_code == 401

    @patch("auth.ga_id_token.verify_oauth2_token")
    def test_wrong_issuer_raises_403(self, mock_verify):
        mock_verify.return_value = self._valid_claims(iss="https://evil.example.com")
        with pytest.raises(auth.AuthError) as exc_info:
            auth.verify_scheduler_oidc_token("token")
        assert exc_info.value.status_code == 403

    @patch("auth.ga_id_token.verify_oauth2_token")
    def test_wrong_audience_raises_403(self, mock_verify):
        mock_verify.return_value = self._valid_claims(aud="https://other-service/")
        with pytest.raises(auth.AuthError) as exc_info:
            auth.verify_scheduler_oidc_token("token")
        assert exc_info.value.status_code == 403

    @patch("auth.ga_id_token.verify_oauth2_token")
    def test_email_not_verified_raises_403(self, mock_verify):
        mock_verify.return_value = self._valid_claims(email_verified=False)
        with pytest.raises(auth.AuthError) as exc_info:
            auth.verify_scheduler_oidc_token("token")
        assert exc_info.value.status_code == 403

    @patch("auth.ga_id_token.verify_oauth2_token")
    def test_wrong_service_account_raises_403(self, mock_verify):
        mock_verify.return_value = self._valid_claims(email="attacker@example.com")
        with pytest.raises(auth.AuthError) as exc_info:
            auth.verify_scheduler_oidc_token("token")
        assert exc_info.value.status_code == 403

    @patch("auth.ga_id_token.verify_oauth2_token")
    def test_path_suffixed_audience_accepted(self, mock_verify):
        """student-sync-daily は uri にパス付きなので aud もパス付きになりうる"""
        mock_verify.return_value = self._valid_claims(
            aud=f"{auth.CLOUD_RUN_BASE_URL}/admin/sync-students-from-sheets"
        )
        claims = auth.verify_scheduler_oidc_token("token")
        assert claims["email"] == auth.SCHEDULER_SERVICE_ACCOUNT


class TestVerifyFirebaseAdminToken:
    """verify_firebase_admin_token: Firebase ID トークンの検証 + 管理者判定"""

    def _valid_claims(self, **overrides):
        claims = {"email": "admin@example.com", "email_verified": True}
        claims.update(overrides)
        return claims

    @patch("auth.is_admin_email")
    @patch("auth.fb_auth.verify_id_token")
    @patch("auth._get_firebase_app")
    def test_valid_admin_token(self, mock_app, mock_verify, mock_is_admin):
        mock_verify.return_value = self._valid_claims()
        mock_is_admin.return_value = True
        claims = auth.verify_firebase_admin_token("valid-token")
        assert claims["email"] == "admin@example.com"

    @patch("auth.is_admin_email")
    @patch("auth.fb_auth.verify_id_token")
    @patch("auth._get_firebase_app")
    def test_non_admin_raises_403(self, mock_app, mock_verify, mock_is_admin):
        mock_verify.return_value = self._valid_claims(email="nobody@example.com")
        mock_is_admin.return_value = False
        with pytest.raises(auth.AuthError) as exc_info:
            auth.verify_firebase_admin_token("valid-token")
        assert exc_info.value.status_code == 403

    @patch("auth.fb_auth.verify_id_token")
    @patch("auth._get_firebase_app")
    def test_invalid_token_raises_401(self, mock_app, mock_verify):
        mock_verify.side_effect = auth.fb_auth.InvalidIdTokenError("bad token")
        with pytest.raises(auth.AuthError) as exc_info:
            auth.verify_firebase_admin_token("garbage")
        assert exc_info.value.status_code == 401

    @patch("auth.fb_auth.verify_id_token")
    @patch("auth._get_firebase_app")
    def test_expired_token_raises_401(self, mock_app, mock_verify):
        mock_verify.side_effect = auth.fb_auth.ExpiredIdTokenError(
            "expired", cause=None
        )
        with pytest.raises(auth.AuthError) as exc_info:
            auth.verify_firebase_admin_token("expired-token")
        assert exc_info.value.status_code == 401

    @patch("auth.fb_auth.verify_id_token")
    @patch("auth._get_firebase_app")
    def test_email_not_verified_raises_403(self, mock_app, mock_verify):
        mock_verify.return_value = self._valid_claims(email_verified=False)
        with pytest.raises(auth.AuthError) as exc_info:
            auth.verify_firebase_admin_token("token")
        assert exc_info.value.status_code == 403

    @patch("auth.fb_auth.verify_id_token")
    @patch("auth._get_firebase_app")
    def test_missing_email_claim_raises_403(self, mock_app, mock_verify):
        mock_verify.return_value = {"email_verified": True}
        with pytest.raises(auth.AuthError) as exc_info:
            auth.verify_firebase_admin_token("token")
        assert exc_info.value.status_code == 403


class TestIsAdminEmail:
    """is_admin_email: fail-closed の検証を含む"""

    @patch("auth.FirestoreService")
    def test_admin_exists(self, mock_service_cls):
        mock_doc = MagicMock()
        mock_doc.get.return_value.exists = True
        mock_service_cls.return_value.db.collection.return_value.document.return_value = (
            mock_doc
        )
        assert auth.is_admin_email("Admin@Example.com") is True
        # ドキュメントIDはlowercase正規化されていること
        mock_service_cls.return_value.db.collection.return_value.document.assert_called_with(
            "admin@example.com"
        )

    @patch("auth.FirestoreService")
    def test_admin_not_exists(self, mock_service_cls):
        mock_doc = MagicMock()
        mock_doc.get.return_value.exists = False
        mock_service_cls.return_value.db.collection.return_value.document.return_value = (
            mock_doc
        )
        assert auth.is_admin_email("nobody@example.com") is False

    @patch("auth.FirestoreService")
    def test_firestore_exception_fails_closed(self, mock_service_cls):
        mock_service_cls.side_effect = Exception("Firestore unavailable")
        assert auth.is_admin_email("admin@example.com") is False


class TestAuthorize:
    """authorize(): ROUTE_POLICY 参照 + スキーム試行の統合テスト"""

    def test_unknown_path_raises_route_not_found(self):
        request = _fake_request()
        with pytest.raises(auth.RouteNotFound):
            auth.authorize(request, "GET", "/does-not-exist")

    def test_method_mismatch_raises_route_not_found(self):
        """/cleanup は POST のみ登録。GET は未登録パス扱い"""
        request = _fake_request()
        with pytest.raises(auth.RouteNotFound):
            auth.authorize(request, "GET", "/cleanup")

    def test_public_route_no_token_required(self):
        request = _fake_request()
        result = auth.authorize(request, "GET", "/health")
        assert result["scheme"] == "public"

    def test_no_bearer_token_raises_401(self):
        request = _fake_request()
        with pytest.raises(auth.AuthError) as exc_info:
            auth.authorize(request, "GET", "/admin/duplicate-students")
        assert exc_info.value.status_code == 401

    @patch("auth.verify_scheduler_oidc_token")
    def test_scheduler_scheme_success(self, mock_verify):
        mock_verify.return_value = {"email": auth.SCHEDULER_SERVICE_ACCOUNT}
        request = _fake_request(bearer_token="valid")
        result = auth.authorize(request, "POST", "/")
        assert result["scheme"] == auth.SCHEME_SCHEDULER

    @patch("auth.verify_firebase_admin_token")
    def test_firebase_admin_scheme_success(self, mock_verify):
        mock_verify.return_value = {"email": "admin@example.com"}
        request = _fake_request(bearer_token="valid")
        result = auth.authorize(request, "GET", "/admin/duplicate-students")
        assert result["scheme"] == auth.SCHEME_FIREBASE_ADMIN

    @patch("auth.verify_firebase_admin_token")
    @patch("auth.verify_scheduler_oidc_token")
    def test_post_root_only_tries_scheduler_scheme(self, mock_scheduler, mock_firebase):
        """POST / はSchedulerスキームのみポリシーに登録されている。
        Firebase管理者スキームの検証関数は一切呼ばれないことを確認する。"""
        mock_scheduler.side_effect = auth.AuthError(
            403, "権限がありません", "not scheduler"
        )
        request = _fake_request(bearer_token="valid")
        with pytest.raises(auth.AuthError):
            auth.authorize(request, "POST", "/")
        mock_firebase.assert_not_called()

    @patch("auth.verify_firebase_admin_token")
    @patch("auth.verify_scheduler_oidc_token")
    def test_cleanup_only_tries_firebase_admin_scheme(
        self, mock_scheduler, mock_firebase
    ):
        """POST /cleanup はFirebase管理者スキームのみポリシーに登録されている。
        Schedulerスキームの検証関数は一切呼ばれないことを確認する。"""
        mock_firebase.return_value = {"email": "admin@example.com"}
        request = _fake_request(bearer_token="valid")
        result = auth.authorize(request, "POST", "/cleanup")
        assert result["scheme"] == auth.SCHEME_FIREBASE_ADMIN
        mock_scheduler.assert_not_called()

    @patch("auth.verify_firebase_admin_token")
    @patch("auth.verify_scheduler_oidc_token")
    def test_sync_students_tries_both_schemes(self, mock_scheduler, mock_firebase):
        """Scheduler検証が失敗してもFirebase検証にフォールバックする"""
        mock_scheduler.side_effect = auth.AuthError(
            403, "権限がありません", "not scheduler"
        )
        mock_firebase.return_value = {"email": "admin@example.com"}
        request = _fake_request(bearer_token="valid")
        result = auth.authorize(request, "POST", "/admin/sync-students-from-sheets")
        assert result["scheme"] == auth.SCHEME_FIREBASE_ADMIN

    @patch("auth.verify_firebase_admin_token")
    @patch("auth.verify_scheduler_oidc_token")
    def test_sync_students_both_schemes_fail(self, mock_scheduler, mock_firebase):
        mock_scheduler.side_effect = auth.AuthError(
            403, "権限がありません", "not scheduler"
        )
        mock_firebase.side_effect = auth.AuthError(
            403, "管理者権限がありません", "not admin"
        )
        request = _fake_request(bearer_token="valid")
        with pytest.raises(auth.AuthError) as exc_info:
            auth.authorize(request, "POST", "/admin/sync-students-from-sheets")
        assert exc_info.value.status_code == 403
