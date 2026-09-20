<template>
  <div
    class="bg-white rounded-lg shadow-sm hover:shadow-md transition-shadow duration-200 p-6 cursor-pointer border border-gray-200"
    @click="handleClick"
    @keydown.enter="handleClick"
    tabindex="0"
    role="button"
    :aria-label="ariaLabel"
  >
    <h3 class="text-xl font-bold text-gray-900 mb-4">
      {{ group }} グループ
    </h3>

    <div class="space-y-2 text-sm text-gray-600">
      <div class="flex justify-between items-center">
        <span>受講生数</span>
        <span class="font-semibold text-gray-900">{{ studentCount }} 人</span>
      </div>
    </div>

    <SubmissionBar :total="studentCount" :submission="submission" :loading="submissionLoading" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import SubmissionBar from './SubmissionBar.vue';
import type { GroupSubmission } from '../composables/useGroupStats';

interface Props {
  className: string;
  taskId: string;
  group: string;
  studentCount: number;
  /** 提出状況の配分（取得中・失敗・突合不能のときは渡さない） */
  submission?: GroupSubmission | null;
  /** 提出状況を取得中（バーの骨格を表示する） */
  submissionLoading?: boolean;
}

const props = defineProps<Props>();
const router = useRouter();

// カード全体が button なので、読み上げには提出状況もここに含める
const ariaLabel = computed(() => {
  const base = `${props.group}グループ、受講生${props.studentCount}人`;
  const s = props.submission;
  if (!s) return base;
  return `${base}、提出${s.submitted}人、未提出${s.notSubmitted}人（合格${s.passed}・採点待ち${s.pending}・不合格${s.failed}）`;
});

const handleClick = () => {
  router.push(`/class/${props.className}/task/${props.taskId}/group/${props.group}/students`);
};
</script>
