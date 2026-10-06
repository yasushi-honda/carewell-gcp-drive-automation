# クラス展開ランブック（出欠確認表への課題提出連携）

クラス№01で行った作業を、全クラス（№01〜07・09。№08・10は別途）で同じ結果になるよう再現する手順。
目的: 各クラスの `{No}_受講者リスト_出欠管理` の「{No}_出欠確認」シートの課題①列に、提出/未提出が自動表示されること。

- 経緯・進捗の正本: `docs/handoff/GOAL.md`
- 設計判断の背景（Issue #18、plan-crossreview 済み）: GOAL.md「背景・why」

## 1. 仕組み（全体像）

```
受講者がzenkoukaiへ提出
  → Cloud Run(carewell-file-collector、30分ごと)がDrive保存+Firestore記録
  → 提出記録シート「課題①」タブへ追記(初回にタブを自動作成、非表示)
        │ IMPORTRANGE(氏名, 日介番号)
        ▼
{No}_受講者リスト_出欠管理 の「課題①」タブ(非表示+保護)
  A:B=提出記録(氏名,日介番号) / C=XLOOKUPで受講者番号に変換
        │ COUNTIF
        ▼
「{No}_出欠確認」の課題①列: 提出 / 未提出
```

コード変更は不要。Sheets側の数式だけで反映する（バックエンドは変更しない）。

## 1.5 この手順の範囲（収集側は別手順）

本ランブックは「**出欠確認表への反映**」まで。提出された課題を集めて提出記録シートへ書き込む**収集側**は対象外。

| 領域 | 本ランブック | 備考 |
|---|---|---|
| 名簿の取込み・グループ分けとの照合・数式連携・非表示/保護・進捗確認 | **対象** | 手順0〜5 |
| 収集側: Cloud Schedulerの課題①ジョブ（resume/作成）、Driveの保存先フォルダ、Cloud Runの設定 | 対象外 | 別手順（`docs/cloud-scheduler-operations-guide.md`、`docs/SERVICE_SHUTDOWN_AND_RESUME.md`） |
| 収集の不具合の修正（例: 提出0件のタイムアウト誤検知、`docs/common-mistakes.md` #17） | 対象外 | コードの修正 |

**収集側の現状（2026-10-06、`gcloud scheduler jobs list` で確認）**
- 課題①ジョブ: №01〜07・09は `ENABLED`（30分間隔）。№08・10は `PAUSED`。
- 課題②ジョブ: 全クラス `PAUSED`。

このため、№04〜07・09は名簿・グループ分けが届けば本ランブックだけで連携まで完了する。**№08・10と課題②に着手するときは、本ランブックの前に収集側の作業が必要**: ジョブをresumeし、ログ（`Count verification passed`、提出0件なら確定ゼロ件のログ）で動作を確認してから、手順1に進む。

## 2. 権限モデル（二系統）

| SA | 用途 | 権限 |
|---|---|---|
| `carewell-automation-sa` | 出欠管理ファイルの読取り・編集、提出記録シートの**閲覧のみ** | `merge_student_roster.py`、`apply_submission_formulas.py`と`check_rollout_status.py`の**すべての読取り**(提出記録シートの読取りを含む) |
| `github-actions-sa` | **Cloud Run実行SAでもある**。提出記録シートの編集権限を持つ | 提出記録シートへの**書込みだけ**: `apply_submission_formulas.py --provision-submission-tab --commit`のタブ作成、`hide_sensitive_sheets.py` |

どちらもユーザーアカウントからの権限借用(`gcloud auth login` 済みが前提、`src/gcp_sa_auth.py`)。
共有ファイルへの `--commit` は、auto mode の権限判定で止まることがある。その場合は実行コマンドを提示して**ユーザーが実行**する。

## 3. クラス追加の手順

名簿データ（クライアント入力の「№{N}リスト」タブ、および共有フォルダ R08 の「グループ分け」）が届いたら、№01 と同じ順で進める。

