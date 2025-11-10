<template>
  <div>
    <!-- ローディング状態 -->
    <div v-if="loading" class="py-4 text-center">
      <div
        class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"
      ></div>
      <p class="mt-2 text-sm text-gray-600">提出履歴を読み込み中...</p>
    </div>

    <!-- エラー状態 -->
    <ErrorAlert v-else-if="error" :message="error" />

    <!-- 空状態 -->
    <div v-else-if="files.length === 0" class="py-12 text-center">
      <svg
        class="mx-auto h-12 w-12 text-gray-400"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
      </svg>
      <p class="mt-2 text-sm text-gray-500">提出ファイルがありません</p>
    </div>

    <!-- ファイル一覧（課題別にグループ化） -->
    <div v-else class="space-y-6">
      <div v-for="task in groupedByTask" :key="task.taskId" class="border-l-4 border-blue-500 pl-4">
        <h3 class="text-lg font-bold text-gray-900 mb-3">
          {{ task.taskPattern }}
        </h3>

        <ul class="space-y-2">
          <li
            v-for="file in task.files"
            :key="file.composite_key"
            class="flex items-center gap-3 p-3 hover:bg-gray-50 rounded-lg transition-colors"
          >
            <!-- ファイルアイコン -->
            <svg class="h-5 w-5 text-gray-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path
                d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"
              />
            </svg>

            <!-- ファイル名 -->
            <a
              :href="`https://drive.google.com/file/d/${file.drive_file_id}/view`"
              target="_blank"
              rel="noopener noreferrer"
              class="text-blue-600 hover:text-blue-800 hover:underline flex-1 font-medium"
            >
              {{ file.filename }}
            </a>

            <!-- 提出日 -->
            <span class="text-sm text-gray-500 flex-shrink-0">
              {{ formatDate(file.submit_date) }}
            </span>

            <!-- 合否情報（あれば表示） -->
            <span
              v-if="file.metadata?.pass_status"
              class="px-2 py-1 text-xs font-semibold rounded-full flex-shrink-0"
              :class="{
                'bg-green-100 text-green-800': file.metadata.pass_status === '合格',
                'bg-red-100 text-red-800': file.metadata.pass_status === '不合格',
                'bg-gray-100 text-gray-800': file.metadata.pass_status !== '合格' && file.metadata.pass_status !== '不合格',
              }"
            >
              {{ file.metadata.pass_status }}
            </span>
          </li>
        </ul>
      </div>

      <!-- サマリー -->
      <div class="mt-6 pt-4 border-t border-gray-200">
        <p class="text-sm text-gray-600">
          合計 <span class="font-semibold">{{ files.length }}</span> ファイル
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { collectionGroup, query, where, getDocs } from 'firebase/firestore';
import { getDb } from '../config/firebase';
import type { FileData } from '../types/models';
import ErrorAlert from './ErrorAlert.vue';

const props = defineProps<{
  studentId: string;
}>();

const files = ref<FileData[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

onMounted(async () => {
  try {
    const db = getDb();
    // collectionGroup クエリで全クラス・全課題から検索
    const q = query(
      collectionGroup(db, 'files'),
      where('student_id', '==', props.studentId)
    );

    const snapshot = await getDocs(q);
    files.value = snapshot.docs.map((doc) => {
      const data = doc.data();
      return {
        composite_key: data.composite_key || doc.id,
        student_id: data.student_id || '',
        student_name: data.student_name || '',
        filename: data.filename || '',
        submit_date: data.submit_date || '',
        drive_file_id: data.drive_file_id || '',
        task_id: data.task_id || '',
        task_pattern: data.task_pattern || data.task_id || '',
        metadata: data.metadata,
      } as FileData;
    });

    // 提出日時の降順でソート（新しい順）
    files.value.sort((a, b) => {
      return b.submit_date.localeCompare(a.submit_date);
    });
  } catch (err) {
    console.error('Error fetching files:', err);
    error.value = `提出履歴の取得に失敗しました: ${err instanceof Error ? err.message : String(err)}`;
  } finally {
    loading.value = false;
  }
});

// 課題別にグループ化
const groupedByTask = computed(() => {
  const groups = new Map<string, { taskId: string; taskPattern: string; files: FileData[] }>();

  files.value.forEach((file) => {
    const taskId = file.task_id || 'unknown';
    if (!groups.has(taskId)) {
      groups.set(taskId, {
        taskId,
        taskPattern: file.task_pattern || taskId,
        files: [],
      });
    }
    groups.get(taskId)!.files.push(file);
  });

  return Array.from(groups.values());
});

const formatDate = (dateString: string): string => {
  if (!dateString) return '-';

  // 既に "YYYY/MM/DD" 形式の場合はそのまま返す
  if (/^\d{4}\/\d{2}\/\d{2}/.test(dateString)) {
    return dateString.split(' ')[0]; // 時刻部分を除去
  }

  // Date オブジェクトに変換して整形
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('ja-JP', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).replace(/\//g, '/');
  } catch {
    return dateString;
  }
};
</script>
