<template>
  <div
    class="bg-white rounded-lg shadow-sm hover:shadow-md transition-shadow duration-200 p-6 cursor-pointer border border-gray-200"
    @click="handleClick"
    @keydown.enter="handleClick"
    tabindex="0"
    role="button"
    :aria-label="`${group}グループ、受講生${studentCount}人`"
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
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';

interface Props {
  className: string;
  taskId: string;
  group: string;
  studentCount: number;
}

const props = defineProps<Props>();
const router = useRouter();

const handleClick = () => {
  router.push(`/class/${props.className}/task/${props.taskId}/group/${props.group}/students`);
};
</script>
