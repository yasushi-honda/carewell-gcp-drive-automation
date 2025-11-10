# Requirements Document

## Project Description (Input)

### プロジェクト概要

Firestoreに蓄積された提出ファイルのメタ情報を、講師が見やすく確認できるWebダッシュボードを構築する。

### 背景・目的

現在、Carewell自動収集システム（carewell-drive-automation）により、学生の提出ファイルがGoogle Driveに保存され、メタ情報がFirestoreに記録されている。しかし、講師がこれらの情報を確認するには、FirestoreコンソールやGoogle Driveを直接操作する必要があり、使いにくい。

本プロジェクトでは、講師が自分の担当クラスの提出状況を直感的に確認できるWebインターフェースを提供する。

---

## Introduction

Carewell Dashboardは、講師がFirestoreに蓄積された学生の提出ファイルメタ情報を直感的に確認できるWebベースの可視化ダッシュボードです。3段階のドリルダウンUI（クラス一覧 → 課題一覧 → ファイル一覧）により、講師は必要な情報のみに段階的に絞り込んでアクセスできます。

**ビジネス価値**:
- 講師の情報確認作業時間を大幅削減
- FirestoreコンソールやGoogle Drive直接操作の学習コスト削減
- 提出状況の視覚的把握による教育品質向上
- 既存システム（carewell-drive-automation）の価値最大化

---

## Requirements

### Requirement 1: クラス一覧表示機能

**Objective:** As a 講師, I want 全クラスの概要を一覧で確認できる, so that 自分の担当クラスを素早く見つけて選択できる

#### Acceptance Criteria

1. WHEN Dashboardがロードされる THEN Dashboardは全クラスをカード形式でグリッド表示する
2. WHEN クラスデータがFirestoreから取得される THEN Dashboardは各クラスカードにクラス名、課題数、ファイル総数、最終更新日時を表示する
3. IF Firestoreにクラスデータが存在しない THEN Dashboardは「データがありません」メッセージを表示する
4. WHEN クラスカードがクリックされる THEN Dashboardは該当クラスの課題一覧画面へ遷移する
5. WHILE クラスデータを取得中 THE Dashboardはローディングインジケーターを表示する

---

### Requirement 2: 課題一覧表示機能

**Objective:** As a 講師, I want 選択したクラスの全課題を一覧で確認できる, so that 確認したい課題を素早く選択できる

#### Acceptance Criteria

1. WHEN クラスが選択される THEN Dashboardは該当クラスの全課題をリスト形式で表示する
2. WHEN 課題データがFirestoreから取得される THEN Dashboardは各課題カードに課題名（task_id）、提出ファイル数、提出学生数、最終提出日時を表示する
3. IF 選択されたクラスに課題が存在しない THEN Dashboardは「課題がありません」メッセージを表示する
4. WHEN 課題カードがクリックされる THEN Dashboardは該当課題のファイル一覧画面へ遷移する
5. WHEN 「戻る」ボタンがクリックされる THEN Dashboardはクラス一覧画面へ戻る
6. WHERE 課題一覧画面 THE Dashboardは現在選択中のクラス名をヘッダーに表示する

---

### Requirement 3: ファイル一覧表示機能

**Objective:** As a 講師, I want 選択した課題の全提出ファイル情報を詳細に確認できる, so that 学生の提出状況を正確に把握できる

#### Acceptance Criteria

1. WHEN 課題が選択される THEN Dashboardは該当課題の全提出ファイルをテーブル形式で表示する
2. WHEN ファイルデータがFirestoreから取得される THEN Dashboardは各行に学生名、学生ID、ファイル名、提出日時、Driveリンクボタンを表示する
3. IF 選択された課題に提出ファイルが存在しない THEN Dashboardは「提出ファイルがありません」メッセージを表示する
4. WHEN 「戻る」ボタンがクリックされる THEN Dashboardは課題一覧画面へ戻る
5. WHERE ファイル一覧画面 THE Dashboardは現在選択中のクラス名と課題名をヘッダーに表示する
6. WHERE ファイル一覧画面 THE Dashboardは提出者総数と最終提出日時を統計情報として表示する

