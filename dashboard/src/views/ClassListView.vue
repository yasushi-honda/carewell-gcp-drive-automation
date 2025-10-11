<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- ページタイトル -->
    <h1 class="text-3xl font-bold text-gray-900 mb-8">クラス一覧</h1>

    <!-- ローディング状態 -->
    <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <LoadingSkeleton v-for="i in 6" :key="i" variant="card" />
    </div>

    <!-- エラー状態 -->
    <ErrorAlert
      v-else-if="error"
      :message="error"
      @retry="fetchClasses"
    />

    <!-- 空状態 -->
    <div
      v-else-if="classes.length === 0"
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
      <h3 class="mt-2 text-sm font-medium text-gray-900">クラスがありません</h3>
      <p class="mt-1 text-sm text-gray-500">
        クラスデータが見つかりませんでした。
      </p>
    </div>

    <!-- クラス一覧グリッド -->
    <div
      v-else
      class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
    >
      <ClassCard
        v-for="classData in classes"
        :key="classData.name"
        :class-name="classData.name"
        :task-count="classData.taskCount"
        :file-count="classData.fileCount"
        :last-updated="classData.lastUpdated"
        @click="navigateToClass(classData.name)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useClassList } from '../composables/useClassList';
import ClassCard from '../components/ClassCard.vue';
import LoadingSkeleton from '../components/LoadingSkeleton.vue';
import ErrorAlert from '../components/ErrorAlert.vue';

/**
 * ClassListView
 * クラス一覧ページ
 */

const router = useRouter();
const { classes, loading, error, fetchClasses } = useClassList();

/**
 * 初回マウント時にクラス一覧を取得
 */
onMounted(async () => {
  await fetchClasses();
});

/**
 * クラスカードクリック時のナビゲーション
 */
function navigateToClass(className: string): void {
  router.push({
    name: 'tasks',
    params: { className },
  });
}
</script>
