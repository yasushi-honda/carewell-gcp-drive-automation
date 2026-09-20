# Dashboard モバイル計測ゲート（段階0）: 手順・基準値・スクリプト

Dashboard（`https://carewell-dashboard-2026.web.app/`）のモバイル対応（表示崩れ・読み込み遅延）で、**修正前後を同一条件で比較する**ための計測手順と修正前の基準値。
各段階（読込高速化 → ヘッダー → 表のカード化）のマージ後に、この手順で再計測して GO/NO-GO を判定する。

- 計測日: 2026-09-20（`main` = `34e97d4`、配信 JS `index-BYXiGcVp.js` 時点）
- 計測者: Claude Code（Playwright MCP）。実機ではなくエミュレーション（限界は末尾）
- 制約: `dashboard/` でのローカル `npm run` は禁止（`dashboard/` 配下の CLAUDE.md 規約）。計測は本番 URL に対する Playwright MCP のみ。CI では実行しない

## 1. 計測条件

| 項目 | 値 |
|---|---|
| ビューポート | 390×844、DPR 3、`isMobile`、`hasTouch` |
| コンテキスト | **毎回 fresh context**（キャッシュ・IndexedDB なし＝初回訪問） |
| 回数 | 各条件 **5回**、中央値と最悪値を採用 |
| ネットワーク（`slow4g`） | latency 150ms / 下り 1.6Mbps / 上り 750Kbps、CPU 4倍遅延 |
| ネットワーク（`lat400`） | latency 400ms / 下り 1.6Mbps / 上り 750Kbps、CPU 4倍遅延（3G相当の悪条件） |
| ネットワーク（`none`） | 絞りなし |
| 認証 | 未ログイン（匿名） |

## 2. 指標の定義（ナビゲーション開始 = 0ms）

| 指標 | 意味 |
|---|---|
| `dcl` / `load` | `domContentLoadedEventEnd` / `loadEventEnd`（Hosting の HTML+JS 到着〜評価） |
| `firstFsResp` | 最初の Firestore レスポンス受信 |
| `dataVisible`（`firstDataVisible`） | 対象データが画面に出た最初の時刻（`performance.now()`、50ms ポーリング） |
| `lastFsEnd` | 最後の Firestore リクエスト完了 |
| `fsReq` / `kb` | Firestore リクエスト本数 / 総転送量（KB） |

「データが出た」の判定条件（画面別）:
- `home`（`/`）: 本文中の「提出ファイル数」が10個以上（10クラスのカード）
- `class`（課題一覧）: 本文に「提出受講生数」が出現
- `files`（ファイル一覧）: `table tbody tr` が13行以上
- `students`（`/students`）: `table tbody tr` が254行以上

## 3. 基準値（修正前・2026-09-20）

### 3.1 `dataVisible` 中央値（ms）（最悪値、括弧内は5回の範囲）

| 画面 | none | slow4g | lat400 |
|---|---|---|---|
| **`/`（クラス一覧）** | **1331**（最悪1553） | **3210**（最悪3318） | **4823**（最悪4871） |
| 課題一覧 | 502（最悪527） | 1963（最悪2088） | 3208（最悪3462） |
| ファイル一覧 | 352（最悪474） | 1854（最悪2149） | — |
| 受講生一覧 | 444（最悪738） | 1957（最悪2384） | — |

分離指標（中央値）:

| 画面・条件 | dcl | firstFsResp | dataVisible | lastFsEnd | fsReq |
|---|---|---|---|---|---|
| `/` none | 187 | 280 | 1331 | 1325 | 41 |
| `/` slow4g | 1096 | 1552 | 3210 | 3166 | 41 |
| `/` lat400 | 1592 | 2552 | 4823 | 4746 | 37 |
| 課題一覧 none | 201 | 319 | 502 | 488 | 7 |
| 課題一覧 slow4g | 1099 | 1575 | 1963 | 1933 | 7 |
| 課題一覧 lat400 | 1603 | 2579 | 3208 | 2578 | 7 |

転送量はどの画面も約136〜140KB。

### 3.2 読み取り
- **クラス一覧（`/`）だけが突出して遅い**。他の画面の約2.5〜3.8倍（none）。入口の画面であり、「スマホで開くと遅い」の報告と整合する。
- 課題一覧（Firestore 7本）の中央値が、クラス一覧を高速化したときの**下限の目安**になる（同一 shell・同一転送量で、Firestore 段階のみ小さい）。クラス一覧が下限に近づいたときの最大短縮幅は、none で約62%、slow4g で約39%、lat400 で約33%。したがって「どの条件でも50%短縮」は**達成不能**で、合否線は下限基準にする（§5）。
- クラス一覧の Firestore 段階（`dataVisible − firstFsResp`）は none 約1.05s、slow4g 約1.66s、lat400 約2.27s。他画面は none 約0.18s、slow4g 約0.39s。

