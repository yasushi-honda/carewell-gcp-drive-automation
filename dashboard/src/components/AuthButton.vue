<template>
  <div class="flex items-center">
    <!-- 初期化待ち: ちらつき防止のスケルトン -->
    <div v-if="!authReady" class="h-8 w-24 rounded-md bg-gray-100 animate-pulse" />

    <!-- 未ログイン -->
    <!-- <sm は「管理者」に短縮（320px でも2行目に収めるため。読み上げ名は aria-label で維持） -->
    <button
      v-else-if="!user"
      @click="handleLogin"
      :disabled="loggingIn"
      aria-label="管理者ログイン"
      class="inline-flex items-center justify-center min-h-11 lg:min-h-0 px-3 py-1.5 text-sm font-medium whitespace-nowrap rounded-md border border-gray-300 text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
    >
      <span class="sm:hidden" aria-hidden="true">管理者</span>
      <span class="hidden sm:inline">管理者ログイン</span>
    </button>

    <!-- ログイン済み: メールは狭幅で省略表示（truncate）、ログアウトは <lg で44px以上 -->
    <div v-else class="flex items-center gap-2 text-sm min-w-0">
      <span class="text-gray-600 truncate max-w-[9rem] sm:max-w-[16rem] lg:max-w-none">
        {{ user.email }}<span v-if="!isAdmin" class="text-gray-400">（権限なし）</span>
      </span>
      <button
        @click="handleLogout"
        class="inline-flex items-center min-h-11 lg:min-h-0 px-2 py-1 text-gray-500 hover:text-gray-700 hover:underline focus:outline-none whitespace-nowrap"
      >
        ログアウト
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useAuth } from '../composables/useAuth'

const { user, isAdmin, authReady, signInWithGoogle, logout } = useAuth()

const loggingIn = ref(false)

const handleLogin = async () => {
  loggingIn.value = true
  try {
    await signInWithGoogle()
  } catch (err) {
    console.error('[AuthButton] login failed', err)
    alert('ログインに失敗しました')
  } finally {
    loggingIn.value = false
  }
}

const handleLogout = async () => {
  try {
    await logout()
  } catch (err) {
    console.error('[AuthButton] logout failed', err)
  }
}
</script>
