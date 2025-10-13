# ブラウザ互換性ガイド

## 対応ブラウザ

Carewell Dashboardは以下のモダンブラウザで動作します：

### デスクトップブラウザ
- **Chrome**: 最新版およびバージョン90以降
- **Firefox**: 最新版およびバージョン88以降
- **Safari**: 最新版およびバージョン14以降
- **Edge**: 最新版およびバージョン90以降

### モバイルブラウザ
- **Chrome for Android**: 最新版
- **Safari on iOS**: バージョン14以降

## 技術スタック

- **Vue 3.4**: Composition API、`<script setup>`構文
- **Vite 5**: ES2015+をサポートするブラウザ向けビルド
- **Firebase 10.7**: モジュラーSDK
- **Tailwind CSS 3.4**: モダンCSS機能

## ブラウザ互換性テスト手順

### 1. Chrome最新版での動作確認

```bash
# テストURL
https://carewell-automation.web.app/
```

**確認項目**:
- [x] クラス一覧の表示
- [x] 課題一覧への遷移
- [x] ファイル一覧の表示とソート
- [x] 検索機能（学生名・学生ID）
- [x] Google Driveリンクの動作
- [x] レスポンシブデザイン（DevToolsでモバイル表示確認）
- [x] パンくずリストのナビゲーション

### 2. Safari最新版での動作確認

**確認項目**:
- [x] 全機能が正常動作するか
- [x] Firestoreデータの取得
- [x] 日本語表示の適切なレンダリング
- [x] タッチ操作（iPadの場合）

### 3. Edge最新版での動作確認

**確認項目**:
- [x] Chromeと同等の動作
- [x] レンダリングの一貫性

### 4. Firefox最新版での動作確認

**確認項目**:
- [x] 全機能が正常動作するか
- [x] CSSレイアウトの一貫性

## E2Eテストによる自動検証

Playwrightを使用した自動E2Eテストで以下のブラウザをカバー：

```typescript
// playwright.config.ts
projects: [
  { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
  { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  { name: 'Mobile Chrome', use: { ...devices['Pixel 5'] } },
  { name: 'Mobile Safari', use: { ...devices['iPhone 12'] } },
]
```

**実行方法**:
```bash
cd dashboard
npm run test:e2e
```

## 非対応ブラウザ

以下のブラウザは**サポート対象外**です：

- Internet Explorer 11以前（2022年6月にサポート終了）
- 古いバージョンのモバイルブラウザ（iOS 13以前、Android 5以前）
- ES2015非対応ブラウザ

### 非対応ブラウザでのアクセス時の動作

現在の実装では、非対応ブラウザでアクセスした場合：
- ページが正常に読み込まれない可能性があります
- JavaScriptエラーが発生する可能性があります

**Phase 1の方針**:
- Phase 1では認証なし・読み取り専用のため、明示的な警告表示は実装していません
- モダンブラウザの使用を前提とした設計です

## トラブルシューティング

### 問題: ページが白紙表示になる

**原因**: JavaScriptエラーまたはFirebaseの初期化失敗

**対処法**:
1. ブラウザのコンソールでエラーを確認
2. ブラウザのキャッシュをクリア
3. ハードリロード（Ctrl+Shift+R / Cmd+Shift+R）

### 問題: データが表示されない

**原因**: Firestore接続エラー

**対処法**:
1. ネットワーク接続を確認
2. Firebaseコンソールでデータが存在することを確認
3. ブラウザのコンソールでエラーログを確認

### 問題: スタイルが崩れる

**原因**: CSSの読み込み失敗またはブラウザ互換性

**対処法**:
1. ハードリロードでCSSをリフレッシュ
2. ブラウザバージョンが対応しているか確認
3. ブラウザの開発者ツールでCSSエラーを確認

## パフォーマンス最適化

### 初期ロード時間
- **目標**: 3秒以内（3G接続環境）
- **対策**: コード分割、遅延ロード、キャッシング

### Lighthouse スコア目標
- Performance: 90+
- Accessibility: 95+
- Best Practices: 95+
- SEO: 90+

## 今後の拡張（Phase 2）

Phase 2では以下の対応を検討：
- 非対応ブラウザ向けの警告バナー表示
- Polyfillの追加（必要に応じて）
- ブラウザ機能検出とグレースフルデグラデーション
