<template>
  <nav class="flex" aria-label="Breadcrumb">
    <ol class="inline-flex items-center space-x-1 md:space-x-3">
      <li
        v-for="(item, index) in items"
        :key="index"
        class="inline-flex items-center"
      >
        <!-- Separator (except for first item) -->
        <svg
          v-if="index > 0"
          class="w-3 h-3 text-gray-400 mx-1"
          aria-hidden="true"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 6 10"
        >
          <path
            stroke="currentColor"
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="m1 9 4-4-4-4"
          />
        </svg>

        <!-- Home icon for first item -->
        <router-link
          v-if="index === 0"
          :to="item.to"
          class="inline-flex items-center text-sm font-medium text-gray-700 hover:text-blue-600"
        >
          <svg
            class="w-4 h-4 mr-2"
            aria-hidden="true"
            xmlns="http://www.w3.org/2000/svg"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              d="m19.707 9.293-2-2-7-7a1 1 0 0 0-1.414 0l-7 7-2 2a1 1 0 0 0 1.414 1.414L2 10.414V18a2 2 0 0 0 2 2h3a1 1 0 0 0 1-1v-4a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v4a1 1 0 0 0 1 1h3a2 2 0 0 0 2-2v-7.586l.293.293a1 1 0 0 0 1.414-1.414Z"
            />
          </svg>
          {{ item.label }}
        </router-link>

        <!-- Link for middle items -->
        <router-link
          v-else-if="index < items.length - 1"
          :to="item.to"
          class="inline-flex items-center text-sm font-medium text-gray-700 hover:text-blue-600"
        >
          {{ item.label }}
        </router-link>

        <!-- Current page (last item, not clickable) -->
        <span
          v-else
          class="inline-flex items-center text-sm font-medium text-gray-500"
          aria-current="page"
        >
          {{ item.label }}
        </span>
      </li>
    </ol>
  </nav>
</template>

<script setup lang="ts">
/**
 * Breadcrumb Component
 * パンくずリストコンポーネント
 *
 * 現在位置を視覚的に表示し、上位階層への直接ナビゲーションを提供
 */

export interface BreadcrumbItem {
  label: string;
  to: string;
}

interface Props {
  items: BreadcrumbItem[];
}

defineProps<Props>();
</script>