### 3.3 ウォーターフォール（`/` none、Firestore のみ）
- Firestore リクエスト41本＝Listen POST 40本＋Listen GET 1本。POST は**約2本ずつ組**で、321ms〜1494ms に約30〜60ms 間隔で順次発行（同時発行の形跡なし）。1組が `getDoc` 1件（20件×2本＝40本）に相当。
- GET 1本は完了しない長寿命の接続（ストリーミング）。この環境では long-polling へのフォールバックは観測されなかった（実回線での有無は未確認）。
- 出典: `getDoc` は SDK 内で Listen ストリーム経由（`@firebase/firestore` の `firestoreClientGetDocumentViaSnapshotListener`）。`experimentalAutoDetectLongPolling` は未指定時に既定 `true`（インストール版 firebase 10.14.1 / @firebase/firestore 4.7.3 のコードで確認）。

### 3.4 ヘッダー基準値（未ログイン、`/`、ms/px）

| 幅 | ヘッダー高 | タイトル | 年度バッジ | ナビリンク（幅×高） | 認証ボタン | scrollW / clientW | ヘッダー内操作 44px未満 |
|---|---|---|---|---|---|---|---|
| 320 | 202 | 154×72 | 34×104 | 38×116, 38×116 | 幅40（x=324＝**画面外**） | **363 / 320（横スクロール発生）** | 3/4 |
| 390 | 202 | 154×72 | 34×104 | 38×116, 38×116 | 50×154 | 390 / 390 | 2/4 |
| 768 | 120 | 282×72 | 85×44 | 93×56, 94×56 | 122×54 | 768 / 768 | 0/4 |
| 1280 | 84 | 283×36 | 85×24 | 93×36, 94×36 | 123×34 | 1280 / 1280 | 4/4（高さ36px） |

- 1280px の座標（各要素 x/y）: タイトル x=32,y=24 ／ バッジ x=327,y=30 ／ ナビ x=906,1015（y=24）／ 認証 x=1125,y=25。修正後の回帰比較（±2px）に使う。
- 1280px の操作要素は高さ36px。**44px以上の要件はタッチ幅（<1024px）に適用**し、1280px は現状維持とする（さもないと「1280px 不変」と矛盾）。

### 3.5 その他の画面（@390px）
- 受講生詳細（`/students/:id`）: 横はみ出しなし、画面外要素0、`<table>` なし。段階3の対象外でよい。
- `/students`: 表幅1012px・画面外要素1537／グループ内受講生: 表幅812px・画面外要素60（段階3で対応）。

## 4. 手順

`browser_run_code_unsafe` の `filename` に渡せるのは、リポジトリ直下と `.playwright-mcp/` 配下のみ。テンプレートの3つのプレースホルダを `sed` で置換し、`.playwright-mcp/measure/`（gitignore 済み）に生成して実行する。

```bash
mkdir -p .playwright-mcp/measure
# 1. 本ドキュメント末尾の ```js ブロック（計測スクリプト）を取り出す
awk '/^```js$/{f=1;next} /^```$/{f=0} f' docs/dashboard-mobile-measurement.md \
  > .playwright-mcp/measure/measure_template.js
# 2. 例: クラス一覧を slow4g で5回（screen: home|class|files|students / profile: none|slow4g|lat400）
sed -e "s/__SCREEN__/home/" -e "s/__PROFILE__/slow4g/" -e "s/__RUNS__/5/" \
  .playwright-mcp/measure/measure_template.js > .playwright-mcp/measure/measure_home_slow4g.js
