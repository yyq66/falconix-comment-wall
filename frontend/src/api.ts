export interface User { id: string; username: string; name: string; avatar: string }
export interface Note { id: string; author: User; content_html: string; text: string; x: number; y: number; rotation: number; color: string; created_at: number; updated_at: number; content_version: number; position_version: number; sentiment: string; liked_by: string[] }
export interface Board { revision: number; comments: Note[] }

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch('/api' + path, {
      ...options,
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', ...options.headers },
    })
  } catch {
    throw new ApiError(0, '连接失败，请检查网络后重试')
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new ApiError(response.status, typeof data.detail === 'string' ? data.detail : '操作失败，请稍后重试')
  }
  return response.json()
}
