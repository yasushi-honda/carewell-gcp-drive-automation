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
      json: async () => ({
        status: 'success',
        classes: [{ class_name: 'No1', status: 'ok', synced: 5, created: 5, updated: 0 }],
      }),
    } as any);

    const { syncStudents } = useStudentSync();
    const result = await syncStudents();

    expect(result.status).toBe('success');
    const [, requestInit] = vi.mocked(fetch).mock.calls[0];
    expect((requestInit?.headers as Record<string, string>).Authorization).toBe(
      'Bearer fake-id-token'
    );
  });

  it('dryRun: trueの場合、リクエストボディにdry_run: trueを含める', async () => {
    vi.mocked(useAuth).mockReturnValue({
      getIdToken: vi.fn().mockResolvedValue('fake-id-token'),
    } as any);
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'success', dry_run: true, classes: [] }),
    } as any);

    const { syncStudents } = useStudentSync();
    await syncStudents({ dryRun: true });

    const [, requestInit] = vi.mocked(fetch).mock.calls[0];
    const body = JSON.parse(requestInit?.body as string);
    expect(body).toEqual({ dry_run: true });
  });

  it('409応答(フェーズA中断)はHTTPエラーにせず、abortedのJSONをそのまま返す', async () => {
    vi.mocked(useAuth).mockReturnValue({
      getIdToken: vi.fn().mockResolvedValue('fake-id-token'),
    } as any);
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({
        status: 'aborted',
        error_classes: [{ class_name: 'No5', status: 'read_error', error: 'permission denied' }],
      }),
    } as any);

    const { syncStudents } = useStudentSync();
    const result = await syncStudents();

    expect(result.status).toBe('aborted');
    expect(result.error_classes?.[0].class_name).toBe('No5');
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
