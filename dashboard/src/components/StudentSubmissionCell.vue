<template>
  <!--
    受講生1人の提出状況（バッジ + 最終提出日時）。色だけに頼らず、文字でも状態を出す。
    取得できなかった（失敗・名簿と不一致）ときは「未提出」と誤読されないよう、状態は出さず「-」にする。
  -->
  <span v-if="state === 'loading'" class="inline-block h-5 w-16 animate-pulse rounded-full bg-gray-200" aria-hidden="true" data-testid="submission-cell-loading"></span>

  <!-- 退会した受講生で提出が無い場合は、提出の対象外（「未提出」とは言わない） -->
  <span v-else-if="state === 'ready' && !submission && notRequired" class="text-sm text-gray-500" data-testid="submission-cell-not-required">対象外</span>

  <span v-else-if="state === 'ready'" class="inline-flex flex-col items-start gap-0.5" data-testid="submission-cell">
    <span
      class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold"
      :class="badge.color"
      :data-status="status"
    >
      {{ badge.label }}
    </span>
    <span v-if="submission?.latestSubmitDate" class="text-xs text-gray-500">
      最終提出 {{ formattedDate }}
      <template v-if="submission.fileCount > 1">（{{ submission.fileCount }}回）</template>
    </span>
  </span>

  <span v-else class="text-sm text-gray-400" data-testid="submission-cell-unavailable">-</span>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { StudentStatus, StudentSubmission } from '../composables/useStudentSubmissions';

const props = defineProps<{
  /** 取得状態。ready 以外は状態を出さない */
  state: 'loading' | 'ready' | 'error' | 'mismatch';
  /** 提出ファイルがある受講生のみ。無ければ「未提出」 */
  submission?: StudentSubmission;
  /** 提出の対象外（退会した受講生）。提出が無いときだけ「未提出」の代わりに「対象外」を出す */
  notRequired?: boolean;
}>();

const BADGES: Record<StudentStatus, { label: string; color: string }> = {
  passed: { label: '合格', color: 'bg-green-100 text-green-800' },
  pending: { label: '採点待ち', color: 'bg-blue-100 text-blue-800' },
  failed: { label: '不合格', color: 'bg-red-100 text-red-800' },
  not_submitted: { label: '未提出', color: 'bg-amber-100 text-amber-800' },
};

const status = computed<StudentStatus>(() => props.submission?.status ?? 'not_submitted');
const badge = computed(() => BADGES[status.value]);

// "YYYY/MM/DD HH:mm:ss" → "YYYY/MM/DD HH:mm"（秒は不要）
const formattedDate = computed(() => props.submission?.latestSubmitDate.slice(0, 16) ?? '');
</script>
