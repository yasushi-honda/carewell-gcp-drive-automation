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
- 課題②ジョブ: 全クラス `PAUSED`（この時点の記録。現在の状態は「3.5 課題②の受け入れ」の表が正本）。

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

注: 期待人数を先に登録した（取込み前のdry-runのため）未取込みのクラスは、「受講者リストが空になっている」として「退行・検証失敗」と表示される。実際は未取込みで、取込み後に解消する。

「次のアクション」に従う。

### 手順1: 名簿（受講者リスト）の取込み
1. `scripts/merge_student_roster.py --class 0N`（dry-run）で検証ゲートを通す。
2. 失敗時の典型対応:
   - 「入所・居宅系マッピングが未登録」→ `GROUP_CATEGORY_MAP_BY_CLASS` に追加。**№01・02・03 は同一規則**（A〜J=入所系居住系 / K〜Q=通所系訪問系 / R=居宅介護支援）。適用は decision-maker 承認が必要。サービス種別内訳が規則と整合するか確認してから申請。
   - グループが**全角（Ａ〜Ｒ）**で届く（№03）→ パース時にNFKCで半角化済み。
   - ふりがなの拗音表記ゆれで名寄せ失敗 → `MATCH_EXCEPTIONS_BY_CLASS` に人間確認のうえ登録。
   - 「№0Nリストのヘッダーが想定と異なります」（例: A1セルが「グループ」でなく「\」、№05で発生）→ クライアントの入力ミス。コードの検証は緩めず、クライアントに該当セルの修正を依頼する。
   - 受講者数の検証 → `EXPECTED_STUDENT_COUNT_BY_CLASS` に正しい総数を登録（人間確認した値のみ）。
3. `--commit` で書き込み（読み戻し検証つき。「受講者リスト」の非表示・保護も同時に適用される）。
4. **会社・事業所欄（D・E列）は常に空欄**（個人情報保護のクライアント要望）。取込みスクリプトは空欄で書き込み、`check_rollout_status.py` が実データの混入を「退行」として検出する。2026-09-18に、スクリプトの仕様で実データが復活していたのに「対応完了」と報告していた事故の再発防止。

5. **クラス横断の日介番号重複は、ゲート`9_他クラス日介番号重複`が書込み前に止める**（PR #75で追加）。他クラスの「受講者リスト」と日介番号が重複すると、Dashboardの名簿同期が全クラスで中断するため（2026-10-19、№04で3件を見逃した）。ゲートが失敗したら、書込みせずdecision-makerへ確認する。登録済みの異動者は、異動元と異動先の組だけ許容される。クライアントは異動した人の行を旧クラスに残し、**行をグレーにして示す**ことがある（正本リスト・出欠確認とも）。システムは色を読まないため、旧クラスの名簿にも残る。
6. 異動と確認できた受講者は、`src/config/classes.py`の`ATTENDANCE_ROSTER_TRANSFERRED_STUDENTS`に`{"日介番号": {"from": "異動元No", "to": "異動先No"}}`で登録する（decision-makerの確認が前提、PRで反映）。名簿同期は、異動先の名簿に載っている場合に限り、確認済みの異動元の行を読み飛ばす。適用されなかった登録は、同期の応答の`unapplied_transfers`と警告ログに出る。登録は静的で期限がないため、再異動があれば見直す。
   - 異動の登録の運用上の注意（2026-10-20、独立レビューの指摘）:
     - 登録は1人につき`{from, to}`の1組のみで、連鎖（例: №04→№05→№06）は表せない。現在のクラスへの異動だけを登録し、次の異動先の取込み時はゲート9が書込み前に止める。その時点で登録形式の拡張が要る（N9907036、2026-10-23）
     - 登録に期限はない。異動元のグレー行をクライアントが削除した、異動先の行が消えた、クラス名を誤記した、などの場合は、登録が適用されず、同期の応答の`unapplied_transfers`と警告ログ（`registered transfers were not applied`）に15分ごとに出続ける。定期的に見直し、不要な登録は外す
     - 異動先の行が後で消えた場合（例: 異動先で辞退して行を削除）は、登録が未適用になり、異動元のグレー行が在籍として同期される（警告ログのみ、同期は`success`のまま）。全クラスを止めないための意図的な設計
     - 再異動（異動先から元のクラスへ戻る等）では、登録が古いまま、異動先の側が正本として扱われる。重複は検出されない。再異動を知ったら、登録を書き換える
   - クライアントとの取り決め（2026-10-20）: 異動があったときは、クライアントが異動した方の日介IDと、異動元・異動先のクラスを連絡する。名簿の入力は従来どおり（異動元の行をグレーにする運用のまま）。こちらは内容を確認し、上記の登録を行って、Dashboardの受講生一覧に反映する。

