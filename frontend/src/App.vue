<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, ApiError, type User } from './api'
import Icon from './components/Icon.vue'
import LoginModal from './components/LoginModal.vue'
import Wall from './components/Wall.vue'

const user = ref<User | null>(null)
const loading = ref(true)
const showLogin = ref(false)
const toast = ref('')
const onlineMembers = ref<User[]>([])
const bootstrapError = ref('')
const loggingOut = ref(false)
async function restoreSession() {
  loading.value = true; bootstrapError.value = ''
  try { user.value = await api<User>('/auth/me') }
  catch (e) { if (!(e instanceof ApiError && e.status === 401)) bootstrapError.value = (e as Error).message }
  finally { loading.value = false }
}
onMounted(restoreSession)
function authenticated(value: User) { user.value = value; showLogin.value = false; toast.value = '登录成功！'; setTimeout(() => toast.value = '', 2500) }
function notify(text: string) { toast.value = text; setTimeout(() => toast.value = '', 3000) }
function expired() { if (!loggingOut.value) { user.value = null; showLogin.value = true; notify('登录已过期，请重新登录') } }
async function logout() {
  if (loggingOut.value) return
  loggingOut.value = true
  try { await api('/auth/logout', { method: 'POST' }); user.value = null; showLogin.value = false }
  catch (e) { notify((e as Error).message) }
  finally { loggingOut.value = false }
}
</script>

<template>
  <main class="canvas-shell" aria-label="实时评论墙">
    <aside class="sidebar" aria-label="在线成员">
      <img src="/assets/logo.svg" class="brand-logo" alt="鹰眼智能" />
      <div class="sidebar-divider" />
      <div class="members" :aria-label="`${onlineMembers.length} 人在线`"><span v-for="member in onlineMembers" :key="member.id" class="member" :title="`${member.name}${member.id === user?.id ? '（我）' : ''}`"><img :src="member.avatar" :alt="member.name" /><i /></span></div>
      <button v-if="user" class="account-button member" :title="`${user.name} · 点击退出登录`" aria-label="退出登录" :disabled="loggingOut" @click="logout"><img :src="user.avatar" :alt="user.name" /><i /></button>
      <button v-else class="account-button anonymous" aria-label="登录账号" @click="showLogin = true"><Icon name="account" :size="20" /></button>
    </aside>
    <section class="wall-viewport">
      <button v-if="!user && !loading" class="top-login primary-button" @click="showLogin = true"><Icon name="account" :size="16" /> 登录</button>
      <div v-if="!user && !loading && !bootstrapError" class="welcome-state"><h1>每一个想法，都值得被看见。</h1><p>登录后，点击画布留下你的建议。</p><button class="welcome-login" @click="showLogin = true">登录评论墙 <span aria-hidden="true">↗</span></button></div>
      <p v-if="loading" class="boot-state">正在连接评论墙…</p>
      <div v-if="bootstrapError" class="load-error" role="alert">{{ bootstrapError }} <button @click="restoreSession">重新连接</button></div>
      <Wall v-if="user" :key="user.id" :user="user" @expired="expired" @notify="notify" @members="value => onlineMembers = value" />
    </section>
    <LoginModal v-if="showLogin" @close="showLogin = false" @authenticated="authenticated" />
    <div v-if="toast" class="toast" role="status">{{ toast }}</div>
  </main>
</template>
