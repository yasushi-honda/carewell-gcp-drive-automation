<template>
  <!--
    受講生のカードリスト（狭い画面用。広い画面では従来のテーブルを使う）。
    カード全体が詳細画面へのリンク（router-link）なので、キーボード（Tab / Enter）でも操作できる。
  -->
  <ul class="grid grid-cols-1 gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3" aria-label="受講生一覧">
    <li v-for="student in students" :key="student.student_id">
      <router-link
        :to="`/students/${student.student_id}`"
        class="block h-full min-h-11 rounded-lg border p-4 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        :class="
          student.status === 'withdrawn'
            ? 'border-gray-200 bg-gray-100 opacity-60 hover:bg-gray-200'
            : 'border-gray-200 bg-white hover:border-blue-300 hover:bg-gray-50'
        "
      >
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <p class="break-words text-base font-semibold text-gray-900">{{ student.name }}</p>
            <p class="break-words text-xs text-gray-500">{{ student.furigana }}</p>
          </div>
          <span class="shrink-0 text-sm font-medium text-blue-600">{{ student.student_id }}</span>
        </div>

        <dl class="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
          <div>
            <dt class="text-gray-500">通し番号</dt>
            <dd class="text-gray-900">{{ student.serial_number || '-' }}</dd>
          </div>
          <div v-if="showClass">
            <dt class="text-gray-500">クラス</dt>
            <dd class="text-gray-900">{{ student.class_name || '-' }}</dd>
          </div>
          <div v-if="showGroup">
            <dt class="text-gray-500">グループ</dt>
            <dd class="text-gray-900">{{ student.group }}</dd>
          </div>
          <div>
            <dt class="text-gray-500">サービス種別</dt>
            <dd class="text-gray-900">{{ student.service_type }}</dd>
          </div>
        </dl>
      </router-link>
    </li>
  </ul>
</template>

<script setup lang="ts">
import type { Student } from '../types/models';

withDefaults(
  defineProps<{
    students: Student[];
    /** クラスを表示する（受講生一覧。グループ内の一覧では全員同じクラスなので不要） */
    showClass?: boolean;
    /** グループを表示する（受講生一覧。グループ内の一覧では全員同じグループなので不要） */
    showGroup?: boolean;
  }>(),
  { showClass: false, showGroup: false }
);
</script>
