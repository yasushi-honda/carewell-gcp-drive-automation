// src/composables/useGroupList.ts
// グループ一覧とサービス種別一覧の取得

import { ref, Ref } from 'vue';
import { collection, getDocs } from 'firebase/firestore';
import { getDb } from '../config/firebase';

interface UseGroupListReturn {
  groups: Ref<string[]>;
  serviceTypes: Ref<string[]>;
  loading: Ref<boolean>;
  error: Ref<string | null>;
  fetchLists: () => Promise<void>;
}

/**
 * グループ一覧とサービス種別一覧を取得するComposable
 *
 * @returns グループ・サービス種別一覧と取得関数
 *
 * @example
 * const { groups, serviceTypes, loading, fetchLists } = useGroupList();
 * await fetchLists();
 */
export function useGroupList(): UseGroupListReturn {
  const groups = ref<string[]>([]);
  const serviceTypes = ref<string[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const fetchLists = async (): Promise<void> => {
    loading.value = true;
    error.value = null;

    try {
      const db = getDb();
      const snapshot = await getDocs(collection(db, 'students'));

      // 一意の値を Set で収集
      const groupSet = new Set<string>();
      const serviceSet = new Set<string>();

      snapshot.docs.forEach((doc) => {
        const data = doc.data();
        if (data.group && data.group.trim()) {
          groupSet.add(data.group);
        }
        if (data.service_type && data.service_type.trim()) {
          serviceSet.add(data.service_type);
        }
      });

      // ソートして配列に変換
      groups.value = Array.from(groupSet).sort();
      serviceTypes.value = Array.from(serviceSet).sort();
    } catch (err) {
      console.error('Error fetching lists:', err);
      error.value = `一覧の取得に失敗しました: ${err instanceof Error ? err.message : String(err)}`;
    } finally {
      loading.value = false;
    }
  };

  return {
    groups,
    serviceTypes,
    loading,
    error,
    fetchLists,
  };
}
