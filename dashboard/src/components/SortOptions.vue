<template>
  <!--
    並べ替えボタン（カード表示用。テーブル表示では見出しセルのクリックで並べ替える）。
    各ボタンは44px以上。現在の並び順は aria-pressed と読み上げ用テキストでも伝える。
  -->
  <div
    role="group"
    aria-label="ソートオプション"
    class="flex flex-wrap gap-2 border-b border-gray-200 px-4 py-3"
  >
    <button
      v-for="option in options"
      :key="option.key"
      type="button"
      :aria-pressed="option.order !== null"
      class="inline-flex min-h-11 items-center gap-1.5 rounded-md border px-3 text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
      :class="
        option.order !== null
          ? 'border-blue-500 bg-blue-50 text-blue-700'
          : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
      "
      @click="emit('toggle', option.key)"
    >
      <span>{{ option.label }}</span>
      <span class="text-xs" aria-hidden="true">{{ indicator(option.order) }}</span>
      <span class="sr-only">{{ description(option.order) }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
type SortOrder = 'asc' | 'desc' | null;

defineProps<{
  options: Array<{ key: string; label: string; order: SortOrder }>;
}>();

const emit = defineEmits<{
  toggle: [key: string];
}>();

const indicator = (order: SortOrder) => (order === 'asc' ? '▲' : order === 'desc' ? '▼' : '⇅');
const description = (order: SortOrder) =>
  order === 'asc' ? '（昇順）' : order === 'desc' ? '（降順）' : '（並べ替えなし）';
</script>
