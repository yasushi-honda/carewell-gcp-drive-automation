#!/usr/bin/env python3
"""
Firestore admins コレクションの投入・一覧・削除スクリプト（Issue #12）

`admins/{email}` ドキュメントの存在チェックのみで管理者判定を行う設計
（src/auth.py の is_admin_email、dashboard/firestore.rules の isAdmin() と対）。
ドキュメント自体には added_at/added_by の監査用メタデータのみを持たせ、
値そのものは判定に使わない。

実際の管理者メールアドレスはこのリポジトリにハードコードしない
（PUBLICリポジトリのため）。--email 引数、または .gitignore で除外される
scripts/admins.local.json（1行1メールのJSON配列）から与えること。

Usage:
    # 一覧表示（読み取りのみ、DRY_RUN不要）
    python3 scripts/seed_admins.py --list

    # ドライラン（デフォルト、実際には書き込まない）
    python3 scripts/seed_admins.py --email you@example.com --email member@example.com

    # 本実行
    DRY_RUN=false python3 scripts/seed_admins.py --email you@example.com

    # ローカルJSONファイルから読み込み（scripts/admins.local.json省略時のデフォルト）
    DRY_RUN=false python3 scripts/seed_admins.py --file scripts/admins.local.json

    # 削除
    DRY_RUN=false python3 scripts/seed_admins.py --remove former-member@example.com
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from google.cloud import firestore  # noqa: E402

from firestore_service import FirestoreService  # noqa: E402

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"

ADMINS_COLLECTION = "admins"
DEFAULT_ADMINS_FILE = os.path.join(os.path.dirname(__file__), "admins.local.json")


def is_dry_run() -> bool:
    """scripts/create-scheduler-jobs.sh と同じ DRY_RUN 環境変数パターン。
    未指定時はドライラン（安全側デフォルト）。"""
    return os.environ.get("DRY_RUN", "true").lower() != "false"


def load_emails_from_file(path: str) -> list:
    """1行1メール、またはJSON配列形式のファイルを読む。"""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if not content:
        return []
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return [str(e) for e in data]
        raise ValueError("JSON file must contain a list of email strings")
    except json.JSONDecodeError:
        # JSON形式でなければ1行1メールとして読む
        return [line.strip() for line in content.splitlines() if line.strip()]


def cmd_list(db):
    print(f"{BLUE}=== admins コレクション（database=carewell-native）==={NC}")
    docs = list(db.collection(ADMINS_COLLECTION).stream())
    if not docs:
        print(f"{YELLOW}管理者は0件です{NC}")
        return
    for doc in sorted(docs, key=lambda d: d.id):
        data = doc.to_dict() or {}
        added_by = data.get("added_by", "unknown")
        added_at = data.get("added_at", "unknown")
        print(f"  - {doc.id}  (added_by={added_by}, added_at={added_at})")
    print(f"{GREEN}合計: {len(docs)}件{NC}")


def cmd_add(db, emails, added_by, dry_run):
    normalized = sorted({e.strip().lower() for e in emails if e.strip()})
    if not normalized:
        print(f"{YELLOW}追加対象のメールアドレスがありません{NC}")
        return

    print(f"{BLUE}=== admins 追加対象（{len(normalized)}件）==={NC}")
    for email in normalized:
        print(f"  - {email}")

    if dry_run:
        print()
        print(f"{YELLOW}[ドライラン] 実際には書き込みません{NC}")
        print(f"{YELLOW}実行するには: DRY_RUN=false {' '.join(sys.argv)}{NC}")
        return

    print()
    print(f"{BLUE}書き込み中...{NC}")
    for email in normalized:
        doc_ref = db.collection(ADMINS_COLLECTION).document(email)
        doc_ref.set(
            {
                "added_by": added_by,
                "added_at": firestore.SERVER_TIMESTAMP,
            }
        )
        print(f"  {GREEN}✓{NC} {email}")
    print(f"{GREEN}完了: {len(normalized)}件{NC}")


def cmd_remove(db, emails, dry_run):
    normalized = sorted({e.strip().lower() for e in emails if e.strip()})
    if not normalized:
        print(f"{YELLOW}削除対象のメールアドレスがありません{NC}")
        return

    print(f"{BLUE}=== admins 削除対象（{len(normalized)}件）==={NC}")
    for email in normalized:
        print(f"  - {email}")

    if dry_run:
        print()
        print(f"{YELLOW}[ドライラン] 実際には削除しません{NC}")
        print(f"{YELLOW}実行するには: DRY_RUN=false {' '.join(sys.argv)}{NC}")
        return

    print()
    confirm = input(f"{RED}本当に削除しますか? (yes/no): {NC}")
    if confirm != "yes":
        print("キャンセルしました")
        return

    for email in normalized:
        db.collection(ADMINS_COLLECTION).document(email).delete()
        print(f"  {GREEN}✓{NC} {email} を削除しました")
    print(f"{GREEN}完了: {len(normalized)}件削除{NC}")


def main():
    parser = argparse.ArgumentParser(
        description="Firestore admins コレクションの投入・一覧・削除（Issue #12）"
    )
    parser.add_argument(
        "--email",
        action="append",
        default=[],
        help="追加するメールアドレス（複数指定可）",
    )
    parser.add_argument(
        "--file",
        default=None,
        help=(
            "メールアドレス一覧を読み込むファイル（JSON配列 or 1行1メール）。"
            f"--emailも--removeも未指定の場合、{DEFAULT_ADMINS_FILE} が存在すれば自動的に使う"
        ),
    )
    parser.add_argument(
        "--remove",
        action="append",
        default=[],
        help="削除するメールアドレス（複数指定可）",
    )
    parser.add_argument("--list", action="store_true", help="現在の管理者一覧を表示")
    parser.add_argument(
        "--added-by",
        default=os.environ.get("USER", "unknown"),
        help="監査用: 誰がこの管理者を追加したか（デフォルト: OSユーザー名）",
    )
    args = parser.parse_args()

    dry_run = is_dry_run()
    print(f"{BLUE}{'=' * 60}{NC}")
    print(f"{BLUE}  Firestore admins コレクション管理{NC}")
    print(f"{BLUE}{'=' * 60}{NC}")
    print(f"モード: {(YELLOW + 'ドライラン' if dry_run else GREEN + '実行') + NC}")
    print()

    firestore_service = FirestoreService()  # database="carewell-native" を内部で固定
    db = firestore_service.db

    if args.list:
        cmd_list(db)
        return 0

    if args.remove:
        cmd_remove(db, args.remove, dry_run)
        return 0

    emails = list(args.email)
    if not emails:
        file_path = args.file or (
            DEFAULT_ADMINS_FILE if os.path.exists(DEFAULT_ADMINS_FILE) else None
        )
        if file_path:
            print(f"{BLUE}{file_path} からメールアドレスを読み込みます{NC}")
            emails = load_emails_from_file(file_path)

    if not emails:
        print(
            f"{RED}エラー: --email, --file, --remove, --list のいずれかを指定してください{NC}"
        )
        parser.print_help()
        return 1

    cmd_add(db, emails, args.added_by, dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
