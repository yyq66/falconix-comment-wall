<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import type { User } from '../api'

defineProps<{ user: User; busy: boolean }>()
defineEmits<{ logout: [] }>()
const open = ref(false)
const root = ref<HTMLElement>()
const trigger = ref<HTMLButtonElement>()
const logoutButton = ref<HTMLButtonElement>()

function dismissOutside(event: PointerEvent) {
  if (!root.value?.contains(event.target as Node)) open.value = false
}
function dismissOnBlur(event: FocusEvent) {
  if (!root.value?.contains(event.relatedTarget as Node | null)) open.value = false
}
function escape(event: KeyboardEvent) {
  if (!open.value) return
  event.preventDefault()
  event.stopPropagation()
  open.value = false
  trigger.value?.focus()
}
async function focusAction() {
  open.value = true
  await nextTick()
  logoutButton.value?.focus()
}
onMounted(() => document.addEventListener('pointerdown', dismissOutside))
onBeforeUnmount(() => document.removeEventListener('pointerdown', dismissOutside))
</script>

<template>
  <div ref="root" class="account-control" @focusout="dismissOnBlur" @keydown.esc="escape">
    <button ref="trigger" class="account-button member" :class="{ 'account-active': open }" :title="`${user.name} · 账号菜单`" aria-label="账号菜单" :aria-expanded="open" aria-controls="account-panel" :disabled="busy" @click="open = !open" @keydown.down.prevent="focusAction">
      <img :src="user.avatar" :alt="user.name" /><i />
    </button>
    <section v-if="open" id="account-panel" class="account-panel" aria-label="当前登录账号">
      <div class="account-profile"><img :src="user.avatar" alt="" /><div><strong>{{ user.name }}</strong><span>{{ user.username }}</span></div></div>
      <button ref="logoutButton" class="logout-button" aria-label="退出登录" :disabled="busy" :aria-busy="busy" @click="$emit('logout')">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h4M14 8l4 4-4 4M9 12h9" /></svg>
        {{ busy ? '正在退出…' : '退出登录' }}
      </button>
    </section>
  </div>
</template>
