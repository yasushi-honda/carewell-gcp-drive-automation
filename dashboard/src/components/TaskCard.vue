<template>
  <div
    class="bg-white rounded-lg shadow-md hover:shadow-lg active:shadow-xl transition-shadow duration-200 cursor-pointer p-6 min-h-[12rem] sm:min-h-0"
    @click="$emit('click')"
    @keydown.enter="$emit('click')"
    tabindex="0"
    role="button"
    :aria-label="`${taskId}を開く`"
  >
    <!-- 課題名 -->
    <h2 class="text-xl font-bold text-gray-900 mb-4">
      {{ taskId }}
    </h2>

    <!-- 統計情報 -->
    <div class="space-y-2 text-sm text-gray-600">
      <div class="flex items-center">
        <svg
          class="h-5 w-5 text-gray-400 mr-2"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
          />
        </svg>
        <span>提出ファイル数: <span class="font-semibold">{{ fileCount }}</span></span>
      </div>

      <div class="flex items-center">
        <svg
          class="h-5 w-5 text-gray-400 mr-2"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
          />
        </svg>
        <span>提出学生数: <span class="font-semibold">{{ studentCount }}</span></span>
      </div>

      <div class="flex items-center">
        <svg
          class="h-5 w-5 text-gray-400 mr-2"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <span>最終提出: <span class="font-semibold">{{ lastSubmit ? formatDate(lastSubmit) : '未提出' }}</span></span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * TaskCard Component
 * 課題情報を1枚のカードとして表示
 */

interface Props {
  taskId: string;
  fileCount: number;
  studentCount: number;
  lastSubmit: string | null;
}

defineProps<Props>();

defineEmits<{
  click: [];
}>();

/**
 * ISO 8601日時をYYYY/MM/DD形式に変換
 */
function formatDate(isoDate: string): string {
  try {
    const date = new Date(isoDate);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}/${month}/${day}`;
  } catch (error) {
    console.warn('Failed to format date:', isoDate, error);
    return isoDate;
  }
}
</script>
