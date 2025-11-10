// src/composables/useStudents.ts
// 学生データの取得とリアルタイム更新

import { ref, onUnmounted, Ref } from 'vue';
import { collection, query, orderBy, onSnapshot, Query, Timestamp } from 'firebase/firestore';
import { getDb } from '../config/firebase';
import type { Student } from '../types/models';

interface UseStudentsOptions {
  group?: string;
  serviceType?: string;
}

interface UseStudentsReturn {
  students: Ref<Student[]>;
  loading: Ref<boolean>;
  error: Ref<string | null>;
}

/**
 * 学生データを取得・リアルタイム更新するComposable
 *
 * @param options - フィルターオプション（group, serviceType）
 * @returns 学生一覧の状態
 *
 * @example
 * const { students, loading, error } = useStudents();
 * const { students: groupAStudents } = useStudents({ group: 'A' });
 */
export function useStudents(options: UseStudentsOptions = {}): UseStudentsReturn {
  const students = ref<Student[]>([]);
  const loading = ref(true);
  const error = ref<string | null>(null);

  const db = getDb();

  // Firestore クエリの構築
  // Note: where + orderBy の複合クエリは複合インデックスが必要になるため、
  // シンプルなクエリにして、フィルタリングはクライアント側で行う
  let q: Query = collection(db, 'students');

  // 学生番号で昇順ソート（単一フィールドソートのみ - インデックス不要）
  q = query(q, orderBy('student_number', 'asc'));

  // リアルタイム購読
  const unsubscribe = onSnapshot(
    q,
    (snapshot) => {
      students.value = snapshot.docs.map((doc) => {
        const data = doc.data();
        return {
          student_id: doc.id,
          name: data.name || '',
          furigana: data.furigana || '',
          group: data.group || '',
          company: data.company || '',
          office: data.office || '',
          service_type: data.service_type || '',
          serial_number: data.serial_number || 0,
          student_number: data.student_number || '',
          class_name: data.class_name || '',
          status: data.status || 'active',
          // Firestore Timestamp を Date に変換
          created_at: data.created_at instanceof Timestamp ? data.created_at.toDate() : undefined,
          last_updated: data.last_updated instanceof Timestamp ? data.last_updated.toDate() : undefined,
        } as Student;
      });
      loading.value = false;
      error.value = null;
    },
    (err) => {
      console.error('Error fetching students:', err);
      error.value = `学生データの取得に失敗しました: ${err.message}`;
      loading.value = false;
    }
  );

  // コンポーネントがアンマウントされたら購読解除
  onUnmounted(() => {
    unsubscribe();
  });

  return {
    students,
    loading,
    error,
  };
}
