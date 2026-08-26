import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useStudentSync } from '../useStudentSync';
import { useAuth } from '../useAuth';

vi.mock('../useAuth', () => ({
  useAuth: vi.fn(),
}));

describe('useStudentSync', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
  });

  it('未ログイン時はfetchを呼ばずthrowする', async () => {
    vi.mocked(useAuth).mockReturnValue({
      getIdToken: vi.fn().mockResolvedValue(null),
    } as any);

    const { syncStudents } = useStudentSync();

    await expect(syncStudents()).rejects.toThrow('管理者ログインが必要です');
    expect(fetch).not.toHaveBeenCalled();
  });

  it('ログイン済みの場合Authorization: Bearer <token>を付与してfetchする', async () => {
    vi.mocked(useAuth).mockReturnValue({
      getIdToken: vi.fn().mockResolvedValue('fake-id-token'),
    } as any);
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'success', students_synced: 5 }),
    } as any);

    const { syncStudents } = useStudentSync();
    const result = await syncStudents({ backfill: true });

    expect(result.status).toBe('success');
    const [, requestInit] = vi.mocked(fetch).mock.calls[0];
    expect((requestInit?.headers as Record<string, string>).Authorization).toBe(
      'Bearer fake-id-token'
    );
  });

  it('401応答時は「セッションが切れました」エラーになる', async () => {
    vi.mocked(useAuth).mockReturnValue({
      getIdToken: vi.fn().mockResolvedValue('fake-id-token'),
    } as any);
    vi.mocked(fetch).mockResolvedValue({ ok: false, status: 401 } as any);

    const { syncStudents } = useStudentSync();

    await expect(syncStudents()).rejects.toThrow('セッションが切れました');
  });

  it('403応答時は「管理者権限がありません」エラーになる', async () => {
    vi.mocked(useAuth).mockReturnValue({
      getIdToken: vi.fn().mockResolvedValue('fake-id-token'),
    } as any);
    vi.mocked(fetch).mockResolvedValue({ ok: false, status: 403 } as any);

    const { syncStudents } = useStudentSync();

    await expect(syncStudents()).rejects.toThrow('管理者権限がありません');
  });

  it('その他のエラー応答はHTTPステータスを含むエラーになる', async () => {
    vi.mocked(useAuth).mockReturnValue({
      getIdToken: vi.fn().mockResolvedValue('fake-id-token'),
    } as any);
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 500,
      text: async () => 'Internal Server Error',
    } as any);

    const { syncStudents } = useStudentSync();

    await expect(syncStudents()).rejects.toThrow('HTTP 500');
  });
});
