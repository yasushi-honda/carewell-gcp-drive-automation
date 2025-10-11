<template>
  <div
    class="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow duration-200 cursor-pointer p-6"
    @click="$emit('click')"
    @keypress.enter="$emit('click')"
    tabindex="0"
    role="button"
    :aria-label="`${className}を開く`"
  >
    <!-- クラス名 -->
    <h2 class="text-xl font-bold text-gray-900 mb-4">
      {{ className }}
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
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
        <span>課題数: <span class="font-semibold">{{ taskCount }}</span></span>
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
            d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
          />
        </svg>
        <span>提出ファイル数: <span class="font-semibold">{{ fileCount }}</span></span>
      </div>

      <div v-if="lastUpdated" class="flex items-center">
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
        <span>最終更新: <span class="font-semibold">{{ formatDate(lastUpdated) }}</span></span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * ClassCard Component
 * クラス情報を1枚のカードとして表示
 */

interface Props {
  className: string;
  taskCount: number;
  fileCount: number;
  lastUpdated: string | null;
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
