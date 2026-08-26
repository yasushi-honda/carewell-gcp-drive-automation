---
updated: 2026-08-27
---

## 現在のミッション
Issue #12（Cloud Run管理者エンドポイント・Firestore書き込みの無認証公開）の完全クローズ。コード側の実装（4PR）は完了済み、残るはdecision-maker自身のFirebase Console作業と実機E2E確認。

## 背景・why
`/cleanup`, `/admin/sync-students-from-sheets`, `/admin/duplicate-students`と`students`コレクションの書き込みが無認証で誰でも実行できる状態だった（README「認証トークン必須」の記載とも矛盾）。PR #11のセカンドオピニオンレビューで発見しIssue #12（bug, P1）として起票。plan mode + plan-crossreview（grip/codex）でアプリ層認証ゲート設計を確定し、PR #13（バックエンド）→#14（フロントエンド）→#15（Firestoreルール）→#16（ドキュメント）の順で実装・全マージ済み（2026-08-26〜27）。詳細設計: `docs/admin-authentication.md`。

## 完了の定義
- [ ] decision-maker: Firebase Console でAuthentication有効化・Google Sign-Inプロバイダ設定・`carewell-dashboard-2026.web.app`を認可済みドメインに追加（証明: Firebase Console上で設定確認）
- [ ] decision-maker: `scripts/seed_admins.py --add --email <addr>` で自分＋運営メンバーを`admins`コレクションに投入（証明: `python scripts/seed_admins.py --list` で1件以上表示）
- [ ] 認証なしでCloud Runの書き込み系エンドポイントが401になる（証明: `curl -s -o /dev/null -w "%{http_code}\n" -X POST $BASE/admin/sync-students-from-sheets -d '{}'` 等が全て`401`）
- [ ] `/health`は無認証のまま200（証明: `curl -s -o /dev/null -w "%{http_code}\n" $BASE/health` → `200`）
- [ ] Scheduler経路のOIDC認証が通過する（証明: `gcloud auth print-identity-token --impersonate-service-account=... --audiences="$BASE"`で取得したトークンで`POST $BASE/`が`400`＝認証通過・パラメータ検証で拒否、`401`ではない）
- [ ] Dashboardで管理者ログイン後、同期ボタン・重複一覧が動作する（証明: ブラウザDevTools NetworkでAuthorization: Bearer送信と200応答を確認）
- [ ] 未ログインで受講生の辞退切替がFirestore側で拒否される（証明: ブラウザDevTools Consoleで`permission-denied`エラーを確認）
- [ ] デプロイ後の3点確認（証明: `gcloud run services describe carewell-file-collector --region=asia-northeast1`でrevision更新確認 + `gcloud logging read`でエラーなし確認）
- [ ] 上記全項目確認後、Issue #12を`gh issue close 12`でクローズ

## 進行中のtasks
- [x] Step1: バックエンド認証ゲート実装（PR #13、マージ済み）
- [x] Step2実装: `scripts/seed_admins.py`作成（PR #13、マージ済み。実行はdecision-maker待ち）
- [x] Step3: フロントエンド認証（Firebase Authentication）実装（PR #14、マージ済み）
- [x] Step4: Firestoreセキュリティルール変更（PR #15、マージ済み）
- [x] Step5: ドキュメント整備（PR #16、マージ済み）
- [ ] decision-maker: Step0（Firebase Console設定）の実施
- [ ] decision-maker: Step2実行（管理者メールアドレスの投入）
- [ ] 実機E2E確認（上記「完了の定義」チェックリスト、Step0/Step2完了後に着手可能）
- [ ] Issue #12クローズ

## 🔄 中断点（in-flight）
なし（コード側の作業は全て完了・マージ済み。次の一手はdecision-maker自身のFirebase Console作業であり、AI側の中断作業はない）