---

### Requirement 4: 検索・フィルター機能

**Objective:** As a 講師, I want ファイル一覧を検索できる, so that 特定の学生の提出物を素早く見つけられる

#### Acceptance Criteria

1. WHERE ファイル一覧画面 THE Dashboardは検索ボックスを提供する
2. WHEN 検索ボックスにテキストが入力される THEN Dashboardは学生名または学生IDに入力テキストが部分一致するファイルのみを表示する
3. WHEN 検索ボックスがクリアされる THEN Dashboardは全ファイルを再表示する
4. WHILE 検索フィルターが適用されている THE Dashboardは検索条件に一致する件数を表示する

---

### Requirement 5: ソート機能

**Objective:** As a 講師, I want ファイル一覧をソートできる, so that 提出順や学生名順で整理された情報を確認できる

#### Acceptance Criteria

1. WHERE ファイル一覧画面 THE Dashboardは「学生名」と「提出日時」カラムにソート可能インジケーターを表示する
2. WHEN 「学生名」カラムヘッダーがクリックされる THEN Dashboardはファイル一覧を学生名の昇順/降順でソートする
3. WHEN 「提出日時」カラムヘッダーがクリックされる THEN Dashboardはファイル一覧を提出日時の昇順/降順でソートする
4. WHEN ソートが適用される THEN Dashboardは現在のソート方向を視覚的に示す（矢印アイコン）

---

### Requirement 6: ナビゲーション機能

**Objective:** As a 講師, I want 画面間をスムーズに移動できる, so that 効率的に情報を探索できる

#### Acceptance Criteria

1. WHERE 課題一覧画面とファイル一覧画面 THE Dashboardは「戻る」ボタンを提供する
2. WHEN 「戻る」ボタンがクリックされる THEN Dashboardは一つ前の画面へ遷移する
3. WHEN ブラウザの戻るボタンが押される THEN Dashboardは適切に前画面へ遷移する
4. WHEN 画面遷移が発生する THEN Dashboardはページ全体のリロードなしにSPA方式で遷移する
5. WHERE 全画面 THE Dashboardはパンくずリスト形式で現在位置を表示する

---

### Requirement 7: Google Drive連携機能

**Objective:** As a 講師, I want 提出ファイルのDriveリンクにアクセスできる, so that 実際のファイルを確認できる

#### Acceptance Criteria

1. WHERE ファイル一覧画面 THE Dashboardは各ファイル行にDriveリンクボタンを表示する
2. WHEN Driveリンクボタンがクリックされる THEN Dashboardは該当ファイルのGoogle DriveページをNew Tabで開く
3. IF Firestoreに保存されたdrive_urlが無効な場合 THEN Dashboardはリンクを無効化しエラーメッセージを表示する

---

### Requirement 8: Firestoreデータ取得機能

**Objective:** As a システム, I want Firestoreから必要なデータを効率的に取得できる, so that ユーザーに正確な情報を提供できる

#### Acceptance Criteria

1. WHEN クラス一覧が要求される THEN DashboardはFirestoreのルートコレクション一覧を取得する
2. WHEN 特定クラスの課題一覧が要求される THEN DashboardはFirestoreの`{class_name}`コレクション配下のドキュメント一覧を取得する
3. WHEN 特定課題のファイル一覧が要求される THEN DashboardはFirestoreの`{class_name}/{task_id}/documents`コレクションの全ドキュメントを取得する
4. IF Firestore接続に失敗する THEN Dashboardはエラーメッセージをユーザーに表示する
5. WHILE データ取得中 THE Dashboardは適切なローディング状態を表示する

---

### Requirement 9: レスポンシブUI要件

