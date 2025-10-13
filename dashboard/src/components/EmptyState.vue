<template>
  <div class="text-center py-12">
    <!-- Icon -->
    <div class="flex justify-center mb-4">
      <svg
        v-if="icon === 'folder'"
        class="w-16 h-16 text-gray-400"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
        />
      </svg>

      <svg
        v-else-if="icon === 'document'"
        class="w-16 h-16 text-gray-400"
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

      <svg
        v-else-if="icon === 'search'"
        class="w-16 h-16 text-gray-400"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
        />
      </svg>

      <svg
        v-else-if="icon === 'inbox'"
        class="w-16 h-16 text-gray-400"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
        />
      </svg>

      <!-- Default icon -->
      <svg
        v-else
        class="w-16 h-16 text-gray-400"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
        />
      </svg>
    </div>

    <!-- Title -->
    <h3 class="text-lg font-medium text-gray-900 mb-2">
      {{ title }}
    </h3>

    <!-- Message -->
    <p class="text-sm text-gray-500 mb-6 max-w-md mx-auto">
      {{ message }}
    </p>

    <!-- Action Button (optional) -->
    <div v-if="actionLabel && actionTo" class="flex justify-center">
      <router-link
        :to="actionTo"
        class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
      >
        {{ actionLabel }}
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * EmptyState Component
 * データが存在しない場合の空状態表示コンポーネント
 *
 * 状況に応じたアイコン、メッセージ、アクションボタンを表示
 */

interface Props {
  /** アイコンの種類 */
  icon?: 'folder' | 'document' | 'search' | 'inbox' | 'default';
  /** タイトル */
  title: string;
  /** メッセージ */
  message: string;
  /** アクションボタンのラベル（任意） */
  actionLabel?: string;
  /** アクションボタンの遷移先（任意） */
  actionTo?: string;
}

withDefaults(defineProps<Props>(), {
  icon: 'default',
});
</script>
