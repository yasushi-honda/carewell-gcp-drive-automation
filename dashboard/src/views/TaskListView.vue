<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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
      クラス一覧に戻る
    </button>

    <!-- ページタイトル -->
    <h1 class="text-3xl font-bold text-gray-900 mb-2">{{ className }}</h1>
    <p class="text-gray-600 mb-8">課題一覧</p>

    <!-- ローディング状態 -->
    <div v-if="loading" class="space-y-4">
      <LoadingSkeleton v-for="i in 4" :key="i" variant="card" />
    </div>

    <!-- エラー状態 -->
    <ErrorAlert
      v-else-if="error"
      :message="error"
      @retry="fetchTasks"
    />

    <!-- 空状態 -->
    <div
      v-else-if="tasks.length === 0"
      class="text-center py-12"
    >
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
      <h3 class="mt-2 text-sm font-medium text-gray-900">課題がありません</h3>
      <p class="mt-1 text-sm text-gray-500">
        このクラスには課題データが見つかりませんでした。
      </p>
    </div>

    <!-- 課題一覧 -->
    <div
      v-else
      class="space-y-4"
    >
      <TaskCard
        v-for="task in tasks"
        :key="task.taskId"
        :task-id="task.taskId"
        :file-count="task.fileCount"
        :student-count="task.studentCount"
        :last-submit="task.lastSubmit"
        @click="navigateToTask(task.taskId)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useTaskList } from '../composables/useTaskList';
import TaskCard from '../components/TaskCard.vue';
import LoadingSkeleton from '../components/LoadingSkeleton.vue';
import ErrorAlert from '../components/ErrorAlert.vue';

/**
 * TaskListView
 * 課題一覧ページ
 */

const router = useRouter();
const route = useRoute();

// ルートパラメータからクラス名を取得
const className = route.params.className as string;

const { tasks, loading, error, fetchTasks } = useTaskList(className);

/**
 * 初回マウント時に課題一覧を取得
 */
onMounted(async () => {
  await fetchTasks();
});

/**
 * classNameが変更された場合に再取得
 */
watch(
  () => route.params.className,
  async (newClassName) => {
    if (newClassName && newClassName !== className) {
      await fetchTasks();
    }
  }
);

/**
 * クラス一覧に戻る
 */
function navigateBack(): void {
  router.push({ name: 'home' });
}

/**
 * 課題カードクリック時のナビゲーション
 */
function navigateToTask(taskId: string): void {
  router.push({
    name: 'files',
    params: {
      className,
      taskId,
    },
  });
}
</script>
