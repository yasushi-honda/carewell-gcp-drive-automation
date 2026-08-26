import { describe, it, expect, vi, beforeEach } from 'vitest';
import { onAuthStateChanged, type User } from 'firebase/auth';
import { getDoc } from 'firebase/firestore';

vi.mock('../../config/firebase', () => ({
  getAuthInstance: vi.fn(() => ({})),
  getDb: vi.fn(() => ({})),
}));

vi.mock('firebase/firestore', () => ({
  doc: vi.fn(),
  getDoc: vi.fn(),
}));

vi.mock('firebase/auth', () => ({
  getAuth: vi.fn(() => ({})),
  onAuthStateChanged: vi.fn(),
  signInWithPopup: vi.fn(),
  signOut: vi.fn(),
  GoogleAuthProvider: vi.fn(),
}));

/** onAuthStateChangedのコールバックを捕捉するヘルパー */
function captureAuthCallback() {
  let callback: ((user: User | null) => void) | undefined;
  vi.mocked(onAuthStateChanged).mockImplementation((_auth, cb) => {
    callback = cb as (user: User | null) => void;
    return vi.fn();
  });
  return () => callback;
}

describe('useAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  it('複数回useAuth()を呼んでもonAuthStateChangedのリスナー登録は1回だけ', async () => {
    const getCallback = captureAuthCallback();
    const { useAuth } = await import('../useAuth');

    useAuth();
    useAuth();
    useAuth();

    expect(onAuthStateChanged).toHaveBeenCalledTimes(1);
    expect(getCallback()).toBeDefined();
  });

  it('管理者メールでログインするとisAdminがtrueになる', async () => {
    vi.mocked(getDoc).mockResolvedValue({ exists: () => true } as any);
    const getCallback = captureAuthCallback();

    const { useAuth } = await import('../useAuth');
    const { user, isAdmin, authReady } = useAuth();

    const fakeUser = { email: 'Admin@Example.com' } as User;
    await getCallback()!(fakeUser);

    // user.valueはVueのreadonly()でProxyラップされるため、toBeでの参照比較は
    // 常に失敗する（内容が同じでも別オブジェクト扱い）。内容の一致で検証する。
    expect(user.value?.email).toBe('Admin@Example.com');
    expect(isAdmin.value).toBe(true);
    expect(authReady.value).toBe(true);
  });

  it('admins/{email}が存在しない場合はisAdminがfalseになる', async () => {
    vi.mocked(getDoc).mockResolvedValue({ exists: () => false } as any);
    const getCallback = captureAuthCallback();

    const { useAuth } = await import('../useAuth');
    const { isAdmin } = useAuth();

    await getCallback()!({ email: 'nobody@example.com' } as User);

    expect(isAdmin.value).toBe(false);
  });

  it('Firestore参照が例外を投げた場合はisAdminがfalseになる（fail-closed）', async () => {
    vi.mocked(getDoc).mockRejectedValue(new Error('Firestore unavailable'));
    const getCallback = captureAuthCallback();

    const { useAuth } = await import('../useAuth');
    const { isAdmin } = useAuth();

    await getCallback()!({ email: 'admin@example.com' } as User);

    expect(isAdmin.value).toBe(false);
  });

  it('emailを持たないユーザーはisAdminがfalseになる', async () => {
    const getCallback = captureAuthCallback();

    const { useAuth } = await import('../useAuth');
    const { isAdmin } = useAuth();

    await getCallback()!({ email: null } as unknown as User);

    expect(isAdmin.value).toBe(false);
    expect(getDoc).not.toHaveBeenCalled();
  });

  it('ログアウト時はuser/isAdminがリセットされる', async () => {
    vi.mocked(getDoc).mockResolvedValue({ exists: () => true } as any);
    const getCallback = captureAuthCallback();

    const { useAuth } = await import('../useAuth');
    const { user, isAdmin } = useAuth();

    await getCallback()!({ email: 'admin@example.com' } as User);
    expect(isAdmin.value).toBe(true);

    await getCallback()!(null);
    expect(user.value).toBeNull();
    expect(isAdmin.value).toBe(false);
  });

  it('古いadminチェックが新しいログアウトイベントの結果を上書きしない（レース条件の回帰テスト）', async () => {
    let resolveFirstCheck!: (value: { exists: () => boolean }) => void;
    const firstCheckPromise = new Promise<{ exists: () => boolean }>((resolve) => {
      resolveFirstCheck = resolve;
    });
    vi.mocked(getDoc).mockReturnValueOnce(firstCheckPromise as any);

    const getCallback = captureAuthCallback();
    const { useAuth } = await import('../useAuth');
    const { user, isAdmin } = useAuth();

    // イベント1: 管理者としてログイン（Firestore確認がpendingのまま止まる）
    const firstEventDone = getCallback()!({ email: 'admin@example.com' } as User);

    // イベント2: 直後にログアウト（同期的にuser/isAdminがリセットされる）
    await getCallback()!(null);
    expect(user.value).toBeNull();
    expect(isAdmin.value).toBe(false);

    // イベント1のFirestore確認が今頃解決する（本来は管理者だった）
    resolveFirstCheck({ exists: () => true });
    await firstEventDone;

    // 古いイベントの結果でisAdminが誤ってtrueに戻っていないこと
    expect(user.value).toBeNull();
    expect(isAdmin.value).toBe(false);
  });

  it('waitUntilReadyはauthStateChangedの初回発火後に解決する', async () => {
    vi.mocked(getDoc).mockResolvedValue({ exists: () => false } as any);
    const getCallback = captureAuthCallback();

    const { useAuth } = await import('../useAuth');
    const { authReady, waitUntilReady } = useAuth();

    expect(authReady.value).toBe(false);

    const readyPromise = waitUntilReady();
    await getCallback()!({ email: 'x@example.com' } as User);
    await readyPromise;

    expect(authReady.value).toBe(true);
  });

  it('getIdTokenは未ログイン時にnullを返す', async () => {
    captureAuthCallback();
    const { useAuth } = await import('../useAuth');
    const { getIdToken } = useAuth();

    expect(await getIdToken()).toBeNull();
  });

  it('getIdTokenはログイン済みユーザーのトークンを返す', async () => {
    vi.mocked(getDoc).mockResolvedValue({ exists: () => true } as any);
    const getCallback = captureAuthCallback();

    const { useAuth } = await import('../useAuth');
    const { getIdToken } = useAuth();

    const fakeUser = {
      email: 'admin@example.com',
      getIdToken: vi.fn().mockResolvedValue('fake-id-token'),
    } as unknown as User;
    await getCallback()!(fakeUser);

    expect(await getIdToken()).toBe('fake-id-token');
  });
});
