<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- パンくずリスト -->
    <Breadcrumb
      :items="[
        { label: 'ホーム', to: '/' },
        { label: className, to: `/class/${className}` },
        { label: taskId, to: `/class/${className}/task/${taskId}` },
        { label: 'グループ一覧' }
      ]"
    />

    <!-- ページタイトル -->
    <h1 class="text-3xl font-bold text-gray-900 mb-2 mt-6">グループ一覧</h1>
    <p class="text-gray-600 mb-6">{{ className }} - {{ taskId }}</p>

    <!-- ローディング状態 -->
    <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <LoadingSkeleton v-for="i in 6" :key="i" variant="card" />
    </div>

    <!-- エラー状態 -->
    <ErrorAlert v-else-if="error" :message="error" @retry="refetch" />

    <!-- グループカード一覧 -->
    <div v-else-if="groupStats.length > 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <GroupCard
        v-for="stat in groupStats"
        :key="stat.group"
        :className="className"
        :taskId="taskId"
        :group="stat.group"
        :studentCount="stat.studentCount"
      />
    </div>

    <!-- 空状態 -->
    <EmptyState
      v-else
      icon="document"
      title="グループが見つかりませんでした"
      message="このクラスにはグループがありません。"
      :action-to="`/class/${className}`"
      action-label="課題一覧に戻る"
    />
  </div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router';
import { useGroupStats } from '../composables/useGroupStats';
import Breadcrumb from '../components/Breadcrumb.vue';
import GroupCard from '../components/GroupCard.vue';
import LoadingSkeleton from '../components/LoadingSkeleton.vue';
import ErrorAlert from '../components/ErrorAlert.vue';
import EmptyState from '../components/EmptyState.vue';

const route = useRoute();
const className = route.params.className as string;
const taskId = route.params.taskId as string;

const { groupStats, loading, error, refetch } = useGroupStats(className);
</script>
