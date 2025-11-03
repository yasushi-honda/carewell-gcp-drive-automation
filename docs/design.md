# アーキテクチャ設計ドキュメント

## プロジェクト概要

Carewell Webサービスからの提出ファイル自動収集システム。Cloud Run上で動作し、Cloud Schedulerによって定期実行されます。

## システムアーキテクチャ

```
Cloud Scheduler
  ↓ HTTP Request (cron)
Cloud Run Function (carewell-file-collector)
  ↓ Automation
Carewell Web Service (Playwright)
  ↓ Download
Google Drive (Storage)
  ↓ Metadata
Firestore (Tracking) + Google Sheets (Records)
```

## コンポーネント構成

### 1. Cloud Scheduler
- **役割**: 定期実行トリガー
- **設定**: 毎週水曜日・土曜日 12:00 JST
- **タイムアウト**: attemptDeadline = 900秒（class01-task01）、540秒（その他）

### 2. Cloud Run Function
- **サービス名**: carewell-file-collector
- **リージョン**: asia-northeast1
- **リソース**: 2Gi memory, 1 CPU
- **タイムアウト**: 900秒
- **認証**: github-actions-sa

### 3. Playwright Automation Engine (`src/playwright_automation.py`)
- **役割**: Carewell Webサービスの自動操作
- **主要メソッド**:
  - `navigate_to_task()`: クラス・課題ページへのナビゲーション
  - `get_submission_list()`: 提出ファイル一覧の取得（ページネーション対応）
  - `download_file()`: ファイルのダウンロード

### 4. Firestore Service (`src/firestore_service.py`)
- **役割**: アップロード済みファイルの追跡
- **データベース**: carewell-native (Native Mode)
- **スキーマ**:
  ```
  {class_name}/
    └── {task_id}/
        ├── (metadata fields)
        └── documents/
            └── {composite_key}
                ├── student_id
                ├── student_name
                ├── filename
                ├── submit_date
                ├── drive_file_id
                └── ...
  ```

### 5. Google Drive Service (`src/google_drive_service.py`)
- **役割**: ファイルのアップロード
- **フォルダID**: 1gxt-OVloMfJWi73Yjm4v5bjupKL25Pag

### 6. Sheets Service (`src/sheets_service.py`)
- **役割**: 提出記録の記録
- **スプレッドシートID**: 1R1bsr24uyFf67p7_0I0yUA47ap5uIrJE7n89A9NbRYI

## 主要な設計決定

### 重複チェック早期化（2025-11-04実装）

#### 背景
- 初期実装では、download link取得（約5.5秒/件）の**後**に重複チェックを実施
- 重複ファイル分の処理時間が無駄（149件中44件重複の場合、約4分の無駄）
- 900秒タイムアウトでも処理完了できない

#### 設計アプローチ

**早期重複チェックの統合**:
1. `get_submission_list()` メソッド内で重複チェックを実施
2. download link取得**前**に重複を検出
3. 重複ファイルはdownload link取得をスキップ

**実装詳細**:

1. **Firestore Service拡張** (`src/firestore_service.py:100-150`)
   ```python
   def check_already_uploaded_by_student_date(
       self, class_name, task_id, student_id, submit_date
   ) -> Optional[dict]:
       """
       filenameなしで重複チェック（早期チェック用）
       student_id + submit_date でFirestore検索
       """
   ```

2. **Playwright Automation拡張** (`src/playwright_automation.py:329-558`)
   ```python
   def get_submission_list(
       self,
       class_name: Optional[str] = None,
       task_id: Optional[str] = None,
       firestore_service = None
   ) -> dict:
       """
       各ページで：
       1. 基本情報取得
       2. 早期重複チェック（Firestore）← 新規追加
       3. download link取得（非重複のみ）← 最適化
       """
   ```

