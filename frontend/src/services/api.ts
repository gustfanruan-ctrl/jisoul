// 文件路径：frontend/src/services/api.ts
// 用途：后端 API 调用封装
// MVP 范围：覆盖所有接口，统一错误处理
// 变更：新增 ERROR_MESSAGES 映射表，拦截器返回友好文案（评审修复）

import axios, { AxiosError } from 'axios'
import type {
  SuggestRequest,
  SuggestResponse,
  UploadResponse,
  ChunkListResponse,
  SearchResponse,
  KnowledgeChunk,
} from '../types'

// 错误码 → 用户友好提示映射
const ERROR_MESSAGES: Record<string, string> = {
  VECTOR_STORE_ERROR: '知识库服务暂时不可用，请稍后重试',
  VECTOR_STORE_TIMEOUT: '知识库检索超时，请稍后重试',
  LLM_ERROR: 'AI 服务暂时不可用，请检查 LLM 配置',
  LLM_TIMEOUT: 'AI 服务响应超时，已为您推荐知识库内容',
  FILE_PROCESS_ERROR: '文件处理失败，请检查文件格式',
  INTERNAL_ERROR: '系统异常，请稍后重试',
}

function friendlyError(raw: string, errorCode?: string): string {
  // 优先用错误码映射
  if (errorCode && ERROR_MESSAGES[errorCode]) {
    return ERROR_MESSAGES[errorCode]
  }
  // 兜底：常见技术错误文案替换
  if (raw.includes('timeout') || raw.includes('超时')) return '服务响应超时，请稍后重试'
  if (raw.includes('Network Error') || raw.includes('网络')) return '网络异常，请检查网络连接'
  if (raw.includes('API Key') || raw.includes('api_key')) return '请检查 LLM API Key 配置是否正确'
  if (raw.includes('413') || raw.includes('too large')) return '文件太大，请压缩后重试'
  return raw
}

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 30000, // 30 秒（上传文件需要较长时间）
  headers: { 'Content-Type': 'application/json' },
})

// 统一错误处理
client.interceptors.response.use(
  (res) => res,
  (err: AxiosError<{ detail?: string; message?: string; error_code?: string }>) => {
    const rawMsg =
      err.response?.data?.detail ||
      err.response?.data?.message ||
      err.message ||
      '网络异常'
    const errorCode = err.response?.data?.error_code
    const friendly = friendlyError(rawMsg, errorCode)
    console.error('[API Error]', rawMsg, `(code: ${errorCode || 'none'})`)
    return Promise.reject(new Error(friendly))
  }
)

// ============ 核心链路 ============

export async function fetchSuggestions(req: SuggestRequest): Promise<SuggestResponse> {
  const { data } = await client.post<SuggestResponse>('/suggestions', req, {
    timeout: 60000, // 60 秒，给 LLM 足够响应时间
  })
  return data
}


// ============ 知识库 ============

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await client.post<UploadResponse>('/knowledge/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000, // 上传 + 处理可能需要更久
  })
  return data
}

export async function fetchChunks(
  fileId?: string,
  page = 1,
  pageSize = 20,
): Promise<ChunkListResponse> {
  const params: Record<string, string | number> = { page, page_size: pageSize }
  if (fileId) params.file_id = fileId
  const { data } = await client.get<ChunkListResponse>('/knowledge/chunks', { params })
  return data
}

export async function updateChunk(
  chunkId: string,
  content: string,
): Promise<{ chunk_id: string; status: string }> {
  const { data } = await client.put(`/knowledge/chunks/${chunkId}`, { content })
  return data
}

export async function deleteChunk(chunkId: string): Promise<{ success: boolean }> {
  const { data } = await client.delete(`/knowledge/chunks/${chunkId}`)
  return data
}

export async function deleteFile(
  fileId: string,
): Promise<{ success: boolean; deleted_chunks: number }> {
  const { data } = await client.delete(`/knowledge/files/${fileId}`)
  return data
}

export async function searchKnowledge(query: string): Promise<SearchResponse> {
  const { data } = await client.post<SearchResponse>('/knowledge/search', { query })
  return data
}

// ============ 健康检查 ============

export async function healthCheck(): Promise<{
  status: string
  version: string
  knowledge_count: number
}> {
  const { data } = await axios.get('/health')
  return data
}

// ============ 会议摘要 ============

export interface SummaryRequest {
  inputs: string[]
  existing_summary?: string
  llm_base_url?: string
  llm_api_key?: string
  llm_model?: string
}

export interface SummaryResponse {
  summary: string
  latency_ms: number
}

export async function generateSummary(data: SummaryRequest): Promise<SummaryResponse> {
  const { data: res } = await client.post<SummaryResponse>('/suggestions/summary', data, {
    timeout: 60000,
  })
  return res
}
