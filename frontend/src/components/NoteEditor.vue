<script setup lang="ts">
import { nextTick, onMounted, onBeforeUnmount, ref } from 'vue'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import Placeholder from '@tiptap/extension-placeholder'
import Icon from './Icon.vue'
import { api, type Board, type Note, type User } from '../api'

const props = defineProps<{ user: User; note: Note | null; position: { x: number; y: number }; readonly?: boolean }>()
const emit = defineEmits<{ close: []; saved: [board: Board]; deleted: [board: Board] }>()
const dialog = ref<HTMLDialogElement>()
const busy = ref(false)
const error = ref('')
const confirmingDelete = ref(false)
const deleteButton = ref<HTMLButtonElement>()
const cancelDeleteButton = ref<HTMLButtonElement>()
const length = ref(props.note?.text.length || 0)
const requestId = crypto.randomUUID()
let previousFocus: HTMLElement | null = null
const editor = useEditor({
  content: props.note?.content_html || '',
  editable: !props.readonly,
  extensions: [StarterKit.configure({ heading: false, codeBlock: false, code: false, blockquote: false, horizontalRule: false }), Underline, Placeholder.configure({ placeholder: '说说你的想法，好的建议会被看见…' })],
  editorProps: { attributes: { 'aria-label': '评论内容', role: 'textbox', 'aria-multiline': 'true' } },
  onUpdate: ({ editor }) => length.value = editor.getText().trim().length,
})
onMounted(() => { previousFocus = document.activeElement as HTMLElement; dialog.value?.showModal(); if (!props.readonly) editor.value?.commands.focus('end') })
onBeforeUnmount(() => { editor.value?.destroy(); (previousFocus?.isConnected ? previousFocus : document.querySelector<HTMLElement>('[aria-label="鼠标选择"]'))?.focus() })
const tools = [
  { icon: 'bold', label: '加粗', active: 'bold', command: () => editor.value?.chain().focus().toggleBold().run() },
  { icon: 'italic', label: '斜体', active: 'italic', command: () => editor.value?.chain().focus().toggleItalic().run() },
  { icon: 'underline', label: '下划线', active: 'underline', command: () => editor.value?.chain().focus().toggleUnderline().run() },
  { icon: 'strike', label: '删除线', active: 'strike', command: () => editor.value?.chain().focus().toggleStrike().run() },
  { icon: 'bullet-list', label: '无序列表', active: 'bulletList', command: () => editor.value?.chain().focus().toggleBulletList().run() },
  { icon: 'ordered-list', label: '有序列表', active: 'orderedList', command: () => editor.value?.chain().focus().toggleOrderedList().run() },
]
async function save() {
  if (props.readonly || confirmingDelete.value || !editor.value || !length.value || length.value > 1000 || busy.value) return
  busy.value = true; error.value = ''
  try {
    const board = await api<Board>(props.note ? `/comments/${props.note.id}/content` : '/comments', {
      method: props.note ? 'PATCH' : 'POST', body: JSON.stringify(props.note
        ? { content_html: editor.value.getHTML(), content_version: props.note.content_version }
        : { content_html: editor.value.getHTML(), ...props.position, request_id: requestId }),
    })
    emit('saved', board)
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
async function confirmDelete() {
  if (!props.note || props.readonly || props.note.author.id !== props.user.id || busy.value) return
  error.value = ''; confirmingDelete.value = true
  await nextTick()
  cancelDeleteButton.value?.focus()
}
async function cancelDelete() {
  if (busy.value) return
  confirmingDelete.value = false; error.value = ''
  await nextTick()
  deleteButton.value?.focus()
}
function cancel() {
  if (busy.value) return
  if (confirmingDelete.value) cancelDelete()
  else emit('close')
}
async function remove() {
  if (!confirmingDelete.value || !props.note || props.readonly || props.note.author.id !== props.user.id || busy.value) return
  busy.value = true; error.value = ''
  try {
    const board = await api<Board>(`/comments/${props.note.id}`, { method: 'DELETE', body: JSON.stringify({ content_version: props.note.content_version, position_version: props.note.position_version }) })
    emit('deleted', board)
  } catch (e) { error.value = (e as Error).message }
  finally { busy.value = false }
}
</script>

<template>
  <dialog ref="dialog" class="modal note-modal" aria-labelledby="note-title" @cancel.prevent="cancel" @keydown.ctrl.enter.prevent="save" @keydown.meta.enter.prevent="save">
    <header class="modal-header"><h2 id="note-title">{{ confirmingDelete ? '删除这张贴纸？' : readonly ? '查看建议' : note ? '编辑我的贴纸' : '发表新想法' }}</h2><button class="icon-button" aria-label="关闭编辑器" :disabled="busy" @click="cancel"><Icon name="close" :size="16" /></button></header>
    <div v-if="confirmingDelete" class="delete-confirmation">
      <p>删除后无法恢复，其他人的评论墙也会同步移除。</p>
      <blockquote>{{ note?.text }}</blockquote>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <div class="delete-actions"><button ref="cancelDeleteButton" class="cancel-delete" :disabled="busy" @click="cancelDelete">取消删除</button><button class="confirm-delete" :disabled="busy" @click="remove">{{ busy ? '正在删除…' : '确认删除' }}</button></div>
    </div>
    <template v-else>
    <div v-if="!readonly" class="format-toolbar" role="toolbar" aria-label="文字格式"><button v-for="tool in tools" :key="tool.icon" type="button" class="icon-button" :class="{ active: editor?.isActive(tool.active) }" :aria-label="tool.label" :aria-pressed="editor?.isActive(tool.active)" :title="tool.label" @click="tool.command"><Icon :name="tool.icon" :size="16" /></button></div>
    <EditorContent :editor="editor" class="editor-content" />
    <footer class="editor-footer"><span v-if="readonly && note">{{ note.author.name }} · {{ new Date(note.created_at).toLocaleString('zh-CN', { hour12: false }) }}</span><span v-else :class="{ over: length > 1000 }">{{ length }} / 1000 <span class="keyboard-hint">· Ctrl + Enter 发表</span></span><p v-if="error" class="form-error" role="alert">{{ error }}</p><button v-if="!readonly" class="primary-button" :disabled="busy || !length || length > 1000" @click="save">{{ busy ? '正在保存…' : note ? '保存修改' : '马上发表' }}</button><button v-if="note && !readonly && note.author.id === user.id" ref="deleteButton" class="delete-note-button" :disabled="busy" @click="confirmDelete">删除贴纸</button></footer>
    </template>
  </dialog>
</template>
