<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- 戻るボタン -->
    <button
      @click="navigateBack"
      class="mb-4 inline-flex items-center text-sm font-medium text-gray-700 hover:text-gray-900"
    >
      <svg
        class="mr-2 h-5 w-5"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M10 19l-7-7m0 0l7-7m-7 7h18"
        />
      </svg>
      受講生一覧に戻る
    </button>

    <!-- ローディング状態 -->
    <div v-if="loading" class="space-y-4">
      <LoadingSkeleton variant="card" />
      <LoadingSkeleton variant="card" />
    </div>

    <!-- 受講生が見つからない -->
    <ErrorAlert
      v-else-if="!student"
      message="受講生が見つかりませんでした"
    />

    <!-- 受講生情報 -->
    <div v-else>
      <!-- 基本情報カード -->
      <div
        class="shadow-sm rounded-lg p-6 mb-6 transition-colors"
        :class="student.status === 'withdrawn' ? 'bg-gray-100' : 'bg-white'"
      >
        <h1 class="text-3xl font-bold text-gray-900 mb-6">{{ student.name }}</h1>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <!-- ふりがな -->
          <div>
            <div class="text-sm font-semibold text-gray-600 mb-1">ふりがな</div>
            <div class="text-gray-900">{{ student.furigana }}</div>
          </div>

          <!-- 受講生番号 -->
          <div>
            <div class="text-sm font-semibold text-gray-600 mb-1">受講生番号</div>
            <div class="text-gray-900">{{ student.student_number }}</div>
          </div>

          <!-- 日介番号 -->
          <div>
            <div class="text-sm font-semibold text-gray-600 mb-1">日介番号</div>
            <div class="text-gray-900">{{ student.student_id }}</div>
          </div>

          <!-- クラス -->
          <div>
            <div class="text-sm font-semibold text-gray-600 mb-1">クラス</div>
            <div class="text-gray-900">{{ student.class_name || '-' }}</div>
          </div>

          <!-- グループ -->
          <div>
            <div class="text-sm font-semibold text-gray-600 mb-1">グループ</div>
            <div class="text-gray-900">{{ student.group }}</div>
          </div>

          <!-- サービス種別 -->
          <div class="md:col-span-2 lg:col-span-3">
            <div class="text-sm font-semibold text-gray-600 mb-1">サービス種別</div>
            <div class="text-gray-900">{{ student.service_type }}</div>
          </div>

          <!-- 会社 -->
          <div>
            <div class="text-sm font-semibold text-gray-600 mb-1">会社</div>
            <div class="text-gray-900">{{ student.company || '-' }}</div>
          </div>

          <!-- 事業所 -->
          <div>
            <div class="text-sm font-semibold text-gray-600 mb-1">事業所</div>
            <div class="text-gray-900">{{ student.office || '-' }}</div>
          </div>

          <!-- ステータス -->
          <div>
            <div class="text-sm font-semibold text-gray-600 mb-1">ステータス</div>
            <div class="flex items-center gap-3">
              <span
                :class="student.status === 'active' ? 'text-green-600' : 'text-red-600'"
                class="font-medium"
              >
                {{ student.status === 'active' ? 'アクティブ' : '辞退' }}
              </span>
              <button
                v-if="isAdmin"
                @click="toggleStatus"
                :disabled="updating"
                class="px-3 py-1 text-sm font-medium rounded-md transition-colors"
                :class="student.status === 'active'
                  ? 'bg-red-50 text-red-700 hover:bg-red-100'
                  : 'bg-green-50 text-green-700 hover:bg-green-100'"
              >
                {{ updating ? '更新中...' : (student.status === 'active' ? '辞退に変更' : 'アクティブに変更') }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 提出履歴 -->
      <div class="bg-white shadow-sm rounded-lg p-6">
        <h2 class="text-2xl font-bold text-gray-900 mb-4">提出履歴</h2>
        <SubmissionFileList :student-id="studentId" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { doc, getDoc, updateDoc, Timestamp } from 'firebase/firestore';
import { getDb } from '../config/firebase';
import type { Student } from '../types/models';
import LoadingSkeleton from '../components/LoadingSkeleton.vue';
import ErrorAlert from '../components/ErrorAlert.vue';
import SubmissionFileList from '../components/SubmissionFileList.vue';

const route = useRoute();
const router = useRouter();
const studentId = route.params.id as string;

const student = ref<Student | null>(null);
const loading = ref(true);
const updating = ref(false);
const isAdmin = ref(false);

onMounted(async () => {
  // 管理者モード判定（App.vueでグローバル管理されているsessionStorageを読み取るだけ）
  isAdmin.value = sessionStorage.getItem('adminMode') === 'true';
  console.log('[StudentDetailView] Admin mode:', isAdmin.value);

  try {
    const db = getDb();
    const docRef = doc(db, 'students', studentId);
    const docSnap = await getDoc(docRef);

    if (docSnap.exists()) {
      const data = docSnap.data();
      student.value = {
        student_id: docSnap.id,
        name: data.name || '',
        furigana: data.furigana || '',
        group: data.group || '',
        company: data.company || '',
        office: data.office || '',
        service_type: data.service_type || '',
        serial_number: data.serial_number || 0,
        student_number: data.student_number || '',
        class_name: data.class_name || '',
        status: data.status || 'active',
        created_at: data.created_at instanceof Timestamp ? data.created_at.toDate() : undefined,
        last_updated: data.last_updated instanceof Timestamp ? data.last_updated.toDate() : undefined,
      } as Student;
    }
  } catch (err) {
    console.error('Error fetching student:', err);
  } finally {
    loading.value = false;
  }
});

/**
 * ステータス切り替え（アクティブ ⇔ 辞退）
 */
const toggleStatus = async () => {
  if (!student.value) return;

  updating.value = true;
  try {
    const db = getDb();
    const docRef = doc(db, 'students', studentId);
    const newStatus = student.value.status === 'active' ? 'withdrawn' : 'active';

    await updateDoc(docRef, {
      status: newStatus,
      last_updated: Timestamp.now()
    });

    student.value.status = newStatus;
  } catch (err) {
    console.error('Error updating student status:', err);
    alert('ステータスの更新に失敗しました');
  } finally {
    updating.value = false;
  }
};

const navigateBack = () => {
  router.push('/students');
};
</script>
