import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getDocuments, getTaskDocument, getErrorMessage } from '../useFirestore';
import * as firebaseConfig from '../../config/firebase';
import { getDocs, getDoc, collection, doc } from 'firebase/firestore';

// Mock Firebase config
vi.mock('../../config/firebase', () => ({
  getDb: vi.fn(() => ({ name: 'mock-db' })),
}));

// Mock Firestore functions
vi.mock('firebase/firestore', () => ({
  collection: vi.fn(),
  getDocs: vi.fn(),
  doc: vi.fn(),
  getDoc: vi.fn(),
}));

describe('useFirestore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getDocuments', () => {
    it('should fetch documents from a collection', async () => {
      const mockDocs = [
        {
          id: 'doc1',
          data: () => ({ field1: 'value1', field2: 123 }),
        },
        {
          id: 'doc2',
          data: () => ({ field1: 'value2', field2: 456 }),
        },
      ];

      const mockSnapshot = {
        docs: mockDocs,
      };

      vi.mocked(collection).mockReturnValue({ path: 'test-collection' } as any);
      vi.mocked(getDocs).mockResolvedValue(mockSnapshot as any);

      const result = await getDocuments('test-collection');

      expect(result).toHaveLength(2);
      expect(result[0]).toEqual({ id: 'doc1', field1: 'value1', field2: 123 });
      expect(result[1]).toEqual({ id: 'doc2', field1: 'value2', field2: 456 });
      expect(firebaseConfig.getDb).toHaveBeenCalled();
      expect(collection).toHaveBeenCalled();
      expect(getDocs).toHaveBeenCalled();
    });

    it('should handle Firestore Timestamps correctly', async () => {
      const mockTimestamp = {
        toDate: () => new Date('2025-10-13T10:00:00Z'),
      };

      const mockDocs = [
        {
          id: 'doc1',
          data: () => ({ created_at: mockTimestamp }),
        },
      ];

      const mockSnapshot = {
        docs: mockDocs,
      };

      vi.mocked(collection).mockReturnValue({ path: 'test-collection' } as any);
      vi.mocked(getDocs).mockResolvedValue(mockSnapshot as any);

      const result = await getDocuments('test-collection');

      expect(result[0].created_at).toBe('2025-10-13T10:00:00.000Z');
    });

    it('should throw error on Firestore failure', async () => {
      vi.mocked(getDocs).mockRejectedValue(new Error('Firestore error'));

      await expect(getDocuments('test-collection')).rejects.toThrow('Firestore error');
    });
  });

  describe('getTaskDocument', () => {
    it('should fetch task document with metadata', async () => {
      const mockTimestamp = {
        toDate: () => new Date('2025-10-13T10:00:00Z'),
      };

      const mockDocSnap = {
        exists: () => true,
        data: () => ({
          task_id: '課題①',
          task_pattern: '課題①',
          file_count: 5,
          created_at: mockTimestamp,
          last_updated: mockTimestamp,
        }),
      };

      vi.mocked(doc).mockReturnValue({ path: 'class/task' } as any);
      vi.mocked(getDoc).mockResolvedValue(mockDocSnap as any);

      const result = await getTaskDocument('令和7年度 デジタル中核人材養成研修 №01', '課題①');

      expect(result).toEqual({
        task_id: '課題①',
        task_pattern: '課題①',
        file_count: 5,
        created_at: '2025-10-13T10:00:00.000Z',
        last_updated: '2025-10-13T10:00:00.000Z',
      });
      expect(doc).toHaveBeenCalled();
      expect(getDoc).toHaveBeenCalled();
    });

    it('should return null if document does not exist', async () => {
      const mockDocSnap = {
        exists: () => false,
      };

      vi.mocked(doc).mockReturnValue({ path: 'class/task' } as any);
      vi.mocked(getDoc).mockResolvedValue(mockDocSnap as any);

      const result = await getTaskDocument('令和7年度 デジタル中核人材養成研修 №01', '課題①');

      expect(result).toBeNull();
    });

    it('should throw error on Firestore failure', async () => {
      vi.mocked(getDoc).mockRejectedValue(new Error('Firestore error'));

      await expect(
        getTaskDocument('令和7年度 デジタル中核人材養成研修 №01', '課題①')
      ).rejects.toThrow('Firestore error');
    });
  });

  describe('getErrorMessage', () => {
    it('should return permission denied message', () => {
      const error = new Error('permission-denied: Access denied');
      const message = getErrorMessage(error);
      expect(message).toBe('アクセス権限がありません');
    });

    it('should return network error message', () => {
      const error = new Error('Failed to fetch');
      const message = getErrorMessage(error);
      expect(message).toBe('ネットワーク接続を確認してください');
    });

    it('should return generic error message for unknown errors', () => {
      const error = new Error('Unknown error');
      const message = getErrorMessage(error);
      expect(message).toContain('データの取得に失敗しました');
    });

    it('should handle non-Error objects', () => {
      const message = getErrorMessage('string error');
      expect(message).toBe('データの取得に失敗しました');
    });
  });
});
