// テスト用: window.matchMedia を「画面幅」でシミュレートする
//
// happy-dom はレイアウトを持たないため、`(max-width: Npx)` 形式のクエリだけを、
// テストが指定した幅で評価する（useMediaQuery / BELOW_LG / BELOW_XL 用）。

type Listener = (event: MediaQueryListEvent) => void;

let width = 1280;
let registered: Array<{ query: string; listener: Listener }> = [];
const originalMatchMedia = window.matchMedia;

function evaluate(query: string): boolean {
  const match = /max-width:\s*([\d.]+)px/.exec(query);
  return match ? width <= Number(match[1]) : false;
}

/** matchMedia を差し替え、指定の幅から開始する */
export function installViewport(initialWidth: number): void {
  width = initialWidth;
  registered = [];
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: (query: string) => ({
      get matches() {
        return evaluate(query);
      },
      media: query,
      addEventListener: (_type: string, listener: Listener) => {
        registered.push({ query, listener });
      },
      removeEventListener: (_type: string, listener: Listener) => {
        registered = registered.filter((entry) => entry.listener !== listener);
      },
    }),
  });
}

/** 画面幅を変える（回転・リサイズ）。購読中のリスナーへ change を通知する */
export function resizeTo(nextWidth: number): void {
  width = nextWidth;
  registered.forEach(({ query, listener }) => listener({ matches: evaluate(query) } as MediaQueryListEvent));
}

/** 元の matchMedia に戻す */
export function resetViewport(): void {
  registered = [];
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: originalMatchMedia,
  });
}
