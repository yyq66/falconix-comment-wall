import { onMounted, onBeforeUnmount, ref } from 'vue'
import type { Board, User } from './api'

export function useRealtime(callbacks: { board: (value: Board) => void; members: (value: User[]) => void; expired: () => void }) {
  const status = ref<'connecting' | 'online' | 'offline'>('connecting')
  let socket: WebSocket | null = null
  let retry: ReturnType<typeof setTimeout> | undefined
  let heartbeat: ReturnType<typeof setInterval> | undefined
  let attempts = 0
  let stopped = false
  let lastSeen = Date.now()
  function connect() {
    if (stopped) return
    clearTimeout(retry)
    if (!navigator.onLine) { status.value = 'offline'; return }
    status.value = 'connecting'
    const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/api/ws`)
    socket = ws
    ws.onopen = () => {
      lastSeen = Date.now()
      clearInterval(heartbeat)
      heartbeat = setInterval(() => {
        if (Date.now() - lastSeen > 45000) ws.close()
        else if (ws.readyState === WebSocket.OPEN) ws.send('ping')
      }, 15000)
    }
    ws.onmessage = event => {
      if (socket !== ws || stopped || !navigator.onLine) return
      try {
        const message = JSON.parse(event.data)
        lastSeen = Date.now()
        if (message.type === 'board') {
          callbacks.board(message.board)
          attempts = 0
          status.value = 'online'
        } else if (message.type === 'presence') callbacks.members(message.members)
      } catch { ws.close() }
    }
    ws.onclose = event => {
      if (socket !== ws || stopped) return
      clearInterval(heartbeat)
      status.value = 'offline'
      callbacks.members([])
      if (event.code === 1008) { stopped = true; callbacks.expired(); return }
      retry = setTimeout(connect, Math.min(10000, 700 * 2 ** Math.min(attempts++, 4)) + Math.random() * 300)
    }
    ws.onerror = () => ws.close()
  }
  function reconnect() {
    if (socket) { socket.onclose = null; socket.close() }
    clearInterval(heartbeat)
    attempts = 0
    connect()
  }
  function online() { if (status.value !== 'online') reconnect() }
  function offline() { status.value = 'offline'; clearInterval(heartbeat); socket?.close(); callbacks.members([]) }
  onMounted(() => { connect(); window.addEventListener('online', online); window.addEventListener('offline', offline) })
  onBeforeUnmount(() => {
    stopped = true; clearTimeout(retry); clearInterval(heartbeat); socket?.close()
    callbacks.members([]); window.removeEventListener('online', online); window.removeEventListener('offline', offline)
  })
  return { status, reconnect }
}
