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

    <template v-else-if="groupStats.length > 0">
      <!-- 提出状況の取得失敗（カードは残す）。「全員未提出」とは区別する -->
      <div
        v-if="submissionState === 'error'"
        role="alert"
        class="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900"
      >
        <p>提出状況を取得できませんでした。受講生数のみ表示しています。</p>
        <button
          type="button"
          class="inline-flex min-h-11 items-center rounded-md border border-amber-400 bg-white px-4 font-medium text-amber-900 hover:bg-amber-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
          @click="refetchSubmissions"
        >
          再取得
        </button>
      </div>

      <!-- ファイルはあるのに誰も受講生名簿と一致しない（配分は出さない） -->
      <div
        v-else-if="submissionState === 'mismatch'"
        role="alert"
        class="mb-4 rounded-md border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900"
      >
        提出データと受講生名簿が一致しなかったため、提出状況を表示できません。提出データの日介番号が空、または受講生名簿と食い違っている可能性があります。
      </div>

      <!-- 凡例（色だけに頼らず、カードにも数字を出している）。取得中から出して、データ到着時にカードが動かないようにする -->
      <ul
        v-else
        class="mb-4 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-600"
        aria-label="バーの凡例"
      >
        <li class="flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-green-500"></span>合格</li>
        <li class="flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-blue-500"></span>採点待ち</li>
        <li class="flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-red-500"></span>不合格</li>
        <li class="flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-full bg-gray-300"></span>未提出</li>
      </ul>

      <!-- グループカード一覧 -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <GroupCard
          v-for="stat in groupStats"
          :key="stat.group"
          :className="className"
          :taskId="taskId"
          :group="stat.group"
          :studentCount="stat.studentCount"
          :submission="stat.submission"
          :submissionLoading="submissionState === 'loading'"
        />
      </div>

      <!-- 集計に含まれない提出（カードの下に出し、データ到着時にカードが動かないようにする） -->
      <div v-if="submissionState === 'ready'" class="mt-4 space-y-1 text-sm">
        <p
          v-if="unmatchedSubmitters > 0"
          role="status"
          :class="unmatchedIsMostSubmitters ? 'font-medium text-amber-800' : 'text-gray-600'"
        >
          受講生名簿にない提出が {{ unmatchedSubmitters }} 人分あります（上の集計には含まれません）。
          <template v-if="unmatchedIsMostSubmitters">日介番号の食い違いの可能性があります。</template>
        </p>
        <p v-if="unidentifiedFiles > 0" role="status" class="font-medium text-amber-800">
          日介番号が空の提出ファイルが {{ unidentifiedFiles }} 件あります（上の集計には含まれません）。
        </p>
      </div>
    </template>

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
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { useGroupStats } from '../composables/useGroupStats';
import Breadcrumb from '../components/Breadcrumb.vue';
import GroupCard from '../components/GroupCard.vue';
import LoadingSkeleton from '../components/LoadingSkeleton.vue';
import ErrorAlert from '../components/ErrorAlert.vue';
import EmptyState from '../components/EmptyState.vue';

const route = useRoute();
// 同じルートのまま className / taskId だけが変わる遷移（戻る・進む）にも追従する
const className = computed(() => route.params.className as string);
const taskId = computed(() => route.params.taskId as string);

const {
  groupStats,
  loading,
  error,
  refetch,
  submissionState,
  unmatchedSubmitters,
  unidentifiedFiles,
  submitters,
  refetchSubmissions,
} = useGroupStats(className, taskId);

// 名簿外が提出者の半数以上なら、退会などではなく日介番号の食い違いを疑って目立たせる
const unmatchedIsMostSubmitters = computed(
  () => unmatchedSubmitters.value > 0 && unmatchedSubmitters.value * 2 >= submitters.value
);
</script>