3. **Main処理フロー更新** (`src/main.py:107-156`)
   ```python
   # get_submission_list呼び出し時にFirestore serviceを渡す
   submission_data = engine.get_submission_list(
       class_name=class_name,
       task_id=task_id,
       firestore_service=firestore_service
   )

   # 処理ループで早期チェック結果を尊重
   for submission in submissions:
       if submission.get("is_duplicate", False):
           # 早期チェックで検出済み、スキップ
           continue

       # Defense-in-depth: filenameでも再チェック
       existing_upload = firestore_service.check_already_uploaded(...)
   ```

#### パフォーマンス改善

| シナリオ | 改善前 | 改善後 | 短縮 |
|---------|--------|--------|------|
| 初回実行（149件新規） | 約24-30分 | 約24-30分 | - |
| 2回目実行（44件重複） | 約17分 | **約13分** | **4分** |
| 2回目実行（全て重複） | 約17分 | **約3分** | **14分** |

#### トレードオフ

**メリット**:
- ✅ 処理時間の大幅短縮（2回目以降）
- ✅ タイムアウトリスクの低減
- ✅ Firestoreクエリコストの削減（download link取得回数減少）

**デメリット**:
- ❌ Firestoreクエリ回数の増加（全submissionで早期チェック）
- ❌ コードの複雑性増加（2段階の重複チェック）

**選択理由**:
- download link取得の処理時間（5.5秒/件）が支配的
- Firestoreクエリはミリ秒オーダー（影響小）
- 2回目以降の実行が大半（日常運用）

### ページネーション対応（2025-11-03実装）

#### 背景
- 初期実装では1ページ目（100件）のみ処理
- class01-task01で149件（2ページ）あり、2ページ目が未処理

#### 設計アプローチ

**Frame Reference管理**:
1. ASP.NET `__doPostBack`によるページ遷移でframe参照が無効化
2. ページループ開始時とページネーションチェック前にframe参照を更新

**実装詳細** (`src/playwright_automation.py:382-543`):
```python
while True:
    # ページループ開始時: frame参照を更新
    list_frame = self._get_list_frame()

    # 基本情報取得
    # download link取得

    # ページネーションチェック前: frame参照を再更新
    list_frame = self._get_list_frame()

    # 次ページ判定・遷移
```

**待機時間の調整**:
- 1ページ目（frame reload後）: 5秒待機
- 2ページ目以降（page transition後）: 3秒待機

### タイムアウト設定延長（2025-11-03実装）

#### 背景
- デフォルト540秒では149件処理に不足

#### 設定変更
| 項目 | 変更前 | 変更後 |
|------|--------|--------|
| Cloud Scheduler attemptDeadline (class01-task01) | 540秒 | 900秒 |
| Cloud Run timeout (全体) | 540秒 | 900秒 |

#### GitHub Actions対策
- `.github/workflows/deploy.yml`にハードコードされていた540秒を900秒に変更
- 手動設定が自動デプロイで上書きされる問題を解決

## エラーハンドリング戦略

### Fail-Open設計
- Firestore重複チェック失敗時: 重複なしとして処理続行
- Google Drive/Sheetsアップロード失敗時: ログ記録のみ、処理続行
- **理由**: 高可用性優先（一部失敗でも全体を止めない）

### Defense-in-Depth
- 早期重複チェック + filename付き重複チェックの2段階チェック
- **理由**: 早期チェックの精度を完全に信頼せず、安全性を確保

## 将来の改善候補

### パフォーマンス最適化
1. **並列処理**: 複数ファイルの同時ダウンロード（要検討：Carewell側の負荷）
2. **待機時間の最適化**: 動的な待機時間調整（ページロード検出）
3. **Firestoreインデックス**: `student_id` + `submit_date` 複合インデックス

### 機能拡張
1. **リトライ機構**: 一時的なエラーの自動リトライ
2. **通知機能**: 処理完了/エラー時のSlack/Email通知
3. **ダッシュボード**: 処理状況の可視化（dashboard/）

### 保守性向上
1. **テストカバレッジ拡大**: 統合テストの追加
2. **設定外部化**: タイムアウト等をCloud Secretsで管理
3. **ログ集約**: Cloud Loggingの構造化ログ活用

---

**最終更新**: 2025-11-04
**担当者**: Claude Code
