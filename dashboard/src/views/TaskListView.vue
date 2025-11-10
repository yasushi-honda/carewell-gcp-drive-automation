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
    <EmptyState
      v-else-if="tasks.length === 0"
      icon="document"
      title="課題がありません"
      message="このクラスには課題データが見つかりませんでした。"
      action-label="クラス一覧に戻る"
      action-to="/"
    />

    <!-- 課題一覧 -->
    <div
      v-else
      class="space-y-4"
    >
      <div v-for="task in tasks" :key="task.taskId" class="relative">
        <TaskCard
          :task-id="task.taskId"
          :file-count="task.fileCount"
          :student-count="task.studentCount"
          :last-submit="task.lastSubmit"
          @click="navigateToTask(task.taskId)"
        />

        <!-- 受講生一覧リンク -->
        <div class="absolute bottom-4 right-4" @click.stop>
          <router-link
            :to="`/class/${className}/task/${task.taskId}/groups`"
            class="inline-flex items-center px-3 py-1.5 text-sm font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-md transition-colors"
          >
            👥 受講生一覧
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, watch, computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useTaskList } from '../composables/useTaskList';
import TaskCard from '../components/TaskCard.vue';
import LoadingSkeleton from '../components/LoadingSkeleton.vue';
import ErrorAlert from '../components/ErrorAlert.vue';
import EmptyState from '../components/EmptyState.vue';
import Breadcrumb, { type BreadcrumbItem } from '../components/Breadcrumb.vue';

/**
 * TaskListView
 * 課題一覧ページ
 */

const router = useRouter();
const route = useRoute();

// ルートパラメータからクラス名を取得
const className = route.params.className as string;

const { tasks, loading, error, fetchTasks } = useTaskList(className);

// パンくずリスト
const breadcrumbItems = computed<BreadcrumbItem[]>(() => [
  { label: 'ホーム', to: '/' },
  { label: className, to: `/class/${className}` },
]);

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
