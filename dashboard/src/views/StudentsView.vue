<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- ページタイトル -->
    <h1 class="text-3xl font-bold text-gray-900 mb-6">学生一覧</h1>

    <!-- 検索ボックス -->
    <div class="bg-white shadow-sm rounded-lg p-4 mb-6">
      <div class="max-w-md">
        <label for="search-query" class="block text-sm font-medium text-gray-700 mb-1">
          検索
        </label>
        <input
          id="search-query"
          v-model="searchQuery"
          type="text"
          placeholder="氏名・ふりがなで検索"
          class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2 px-3 border"
        />
      </div>
    </div>

    <!-- ローディング状態 -->
    <div v-if="loading" class="space-y-4">
      <LoadingSkeleton v-for="i in 5" :key="i" variant="card" />
    </div>

    <!-- エラー状態 -->
    <ErrorAlert v-else-if="error" :message="error" />

    <!-- 学生一覧テーブル -->
    <div v-else class="bg-white shadow-sm rounded-lg overflow-hidden">
      <!-- テーブルヘッダー -->
      <div class="px-4 py-3 border-b border-gray-200 bg-gray-50">
        <p class="text-sm text-gray-700">
          {{ filteredStudents.length }} 人の学生が見つかりました
        </p>
      </div>

      <!-- テーブル本体 -->
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th
                scope="col"
                class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                日介番号
              </th>
              <th
                scope="col"
                class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                氏名
              </th>
              <th
                scope="col"
                class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 select-none"
                @click="toggleSort"
              >
                <div class="flex items-center gap-2">
                  <span>ふりがな</span>
                  <span class="text-xs" v-if="sortOrder === 'asc'">▲</span>
                  <span class="text-xs" v-else-if="sortOrder === 'desc'">▼</span>
                  <span class="text-xs text-gray-300" v-else>⇅</span>
                </div>
              </th>
              <th
                scope="col"
                class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                グループ
              </th>
              <th
                scope="col"
                class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                サービス種別
              </th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr
              v-for="student in sortedStudents"
              :key="student.student_id"
              class="hover:bg-gray-50 cursor-pointer"
              @click="navigateToDetail(student.student_id)"
            >
              <td class="px-6 py-4 whitespace-nowrap">
                <router-link
                  :to="`/students/${student.student_id}`"
                  class="text-blue-600 hover:text-blue-800 font-medium"
                  @click.stop
                >
                  {{ student.student_id }}
                </router-link>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                {{ student.name }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {{ student.furigana }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                {{ student.group }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {{ student.service_type }}
              </td>
            </tr>
          </tbody>
        </table>

        <!-- 空状態 -->
        <div v-if="filteredStudents.length === 0" class="px-6 py-12 text-center">
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
              d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
            />
          </svg>
          <p class="mt-2 text-sm text-gray-500">該当する学生が見つかりませんでした</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useStudents } from '../composables/useStudents';
import LoadingSkeleton from '../components/LoadingSkeleton.vue';
import ErrorAlert from '../components/ErrorAlert.vue';

const router = useRouter();

const searchQuery = ref('');
const sortOrder = ref<'asc' | 'desc' | null>(null);

const { students, loading, error } = useStudents();

// クライアント側でのフィルタリング
const filteredStudents = computed(() => {
  return students.value.filter((student) => {
    // ステータスフィルター（アクティブな学生のみ表示）
    if (student.status !== 'active') {
      return false;
    }

    // 検索クエリ
    if (searchQuery.value) {
      const query = searchQuery.value.toLowerCase();
      const matchName = student.name.toLowerCase().includes(query);
      const matchFurigana = student.furigana.toLowerCase().includes(query);
      return matchName || matchFurigana;
    }

    return true;
  });
});

// ふりがなでソート
const sortedStudents = computed(() => {
  const list = [...filteredStudents.value];

  if (sortOrder.value === 'asc') {
    return list.sort((a, b) => a.furigana.localeCompare(b.furigana, 'ja'));
  } else if (sortOrder.value === 'desc') {
    return list.sort((a, b) => b.furigana.localeCompare(a.furigana, 'ja'));
  }

  return list;
});

const toggleSort = () => {
  if (sortOrder.value === null) {
    sortOrder.value = 'asc';
  } else if (sortOrder.value === 'asc') {
    sortOrder.value = 'desc';
  } else {
    sortOrder.value = null;
  }
};

const navigateToDetail = (studentId: string) => {
  router.push(`/students/${studentId}`);
};
</script>