```

3. Playwright MCP の `browser_run_code_unsafe` に `filename`（上で生成した絶対パス）を指定して実行する。測定は互いに干渉するので**順番に**実行する。
4. 出力の `median` / `worstDataVisible` / `dataVisibleRuns` を §3 の表と比較する。

### 計測スクリプト

```js
async (page) => {
  // ==== 設定（ここだけ書き換えて実行する）====
  const cfg = { screen: '__SCREEN__', profile: '__PROFILE__', runs: __RUNS__ };
  // screen : home | class | files | students
  // profile: none | slow4g | lat400
  // ===========================================
  const base = 'https://carewell-dashboard-2026.web.app';
  const cls = encodeURIComponent('令和8年度 デジタル中核人材養成研修 №01');
  const task = encodeURIComponent('課題①');
  const screens = {
    home:     { path: '/',                              cond: "(document.body.innerText.match(/提出ファイル数/g) || []).length >= 10" },
    class:    { path: '/class/' + cls,                  cond: "document.body.innerText.includes('提出受講生数')" },
    files:    { path: '/class/' + cls + '/task/' + task, cond: "document.querySelectorAll('table tbody tr').length >= 13" },
    students: { path: '/students',                      cond: "document.querySelectorAll('table tbody tr').length >= 254" },
  };
  const profiles = {
    none:   { net: null, cpu: 1 },
    slow4g: { net: { latency: 150, downloadThroughput: 1.6 * 1024 * 1024 / 8, uploadThroughput: 750 * 1024 / 8 }, cpu: 4 },
    lat400: { net: { latency: 400, downloadThroughput: 1.6 * 1024 * 1024 / 8, uploadThroughput: 750 * 1024 / 8 }, cpu: 4 },
  };
  const sc = screens[cfg.screen], pf = profiles[cfg.profile];
  const browser = page.context().browser();
  const median = a => { const s = [...a].sort((x, y) => x - y); const m = Math.floor(s.length / 2); return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
  const rows = [];
  for (let i = 0; i < cfg.runs; i++) {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true });
    const p = await ctx.newPage();
    const cdp = await ctx.newCDPSession(p);
    await cdp.send('Network.enable');
    if (pf.net) await cdp.send('Network.emulateNetworkConditions', Object.assign({ offline: false }, pf.net));
    if (pf.cpu > 1) await cdp.send('Emulation.setCPUThrottlingRate', { rate: pf.cpu });
    const reqs = {}; let docStart = null; let kb = 0; const fsRespTimes = []; const fsEndTimes = [];
    cdp.on('Network.requestWillBeSent', e => { reqs[e.requestId] = { url: e.request.url, t: e.timestamp }; if (docStart === null && e.type === 'Document') docStart = e.timestamp; });
    cdp.on('Network.responseReceived', e => { const r = reqs[e.requestId]; if (r && r.url.indexOf('firestore.googleapis.com') >= 0) fsRespTimes.push(e.timestamp); });
    cdp.on('Network.loadingFinished', e => { kb += e.encodedDataLength; const r = reqs[e.requestId]; if (r && r.url.indexOf('firestore.googleapis.com') >= 0) fsEndTimes.push(e.timestamp); });
    await p.goto(base + sc.path, { waitUntil: 'commit', timeout: 60000 });
    await p.waitForFunction("(() => { if (" + sc.cond + ") { window.__tv = window.__tv || performance.now(); return true; } return false; })()", null, { timeout: 120000, polling: 50 });
    const t = await p.evaluate(() => {
      const n = performance.getEntriesByType('navigation')[0];
      return { dcl: n.domContentLoadedEventEnd, load: n.loadEventEnd || null, dataVisible: window.__tv };
    });
    const fsCount = Object.values(reqs).filter(r => r.url.indexOf('firestore.googleapis.com') >= 0).length;
    rows.push({
      dcl: Math.round(t.dcl), load: t.load ? Math.round(t.load) : null, dataVisible: Math.round(t.dataVisible),
      firstFsResp: fsRespTimes.length ? Math.round((Math.min.apply(null, fsRespTimes) - docStart) * 1000) : null,
      lastFsEnd: fsEndTimes.length ? Math.round((Math.max.apply(null, fsEndTimes) - docStart) * 1000) : null,
      fsReq: fsCount, kb: Math.round(kb / 1024),
    });
    await ctx.close();
  }
  const col = k => rows.map(r => r[k]).filter(v => v !== null);
  return {
    cfg,
    median: { dcl: median(col('dcl')), load: col('load').length ? median(col('load')) : null, firstFsResp: col('firstFsResp').length ? median(col('firstFsResp')) : null, dataVisible: median(col('dataVisible')), lastFsEnd: col('lastFsEnd').length ? median(col('lastFsEnd')) : null },
    worstDataVisible: Math.max.apply(null, col('dataVisible')),
    dataVisibleRuns: col('dataVisible'),
    fsReq: rows[0].fsReq, kb: rows[0].kb,
  };
}
```

## 5. 各段階の合否線（計測結果を受けて改訂）

段階1（クラス一覧の並列化）の主 AC は、**下限（課題一覧の中央値）基準**とする。同一日・同一条件で課題一覧も測り、次を満たすこと。

| 条件 | クラス一覧の合格線（課題一覧の中央値 × 1.2） | 参考: 修正前からの短縮率 |
|---|---|---|
| none | ≤ 約600ms（課題一覧 502） | 約55% |
| slow4g | ≤ 約2360ms（課題一覧 1963） | 約27% |
| lat400 | ≤ 約3850ms（課題一覧 3208） | 約20% |

加えて、**最悪値が修正前（none 1553 / slow4g 3318 / lat400 4871）を悪化させない**こと、表示内容が不変（10カード・№01 が「提出ファイル数: 13」）であること。
（×1.2 は、クラス一覧が課題一覧より多い読取（20件 vs 数件）を行う分の許容。）

段階2・3 の合否線は計画ファイルの AC に従う。ヘッダー基準は §3.4。

### 5.1 本番実測結果（マージ後・2026-09-20）

各段階はマージ後に本番（`https://carewell-dashboard-2026.web.app/`）で、上記の条件・手順で実測した。判定はいずれも **合格（GO）**。

