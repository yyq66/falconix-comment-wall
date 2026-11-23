<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import Placeholder from '@tiptap/extension-placeholder'
import Icon from './Icon.vue'
import { api, type Board, type Note, type User } from '../api'

const props = defineProps<{ user: User; note: Note | null; position: { x: number; y: number }; readonly?: boolean }>()
const emit = defineEmits<{ close: []; saved: [board: Board] }>()
const dialog = ref<HTMLDialogElement>()
const busy = ref(false)
const error = ref('')
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
onBeforeUnmount(() => { editor.value?.destroy(); previousFocus?.focus() })
const tools = [
  { icon: 'bold', label: '加粗', active: 'bold', command: () => editor.value?.chain().focus().toggleBold().run() },
  { icon: 'italic', label: '斜体', active: 'italic', command: () => editor.value?.chain().focus().toggleItalic().run() },
  { icon: 'underline', label: '下划线', active: 'underline', command: () => editor.value?.chain().focus().toggleUnderline().run() },
  { icon: 'strike', label: '删除线', active: 'strike', command: () => editor.value?.chain().focus().toggleStrike().run() },
  { icon: 'bullet-list', label: '无序列表', active: 'bulletList', command: () => editor.value?.chain().focus().toggleBulletList().run() },
  { icon: 'ordered-list', label: '有序列表', active: 'orderedList', command: () => editor.value?.chain().focus().toggleOrderedList().run() },
]
async function save() {
  if (!editor.value || !length.value || length.value > 1000 || busy.value) return
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
</script>

<template>
  <dialog ref="dialog" class="modal note-modal" aria-labelledby="note-title" @cancel.prevent="!busy && emit('close')" @keydown.ctrl.enter.prevent="!readonly && save()" @keydown.meta.enter.prevent="!readonly && save()">
    <header class="modal-header"><h2 id="note-title">{{ readonly ? '查看建议' : note ? '编辑我的贴纸' : '发表新想法' }}</h2><button class="icon-button" aria-label="关闭编辑器" :disabled="busy" @click="emit('close')"><Icon name="close" :size="16" /></button></header>
    <div v-if="!readonly" class="format-toolbar" role="toolbar" aria-label="文字格式"><button v-for="tool in tools" :key="tool.icon" type="button" class="icon-button" :class="{ active: editor?.isActive(tool.active) }" :aria-label="tool.label" :aria-pressed="editor?.isActive(tool.active)" :title="tool.label" @click="tool.command"><Icon :name="tool.icon" :size="16" /></button></div>
    <EditorContent :editor="editor" class="editor-content" />
    <footer class="editor-footer"><span v-if="readonly && note">{{ note.author.name }} · {{ new Date(note.created_at).toLocaleString('zh-CN', { hour12: false }) }}</span><span v-else :class="{ over: length > 1000 }">{{ length }} / 1000 <span class="keyboard-hint">· Ctrl + Enter 发表</span></span><p v-if="error" class="form-error" role="alert">{{ error }}</p><button v-if="!readonly" class="primary-button" :disabled="busy || !length || length > 1000" @click="save">{{ busy ? '正在保存…' : note ? '保存修改' : '马上发表' }}</button></footer>
  </dialog>
</template>