### 手順2: 共有「グループ分け」との照合（個人単位）
正本(R08フォルダの `№0N_グループ分け のコピー`)は `system@jaccw.or.jp` にのみ共有されており、SAからは見えない。
1. Playwright MCP のブラウザで `system@jaccw.or.jp` に**ユーザーがログイン**する（パスワード・2段階認証はAIが入力しない）。
2. 「受講者リスト作業用」タブ（日介番号・グループ・受講者番号）を読み、**ハッシュ値だけ**を取り出して名簿側と比較する。氏名は出力しない。
   - 実施例（№05）: ログイン後のブラウザ内で`/spreadsheets/d/<ID>/gviz/tq?tqx=out:csv&sheet=<タブ名>`を取得し、`日介番号|グループ(NFKC)|受講者番号`を並べ替えたSHA-256を計算する。名簿側は取込みスクリプトのゲート通過後の行から同じ式で計算し、ダイジェストの一致と件数・グループ別人数だけを出力する。
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
注意: 複数コマンドを`&&`でつないだ長い行は、貼付け時の折返しで途中の`--commit`が別コマンドになり、そのコマンドがdry-runのまま後続が止まることがある。コマンドは1つずつ実行する。
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
- **収集から表示までの4段突合**（№01で2026-09-20に実施した方法。収集漏れを検出できる唯一の手段）。**`python scripts/verify_task_rollout.py --class 0N --task 課題X`で、2〜4段目と提出者数の一致を1コマンドで確認できる**（読み取り専用・氏名を出さない。終了コード0=全段一致 / 1=食い違い / 2=確定できない）。1段目の「提出元画面の件数」は、スクリプトでは収集コードが画面から読んだ値（`Count verification`）で代用する（収集コード自身の読み取りなので、「画面の読み誤り」は検出できない）。**各クラスの課題②の初回は、人が画面で数えた件数との比較（下の手順1）を併用する**:
  1. 提出元画面の件数（課題①の「未添削＋添削済」の合計）。decision-makerから画面のスクリーンショットを受け取る（AIはzenkoukaiにログインしない）
  2. Cloud Runログの確認件数。`gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="carewell-file-collector" AND textPayload:"№0N-課題①" AND textPayload:"Count verification"' --freshness=1d --limit=3 --format='value(timestamp,textPayload)'` の `Count verification passed: N/N` のNが、1と一致すること
  3. 提出記録シート「課題①」のデータ行数（見出しを除く）が、1と一致すること
  4. 出欠確認の「提出」件数（`check_rollout_status.py` の提出/未提出）が、提出記録のユニーク日介番号数と一致すること
  - **同じ受講者が複数回提出すると、行数は増えるが提出者は1名として数える**（№01: 13行・12名）。1〜3は行数、4はユニーク数で比べる。
  - 食い違いの読み方: 1≠2 → 収集漏れ（Cloud Runの収集ログを調査）。2≠3 → Sheets追記の失敗（Firestoreの`sheets_sync_status=failed`）。3とユニーク数は合うが4が合わない → 数式・名簿の問題。
- **Dashboardの確認**: 名簿の取込み後、最大15分で`carewell-attendance-roster-sync`がFirestoreへ同期し、Dashboard（https://carewell-dashboard-2026.web.app/）の「受講生一覧」にクラスの受講者が表示される。管理者アカウントでログインし、件数とグループ別人数が名簿と一致することを確認する（氏名をスクリーンショットに残さない）。
- クライアントへの報告は、検証済みの事実だけを書く（2026-09-14の「完了」報告が実際には崩れていた前例あり）。

