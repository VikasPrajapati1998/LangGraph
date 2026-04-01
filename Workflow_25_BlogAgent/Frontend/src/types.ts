export type BlogStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'COMPLETED' | 'FAILED'

export interface Blog {
  id: number
  thread_id: string
  topic: string
  blog_title: string | null
  content: string | null
  status: BlogStatus
  rejection_reason: string | null
  created_at: string | null
  updated_at: string | null
  approved_at: string | null
  rejected_at: string | null
}

export interface GenerateResponse {
  thread_id: string
  blog_id: number
  status: string
  message: string
}

export interface StatusResponse {
  thread_id: string
  status: string
  next: string[]
  message: string
}

export type DownloadFormat = 'markdown' | 'pdf' | 'docx'

export type View = 'list' | 'detail'
