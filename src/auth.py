"""
Cloud Run エンドポイントのアプリ層認証ゲート（Issue #12）

Cloud Run 自体は --allow-unauthenticated のまま運用する。
理由: Firebase の ID トークンは Cloud Run の IAM invoker では受け付けられず、
--allow-unauthenticated を外すと Dashboard(ブラウザ)から一切呼べなくなるため。
認証はこのモジュールで一元的に行う（default-deny）。

呼び出し元は2系統あり、別々のライブラリで別々の issuer を検証する:
- Cloud Scheduler: google.oauth2.id_token で Google 署名の OIDC トークンを検証
- Dashboard: firebase_admin.auth で Firebase ID トークンを検証し、admins コレクションと照合

注意: SCHEDULER_SERVICE_ACCOUNT は「呼び出し元」の識別子であり、Cloud Run の実行SA
（github-actions-sa、deploy.yml参照）とは別物。混同しないこと。
"""

import logging
import os

import firebase_admin
from firebase_admin import auth as fb_auth
from google.auth import exceptions as ga_exceptions
from google.auth.transport import requests as ga_requests
from google.oauth2 import id_token as ga_id_token

from firestore_service import FirestoreService

logger = logging.getLogger(__name__)

# --- 設定 ---
# 環境変数にしない: `gcloud run deploy --set-env-vars` は既存値を丸ごと置換し
# 次回デプロイで消える（src/config/classes.py の resolve_student_spreadsheet_id
# docstring に記録された既知インシデントと同じ罠）。恒久的な値はコードに書く。
CLOUD_RUN_BASE_URL = "https://carewell-file-collector-imczapxkba-an.a.run.app"
SCHEDULER_SERVICE_ACCOUNT = (
    "carewell-automation-sa@carewell-automation.iam.gserviceaccount.com"
)
GOOGLE_ISSUERS = frozenset({"https://accounts.google.com", "accounts.google.com"})
# Cloud Scheduler は --oidc-token-audience 未指定時、ジョブの uri をそのまま aud にする。
# carewell-classXX-taskYY は uri=ベースURL、student-sync-daily は uri=ベースURL+パス。
ALLOWED_OIDC_AUDIENCES = frozenset(
    {
        CLOUD_RUN_BASE_URL,
        f"{CLOUD_RUN_BASE_URL}/",
        f"{CLOUD_RUN_BASE_URL}/admin/sync-students-from-sheets",
    }
)
ADMINS_COLLECTION = "admins"

# 認証スキーム識別子
SCHEME_SCHEDULER = "scheduler_oidc"
SCHEME_FIREBASE_ADMIN = "firebase_admin"

# --- ルートポリシー（単一の真実の源・default-deny） ---
# キー: (HTTPメソッド, パス)。値: 許可する認証スキームのタプル。空タプル = 認証不要。
# ここに登録されていない (method, path) は authorize() が RouteNotFound を送出し、
# app() 側で 404 になる。新エンドポイント追加時にここへの登録を忘れると自動的に
# 404（default-deny）になる設計。
ROUTE_POLICY = {
    ("POST", "/"): (SCHEME_SCHEDULER,),
    ("POST", "/cleanup"): (SCHEME_FIREBASE_ADMIN,),
    ("POST", "/admin/sync-students-from-sheets"): (
        SCHEME_SCHEDULER,
        SCHEME_FIREBASE_ADMIN,
    ),
    ("GET", "/admin/duplicate-students"): (SCHEME_FIREBASE_ADMIN,),
    ("GET", "/health"): (),
}


class RouteNotFound(Exception):
    """ROUTE_POLICY に存在しない (method, path)。app() 側で 404 として扱う。"""


class AuthError(Exception):
    """認証・認可の失敗。

    status_code は 401（資格情報が無い/検証不能）か 403（資格情報は正当だが権限なし）。
    public_message はクライアントに返してよい一般的な文言のみ（内部詳細を含めない）。
    log_reason は Cloud Logging にのみ残す診断用の詳細。
    """

    def __init__(self, status_code: int, public_message: str, log_reason: str):
        super().__init__(log_reason)
        self.status_code = status_code
        self.public_message = public_message
        self.log_reason = log_reason


def _extract_bearer_token(request) -> "str | None":
    """Authorization ヘッダから Bearer トークンを取り出す。スキーム名は大小無視。"""
    header = request.headers.get("Authorization", "")
    if not header:
        return None
    parts = header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


_firebase_app = None


def _get_firebase_app():
    """firebase_admin App の遅延シングルトン。

    projectId は deploy.yml が既に渡している GCP_PROJECT 環境変数から取る
    （src/playwright_automation.py の既存パターンに合わせる、新規env var不要）。
    """
    global _firebase_app
    if _firebase_app is None:
        project_id = os.getenv("GCP_PROJECT", "carewell-automation")
        _firebase_app = firebase_admin.initialize_app(options={"projectId": project_id})
    return _firebase_app


def is_admin_email(email: str) -> bool:
    """admins/{email.lower()} の存在で管理者判定する。

    Firestore の carewell-native データベースを FirestoreService 経由で参照する
    （DB名を2箇所目にハードコードしない）。

    例外時（Firestore一時障害等）は必ず False を返す（fail-closed）。
    誤って fail-open にすると、Firestore障害中に誰でも管理者として通ってしまう。
    """
    normalized_email = email.lower()
    try:
        firestore_service = FirestoreService()
        doc_ref = firestore_service.db.collection(ADMINS_COLLECTION).document(
            normalized_email
        )
        return doc_ref.get().exists
    except Exception as e:  # noqa: BLE001 - fail-closedのため意図的に広く捕捉
        logger.warning(
            "is_admin_email: Firestore参照に失敗したためFalseを返す email=%s error=%s",
            normalized_email,
            e,
        )
        return False