## 3.5 課題②の受け入れ（№01から）

課題②も、課題①と同じ仕組みで出欠確認表（見出し行の「課題②」列）へ反映する。スクリプトの`--task 課題②`で課題ラベルだけを差し替える（省略時は課題①で、従来の挙動は変わらない）。数式・タブの組み立てがすべて課題名に追従する（収集側のコード修正と合わせて、2026-10-29に対応）。

| 項目 | 課題②での扱い |
|---|---|
| 提出記録シートのタブ | 「課題②」。初回の書込み時にCloud Runが**非表示**で自動作成する（課題①と同じ）。 |
| 管理側ファイルのタブ | 「課題②」。非表示＋保護（課題①と同じ）。 |
| 提出記録側の保護 | しない（課題①と同じ。収集用のSAが書込めなくなるのを避ける）。 |
| 出欠確認の列 | 見出し行（4行目）の「課題②」列（№01はM列）。 |

**順序（状態を変える操作の前に、前段を確認する）**
1. **デプロイの前に**、ポータル（zenkoukai）で課題の候補数を確認する（`decision-maker`がログインし、AIは表示名と件数だけを読む）。収集コードと同じ条件（`text=<課題名>`の部分一致）で、**課題①と課題②の両方が候補1件だけ**であること。課題②が未公開なら、課題①だけ確認する。
   - 新しい収集コードは、候補が2件以上だと中断する（誤った課題を黙って集めない）。課題①のジョブは稼働中のため、課題①の候補が2件以上だと**デプロイ後に全クラスの課題①収集が止まる**。課題②の公開で「課題①」を含む文言が増えていないかも、ここで確かめる。
2. 収集コードの修正（課題名の一意選択・ダウンロードの一時ディレクトリ分離・課題②タブの非表示作成）をデプロイし、revision・traffic・ログの3点を確認する（`docs/common-mistakes.md` #8）。デプロイ後の最初の課題①の実行ログで、`Task pattern matched multiple elements`（HTTP 500）が出ていないことを確認する。
3. 課題②がポータルに公開されていることを確認してから、`gcloud scheduler jobs resume carewell-classNN-task02 --location=asia-northeast1 --project=carewell-automation`（1クラスずつ。次の実行は下の表の実行スロット）。再開後は、`python scripts/check_collection_status.py --class 0N --task 課題②`（読み取り専用・氏名が出ない）で、直近の実行が「収集OK」（`Count verification passed`、0件なら「提出0件を確認」）であることを確認する。**スクリプトの結果が「課題が見つからない」「課題ページに到達せず中断」のときは「正常に0件」と読まない**（ログの`Task not found` / `Task not yet created`も同じ）: 課題名の表記違い（`task_pattern`の誤り）や画面の読込み遅れでも同じ応答（HTTP 200）になり、Cloud Schedulerは緑のまま0件収集が続く（課題①から続く既存の仕様）。ポータルに課題②が公開済みなのにこのログが出る場合は、`task_pattern`とポータルの表示名を突き合わせる。
4. 反映（クラスごと）。コマンドは1つずつ実行する。
```
python scripts/apply_submission_formulas.py --class 0N --task 課題②             # dry-run
python scripts/apply_submission_formulas.py --class 0N --task 課題② --commit
# 提出記録側の「課題②」タブがまだ無く、最初の提出前に連携を済ませたいとき:
python scripts/apply_submission_formulas.py --class 0N --task 課題② --commit --provision-submission-tab
python scripts/hide_sensitive_sheets.py --class 0N --task 課題②                 # dry-run
python scripts/hide_sensitive_sheets.py --class 0N --task 課題② --commit
python scripts/check_rollout_status.py --class 0N --task 課題②                  # 「完了」になること
```
- `hide_sensitive_sheets.py`は、エラー・適用後に非表示/保護が効いていない結果があれば終了コード1で終わる（`[失敗]`行に原因が出る）。`--commit`が0で終わっても、読み取りの`check_rollout_status.py`で状態を確かめる。
- **「完了」は設定の完了**。提出が0件の間は収集から表示までが未確認で、`Count verification passed`は一覧の件数照合であり、Sheets追記の成功までは証明しない。最初の実提出後に、手順5の**4段突合**（課題名を「課題②」に読み替える）を必ず行う。
- Dashboardは、課題の親ドキュメントが作られる**初回の収集後**でないと課題②を出さない。表示の確認は初回収集の後に行う。

