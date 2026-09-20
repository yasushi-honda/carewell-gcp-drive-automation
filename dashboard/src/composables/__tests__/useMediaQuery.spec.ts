import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { effectScope, nextTick } from 'vue';
import { useMediaQuery, BELOW_LG, BELOW_XL } from '../useMediaQuery';

type ChangeListener = (event: MediaQueryListEvent) => void;

/** テスト側から一致状態を切り替えられる MediaQueryList のモック */
function createMediaQueryList(initialMatches: boolean, style: 'modern' | 'legacy' = 'modern') {
  const listeners = new Set<ChangeListener>();
  const mql: Record<string, unknown> = {
    matches: initialMatches,
    media: '',
  };
  if (style === 'modern') {
    mql.addEventListener = vi.fn((_type: string, listener: ChangeListener) => listeners.add(listener));
    mql.removeEventListener = vi.fn((_type: string, listener: ChangeListener) => listeners.delete(listener));
  } else {
    // Safari 13 以前
    mql.addListener = vi.fn((listener: ChangeListener) => listeners.add(listener));
    mql.removeListener = vi.fn((listener: ChangeListener) => listeners.delete(listener));
  }
  return {
    mql: mql as unknown as MediaQueryList & Record<string, ReturnType<typeof vi.fn>>,
    listeners,
    change(matches: boolean) {
      (mql as { matches: boolean }).matches = matches;
      listeners.forEach((listener) => listener({ matches } as MediaQueryListEvent));
    },
  };
}

describe('useMediaQuery', () => {
  const originalMatchMedia = window.matchMedia;

  function stubMatchMedia(impl: ((query: string) => MediaQueryList) | undefined) {
    Object.defineProperty(window, 'matchMedia', { value: impl, writable: true, configurable: true });
  }

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    stubMatchMedia(originalMatchMedia);
  });

  it('should expose the Tailwind lg / xl complements as max-width queries', () => {
    // Tailwind の lg:/xl: は min-width。その補集合（境界の1024px/1280px ちょうどは「以上」側）
    expect(BELOW_LG).toBe('(max-width: 1023.98px)');
    expect(BELOW_XL).toBe('(max-width: 1279.98px)');
  });

  it('should return the current match synchronously (no flash of the wrong layout)', () => {
    const { mql } = createMediaQueryList(true);
    const matchMedia = vi.fn(() => mql);
    stubMatchMedia(matchMedia);

    const matches = useMediaQuery(BELOW_LG);

    expect(matchMedia).toHaveBeenCalledWith(BELOW_LG);
    expect(matches.value).toBe(true);
  });

  it('should return false when the query does not match', () => {
    stubMatchMedia(vi.fn(() => createMediaQueryList(false).mql));

    expect(useMediaQuery(BELOW_LG).value).toBe(false);
  });

  it('should follow changes (rotation / resize)', async () => {
    const control = createMediaQueryList(false);
    stubMatchMedia(vi.fn(() => control.mql));

    const matches = useMediaQuery(BELOW_LG);
    expect(matches.value).toBe(false);

    control.change(true);
    await nextTick();
    expect(matches.value).toBe(true);

    control.change(false);
    await nextTick();
    expect(matches.value).toBe(false);
  });

  it('should stop listening when the owning scope is disposed', () => {
    const control = createMediaQueryList(false);
    stubMatchMedia(vi.fn(() => control.mql));

    const scope = effectScope();
    const matches = scope.run(() => useMediaQuery(BELOW_LG))!;
    expect(control.listeners.size).toBe(1);

    scope.stop();

    expect(control.mql.removeEventListener).toHaveBeenCalledTimes(1);
    expect(control.listeners.size).toBe(0);
    // 破棄後の変化は反映しない
    control.change(true);
    expect(matches.value).toBe(false);
  });

  it('should fall back to addListener / removeListener on old browsers', () => {
    const control = createMediaQueryList(false, 'legacy');
    stubMatchMedia(vi.fn(() => control.mql));

    const scope = effectScope();
    const matches = scope.run(() => useMediaQuery(BELOW_LG))!;
    expect(control.mql.addListener).toHaveBeenCalledTimes(1);

    control.change(true);
    expect(matches.value).toBe(true);

    scope.stop();
    expect(control.mql.removeListener).toHaveBeenCalledTimes(1);
    expect(control.listeners.size).toBe(0);
  });

  it('should be false (the wide layout) when matchMedia is unavailable', () => {
    stubMatchMedia(undefined);

    expect(useMediaQuery(BELOW_LG).value).toBe(false);
  });

  it('should not require an active scope (no cleanup registered, no error)', () => {
    const control = createMediaQueryList(true);
    stubMatchMedia(vi.fn(() => control.mql));

    // effectScope の外で呼んでも例外にならない（破棄フックが無いだけ）
    expect(() => useMediaQuery(BELOW_LG)).not.toThrow();
  });
});
