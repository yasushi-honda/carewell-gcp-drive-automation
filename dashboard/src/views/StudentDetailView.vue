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
      戻る
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
        :class="student.status === 'withdrawn' ? 'bg-gray-50' : 'bg-white'"
      >
        <!-- 名前とステータス -->
        <div class="flex items-center justify-between mb-6 pb-4 border-b border-gray-200">
          <div>
            <h1 class="text-3xl font-bold text-gray-900 mb-1">{{ student.name }}</h1>
            <p class="text-sm text-gray-500">{{ student.furigana }}</p>
          </div>
          <div class="flex items-center gap-3">
            <span
              :class="student.status === 'active'
                ? 'bg-green-100 text-green-800 border-green-200'
                : 'bg-red-100 text-red-800 border-red-200'"
              class="px-4 py-2 rounded-full text-sm font-semibold border"
            >
              {{ student.status === 'active' ? 'アクティブ' : '辞退' }}
            </span>
            <button
              v-if="isAdmin"
              @click="toggleStatus"
              :disabled="updating"
              class="px-4 py-2 text-sm font-medium rounded-md transition-colors shadow-sm"
              :class="student.status === 'active'
                ? 'bg-red-50 text-red-700 hover:bg-red-100 border border-red-200'
                : 'bg-green-50 text-green-700 hover:bg-green-100 border border-green-200'"
            >
              {{ updating ? '更新中...' : (student.status === 'active' ? '辞退に変更' : 'アクティブに変更') }}
            </button>
          </div>
        </div>

        <!-- 基本情報 -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          <!-- 受講生番号 -->
          <div class="bg-gray-50 rounded-lg p-4 border border-gray-200">
            <div class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">受講生番号</div>
            <div class="text-lg font-semibold text-gray-900">{{ student.student_number }}</div>
          </div>

          <!-- 日介番号 -->
          <div class="bg-gray-50 rounded-lg p-4 border border-gray-200">
            <div class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">日介番号</div>
            <div class="text-lg font-semibold text-gray-900">{{ student.student_id }}</div>
          </div>

          <!-- クラス -->
          <div class="bg-gray-50 rounded-lg p-4 border border-gray-200">
            <div class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">クラス</div>
            <div class="text-lg font-semibold text-gray-900">{{ student.class_name || '-' }}</div>
          </div>

          <!-- グループ -->
          <div class="bg-gray-50 rounded-lg p-4 border border-gray-200">
            <div class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">グループ</div>
            <div class="text-lg font-semibold text-gray-900">{{ student.group }}</div>
          </div>

          <!-- 会社 -->
          <div class="bg-gray-50 rounded-lg p-4 border border-gray-200 md:col-span-2">
            <div class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">会社</div>
            <div class="text-lg font-semibold text-gray-900">{{ student.company || '-' }}</div>
          </div>

          <!-- 事業所 -->
          <div class="bg-gray-50 rounded-lg p-4 border border-gray-200 md:col-span-2 lg:col-span-3">
            <div class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">事業所</div>
            <div class="text-lg font-semibold text-gray-900">{{ student.office || '-' }}</div>
          </div>
        </div>

        <!-- サービス種別 -->
        <div class="bg-blue-50 rounded-lg p-4 border border-blue-200">
          <div class="text-xs font-medium text-blue-700 uppercase tracking-wider mb-2">サービス種別</div>
          <div class="text-sm text-gray-900 leading-relaxed">{{ student.service_type }}</div>
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
import { useAuth } from '../composables/useAuth';
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
// 管理者モード（Issue #12: Firebase Authenticationのログイン状態+admins許可リストで判定）
const { isAdmin } = useAuth();

onMounted(async () => {
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
  if (!isAdmin.value) {
    alert('管理者ログインが必要です');
    return;
  }

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
    const isPermissionDenied =
      err instanceof Error && 'code' in err && (err as { code?: string }).code === 'permission-denied';
    alert(
      isPermissionDenied
        ? '管理者権限がないか、セッションが切れています。再ログインしてください'
        : 'ステータスの更新に失敗しました'
    );
  } finally {
    updating.value = false;
  }
};

const navigateBack = () => {
  // ブラウザ履歴を使って前のページに戻る
  // (グループページから来た場合はグループページに、受講生一覧から来た場合は受講生一覧に戻る)
  router.back();
};
</script>