**段階1（PR #43・クラス一覧の並列化）**: `firstDataVisible` 中央値（ms、5回。括弧内は最悪値）

| 条件 | 修正前 | 修正後 | 合格線（同日の課題一覧×1.2） | 判定 |
|---|---|---|---|---|
| none | 1331（1553） | **359**（1416） | ≤約600 | 合格 |
| slow4g | 3210（3318） | **1900**（1956） | ≤約2360 | 合格 |
| lat400 | 4823（4871） | **3181**（3409） | ≤約3850 | 合格 |

- Firestore リクエスト 41本 → 12本。課題一覧に退行なし（none 502→383、slow4g 1963→1905）。
- none の最悪値1416は5回中1回の外れ値（残り4回は315〜373）。
- lat400 の合格線は、段階0の課題一覧（3208）を基準にした（同日の課題一覧の lat400 は再測していない）。
- 表示は10カード。№01 の提出ファイル数は 13 → 14 になったが、新しい提出が入ったため（Firestore・Drive・提出記録シートと一致。修正による退行ではない）。

**段階2（PR #44・ヘッダー）**: 未ログイン、`/`

| 幅 | ヘッダー高 | scrollW / clientW | ヘッダー内で44px未満 |
|---|---|---|---|
| 320 | 112（修正前 202） | 320 / 320（修正前 363 / 320） | 0/4 |
| 390 | 112（修正前 202） | 390 / 390 | 0/4 |
| 768 | 112（修正前 120） | 768 / 768 | 0/4 |
| 1024 | 84 | 1024 / 1024 | 4/4（高さ36px。<1024pxのみ44px要件） |
| 1280 | 84 | 1280 / 1280 | 4/4（同上） |

- 1280px の座標（タイトル `32,24,283×36`・ナビ x=906/1015・認証 `1125,25,123×34`）は §3.4 の基準値と完全一致。縦折り返しなし（390px のナビ 139×44・バッジ 76×20）。
- 1行に戻る境界は計画の 640px ではなく 1024px（768px でもタイトルが折り返す基準値のため）。

**段階3（PR #45・受講生一覧・グループ内受講生の表をカードに）**: `/students` の切替は 1280px、グループ内受講生は 1024px

| 画面 | 幅 | 結果 |
|---|---|---|
| `/students` | 390 / 768 | 横スクロールなし、画面外要素 0（修正前 1537）、`<table>` なし、カード254枚 |
| `/students` | 1024 / 1279 | 横スクロールなし、画面外要素 0、カード表示（入力欄は44px以上） |
| `/students` | 1280 | 表254行、横スクロールなし、カードなし |
| グループ内受講生（グループ A） | 390 / 768 / 1023 | 横スクロールなし、画面外要素 0（修正前 60）、カード17枚、`<table>` なし |
| グループ内受講生（グループ A） | 1024 / 1280 | 表17行、横スクロールなし |

- `/students` を1024pxではなく1280pxで切り替えたのは、表の最小幅が約1012pxで、1024〜1075px付近では横スクロールが残るため。
- 操作（390px の `/students`）: ふりがな・通し番号の並べ替えが「なし→昇順→降順→なし」で動作、検索で絞り込み、390⇄1280px のリサイズで検索語が保持、カードは Tab でフォーカスリングが出て Enter で詳細へ遷移。
- 未確認: グループ内受講生の本番での並べ替え・キーボード操作（ユニットテストのみ）、A 以外のグループ。パンくずリンクの高さは 390px で40px・768px で20px だが、44px の対象範囲（ヘッダー・カード・フィルタ・ソート）の外で、今回の変更によるものではない。
- 計測に使ったスクリプトは、ドキュメント末尾のものとは別（画面外要素・`<table>`/カードの数・44px未満の操作を数える使い捨て）。手順化していない。

## 6. 限界（誇張しない）
- エミュレーションであり実回線・実機の再現ではない。実機の体感は decision-maker の確認が最終判断。
- 単一地点・単一日の計測。時間帯・Firestore 側の状態で揺れる（5回の範囲を併記）。
- fresh context のみ（再訪・キャッシュ有りは対象外）。
- 未ログイン状態のみ。管理者ログイン時の画面は計測・検証していない（decision-maker の判断で未確認のまま残す）。
- long-polling へのフォールバックはこの環境では観測されなかったが、実回線での有無は未確認。
