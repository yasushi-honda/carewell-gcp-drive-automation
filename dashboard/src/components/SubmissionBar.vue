<template>
  <!--
    グループの提出状況の配分（積み上げバー + 数字）。
    色だけに頼らず、数字とラベルで同じ情報を出す。
    取得中は同じ高さの骨格を出し、届いた時点でカードが動かないようにする。
  -->
  <div v-if="loading" class="mt-4 animate-pulse" aria-hidden="true" data-testid="submission-skeleton">
    <div class="h-2.5 w-full rounded-full bg-gray-200"></div>
    <!-- 実際の行の高さ（text-sm=20px / text-xs=16px）に合わせ、データが届いてもカードが動かないようにする -->
    <div class="mt-2 flex h-5 items-center"><div class="h-3.5 w-2/3 rounded bg-gray-200"></div></div>
    <div class="mt-1 flex h-4 items-center"><div class="h-2.5 w-1/2 rounded bg-gray-100"></div></div>
  </div>

  <div v-else-if="submission" class="mt-4" data-testid="submission-bar">
    <div class="flex h-2.5 w-full overflow-hidden rounded-full bg-gray-200" aria-hidden="true">
      <div
        v-for="segment in segments"
        :key="segment.key"
        :class="segment.color"
        :style="{ width: segment.width }"
        :data-segment="segment.key"
      ></div>
    </div>

    <div class="mt-2 flex items-baseline justify-between text-sm text-gray-700">
      <span>提出 <span class="font-semibold text-gray-900">{{ submission.submitted }}</span></span>
      <span v-if="submission.notSubmitted > 0" class="font-semibold text-amber-700">
        未提出 {{ submission.notSubmitted }}
      </span>
      <span v-else class="font-semibold text-green-700">全員提出</span>
    </div>

    <p class="mt-1 text-xs text-gray-600">
      合格 {{ submission.passed }} ・ 採点待ち {{ submission.pending }} ・ 不合格 {{ submission.failed }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { GroupSubmission } from '../composables/useGroupStats';

const props = defineProps<{
  /** グループの受講生数（バーの100%） */
  total: number;
  submission?: GroupSubmission | null;
  /** 取得中は骨格を表示する */
  loading?: boolean;
}>();

// 左から 合格 / 採点待ち / 不合格 / 未提出
const segments = computed(() => {
  const s = props.submission;
  if (!s || props.total <= 0) return [];
  // 小数第2位までに丸める（浮動小数点の誤差で 20.000000000000004% のようにならないよう、整数演算で求める）
  const width = (count: number) => `${Math.round((count * 10000) / props.total) / 100}%`;
  return [
    { key: 'passed', count: s.passed, color: 'bg-green-500' },
    { key: 'pending', count: s.pending, color: 'bg-blue-500' },
    { key: 'failed', count: s.failed, color: 'bg-red-500' },
    // 未提出はバーの背景（灰）のままにし、残りの幅を占める
  ]
    .filter((segment) => segment.count > 0)
    .map((segment) => ({ ...segment, width: width(segment.count) }));
});
</script>