def verify_scheduler_oidc_token(token: str) -> dict:
    """Google 署名の OIDC ID トークン（Cloud Scheduler発行）を検証する。

    Returns:
        検証済みclaims dict

    Raises:
        AuthError: 検証失敗（401: トークン自体が不正/期限切れ、403: issuer/aud/emailが不一致）
    """
    try:
        claims = ga_id_token.verify_oauth2_token(
            token, ga_requests.Request(), audience=None
        )
    except ValueError as e:
        raise AuthError(
            401, "認証に失敗しました", f"scheduler oidc token invalid: {e}"
        ) from e
    except ga_exceptions.GoogleAuthError as e:
        # verify_oauth2_token は issuer が Google 既知issuer以外の場合、
        # ValueErrorではなくGoogleAuthErrorを送出する（ライブラリ内部実装）。
        # ここを捕捉しないと未処理例外で500になってしまう。
        raise AuthError(
            401, "認証に失敗しました", f"scheduler oidc token auth error: {e}"
        ) from e

    issuer = claims.get("iss")
    if issuer not in GOOGLE_ISSUERS:
        raise AuthError(
            403, "権限がありません", f"scheduler oidc unexpected issuer={issuer}"
        )

    audience = claims.get("aud")
    if audience not in ALLOWED_OIDC_AUDIENCES:
        logger.warning(
            "scheduler oidc audience不一致 実際のaud=%s allowed=%s",
            audience,
            sorted(ALLOWED_OIDC_AUDIENCES),
        )
        raise AuthError(
            403, "権限がありません", f"scheduler oidc unexpected audience={audience}"
        )

    if not claims.get("email_verified"):
        raise AuthError(403, "権限がありません", "scheduler oidc email not verified")

    email = claims.get("email")
    if email != SCHEDULER_SERVICE_ACCOUNT:
        raise AuthError(
            403, "権限がありません", f"scheduler oidc unexpected email={email}"
        )

    return claims


def verify_firebase_admin_token(token: str) -> dict:
    """Firebase ID トークン（Dashboardのログインユーザー発行）を検証し、管理者許可リストと照合する。

    Returns:
        検証済みclaims dict

    Raises:
        AuthError: 検証失敗（401: トークン自体が不正/期限切れ、403: 管理者ではない）
    """
    try:
        claims = fb_auth.verify_id_token(
            token, app=_get_firebase_app(), check_revoked=False
        )
    except fb_auth.InvalidIdTokenError as e:
        raise AuthError(
            401, "認証に失敗しました", f"firebase id token invalid: {e}"
        ) from e
    except fb_auth.ExpiredIdTokenError as e:
        raise AuthError(
            401,
            "セッションが切れました。再ログインしてください",
            f"firebase id token expired: {e}",
        ) from e
    except Exception as e:  # noqa: BLE001 - Firebase側の一時的な検証失敗も401扱いにする
        raise AuthError(
            401, "認証に失敗しました", f"firebase id token verification error: {e}"
        ) from e

    if not claims.get("email_verified"):
        raise AuthError(
            403, "管理者権限がありません", "firebase token email not verified"
        )

    email = claims.get("email")
    if not email or not is_admin_email(email):
        raise AuthError(
            403, "管理者権限がありません", f"firebase token email not admin: {email}"
        )

    return claims


# 関数名（文字列）で保持し、authorize() 呼び出しのたびに globals() から解決する。
# 関数オブジェクトを直接束縛すると、テストで unittest.mock.patch("auth.verify_...")
# しても authorize() 経由の呼び出しには反映されない（モジュール読み込み時点の
# 参照を保持し続けるため）。文字列解決にすることでその問題を避ける。
_VERIFIER_NAMES = {
    SCHEME_SCHEDULER: "verify_scheduler_oidc_token",
    SCHEME_FIREBASE_ADMIN: "verify_firebase_admin_token",
}


def authorize(request, method: str, path: str) -> dict:
    """認証ゲート本体。

    Returns:
        {"scheme": ..., "principal": <email>} 認証成功時

    Raises:
        RouteNotFound: ROUTE_POLICY に (method, path) が存在しない
        AuthError: 認証・認可に失敗
    """
    policy_key = (method, path)
    if policy_key not in ROUTE_POLICY:
        raise RouteNotFound(f"{method} {path}")

    allowed_schemes = ROUTE_POLICY[policy_key]
    if not allowed_schemes:
        return {"scheme": "public", "principal": None}

    token = _extract_bearer_token(request)
    if token is None:
        raise AuthError(401, "認証が必要です", f"no bearer token for {method} {path}")

    last_error: "AuthError | None" = None
    for scheme in allowed_schemes:
        verifier = globals()[_VERIFIER_NAMES[scheme]]
        try:
            claims = verifier(token)
        except AuthError as e:
            # 情報量の多い失敗（403: 資格情報は解析できたが権限なし）を優先して残す。
            # 401（トークン自体を解析できない）より403の方が診断上有用なため。
            if last_error is None or e.status_code == 403:
                last_error = e
            continue
        principal = claims.get("email")
        logger.info(
            "auth_ok scheme=%s principal=%s method=%s path=%s",
            scheme,
            principal,
            method,
            path,
        )
        return {"scheme": scheme, "principal": principal}

    assert last_error is not None  # allowed_schemesが非空なら必ず1回はループするため
    logger.warning(
        "auth_denied status=%s reason=%s method=%s path=%s",
        last_error.status_code,
        last_error.log_reason,
        method,
        path,
    )
    raise last_error