### 手順0: 現状を確認
```
python scripts/check_rollout_status.py            # 全クラス
python scripts/check_rollout_status.py --class 04
```
| 状態 | 意味 | 終了コード |
|---|---|---|
| 完了 | 連携の**設定**が完了（A1/C1・数式・非表示/保護・集計が整合）。「提出」件数が0の間は、次のアクションに「最初の実提出後に収集〜表示を確認」と出る | 0 |
| 予定された保留 | 名簿データ待ちなど、こちらでできることがない | 0 |
| 要確認(名簿差分) | 正本リストが取込み後に更新された（グループ・氏名・ふりがな・サービス種別）。数式の退行ではない。差分を確認し再取込みの要否を判断 | 0 |
| 要対応 | こちらで次の作業がある（取込み・連携設定・非表示/保護） | 1 |
| 退行・検証失敗 | 番号の不一致、期待人数との不一致、連携(A1/C1/IMPORTRANGE)の切断、集計の不一致 | 1 |

「次のアクション」に従う。

### 手順1: 名簿（受講者リスト）の取込み
1. `scripts/merge_student_roster.py --class 0N`（dry-run）で検証ゲートを通す。
2. 失敗時の典型対応:
   - 「入所・居宅系マッピングが未登録」→ `GROUP_CATEGORY_MAP_BY_CLASS` に追加。**№01・02・03 は同一規則**（A〜J=入所系居住系 / K〜Q=通所系訪問系 / R=居宅介護支援）。適用は decision-maker 承認が必要。サービス種別内訳が規則と整合するか確認してから申請。
   - グループが**全角（Ａ〜Ｒ）**で届く（№03）→ パース時にNFKCで半角化済み。
   - ふりがなの拗音表記ゆれで名寄せ失敗 → `MATCH_EXCEPTIONS_BY_CLASS` に人間確認のうえ登録。
   - 受講者数の検証 → `EXPECTED_STUDENT_COUNT_BY_CLASS` に正しい総数を登録（人間確認した値のみ）。
3. `--commit` で書き込み（読み戻し検証つき。「受講者リスト」の非表示・保護も同時に適用される）。
4. **会社・事業所欄（D・E列）は常に空欄**（個人情報保護のクライアント要望）。取込みスクリプトは空欄で書き込み、`check_rollout_status.py` が実データの混入を「退行」として検出する。2026-09-18に、スクリプトの仕様で実データが復活していたのに「対応完了」と報告していた事故の再発防止。

### 手順2: 共有「グループ分け」との照合（個人単位）
正本(R08フォルダの `№0N_グループ分け のコピー`)は `system@jaccw.or.jp` にのみ共有されており、SAからは見えない。
1. Playwright MCP のブラウザで `system@jaccw.or.jp` に**ユーザーがログイン**する（パスワード・2段階認証はAIが入力しない）。
2. 「受講者リスト作業用」タブ（日介番号・グループ・受講者番号）を読み、**ハッシュ値だけ**を取り出して名簿側と比較する。氏名は出力しない。
   - 「サービス・グループ人数・担当サブ講師」タブでグループ別人数・合計も確認する。
3. 終了後は**必ずログアウト**し、Cookieを消す（`accounts.google.com/Logout`＋`context.clearCookies()`）。

### 手順3: 連携の設定
```
python scripts/apply_submission_formulas.py --class 0N                 # dry-run
python scripts/apply_submission_formulas.py --class 0N --commit
# 提出記録側「課題①」タブがまだ無い場合(最初の提出前でも連携を完了したいとき):
python scripts/apply_submission_formulas.py --class 0N --commit --provision-submission-tab
```
- 事前ゲート: 受講者リストの件数＝期待人数 / 受講者番号・日介番号の空欄と日介番号の重複なし（重複するとXLOOKUPが2人目を引けず、提出しても「未提出」のままになりうる）/ 出欠確認と受講者リストの受講者番号が一対一 / 課題①列を見出し行(4行目)から特定。
- 既存入力は上書きしない（期待と異なる既存入力があれば中断）。見出し行などの既存ラベルも変更しない。
- 事後検証: エラーセル0 / 判定行数＝受講者行数 / 「提出」＝独立集計 / IMPORTRANGE が接続エラーでない。
- 終了コード: 0=成功 / 1=検証失敗 / 2=保留（提出記録側タブなし、またはEXPECTED未登録）。
- 検証失敗のときは、同じコマンドを再実行する（書込み0行で、検証だけが走る）。IMPORTRANGEの再計算待ちは最大3回自動で再確認するが、初回接続は遅れることがある。
- **IMPORTRANGE の接続許可**: 新しいシートの組み合わせでは初回に許可が必要になりうる（Google公式仕様）。№02ではAPI経由の書込みで許可不要だったが、一般化できない。`#REF!`/「接続する必要」が出たら、管理側「課題①」タブのA1セルで「アクセスを許可」を**ユーザーが1回**押す。

