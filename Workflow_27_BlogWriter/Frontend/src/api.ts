import type { Blog, GenerateResponse, StatusResponse } from '../types'

const BASE = '/blogs'

async function req<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// ── Blog CRUD ────────────────────────────────────────────────

export const generateBlog = (topic: string) =>
  req<GenerateResponse>(`${BASE}/generate`, {
    method: 'POST',
    body: JSON.stringify({ topic }),
  })

export const listBlogs = (status?: string, limit = 50, offset = 0) => {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (status) params.set('status', status)
  return req<Blog[]>(`${BASE}?${params}`)
}

export const getBlog = (threadId: string) =>
  req<Blog>(`${BASE}/${threadId}`)

export const getBlogContent = (threadId: string) =>
  req<{ thread_id: string; blog_title: string; content: string }>(
    `${BASE}/${threadId}/content`
  )

export const getBlogStatus = (threadId: string) =>
  req<StatusResponse>(`${BASE}/${threadId}/status`)

export const updateBlog = (threadId: string, payload: { blog_title?: string; content: string }) =>
  req<Blog>(`${BASE}/${threadId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })

export const deleteBlog = (threadId: string) =>
  req<{ message: string }>(`${BASE}/${threadId}`, { method: 'DELETE' })

// ── HITL ─────────────────────────────────────────────────────

export const approveBlog = (threadId: string) =>
  req<{ thread_id: string; status: string; message: string }>(`${BASE}/approve`, {
    method: 'POST',
    body: JSON.stringify({ thread_id: threadId }),
  })

export const rejectBlog = (threadId: string, rejection_reason: string) =>
  req<{ thread_id: string; status: string; message: string }>(`${BASE}/reject`, {
    method: 'POST',
    body: JSON.stringify({ thread_id: threadId, rejection_reason }),
  })
