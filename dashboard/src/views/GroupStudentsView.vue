<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- パンくずリスト -->
    <Breadcrumb
      :items="[
        { label: 'ホーム', to: '/' },
        { label: className, to: `/class/${className}` },
        { label: taskId, to: `/class/${className}/task/${taskId}` },
        { label: 'グループ一覧', to: `/class/${className}/task/${taskId}/groups` },
        { label: `${groupName}グループ` }
      ]"
    />

    <!-- ページタイトル -->
    <h1 class="text-3xl font-bold text-gray-900 mb-6 mt-6">
      {{ groupName }} グループの受講生一覧
    </h1>

    <!-- 検索ボックス -->
    <div class="bg-white shadow-sm rounded-lg p-4 mb-6">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label for="search-query" class="block text-sm font-medium text-gray-700 mb-1">
            検索
          </label>
          <input
            id="search-query"
            v-model="searchQuery"
            type="text"
            placeholder="氏名・ふりがな・日介番号で検索"
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm py-2 px-3 border"
          />
        </div>
      </div>
    </div>

    <!-- ローディング状態 -->
    <div v-if="loading" class="space-y-4">
      <LoadingSkeleton v-for="i in 5" :key="i" variant="card" />
    </div>

    <!-- エラー状態 -->
    <ErrorAlert v-else-if="error" :message="error" />

    <!-- 受講生一覧テーブル -->
    <div v-else class="bg-white shadow-sm rounded-lg overflow-hidden">
      <!-- テーブルヘッダー -->
      <div class="px-4 py-3 border-b border-gray-200 bg-gray-50">
        <p class="text-sm text-gray-700">
          {{ filteredAndSortedStudents.length }} 人の受講生が見つかりました
        </p>
      </div>

      <!-- テーブル本体 -->
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th
                scope="col"
                class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 select-none"
                @click="toggleSortSerialNumber"
              >
                <div class="flex items-center gap-2">
                  <span>通し番号</span>
                  <span class="text-xs" v-if="sortBy === 'serial_number' && sortOrder === 'asc'">▲</span>
                  <span class="text-xs" v-else-if="sortBy === 'serial_number' && sortOrder === 'desc'">▼</span>
                  <span class="text-xs text-gray-300" v-else>⇅</span>
                </div>
              </th>
              <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                日介番号
              </th>
              <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                氏名
              </th>
              <th
                scope="col"
                class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 select-none"
                @click="toggleSortFurigana"
              >
                <div class="flex items-center gap-2">
                  <span>ふりがな</span>
                  <span class="text-xs" v-if="sortBy === 'furigana' && sortOrder === 'asc'">▲</span>
                  <span class="text-xs" v-else-if="sortBy === 'furigana' && sortOrder === 'desc'">▼</span>
                  <span class="text-xs text-gray-300" v-else>⇅</span>
                </div>
              </th>
              <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                勤務先
              </th>
              <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                サービス種別
              </th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr
              v-for="student in filteredAndSortedStudents"
              :key="student.student_id"
              class="cursor-pointer transition-colors"
              :class="student.status === 'withdrawn' ? 'bg-gray-100 hover:bg-gray-200 opacity-60' : 'hover:bg-gray-50'"
              @click="navigateToDetail(student.student_id)"
            >
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                {{ student.serial_number || '-' }}
              </td>
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
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {{ getWorkplace(student) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {{ student.service_type }}
              </td>
            </tr>
          </tbody>
        </table>

        <!-- 空状態 -->
        <div v-if="filteredAndSortedStudents.length === 0" class="px-6 py-12 text-center">
          <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
          </svg>
          <p class="mt-2 text-sm text-gray-500">該当する受講生が見つかりませんでした</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useStudents } from '../composables/useStudents';
import { convertToShortClassName } from '../config/classes';
import type { Student } from '../types/models';
import Breadcrumb from '../components/Breadcrumb.vue';
import LoadingSkeleton from '../components/LoadingSkeleton.vue';
import ErrorAlert from '../components/ErrorAlert.vue';

const route = useRoute();
const router = useRouter();

const className = route.params.className as string;
const taskId = route.params.taskId as string;
const groupName = route.params.groupName as string;

const searchQuery = ref('');
const sortBy = ref<'furigana' | 'serial_number' | null>(null);
const sortOrder = ref<'asc' | 'desc' | null>(null);

// URLから来たクラス名（フルネーム）を短縮形に変換
const shortClassName = convertToShortClassName(className);

const { students, loading, error } = useStudents();

// 勤務先表示関数
const getWorkplace = (student: Student): string => {
  if (student.company && student.office) {
    return `${student.company} - ${student.office}`;
  } else if (student.company) {
    return student.company;
  } else if (student.office) {
    return student.office;
  } else {
    return '-';
  }
};

// フィルタリング（クラス、グループ、検索クエリ）
const filteredStudents = computed(() => {
  return students.value.filter((student) => {
    // 無効な受講生を除外（status が inactive の場合）
    if (student.status === 'inactive') {
      return false;
    }

    // クラスフィルター（短縮形で比較）
    if (student.class_name !== shortClassName) {
      return false;
    }

    // グループフィルター
    if (student.group !== groupName) {
      return false;
    }

    // 検索クエリ（氏名、ふりがな、日介番号で検索）
    if (searchQuery.value) {
      const query = searchQuery.value.toLowerCase();
      const matchName = student.name.toLowerCase().includes(query);
      const matchFurigana = student.furigana.toLowerCase().includes(query);
      const matchStudentId = student.student_id.toLowerCase().includes(query);
      return matchName || matchFurigana || matchStudentId;
    }

    return true;
  });
});

// ソート機能
const toggleSortFurigana = () => {
  if (sortBy.value === 'furigana') {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc';
  } else {
    sortBy.value = 'furigana';
    sortOrder.value = 'asc';
  }
};

const toggleSortSerialNumber = () => {
  if (sortBy.value === 'serial_number') {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc';
  } else {
    sortBy.value = 'serial_number';
    sortOrder.value = 'asc';
  }
};

// フィルタ + ソート
const filteredAndSortedStudents = computed(() => {
  let result = [...filteredStudents.value];

  if (sortBy.value === 'furigana' && sortOrder.value) {
    result.sort((a, b) => {
      const comparison = a.furigana.localeCompare(b.furigana, 'ja');
      return sortOrder.value === 'asc' ? comparison : -comparison;
    });
  } else if (sortBy.value === 'serial_number' && sortOrder.value) {
    result.sort((a, b) => {
      const comparison = (a.serial_number || 0) - (b.serial_number || 0);
      return sortOrder.value === 'asc' ? comparison : -comparison;
    });
  }

  return result;
});

const navigateToDetail = (studentId: string) => {
  router.push(`/students/${studentId}`);
};
</script>