### 手順4: 非表示・保護
```
python scripts/hide_sensitive_sheets.py --class 0N            # dry-run
python scripts/hide_sensitive_sheets.py --class 0N --commit
```
- 提出記録側の「課題①」: **非表示のみ**（保護は現行コードでは対象外）。
- 管理側の「課題①」「受講者リスト」: 非表示＋保護。
- 管理側の「課題①」を作った直後（手順3の後）に必ず実行する（提出者の氏名が見える状態を残さない）。

### 手順5: 確認と報告
```
python scripts/check_rollout_status.py --class 0N     # 「完了」になること
```
- 「完了」は**設定の完了**を意味する。提出が0件の間は、収集から表示までの動作は未確認のまま。初回の実提出が入ったら、**収集から表示までの確認を別途行う**: 実提出者数が「提出」と一致すること（№01では往復テスト＝テスト提出→「提出」→削除→「未提出」で確認済み）。
- **収集から表示までの4段突合**（№01で2026-09-20に実施した方法。収集漏れを検出できる唯一の手段）:
  1. 提出元画面の件数（課題①の「未添削＋添削済」の合計）。decision-makerから画面のスクリーンショットを受け取る（AIはzenkoukaiにログインしない）
  2. Cloud Runログの確認件数。`gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="carewell-file-collector" AND textPayload:"№0N-課題①" AND textPayload:"Count verification"' --freshness=1d --limit=3 --format='value(timestamp,textPayload)'` の `Count verification passed: N/N` のNが、1と一致すること
  3. 提出記録シート「課題①」のデータ行数（見出しを除く）が、1と一致すること
  4. 出欠確認の「提出」件数（`check_rollout_status.py` の提出/未提出）が、提出記録のユニーク日介番号数と一致すること
  - **同じ受講者が複数回提出すると、行数は増えるが提出者は1名として数える**（№01: 13行・12名）。1〜3は行数、4はユニーク数で比べる。
  - 食い違いの読み方: 1≠2 → 収集漏れ（Cloud Runの収集ログを調査）。2≠3 → Sheets追記の失敗（Firestoreの`sheets_sync_status=failed`）。3とユニーク数は合うが4が合わない → 数式・名簿の問題。
- **Dashboardの確認**: 名簿の取込み後、最大15分で`carewell-attendance-roster-sync`がFirestoreへ同期し、Dashboard（https://carewell-dashboard-2026.web.app/）の「受講生一覧」にクラスの受講者が表示される。管理者アカウントでログインし、件数とグループ別人数が名簿と一致することを確認する（氏名をスクリーンショットに残さない）。
- クライアントへの報告は、検証済みの事実だけを書く（2026-09-14の「完了」報告が実際には崩れていた前例あり）。

## 4. 運用上の約束

| 項目 | ルール |
|---|---|
| 誰が | 担当AI（またはdecision-maker）が、クラス追加時と、提出待ちのクラスの定期確認時に `check_rollout_status.py` を実行する |
| いつ | 名簿・グループ分けが届いたとき / 提出開始が見込まれる週は日次 / それ以外は週次 |
| 名簿の後追い変更 | クライアントは取込み後も正本リストを更新しうる（実例: №02は取込み後の9/29に更新、№01のふりがな修正）。statusが「退行・検証失敗」を出したら、差分を確認して再取込みの要否を判断する（再取込みは共有ファイルへの書込みなので承認を取る） |
| PII | 氏名・日介番号を会話・ログに出さない。バックアップは `var/scratch/`（gitignore済み、dir 0700 / file 0600）。ブラウザログインは作業後に必ずログアウト |
| 報告の言葉 | 「設定完了」と言えるのは、`check_rollout_status.py` が「完了」で、独立した再実行結果を示せるとき。「連携が動いている」と言えるのは、実提出で「提出」への切替を確認した後 |

## 5. 既知の限界

