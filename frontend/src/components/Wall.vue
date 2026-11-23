<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { api, ApiError, type Board, type Note, type User } from '../api'
import Icon from './Icon.vue'
import NoteEditor from './NoteEditor.vue'

const props = defineProps<{ user: User }>()
const emit = defineEmits<{ expired: []; notify: [text: string] }>()
const board = ref<Board>({ revision: -1, comments: [] })
const pending = ref(true)
const loadError = ref('')
const tool = ref<'add' | 'select' | 'drag'>('select')
const editorOpen = ref(false)
const selected = ref<Note | null>(null)
const position = ref({ x: 400, y: 250 })
const viewport = ref<HTMLDivElement>()
const width = ref(1748)
const scale = computed(() => Math.min(1, Math.max(.72, width.value / 1748)))
const worldHeight = computed(() => Math.max(1010, ...board.value.comments.map(n => n.y + 450)))
const savedAt = computed(() => Math.max(0, ...board.value.comments.map(n => n.updated_at)))
let observer: ResizeObserver | undefined
onMounted(() => {
  load()
  observer = new ResizeObserver(entries => width.value = entries[0]?.contentRect.width || 1748)
  if (viewport.value) observer.observe(viewport.value)
})
onBeforeUnmount(() => observer?.disconnect())
async function load() {
  pending.value = true; loadError.value = ''
  try { applyBoard(await api<Board>('/board')) }
  catch (e) { if (e instanceof ApiError && e.status === 401) emit('expired'); else loadError.value = (e as Error).message }
  finally { pending.value = false }
}
function applyBoard(value: Board) { if (value.revision >= board.value.revision) board.value = value }
function addAt(event: MouseEvent) {
  if (tool.value !== 'add' || pending.value) return
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  position.value = { x: Math.max(0, Math.min(1448, (event.clientX - rect.left) / scale.value)), y: Math.max(80, Math.min(5000, (event.clientY - rect.top) / scale.value)) }
  selected.value = null; editorOpen.value = true
}
function openNote(note: Note) { if (tool.value === 'add') return; selected.value = { ...note }; editorOpen.value = true }
function saved(value: Board) { applyBoard(value); editorOpen.value = false; tool.value = 'select'; emit('notify', selected.value ? '修改已保存' : '你的想法已贴上墙') }
const formatTime = (time: number) => new Date(time).toLocaleString('zh-CN', { hour12: false }).replaceAll('/', '-')
</script>

<template>
  <div class="board-area">
    <div ref="viewport" class="board-scroll" :class="`tool-${tool}`">
      <div class="world-sizer" :style="{ width: `${1748 * scale}px`, height: `${worldHeight * scale}px` }">
        <div class="world" aria-label="评论画布" :style="{ width: '1748px', height: `${worldHeight}px`, transform: `scale(${scale})` }" @click.self="addAt">
          <article v-for="note in board.comments" :key="note.id" class="sticky" :style="{ left: `${note.x}px`, top: `${note.y}px`, transform: `rotate(${note.rotation}deg)`, background: note.color }" :data-note-id="note.id" tabindex="0" :aria-label="`${note.author.name}的贴纸：${note.text}`" @click.stop="openNote(note)" @keydown.enter.prevent="openNote(note)">
            <span class="tape" aria-hidden="true" :style="{ background: ['#ffca8e', '#9dd3ff', '#ffe68c', '#9df4ec'][note.id.charCodeAt(note.id.length - 1)! % 4] }" />
            <div class="note-body" v-html="note.content_html" />
            <footer class="note-meta"><img :src="note.author.avatar" alt="" class="note-avatar" /><div class="note-author"><span>{{ note.author.name }}</span><time :datetime="new Date(note.created_at).toISOString()">{{ formatTime(note.created_at) }}</time></div></footer>
          </article>
        </div>
      </div>
    </div>
    <p class="wall-count">共反馈 <strong>{{ board.comments.length }}</strong> 条建议</p>
    <p v-if="savedAt" class="save-status">{{ formatTime(savedAt) }} 已保存</p>
    <p v-if="pending" class="boot-state">正在读取评论墙…</p>
    <div v-if="loadError" class="load-error" role="alert">{{ loadError }} <button @click="load">重新连接</button></div>
    <div v-if="!pending && !loadError && !board.comments.length" class="empty-wall"><p>这里，等你的第一个想法。</p><span>选择下方「新增」，再点击画布。</span></div>
    <nav class="wall-tools" aria-label="画布工具"><button :class="{ active: tool === 'add' }" title="新增贴纸 · 点击画布选择位置" aria-label="新增贴纸" :aria-pressed="tool === 'add'" @click="tool = 'add'"><Icon name="add" /></button><button :class="{ active: tool === 'select' }" title="鼠标选择 · 点击贴纸查看或编辑" aria-label="鼠标选择" :aria-pressed="tool === 'select'" @click="tool = 'select'"><Icon name="cursor" /></button><button :class="{ active: tool === 'drag' }" title="拖动自己的贴纸" aria-label="拖动贴纸" :aria-pressed="tool === 'drag'" @click="tool = 'drag'"><Icon name="hand" /></button></nav>
    <div v-if="tool === 'add'" class="tool-hint" role="status">点击画布，贴下一个新想法</div>
    <NoteEditor v-if="editorOpen" :user="props.user" :note="selected" :position="position" :readonly="!!selected && selected.author.id !== user.id" @close="editorOpen = false" @saved="saved" />
  </div>
</template>
