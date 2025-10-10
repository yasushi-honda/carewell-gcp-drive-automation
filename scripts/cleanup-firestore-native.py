#!/usr/bin/env python3
"""
Firestore Native データベースのクリーンアップスクリプト
階層的コレクション構造: {class_name}/{task_id}/documents に対応

Usage:
    python3 scripts/cleanup-firestore-native.py "クラス名" "課題ID"
    python3 scripts/cleanup-firestore-native.py "クラス名" "課題ID" --execute
"""
import sys
import argparse
from google.cloud import firestore
from google.auth import default


def main():
    parser = argparse.ArgumentParser(description='Firestore Native データベースのデータをクリア')
    parser.add_argument('class_name', help='クラス名')
    parser.add_argument('task_id', help='課題ID（例: 課題①）')
    parser.add_argument('--execute', action='store_true', help='実際に削除を実行（指定しない場合はドライラン）')
    parser.add_argument('--database', default='carewell-native', help='データベース名（デフォルト: carewell-native）')

    args = parser.parse_args()

    # 色付きログ
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

    print(f"{BLUE}{'=' * 60}{NC}")
    print(f"{BLUE}  Firestore Native データクリア{NC}")
    print(f"{BLUE}{'=' * 60}{NC}")
    print()
    print(f"データベース: {args.database}")
    print(f"クラス: {args.class_name}")
    print(f"課題: {args.task_id}")
    print(f"コレクションパス: {args.class_name}/{args.task_id}/documents")
    print()

    if not args.execute:
        print(f"{YELLOW}⚠️  ドライランモード: 実際には削除しません{NC}")
        print(f"{YELLOW}   実行するには: {' '.join(sys.argv)} --execute{NC}")
        print()

    try:
        # Firestore クライアント初期化
        credentials, project = default()
        db = firestore.Client(project=project, database=args.database, credentials=credentials)

        # コレクション参照取得
        collection_ref = db.collection(args.class_name).document(args.task_id).collection('documents')

        # ドキュメント一覧取得
        print(f"{BLUE}ドキュメント数を確認中...{NC}")
        docs = list(collection_ref.stream())
        doc_count = len(docs)

        if doc_count == 0:
            print(f"{YELLOW}ドキュメントが見つかりませんでした{NC}")
            print("コレクションは空、または存在しません")
            return 0

        print(f"{GREEN}ドキュメント数: {doc_count}件{NC}")
        print()

        # ドキュメント一覧を表示（最初の10件）
        print("削除対象のドキュメント（最初の10件）:")
        for i, doc in enumerate(docs[:10]):
            data = doc.to_dict()
            student_id = data.get('student_id', 'N/A')
            filename = data.get('filename', 'N/A')
            print(f"  - {doc.id}")
            print(f"    学生ID: {student_id}, ファイル名: {filename}")

        if doc_count > 10:
            print(f"  ... 他 {doc_count - 10}件")
        print()

        # 削除実行
        if args.execute:
            print(f"{RED}⚠️  警告: {doc_count}件のドキュメントを削除します{NC}")
            print(f"{RED}   この操作は取り消せません！{NC}")
            print()

            confirm = input("続行しますか? (yes/no): ")
            if confirm != "yes":
                print("キャンセルしました")
                return 0

            print()
            print(f"{YELLOW}削除中...{NC}")

            deleted_count = 0
            for doc in docs:
                try:
                    doc.reference.delete()
                    deleted_count += 1
                    if deleted_count % 10 == 0 or deleted_count == doc_count:
                        print(f"{GREEN}✓{NC} {deleted_count}/{doc_count} 件削除")
                except Exception as e:
                    print(f"{RED}✗{NC} {doc.id} 削除失敗: {e}")

            print()
            print(f"{GREEN}✓ 削除完了: {deleted_count}件{NC}")
            print()

            # 削除後の確認
            print("削除後の確認...")
            remaining_docs = list(collection_ref.stream())
            remaining_count = len(remaining_docs)

            if remaining_count == 0:
                print(f"{GREEN}✓ コレクションは空になりました{NC}")
            else:
                print(f"{YELLOW}⚠️  {remaining_count}件のドキュメントが残っています{NC}")

        else:
            print(f"{YELLOW}[ドライラン] 削除対象: {doc_count}件{NC}")
            print()
            print("実際に削除するには --execute フラグを追加してください:")
            print(f"  python3 {' '.join(sys.argv)} --execute")

    except Exception as e:
        print(f"{RED}エラー: {e}{NC}")
        import traceback
        traceback.print_exc()
        return 1

    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