- 独立集計は提出記録シート由来のため、**収集漏れは検出できない**。Cloud Runは、Firestoreに記録（`sheets_sync_status=pending`）した後でSheetsへ追記する。追記が失敗すると `failed` になり、後続の収集では既存ファイルとしてスキップされうる（`src/main.py`, `src/firestore_service.py`）。提出者から「出ていない」と言われた場合は、Firestoreの `sheets_sync_status` とCloud Runログを確認する。
- **既存の収集漏れ検出スクリプトは、令和8年度では無効化されている**: `scripts/check_firestore_sheet_consistency.py`、`scripts/check_all_spreadsheets_consistency.py`、補修用の`scripts/fix_missing_sheet_records.py`は、クラス設定（`CLASS_CONFIG`）が空（`docs/SERVICE_SHUTDOWN_AND_RESUME.md`「令和8年度再開ステータス」）。使うには、クラスごとにスプレッドシートIDとFirestoreのクラス名を確認して有効化する別作業が要る。それまでは手順5の4段突合で代替する（過去の事故: `docs/common-mistakes.md` #15 Sheets同期のサイレント失敗）。
- `check_rollout_status.py` は Firestore の件数を取得しない（ローカルからFirestoreに繋がらない場合がある、`CLAUDE.md` Incident Response参照）。必要になったら別PRで追加する。
- バックアップ（`var/scratch/apply_submission_formulas/`）は書込み前の課題①列とA1/C1の値のみで、復元スクリプトは無い。読取りから書込みまでの間の他者による同時編集も検知しない（衝突は書込み前の読取り時点でのみ判定）。復元はGoogleスプレッドシートの版の履歴から行う。
- 提出記録側の「課題①」タブの保護は、現行の `hide_sensitive_sheets.py` では行わない（非表示のみ）。
- 事前作成とCloud Runの書込みの競合: Cloud Runは各クラス30分間隔で動く（№03の課題①は毎時20分・50分起動）。スクリプト側は、タブ作成と見出しを1回のbatchUpdateで行い、「既に存在」の場合は読み直して見出し一致を確認する（`provision_submission_tab`）。**Cloud Run側**は「一覧取得→無ければ作成」が非原子的で、同時に作られると1回目の追記が失敗しうるが、`append_record_with_retry`（最大3回）が再実行するため、2回目は既存のタブに追記できる。それでも念のため、**Cloud Runの起動時刻の前後数分は事前作成を避ける**。
- 検証の読取り上限は5,000行（提出記録シート）。到達すると独立集計が過小になるため、スクリプトは失敗する。上限は`SUBMISSION_READ_CAP`で調整する。

## 6. トラブルシュート

| 症状 | 確認・対応 |
|---|---|
| `apply_submission_formulas.py` が「期待人数が未登録」 | 手順1の `EXPECTED_STUDENT_COUNT_BY_CLASS` を登録（人間確認）。先に名簿取込みが必要 |
| 「課題①列に期待と異なる既存入力」で中断 | 自動修正しない。式の生値・参照先・計算結果を比較して原因を分類。№01は見出し行以外の既存ラベルがあるが、受講者行の式は同一 |
| `403 The caller does not have permission`（提出記録側） | `carewell-automation-sa` で書こうとしている。`github-actions-sa` 経由か確認 |
| `check_rollout_status.py` が「取得失敗: Sheets API HTTP 400」（`Unable to parse range`） | 出欠確認タブの名前が`№{N}_出欠確認`でない。テンプレートのコピー由来の誤ラベル（実例: 2026-09-04、№02が「№01_出欠確認」のまま）。タブ名を確認し、クライアントに修正を依頼する |
| `hide_sensitive_sheets.py` が自己ロックアウト防止ガード（`check_sa_not_locked_out`）で中断 | 保護の編集者リストに`carewell-automation-sa`が含まれない設定。**保護を適用せず中断するのが正しい動作**（2026-09-18、共有ドライブのorganizer系ロールの扱いで発覚）。編集者の取得結果を確認し、勝手に保護を外さない |
| `gcloud` の再認証エラー | `! gcloud auth login`（`system@jaccw.or.jp`） |
| 共有フォルダ（R08）がSAから404 | ユーザーアカウントにのみ共有されている。SAのアクセス権の問題であり、フォルダが存在しないとは限らない。手順2のブラウザ経路を使う |
