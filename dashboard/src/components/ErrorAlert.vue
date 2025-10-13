<template>
  <div class="bg-red-50 border border-red-200 rounded-lg p-4" role="alert" aria-live="assertive">
    <div class="flex items-start">
      <!-- エラーアイコン -->
      <div class="flex-shrink-0">
        <svg
          class="h-5 w-5 text-red-400"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path
            fill-rule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
            clip-rule="evenodd"
          />
        </svg>
      </div>

      <!-- エラーメッセージ -->
      <div class="ml-3 flex-1">
        <h3 class="text-sm font-medium text-red-800">
          {{ title }}
        </h3>
        <div class="mt-2 text-sm text-red-700">
          {{ message }}
        </div>

        <!-- リトライボタン -->
        <div v-if="showRetry" class="mt-4">
          <button
            type="button"
            class="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-red-700 bg-red-100 hover:bg-red-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
            @click="$emit('retry')"
          >
            再試行
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * ErrorAlert Component
 * エラーメッセージを表示するコンポーネント
 */

interface Props {
  title?: string;
  message: string;
  showRetry?: boolean;
}

withDefaults(defineProps<Props>(), {
  title: 'エラーが発生しました',
  showRetry: true,
});

defineEmits<{
  retry: [];
}>();
</script>
