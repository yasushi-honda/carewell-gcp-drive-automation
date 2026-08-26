<template>
  <div class="flex items-center">
    <!-- 初期化待ち: ちらつき防止のスケルトン -->
    <div v-if="!authReady" class="h-8 w-24 rounded-md bg-gray-100 animate-pulse" />

    <!-- 未ログイン -->
    <button
      v-else-if="!user"
      @click="handleLogin"
      :disabled="loggingIn"
      class="inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-md border border-gray-300 text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
    >
      管理者ログイン
    </button>

    <!-- ログイン済み -->
    <div v-else class="flex items-center gap-2 text-sm">
      <span class="text-gray-600">
        {{ user.email }}<span v-if="!isAdmin" class="text-gray-400">（権限なし）</span>
      </span>
      <button
        @click="handleLogout"
        class="px-2 py-1 text-gray-500 hover:text-gray-700 hover:underline focus:outline-none"
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