**Objective:** As a 講師, I want PC・タブレット・スマホで快適に使用できる, so that 場所やデバイスを選ばずに情報を確認できる

#### Acceptance Criteria

1. WHEN Dashboardが画面幅768px未満で表示される THEN Dashboardはモバイルレイアウトに切り替える
2. WHEN Dashboardが画面幅768px以上で表示される THEN Dashboardはデスクトップレイアウトで表示する
3. WHERE モバイルレイアウト THE Dashboardはクラスカードを1カラムで表示する
4. WHERE デスクトップレイアウト THE Dashboardはクラスカードを複数カラムのグリッドで表示する
5. WHERE ファイル一覧テーブル（モバイル） THE Dashboardは横スクロール可能なテーブルまたはカード形式で表示する

---

### Requirement 10: パフォーマンス要件

**Objective:** As a 講師, I want 画面が素早く表示される, so that ストレスなく情報を確認できる

#### Acceptance Criteria

1. WHEN クラス一覧画面がロードされる THEN Dashboardは3秒以内に初回表示を完了する
2. WHEN 画面遷移が発生する THEN Dashboardは1秒以内に次画面の表示を開始する
3. IF ファイル一覧が100件を超える THEN Dashboardはページネーションまたは仮想スクロールを実装する
4. WHERE 全画面 THE Dashboardはブラウザキャッシュを活用して再訪問時のロード時間を短縮する

---

### Requirement 11: セキュリティ要件（Phase 1）

**Objective:** As a システム管理者, I want 不正な書き込みを防止できる, so that Firestoreデータの整合性を保てる

#### Acceptance Criteria

1. WHERE Firestore Security Rules THE システムは全ユーザーに読み取り権限を付与する（`allow read: if true`）
2. WHERE Firestore Security Rules THE システムはフロントエンドからの書き込みを完全に禁止する（`allow write: if false`）
3. WHEN DashboardがFirestoreにアクセスする THEN Dashboardは読み取り専用クエリのみを実行する
4. IF 書き込み操作が試みられる THEN FirestoreはPermission Deniedエラーを返す

---

### Requirement 12: エラーハンドリング要件

**Objective:** As a 講師, I want エラーが発生しても適切なメッセージを確認できる, so that 問題を理解し対処できる

#### Acceptance Criteria

1. IF Firestore接続エラーが発生する THEN Dashboardは「データの取得に失敗しました。ネットワーク接続を確認してください」を表示する
2. IF データが存在しない THEN Dashboardは状況に応じた空状態メッセージを表示する（例: 「クラスがありません」「提出ファイルがありません」）
3. WHEN エラーメッセージが表示される THEN Dashboardはリトライボタンまたは戻るボタンを提供する
4. IF 予期しないエラーが発生する THEN Dashboardはコンソールにエラー詳細をログ出力する

---

### Requirement 13: ブラウザ互換性要件

**Objective:** As a 講師, I want 主要ブラウザで正常に動作する, so that 利用環境に制約を受けない

#### Acceptance Criteria

1. WHERE Google Chrome最新版 THE Dashboardは全機能が正常に動作する
2. WHERE Safari最新版 THE Dashboardは全機能が正常に動作する
3. WHERE Microsoft Edge最新版 THE Dashboardは全機能が正常に動作する
4. IF 非対応ブラウザでアクセスされる THEN Dashboardは互換性警告メッセージを表示する

---

### Requirement 14: 拡張性要件（Phase 2対応）

**Objective:** As a 開発者, I want Phase 2で認証機能を追加できる設計になっている, so that 将来の機能拡張がスムーズに行える

#### Acceptance Criteria

1. WHERE アーキテクチャ設計 THE システムは認証モジュールを後付け可能な構造を採用する
2. WHERE コンポーネント設計 THE システムはFirestore接続ロジックを独立したComposable/Serviceとして実装する
3. WHEN Phase 2で認証が追加される THEN システムは既存コードの大幅な書き換えなしに認証機能を統合できる
4. WHERE Firestore Security Rules THE ルールはコメントでPhase 2の認証ルール案を記載する

