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
    <EmptyState
      v-else-if="classes.length === 0"
      icon="folder"
      title="クラスがありません"
      message="クラスデータが見つかりませんでした。"
    />

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
import EmptyState from '../components/EmptyState.vue';

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
