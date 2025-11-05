# 🚨 必須：インシデント対応チェックリスト

## このメモリファイルを読む条件

以下のいずれかが発生した場合、**必ず最初に**このファイルを読む：
- タイムアウトエラー
- DEADLINE_EXCEEDED
- ページネーション問題
- Firestoreデータ不整合
- Cloud Scheduler実行失敗
- その他の本番環境エラー

## 必須手順（順番厳守）

### ステップ1: ドキュメント確認（最優先）

```bash
# 1. CLAUDE.md の Incident Response Workflow を確認
Read: /Users/yyyhhh/carewell-gcp-drive-automation/CLAUDE.md

# 2. 問題関連ドキュメントを確認
# タイムアウト/ページネーション問題の場合：
Read: /Users/yyyhhh/carewell-gcp-drive-automation/docs/CLASS01_TIMEOUT_ANALYSIS.md

# 3. 過去のインシデント教訓を確認
Read memory: incident_response_lessons
```

### ステップ2: 過去の類似問題を検索

```bash
# 関連するコミットを検索
git log --grep="timeout" --grep="pagination" --grep="DEADLINE" --oneline -20

# 問題のキーワードでコード検索
grep -r "wait_for_selector" src/
grep -r "time.sleep" src/
```

### ステップ3: 分析開始

**⚠️ ステップ1-2を完了してから、初めて分析を開始する**

## 絶対にやってはいけないこと

❌ ドキュメントを読む前にコードを書き始める
❌ 「たぶんこうだろう」という仮定で進める
❌ ユーザーから指摘されて初めてドキュメントを読む
❌ 過去の解決策を無視して新しいアプローチを試す

## 今回の失敗から学んだこと（2025-11-04）

**問題**: 17:30実行でページ2タイムアウトエラー発生

**失敗した対応**:
1. ドキュメント確認をスキップ
2. 独自分析を開始
3. ユーザーの指摘で初めてドキュメントを読んだ

**正しかった対応**:
1. `docs/CLASS01_TIMEOUT_ANALYSIS.md` Lines 218-298 に解決策が既に記載されていた
2. 待機時間を3秒→5秒に延長するだけで解決
3. ドキュメントを最初に読んでいれば5分で解決できた

## 習慣化のための自己チェック

問題を見つけたら、コードを書く前に以下を自問：

1. ✅ CLAUDE.mdを読んだか？
2. ✅ 関連ドキュメントを読んだか？
3. ✅ メモリファイルを確認したか？
4. ✅ 過去のコミット履歴を確認したか？

**すべてYESでない限り、コーディングを開始してはいけない**