---

### Requirement 15: コスト要件

**Objective:** As a システム管理者, I want 月額$1未満で運用できる, so that コストを最小限に抑えられる

#### Acceptance Criteria

1. WHEN 月間1000アクセスを処理する THEN Dashboardは月額$1未満のFirebase Hosting/Firestoreコストで運用される
2. WHERE データ取得 THE Dashboardは不要なFirestoreクエリを実行しない（効率的なクエリ設計）
3. WHERE アセット配信 THE DashboardはFirebase HostingのCDNを活用する
4. IF コストが$1を超える見込みの場合 THEN システムは事前にアラートを発する仕組みを検討する

---

## 成功基準

1. **操作効率**: 講師が3クリック以内で目的のファイル一覧にアクセスできる
2. **コスト**: 月間コストが$1未満
3. **ユーザビリティ**: モバイルでも使いやすいUI（タップターゲットサイズ、読みやすいフォント）
4. **拡張性**: Phase 2で認証機能を追加できる設計

---

### Requirement 16: グループ一覧表示機能

**Objective:** As a 講師, I want 課題選択後にグループ一覧を確認できる, so that 各グループの受講生数を把握できる

#### Acceptance Criteria

1. WHEN 課題一覧で「受講生一覧」リンクがクリックされる THEN Dashboardは該当課題の全グループをカード形式で表示する
2. WHEN グループカードがクリックされる THEN Dashboardは該当グループの受講生一覧画面へ遷移する
3. WHERE グループ一覧画面 THE Dashboardは各グループの受講生数を表示する
4. WHERE グループ一覧画面 THE Dashboardは現在選択中のクラス名と課題名をパンくずリストに表示する
5. WHERE グループ一覧画面 THE DashboardはFirestoreから効率的にデータを取得する（読み取り数を最小化）

---

### Requirement 17: 受講生テーブル拡張機能

**Objective:** As a 講師, I want 受講生一覧に詳細情報を表示できる, so that 提出状況を効率的に確認できる

#### Acceptance Criteria

1. WHERE 受講生一覧画面 THE Dashboardは通し番号カラムを表示する
2. WHERE 受講生一覧画面 THE Dashboardは勤務先（法人名 - 事業所名）カラムを表示する
3. WHERE 受講生一覧画面 THE Dashboardは通し番号でソート（昇順/降順）できる
4. WHERE 全UI THE Dashboard表示文言は「学生」ではなく「受講生」に統一される
5. WHERE ナビゲーションメニュー THE リンクテキストは「受講生一覧」と表示される

---

### Requirement 18: グループ別受講生一覧機能

**Objective:** As a 講師, I want 特定課題・特定グループの受講生のみを表示できる, so that グループごとの状況を確認できる

#### Acceptance Criteria

1. WHEN グループカードがクリックされる THEN Dashboardは該当クラス・課題・グループでフィルタされた受講生一覧を表示する
2. WHERE グループ別受講生一覧画面 THE Dashboardはパンくずリストでクラス→課題→グループ→受講生の階層を表示する
3. WHERE グループ別受講生一覧画面 THE Dashboard既存のStudentsViewと同じカラム（通し番号、氏名、ふりがな、クラス、グループ、勤務先、サービス種別）を表示する
4. WHERE グループ別受講生一覧画面 THE Dashboardは検索・ソート機能を提供する

---

## 制約条件

1. **既存システム依存**: Firestoreのデータ構造は既存システム（carewell-drive-automation）に依存する
2. **読み取り専用**: フロントエンドからFirestoreへの書き込みは一切行わない
3. **認証なし（Phase 1）**: リンクを知っている人全員がアクセス可能
4. **短期運用**: 約1年間の運用期間を想定
5. **小規模利用**: 月間1000アクセス未満を想定

