<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { api, type User } from '../api'
import Icon from './Icon.vue'

const emit = defineEmits<{ close: []; authenticated: [user: User] }>()
const username = ref('')
const password = ref('')
const remember = ref(true)
const visible = ref(false)
const busy = ref(false)
const error = ref('')
const dialog = ref<HTMLDialogElement>()
const ready = computed(() => username.value.trim() && password.value.length >= 6 && !busy.value)
let previousFocus: HTMLElement | null = null
onMounted(() => {
  previousFocus = document.activeElement as HTMLElement
  dialog.value?.showModal()
})
onBeforeUnmount(() => previousFocus?.focus())
async function submit() {
  if (!ready.value) return
  busy.value = true
  error.value = ''
  try {
    emit('authenticated', await api<User>('/auth/login', { method: 'POST', body: JSON.stringify({ username: username.value, password: password.value, remember: remember.value }) }))
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
function demo(account: string) { username.value = account; password.value = 'Wall2027!' }
</script>

<template>
  <dialog ref="dialog" class="modal login-modal" aria-labelledby="login-title" @cancel.prevent="emit('close')" @click="e => e.target === dialog && emit('close')">
    <header class="modal-header"><span>实时评论墙</span><button class="icon-button" aria-label="关闭登录" @click="emit('close')"><Icon name="close" :size="16" /></button></header>
    <form @submit.prevent="submit">
      <h1 id="login-title">账号登录，留下你的想法</h1>
      <label class="sr-only" for="username">账号</label>
      <input id="username" v-model="username" autofocus autocomplete="username" placeholder="输入用户账号" maxlength="80" :disabled="busy" @input="error = ''" />
      <label class="sr-only" for="password">密码</label>
      <div class="password-field" :class="{ invalid: error }">
        <input id="password" v-model="password" :type="visible ? 'text' : 'password'" autocomplete="current-password" placeholder="输入6–30位密码" minlength="6" maxlength="30" :disabled="busy" :aria-invalid="!!error" :aria-describedby="error ? 'login-error' : undefined" @input="error = ''" />
        <button type="button" class="password-toggle" :aria-label="visible ? '隐藏密码' : '显示密码'" @click="visible = !visible">{{ visible ? '隐藏' : '显示' }}</button>
      </div>
      <p v-if="error" id="login-error" class="form-error" role="alert">{{ error }}</p>
      <button class="primary-button login-submit" type="submit" :disabled="!ready">{{ busy ? '正在登录…' : '登录' }}</button>
      <label class="remember"><input v-model="remember" type="checkbox" /> 自动登录</label>
      <div class="demo-accounts"><span>演示账号 · 点击填入</span><div><button type="button" @click="demo('demo_a')">赵欣 · demo_a</button><button type="button" @click="demo('demo_b')">王美丽 · demo_b</button></div><small>统一密码：Wall2027!</small></div>
    </form>
  </dialog>
</template>
