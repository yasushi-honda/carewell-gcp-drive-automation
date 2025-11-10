// src/composables/useGroupStats.ts
// グループ統計の取得

import { ref, onMounted } from 'vue';
import { collection, query, where, getDocs, Timestamp } from 'firebase/firestore';
import { getDb } from '../config/firebase';
import { convertToShortClassName } from '../config/classes';
import type { Student } from '../types/models';

export interface GroupStat {
  group: string;
  studentCount: number;
}

export function useGroupStats(className: string) {
  const groupStats = ref<GroupStat[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const fetchGroupStats = async () => {
    loading.value = true;
    error.value = null;

    try {
      const db = getDb();

      // URLから来たクラス名（フルネーム）を短縮形に変換
      // 理由: students コレクションには短縮形（"No1"）で保存されているため
      const shortClassName = convertToShortClassName(className);

      // students コレクションから該当クラスの受講生を取得
      const q = query(
        collection(db, 'students'),
        where('class_name', '==', shortClassName),
        where('status', '==', 'active')
      );

      const snapshot = await getDocs(q);

      // グループごとにカウント
      const groupCounts = new Map<string, number>();

      snapshot.docs.forEach((doc) => {
        const data = doc.data();
        const group = data.group || '未分類';
        groupCounts.set(group, (groupCounts.get(group) || 0) + 1);
      });

      // Map を配列に変換してソート
      groupStats.value = Array.from(groupCounts.entries())
        .map(([group, count]) => ({
          group,
          studentCount: count
        }))
        .sort((a, b) => a.group.localeCompare(b.group, 'ja'));

    } catch (err) {
      console.error('Error fetching group stats:', err);
      error.value = 'グループ統計の取得に失敗しました';
    } finally {
      loading.value = false;
    }
  };

  onMounted(() => {
    fetchGroupStats();
  });

  return {
    groupStats,
    loading,
    error,
    refetch: fetchGroupStats
  };
}