---

## Future Enhancements (Phase 3候補)

### 未実装機能（Phase 2でスコープ外とした機能）

#### Enhancement 1: 提出状況・合否ステータス統計

**Objective**: As a 講師, I want グループ一覧で各グループの提出状況・合否統計を確認できる, so that グループ全体の進捗を把握できる

**Scope**:
- グループカードに「提出済み/未提出」「合格/不合格」の統計を追加
- GroupStats型に `submittedCount`, `passedCount`, `failedCount` フィールド追加
- useGroupStats.tsでfilesコレクションとのJOINクエリ実装

**Complexity**: Medium（Firestoreクエリ最適化が課題）

**Estimated Effort**: 5-8時間

---

#### Enhancement 2: 受講生一覧の高度なフィルタリング

**Objective**: As a 講師, I want 受講生一覧で提出状況・合否でフィルタできる, so that 未提出者や不合格者を素早く特定できる

**Scope**:
- フィルタUI追加: ドロップダウンまたはチェックボックス
  - 提出状況: 全員/提出済み/未提出
  - 合否状況: 全員/合格/不合格/未採点
  - 在籍状況: 在籍中/退会済み
- フィルタロジック実装: computed内での複合条件

**Complexity**: Low

**Estimated Effort**: 3-5時間

---

#### Enhancement 3: 受講生詳細モーダル化

**Objective**: As a 講師, I want 受講生詳細をモーダルで表示できる, so that ページ遷移なしで詳細確認できる

**Scope**:
- StudentDetailView.vueをモーダルコンポーネントに変換
- ルーティング戦略: `/students/:id` を modal=true パラメータで制御
- Escape キー、背景クリックで閉じる動作

**Complexity**: Medium（既存ページ遷移の破壊的変更の可能性）

**Estimated Effort**: 4-6時間

**Risk**: 既存のブックマークURL（/students/:id）が機能しなくなる可能性

---

#### Enhancement 4: グループ統計のリアルタイム更新

**Objective**: As a 講師, I want グループ統計がリアルタイムに更新される, so that 最新の提出状況を常に確認できる

**Scope**:
- useGroupStats.tsで `getDocs()` → `onSnapshot()` に変更
- リアルタイムリスナーのライフサイクル管理

**Complexity**: Low

**Estimated Effort**: 2-3時間

**Trade-off**: Firestoreコスト増加（onSnapshot = continuous read）

---

#### Enhancement 5: サーバーサイド集計（Cloud Functions）

**Objective**: As a system, I want グループ統計をサーバーサイドで事前集計する, so that クライアントの負荷とFirestoreコストを削減できる

**Scope**:
- Cloud Functionで定期集計（Firestore Trigger or Scheduled Function）
- 集計結果を`group_stats/{className}/{taskId}`に保存
- useGroupStats.tsを集計結果読み取りに変更

**Complexity**: High（インフラ追加、デプロイパイプライン変更）

**Estimated Effort**: 10-15時間

**Benefit**: O(N) reads → O(M) reads (M = number of groups << N)

---

### 優先度評価

| Enhancement | Priority | Value | Effort | ROI |
|-------------|----------|-------|--------|-----|
| E1: 提出状況・合否統計 | High | High | Medium | High |
| E2: 高度なフィルタリング | Medium | Medium | Low | High |
| E3: 詳細モーダル化 | Low | Low | Medium | Low |
| E4: リアルタイム更新 | Low | Low | Low | Medium |
| E5: サーバーサイド集計 | Low | High | High | Low |

**推奨順序**: E2 → E1 → E4 → E5 → E3

---

### Phase 3実装検討時の注意事項

1. **E1実装時**: Firestore複合クエリの制限に注意（インデックス作成必須）
2. **E3実装時**: 既存URLの互換性維持（破壊的変更回避）
3. **E5実装時**: GitHub Actions CI/CDにCloud Functions deployステップ追加必要
