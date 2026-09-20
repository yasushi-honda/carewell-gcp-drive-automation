// src/composables/useMediaQuery.ts
// CSS メディアクエリの一致状態を reactive に扱う（<lg でカード、≥lg で表、のような単一描画の切替用）

import { getCurrentScope, onScopeDispose, readonly, ref, type Ref } from 'vue';

/**
 * Tailwind の `lg`(1024px) / `xl`(1280px) 未満。
 * Tailwind のブレークポイントは `min-width` なので、その補集合として `max-width: <bp - 0.02px>` を使う
 * （1024px ちょうどは「lg 以上」側になり、CSS の `lg:` と境界が一致する）。
 * tailwind.config.js のブレークポイントを変える場合はここも合わせること。
 */
export const BELOW_LG = '(max-width: 1023.98px)';
export const BELOW_XL = '(max-width: 1279.98px)';

/**
 * メディアクエリの一致状態を返す。
 *
 * - 初回描画から正しい値になる（setup 時点で同期的に評価するため、表→カードのちらつきが出ない）
 * - 画面幅の変更（回転・リサイズ）に追従する
 * - コンポーネント（effect scope）の破棄時に購読を解除する
 * - `matchMedia` が使えない環境では常に false（＝従来の表示）
 *
 * @param query - CSS メディアクエリ（例: `(max-width: 1023.98px)`）
 */
export function useMediaQuery(query: string): Readonly<Ref<boolean>> {
  const mediaQueryList =
    typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      ? window.matchMedia(query)
      : null;

  const matches = ref(mediaQueryList ? mediaQueryList.matches : false);

  if (mediaQueryList) {
    const onChange = (event: MediaQueryListEvent) => {
      matches.value = event.matches;
    };

    // Safari 13 以前は addEventListener を持たず addListener のみ
    if (typeof mediaQueryList.addEventListener === 'function') {
      mediaQueryList.addEventListener('change', onChange);
    } else if (typeof mediaQueryList.addListener === 'function') {
      mediaQueryList.addListener(onChange);
    }

    if (getCurrentScope()) {
      onScopeDispose(() => {
        if (typeof mediaQueryList.removeEventListener === 'function') {
          mediaQueryList.removeEventListener('change', onChange);
        } else if (typeof mediaQueryList.removeListener === 'function') {
          mediaQueryList.removeListener(onChange);
        }
      });
    }
  }

  return readonly(matches);
}
