<template>
  <div class="animate-pulse" role="status" aria-busy="true" aria-label="読み込み中">
    <!-- カード形式のスケルトン -->
    <div
      v-if="variant === 'card'"
      class="bg-white rounded-lg shadow-md p-6 space-y-4"
    >
      <div class="h-6 bg-gray-200 rounded w-3/4"></div>
      <div class="h-4 bg-gray-200 rounded w-1/2"></div>
      <div class="h-4 bg-gray-200 rounded w-2/3"></div>
    </div>

    <!-- リスト形式のスケルトン -->
    <div
      v-else-if="variant === 'list'"
      class="bg-white rounded-lg shadow-md p-4 space-y-3"
    >
      <div class="h-5 bg-gray-200 rounded w-full"></div>
      <div class="h-4 bg-gray-200 rounded w-4/5"></div>
    </div>

    <!-- テーブル形式のスケルトン -->
    <div v-else-if="variant === 'table'" class="bg-white rounded-lg shadow-md overflow-hidden">
      <div class="p-4 space-y-3">
        <div class="h-4 bg-gray-200 rounded w-full"></div>
        <div class="h-4 bg-gray-200 rounded w-full"></div>
        <div class="h-4 bg-gray-200 rounded w-full"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * LoadingSkeleton Component
 * ローディング中に表示するスケルトンUI
 */

interface Props {
  variant?: 'card' | 'list' | 'table';
}

withDefaults(defineProps<Props>(), {
  variant: 'card',
});
</script>