### クラス別の展開チェックリスト（課題②）

2026-10-29時点。ジョブは`gcloud scheduler jobs list`で確認した実際の設定（再開済みは№01のみ）。**1クラスずつ**、上の順序（ポータル確認 → デプロイ済みの確認 → 再開 → 反映）で進める。

| クラス | ジョブ | 実行（毎時） | 状態 | 着手の前提 |
|---|---|---|---|---|
| №01 | `carewell-class01-task02` | :05 / :35 | **ENABLED（完了）** | 完了（2026-10-29） |
| №02 | `carewell-class02-task02` | :15 / :45 | PAUSED | №02のポータルで課題②が公開済み・候補1件 |
| №03 | `carewell-class03-task02` | :25 / :55 | PAUSED | 同上（№03） |
| №04 | `carewell-class04-task02` | :05 / :35 | PAUSED | 同上（№04） |
| №05 | `carewell-class05-task02` | :15 / :45 | PAUSED | 同上（№05） |
| №06 | `carewell-class06-task02` | :25 / :55 | PAUSED | 名簿の取込み（手順1〜）が先 |
| №07・№09 | `carewell-class07-task02` / `carewell-class09-task02` | :05 / :35 | PAUSED | 正本リスト（名簿）の入力が先 |
| №08・№10 | `carewell-class08-task02` / `carewell-class10-task02` | :25 / :55、:15 / :45 | PAUSED | 本スクリプト群の対象外（課題①ジョブも停止中。収集側の再開が先） |

**ポータルの候補数の確認（クラスごと、デプロイ済みの今は「課題②の公開確認」が目的）**
1. `decision-maker`がブラウザでログインする。AIは氏名や画面の本文を読まず、件数だけを数える。
2. 収集コードと同じ順で進む: ホームで**「クラス管理」**（`a[href="course/default.aspx"]`）→「教科クラス一覧」→ 対象クラス（`令和8年度 デジタル中核人材養成研修 №0N`）→「レポート採点」。ホームで「教科クラス一覧」を直接探しても見つからない。
3. 課題の一覧で、`text=課題①`と`text=課題②`がそれぞれ**1件**であること（複数なら、そのクラスの収集は中断する）。
4. 作業後は、ポータルからログアウトしてもらい、ブラウザのタブを閉じる。

