<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- パンくずリスト -->
    <Breadcrumb :items="breadcrumbItems" class="mb-4" />

    <!-- 戻るボタン -->
    <button
      @click="navigateBack"
      class="mb-4 inline-flex items-center text-sm font-medium text-gray-700 hover:text-gray-900"
    >
      <svg
        class="mr-2 h-5 w-5"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M10 19l-7-7m0 0l7-7m-7 7h18"
        />
      </svg>
      課題一覧に戻る
    </button>

    <!-- ページタイトル -->
    <h1 class="text-3xl font-bold text-gray-900 mb-2">{{ className }}</h1>
    <p class="text-gray-600 mb-6">{{ taskId }}</p>

    <!-- 統計情報 -->
    <div v-if="!loading && !error && files.length > 0" class="mb-6">
      <div class="flex items-center space-x-6 text-sm text-gray-600">
        <div class="flex items-center">
          <svg
            class="h-5 w-5 text-gray-400 mr-2"
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
          <span>提出者総数: <span class="font-semibold">{{ uniqueStudentCount }}</span></span>
        </div>

        <div v-if="lastSubmitDate" class="flex items-center">
          <svg
            class="h-5 w-5 text-gray-400 mr-2"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <span>最終提出: <span class="font-semibold">{{ lastSubmitDate }}</span></span>
        </div>
      </div>
    </div>

    <!-- 検索ボックス -->
    <div v-if="!loading && !error && files.length > 0" class="mb-6">
      <SearchBox
        v-model="searchQuery"
        placeholder="学生名または学生IDで検索..."
        @update:modelValue="setSearch"
      />
      <p v-if="searchQuery" class="mt-2 text-sm text-gray-600">
        {{ filteredFiles.length }}件 / {{ files.length }}件を表示中
      </p>
    </div>

    <!-- ローディング状態 -->
    <div v-if="loading" class="space-y-4">
      <LoadingSkeleton v-for="i in 5" :key="i" variant="card" />
    </div>

    <!-- エラー状態 -->
    <ErrorAlert
      v-else-if="error"
      :message="error"
      @retry="fetchFiles"
    />

    <!-- 空状態 -->
    <EmptyState
      v-else-if="files.length === 0"
      icon="document"
      title="提出ファイルがありません"
      message="この課題にはまだ提出ファイルがありません。"
      action-label="課題一覧に戻る"
      :action-to="`/tasks/${className}`"
    />

    <!-- ファイル一覧テーブル -->
    <div v-else>
      <FileTable
        :files="filteredFiles"
        :sort-column="sortColumn"
        :sort-order="sortOrder"
        @sort="setSortColumn"
        @open-drive="openDrive"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, computed, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useFileList } from '../composables/useFileList';
import FileTable from '../components/FileTable.vue';
import SearchBox from '../components/SearchBox.vue';
import LoadingSkeleton from '../components/LoadingSkeleton.vue';
import ErrorAlert from '../components/ErrorAlert.vue';
import EmptyState from '../components/EmptyState.vue';
import Breadcrumb, { type BreadcrumbItem } from '../components/Breadcrumb.vue';

/**
 * FileListView
 * ファイル一覧ページ
 */

const router = useRouter();
const route = useRoute();

// ルートパラメータからクラス名とタスクIDを取得
const className = route.params.className as string;
const taskId = route.params.taskId as string;

const {
  files,
  loading,
  error,
  searchQuery,
  sortColumn,
  sortOrder,
  filteredFiles,
  fetchFiles,
  setSearch,
  setSortColumn,
} = useFileList(className, taskId);

// パンくずリスト
const breadcrumbItems = computed<BreadcrumbItem[]>(() => [
  { label: 'ホーム', to: '/' },
  { label: className, to: `/tasks/${className}` },
  { label: taskId, to: `/files/${className}/${taskId}` },
]);

/**
 * 統計情報: 提出者総数（ユニークな学生ID数）
 */
const uniqueStudentCount = computed(() => {
  const uniqueIds = new Set(files.value.map((file) => file.student_id));
  return uniqueIds.size;
});

/**
 * 統計情報: 最終提出日時（submit_dateの最新値）
 */
const lastSubmitDate = computed(() => {
  if (files.value.length === 0) return null;
  const dates = files.value.map((file) => new Date(file.submit_date));
  const latestDate = new Date(Math.max(...dates.map((d) => d.getTime())));
  return formatDate(latestDate.toISOString());
});

/**
 * ISO 8601日時をYYYY/MM/DD形式に変換
 */
function formatDate(isoDate: string): string {
  try {
    const date = new Date(isoDate);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}/${month}/${day}`;
  } catch (error) {
    console.warn('Failed to format date:', isoDate, error);
    return isoDate;
  }
}

/**
 * Google Driveリンクを新しいタブで開く
 */
function openDrive(driveUrl: string): void {
  if (!driveUrl) {
    console.warn('Invalid drive URL:', driveUrl);
    return;
  }
  window.open(driveUrl, '_blank', 'noopener,noreferrer');
}

/**
 * 初回マウント時にファイル一覧を取得
 */
onMounted(async () => {
  await fetchFiles();
});

/**
 * className/taskIdが変更された場合に再取得
 */
watch(
  () => [route.params.className, route.params.taskId],
  async ([newClassName, newTaskId]) => {
    if (newClassName !== className || newTaskId !== taskId) {
      await fetchFiles();
    }
  }
);

/**
 * 課題一覧に戻る
 */
function navigateBack(): void {
  router.push({
    name: 'tasks',
    params: { className },
  });
}
</script>
