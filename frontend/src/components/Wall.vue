<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, onUpdated, ref } from 'vue'
import { api, ApiError, type Board, type Note, type User } from '../api'
import Icon from './Icon.vue'
import NoteEditor from './NoteEditor.vue'
import { useRealtime } from '../useRealtime'

const props = defineProps<{ user: User }>()
const emit = defineEmits<{ expired: []; notify: [text: string]; members: [value: User[]] }>()
const board = ref<Board>({ revision: -1, comments: [] })
const pending = ref(true)
const loadError = ref('')
const tool = ref<'add' | 'select' | 'drag'>('select')
const editorOpen = ref(false)
const selected = ref<Note | null>(null)
const position = ref({ x: 400, y: 250 })
const viewport = ref<HTMLDivElement>()
const width = ref(1748)
const organized = ref(false)
const showOverview = ref(true)
const noteHeights = ref<Record<string, number>>({})
const sentimentColors: Record<string, string> = { positive: '#dffce5', neutral: '#f5f6fa', negative: '#ffe8ef' }
const categories = [{ key: 'positive', label: '正向' }, { key: 'neutral', label: '中性' }, { key: 'negative', label: '负面' }]
const summary = computed(() => {
  const total = board.value.comments.length
  const values = categories.map(c => ({ ...c, count: board.value.comments.filter(n => n.sentiment === c.key).length, percent: 0 }))
  if (total) {
    values.forEach(v => v.percent = Math.floor(v.count * 100 / total))
    const remainder = 100 - values.reduce((sum, v) => sum + v.percent, 0)
    const ranked = [...values].sort((a, b) => (b.count * 100 / total % 1) - (a.count * 100 / total % 1))
    ranked.slice(0, remainder).forEach(v => v.percent++)
  }
  return values
})
const arrangedPositions = computed(() => {
  const result: Record<string, { x: number; y: number }> = {}
  categories.forEach((category, index) => {
    let y = 120
    board.value.comments.filter(n => n.sentiment === category.key).forEach(note => {
      result[note.id] = { x: 260 + index * 370, y }
      y += (noteHeights.value[note.id] || 220) + 36
    })
  })
  return result
})
function notePosition(note: Note) { return organized.value ? arrangedPositions.value[note.id] || note : note }
const scale = computed(() => Math.min(1, Math.max(.72, width.value / 1748)))
const worldWidth = computed(() => Math.max(1748, ...board.value.comments.map(n => notePosition(n).x + 360)))
const worldHeight = computed(() => Math.max(1010, ...board.value.comments.map(n => notePosition(n).y + (noteHeights.value[n.id] || 360) + 160)))
const savedAt = computed(() => Math.max(0, ...board.value.comments.map(n => n.updated_at)))
const busyLikes = ref(new Set<string>())
const busyMoves = ref(new Set<string>())
const dragging = ref<string | null>(null)
let drag: { id: string; startX: number; startY: number; x: number; y: number; version: number } | null = null
const { status, reconnect } = useRealtime({
  board: value => { applyBoard(value); pending.value = false; loadError.value = '' },
  members: value => emit('members', value),
  expired: () => emit('expired'),
})
let observer: ResizeObserver | undefined
onMounted(() => {
  load()
  observer = new ResizeObserver(entries => width.value = entries[0]?.contentRect.width || 1748)
  if (viewport.value) observer.observe(viewport.value)
})
onBeforeUnmount(() => observer?.disconnect())
onUpdated(() => {
  const next = { ...noteHeights.value }
  let changed = false
  viewport.value?.querySelectorAll<HTMLElement>('.sticky').forEach(el => {
    const id = el.dataset.noteId!
    if (Math.abs((next[id] || 0) - el.offsetHeight) > 1) { next[id] = el.offsetHeight; changed = true }
  })
  if (changed) noteHeights.value = next
})
async function load() {
  pending.value = true; loadError.value = ''
  try { applyBoard(await api<Board>('/board')) }
  catch (e) { if (e instanceof ApiError && e.status === 401) emit('expired'); else loadError.value = (e as Error).message }
  finally { pending.value = false }
}
function applyBoard(value: Board) {
  if (value.revision < board.value.revision) return
  const current = drag && board.value.comments.find(n => n.id === drag!.id)
  if (current) value.comments = value.comments.map(note => note.id === current.id ? { ...note, x: current.x, y: current.y } : note)
  board.value = value
}
function addAt(event: MouseEvent) {
  if (tool.value !== 'add' || pending.value) return
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  position.value = { x: Math.max(0, Math.min(5000, (event.clientX - rect.left) / scale.value)), y: Math.max(80, Math.min(5000, (event.clientY - rect.top) / scale.value)) }
  selected.value = null; editorOpen.value = true
}
function openNote(note: Note) { if (tool.value !== 'select') return; selected.value = { ...note }; editorOpen.value = true }
function saved(value: Board) { applyBoard(value); editorOpen.value = false; tool.value = 'select'; emit('notify', selected.value ? '修改已保存' : '你的想法已贴上墙') }
const formatTime = (time: number) => new Date(time).toLocaleString('zh-CN', { hour12: false }).replaceAll('/', '-')
async function like(note: Note) {
  if (busyLikes.value.has(note.id)) return
  busyLikes.value.add(note.id)
  try { applyBoard(await api<Board>(`/comments/${note.id}/like`, { method: 'PUT', body: JSON.stringify({ liked: !note.liked_by.includes(props.user.id) }) })) }
  catch (e) { emit('notify', (e as Error).message) }
  finally { busyLikes.value.delete(note.id) }
}
function startDrag(event: PointerEvent, note: Note) {
  if (tool.value !== 'drag' || note.author.id !== props.user.id || event.button !== 0 || busyMoves.value.has(note.id) || (event.target as HTMLElement).closest('button')) return
  event.preventDefault()
  const target = event.currentTarget as HTMLElement
  target.setPointerCapture(event.pointerId)
  drag = { id: note.id, startX: event.clientX, startY: event.clientY, x: note.x, y: note.y, version: note.position_version }
  dragging.value = note.id
}
function moveDrag(event: PointerEvent) {
  if (!drag) return
  const note = board.value.comments.find(n => n.id === drag!.id)
  if (!note) return
  note.x = Math.max(0, Math.min(5000, drag.x + (event.clientX - drag.startX) / scale.value))
  note.y = Math.max(80, Math.min(5000, drag.y + (event.clientY - drag.startY) / scale.value))
}
async function persistPosition(note: Note, version: number) {
  busyMoves.value.add(note.id)
  try { applyBoard(await api<Board>(`/comments/${note.id}/position`, { method: 'PATCH', body: JSON.stringify({ x: Math.round(note.x), y: Math.round(note.y), position_version: version }) })) }
  catch (e) { emit('notify', (e as Error).message); await load() }
  finally { busyMoves.value.delete(note.id) }
}
function endDrag(event: PointerEvent) {
  if (!drag) return
  const current = drag; drag = null; dragging.value = null
  const target = event.currentTarget as HTMLElement
  if (target.hasPointerCapture(event.pointerId)) target.releasePointerCapture(event.pointerId)
  const note = board.value.comments.find(n => n.id === current.id)
  if (note && (Math.abs(note.x - current.x) > 1 || Math.abs(note.y - current.y) > 1)) persistPosition(note, current.version)
}
function cancelDrag() {
  if (!drag) return
  const note = board.value.comments.find(n => n.id === drag!.id)
  if (note) { note.x = drag.x; note.y = drag.y }
  drag = null; dragging.value = null
}
function nudge(event: KeyboardEvent, note: Note) {
  if (tool.value !== 'drag' || note.author.id !== props.user.id || busyMoves.value.has(note.id)) return
  if (!['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(event.key)) return
  event.preventDefault()
  const step = event.shiftKey ? 50 : 10
  note.x = Math.max(0, Math.min(5000, note.x + (event.key === 'ArrowLeft' ? -step : event.key === 'ArrowRight' ? step : 0)))
  note.y = Math.max(80, Math.min(5000, note.y + (event.key === 'ArrowUp' ? -step : event.key === 'ArrowDown' ? step : 0)))
  persistPosition(note, note.position_version)
}
</script>

<template>
  <div class="board-area">
    <div ref="viewport" class="board-scroll" :class="`tool-${tool}`">
      <div class="world-sizer" :style="{ width: `${worldWidth * scale}px`, height: `${worldHeight * scale}px` }">
        <div class="world" aria-label="评论画布" :style="{ width: `${worldWidth}px`, height: `${worldHeight}px`, transform: `scale(${scale})` }" @click.self="addAt">
          <article v-for="note in board.comments" :key="note.id" class="sticky" :class="{ draggable: tool === 'drag' && note.author.id === user.id, dragging: dragging === note.id }" :style="{ left: `${notePosition(note).x}px`, top: `${notePosition(note).y}px`, transform: `rotate(${organized ? 0 : note.rotation}deg)`, background: sentimentColors[note.sentiment] || sentimentColors.neutral }" :data-note-id="note.id" :data-sentiment="note.sentiment" tabindex="0" :aria-label="`${note.author.name}的贴纸：${note.text}`" @click.stop="openNote(note)" @keydown.enter.prevent="openNote(note)" @keydown="nudge($event, note)" @pointerdown="startDrag($event, note)" @pointermove="moveDrag" @pointerup="endDrag" @pointercancel="cancelDrag">
            <span class="tape" aria-hidden="true" :style="{ background: ['#ffca8e', '#9dd3ff', '#ffe68c', '#9df4ec'][note.id.charCodeAt(note.id.length - 1)! % 4] }" />
            <div class="note-body" v-html="note.content_html" />
            <footer class="note-meta"><img :src="note.author.avatar" alt="" class="note-avatar" /><div class="note-author"><span>{{ note.author.name }}</span><time :datetime="new Date(note.created_at).toISOString()">{{ formatTime(note.created_at) }}</time></div><button class="like-button" :class="{ liked: note.liked_by.includes(user.id) }" :aria-label="`${note.liked_by.includes(user.id) ? '取消点赞' : '点赞'}·${note.author.name}的贴纸`" :aria-pressed="note.liked_by.includes(user.id)" :disabled="busyLikes.has(note.id)" @pointerdown.stop @click.stop="like(note)"><Icon :name="note.liked_by.includes(user.id) ? 'heart-fill' : 'heart'" :size="16" /><span v-if="note.liked_by.length">{{ note.liked_by.length }}</span></button></footer>
          </article>
        </div>
      </div>
    </div>
    <section v-if="showOverview" class="emotion-overview" aria-label="情绪概览">
      <div class="emotion-bar" :class="{ empty: !board.comments.length }" role="img" :aria-label="summary.map(s => `${s.label}${s.count}条，占${s.percent}%`).join('；')"><span v-for="item in summary.filter(s => s.count)" :key="item.key" :class="item.key" :style="{ flex: item.count }" :title="`${item.label}：${item.count}条，${item.percent}%`">{{ width < 768 && item.percent < 18 ? `${item.percent}%` : `${item.label}${item.percent}%` }}</span><span v-if="!board.comments.length">暂无评论</span></div>
      <div class="overview-caption"><span>共 {{ board.comments.length }} 条建议</span><button aria-label="收起情绪概览" @click="showOverview = false">收起概览</button></div>
    </section>
    <template v-else><p class="wall-count">共反馈 <strong>{{ board.comments.length }}</strong> 条建议</p><button class="overview-toggle" @click="showOverview = true">情绪概览</button></template>
    <p class="save-status" :class="{ disconnected: status !== 'online' }"><span class="connection-dot" /><span v-if="status === 'online'"><span v-if="savedAt" class="sync-time">{{ formatTime(savedAt) }} </span>已同步</span><span v-else>{{ status === 'connecting' ? '正在连接…' : '连接中断，正在重连…' }}</span><button v-if="status === 'offline'" @click="reconnect">重试</button></p>
    <p v-if="pending" class="boot-state">正在读取评论墙…</p>
    <div v-if="loadError" class="load-error" role="alert">{{ loadError }} <button @click="load">重新连接</button></div>
    <div v-if="!pending && !loadError && !board.comments.length" class="empty-wall"><p>这里，等你的第一个想法。</p><span>选择下方「新增」，再点击画布。</span></div>
    <nav class="wall-tools" aria-label="画布工具"><button :class="{ active: tool === 'add' }" title="新增贴纸 · 点击画布选择位置" aria-label="新增贴纸" :aria-pressed="tool === 'add'" @click="organized = false; tool = 'add'"><Icon name="add" /></button><button :class="{ active: tool === 'select' }" title="鼠标选择 · 点击贴纸查看或编辑" aria-label="鼠标选择" :aria-pressed="tool === 'select'" @click="tool = 'select'"><Icon name="cursor" /></button><button :class="{ active: tool === 'drag' }" title="拖动自己的贴纸" aria-label="拖动贴纸" :aria-pressed="tool === 'drag'" @click="organized = false; tool = 'drag'"><Icon name="hand" /></button><button class="organize-button" :aria-pressed="organized" :title="organized ? '恢复共享的自由布局' : '按情绪分列，仅整理我的视图'" @click="organized = !organized; tool = 'select'"><span aria-hidden="true">✦</span>{{ organized ? '还原布局' : '智能整理' }}</button></nav>
    <div v-if="tool === 'add'" class="tool-hint" role="status">点击画布，贴下一个新想法</div>
    <div v-if="tool === 'drag'" class="tool-hint" role="status">拖动自己的贴纸 · 也可用方向键移动</div>
    <div v-if="width < 768 && tool === 'select' && !editorOpen" class="mobile-canvas-hint">左右滑动，浏览整面评论墙</div>
    <NoteEditor v-if="editorOpen" :user="props.user" :note="selected" :position="position" :readonly="!!selected && selected.author.id !== user.id" @close="editorOpen = false" @saved="saved" />
  </div>
</template>