**クラスNNごとの実行（番号は置き換える。コマンドは1つずつ実行し、状態を変える操作は都度承認を取る）**
```
gcloud scheduler jobs resume carewell-classNN-task02 --location=asia-northeast1 --project=carewell-automation
python scripts/check_collection_status.py --class NN --task 課題② --strict-not-found   # 次の実行の後に「収集OK」か（公開済みの課題のため、見つからなければ異常）
python scripts/apply_submission_formulas.py --class NN --task 課題②        # dry-run（衝突0・ゲート通過を確認）
python scripts/apply_submission_formulas.py --class NN --task 課題② --commit
python scripts/hide_sensitive_sheets.py --class NN --task 課題②            # dry-run
python scripts/hide_sensitive_sheets.py --class NN --task 課題② --commit
python scripts/check_rollout_status.py --class NN --task 課題②            # 「完了」
python scripts/check_rollout_status.py                                      # 課題①の回帰（全クラスが完了のまま）
python scripts/verify_task_rollout.py --class NN --task 課題②             # 4段突合（全段PASS・終了コード0）
```
- 手動で前倒しして実行するなら `gcloud scheduler jobs run carewell-classNN-task02 --location=asia-northeast1`（定期実行と同じ処理）。実行中に新しい提出が入ると、手動実行と定期実行で件数が違うことがある（既存分は重複せず、新しい分だけ取得される）。
- 出欠確認の「提出」が、新しい提出の直後に独立集計より1件少なく見えて`check_rollout_status.py`が「退行・検証失敗」になることがある。IMPORTRANGEの再計算待ちで、数十秒〜で解消する。1〜2回再実行してから原因を調べる。
- ログを手で確認するときは、氏名が出ない条件に絞る（`Count verification`・`Starting file collection`等）。`textPayload:"№0N-課題②"`のように広く取ると、ダウンロード行に氏名が出る。上の`check_collection_status.py`を使えば原文は出ない。
- **Dashboardの確認**（ログイン不要。閲覧系は認証で塞いでいない。`docs/admin-authentication.md`）: https://carewell-dashboard-2026.web.app/ → クラス一覧 → 対象クラス。クラス画面に「課題①」「課題②」が並び、課題②のグループ画面は`/class/{クラス名}/task/課題②/groups`（グループ一覧）→ グループの受講生一覧で「採点待ち」などの件数が出る。**確認するのは件数だけ**（受講生一覧・提出履歴は氏名が出るため、スクリーンショットを共有・保存しない）。受講生の画面（`/students/{日介番号}`）の「提出履歴」に、課題②のファイルが並ぶ。Dashboardは、課題の親ドキュメント（初回収集で作られる）が無い課題を出さない。管理者ログインは、手動同期など書き込み系の操作のときだけ要る。
- `verify_task_rollout.py`の「提出記録の提出者は全員名簿内」がFAILのとき: 日介番号が空欄、または名簿にない日介番号の提出がある。出欠確認の「提出」件数と独立集計は、その行を**両側から除外して一致してしまう**ため、この項目でしか見つからない（その受講者は出欠確認で「未提出」のまま）。誤入力・別クラス・異動・名簿に載っていない受講者のいずれかなので、提出記録シートの該当行（日介番号）をクライアントの名簿と照合して原因を決める（AIが決めない）。
- `check_collection_status.py`の終了コード: ENABLEDのジョブに「中断・不一致・確認不能・ERROR」があるか、期間内に実行が無い・ジョブが無い場合は1（**再開した直後は、次の実行まで「実行なし」で1になる**）。クラス・課題を特定できないERROR（ダウンロード失敗・保存/同期の失敗・HTTP 500など。`main.py`のログには接頭辞が付かない）は「帰属不明」として別に数え、1件でもあれば1。ログが取得上限（2000件）に達したら不完全なので2。実行は`.venv/bin/python`。
- `check_collection_status.py`の限界: 収集コードに「実行の終了」を示すログ行が無いため、手動実行と定期実行が重なると、片方のERRORがもう片方に付くことがある（誤ってERRORと出る安全側の誤り）。ERRORが出たらログを手で確認する。毎回、課題ページに着く前に中断する場合は「中断（繰り返し）」と出る。

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

- **正本リストの行の色（グレー）は読まれない**: クライアントが異動・辞退などを示すためにグレーにした行も、名簿・出欠確認・Dashboardには通常の受講者として入る。グレーの意味は未確認（2026-10-19時点）。
- **Dashboardの「辞退」の位置づけ**: 状態切替は受講生ごとに1件のデータ（日介番号がキー）を直接更新する。異動には使わない（異動先でも辞退表示になる）。出欠確認表には反映されない。

## 5.5 名簿同期の監視（Dashboardへの15分ごとの同期）

同期の中断（`status=aborted`）は、フェーズAの検証失敗（重複・不正行・読取りエラー）で、書込み前に全クラスを止める。2026-10-19は、中断に約4時間気づけなかった。中断は`WARNING`（`Attendance roster sync aborted: …`、原因の種別と件数のみ）で記録される。

```
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="carewell-file-collector" AND (textPayload:"roster sync aborted" OR textPayload:"transfers were not applied" OR severity>=ERROR)' --freshness=1d --limit=20 --format='value(timestamp,severity,textPayload)'
```
- `roster sync aborted`: 重複なら`duplicate_student_ids`、不正行なら`malformed_rows`、Sheets APIの読取り失敗なら`error_classes`に件数・クラスが出る。読取り失敗（例: Sheets APIのHTTP 500）は次の回で自動回復することが多い
- `transfers were not applied`: 異動の登録が適用されていない（上記の見直し対象）
- 通知（アラート）の仕組みは未導入。必要になったら、decision-makerの判断で追加する

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
