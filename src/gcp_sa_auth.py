"""
サービスアカウント権限借用(impersonation)経由でGoogle APIクライアントを構築するヘルパー。

既存の src/sheets_service.py は google.auth.default() を直接使い、Cloud Run実行時
(SAが実行時アイデンティティとしてアタッチされている環境)専用に作られている。

本モジュールはそれとは別の経路で、ローカル端末上でdecision-maker本人の
gcloudログインセッションを使い、対象SAの権限を借用してトークンを取得する
(ローカル実行専用。gcloudにログイン済みで、かつそのアカウントに対象SAの
roles/iam.serviceAccountTokenCreatorが付与されていることが前提)。

重要な制約(2026-09-11 実機検証で確認):
`--scopes` は権限借用時にgcloud自身が「無視される」と警告を出しており、
実際に狭いスコープ(例: drive.readonlyのみ)を指定したトークンでも
Sheets APIへのアクセスが素通りすることを確認済み。つまり --scopes による
最小権限化は機能しない。実際のアクセス境界は、借用先SAが持つGCP IAM権限と、
対象ファイルのDrive/Sheets共有設定(誰にどの役割で共有されているか)で決まる。
"""

import logging
import subprocess

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class ImpersonationTokenError(RuntimeError):
    """gcloud経由でのSAトークン取得に失敗した"""


def _fetch_impersonated_token(sa_email: str, scopes: list[str]) -> str:
    """gcloud CLI経由で、指定SAを権限借用したアクセストークンを取得する。

    トークンの値そのものはログ・例外メッセージに一切含めない
    (CalledProcessErrorのstderrはgcloudのエラー文言のみで機密を含まない)。
    """
    try:
        result = subprocess.run(
            [
                "gcloud",
                "auth",
                "print-access-token",
                f"--impersonate-service-account={sa_email}",
                f"--scopes={','.join(scopes)}",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
    except subprocess.CalledProcessError as e:
        raise ImpersonationTokenError(
            f"gcloudによるSAトークン取得に失敗しました(SA={sa_email}): {e.stderr.strip()}"
        ) from e
    except subprocess.TimeoutExpired as e:
        raise ImpersonationTokenError(
            f"gcloudによるSAトークン取得がタイムアウトしました(SA={sa_email})"
        ) from e

    token = result.stdout.strip()
    if not token:
        raise ImpersonationTokenError(
            f"gcloudがトークンを返しませんでした(SA={sa_email})"
        )
    return token


def get_impersonated_service(
    api: str, version: str, sa_email: str, scopes: list[str]
) -> Resource:
    """gcloud CLI経由でSAトークンを取得し、Google APIクライアントを構築する。

    ローカル実行専用(gcloudにログイン済みのtoken creator権限が前提)。
    """
    token = _fetch_impersonated_token(sa_email, scopes)
    credentials = Credentials(token=token)
    return build(api, version, credentials=credentials, cache_discovery=False)


def call_with_reauth(build_service_fn, request_fn):
    """Sheets/Drive API呼び出しをラップし、401時のみ1回だけトークンを再取得して再試行する。

    Args:
        build_service_fn: 引数なしでGoogle APIのServiceオブジェクトを返す callable
            (呼び出すたびに新しいトークンでserviceを作り直せるようにするため)
        request_fn: Serviceオブジェクトを受け取り、APIリクエストの.execute()結果を返す callable

    それ以外の失敗(タイムアウト等)は盲目的に再試行せず、そのまま例外を送出する。
    呼び出し元が対象範囲を再読込して実際の結果を確認すること。
    """
    service = build_service_fn()
    try:
        return request_fn(service)
    except HttpError as e:
        if e.resp.status != 401:
            raise
        logger.warning("401を受信。トークンを再取得して1回だけ再試行します。")
        service = build_service_fn()
        return request_fn(service)
