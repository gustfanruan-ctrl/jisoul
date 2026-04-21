// 文件路径：frontend/src/types/index.ts
// 用途：全局类型定义，与后端 schemas.py 对齐
// MVP 范围：覆盖所有接口的请求/响应类型

// ============ 枚举 ============

export const INDUSTRIES = [
  '通用', '制造', '零售', '金融', '医疗', '教育', '互联网', '电商',
] as const
export type Industry = typeof INDUSTRIES[number]

export const SPEECH_STYLES = [
  '专业严谨', '亲和友好', '简洁直接',
] as const
export type SpeechStyle = typeof SPEECH_STYLES[number]

// ============ 核心链路 ============

export interface SuggestRequest {
  input_text: string
  industry: string
  style: string
  session_id?: string
  history_inputs?: string[]
  session_summary?: string  // ← 新增：会议摘要
  llm_base_url?: string
  llm_api_key?: string
  llm_model?: string
}

export interface Suggestion {
  id: string
  text: string
  source: 'knowledge_base' | 'general'
  ref_chunk_id: string | null
}

export interface SuggestResponse {
  suggestions: Suggestion[]
  latency_ms: number
  fallback: boolean
  fallback_reason: string
  error?: string
  message?: string
}

export type BubbleType = 'asr_draft' | 'asr_final' | 'manual'

export interface TranscriptBubble {
  id: string
  item_id?: string
  text: string
  stable_text?: string
  stash_text?: string
  type: BubbleType
  created_at: number
  selected?: boolean
}

export interface SuggestionTask {
  bubbleId: string
  title: string
  status: 'loading' | 'success' | 'error'
  suggestions: Suggestion[]
  error: string | null
  fallback: boolean
  fallbackReason: string
  latencyMs: number
}

// ============ 知识库 ============

export interface KnowledgeChunk {
  chunk_id: string
  content: string
  file_id: string
  file_name: string
  category: string
  industry: string
  created_at: string
}

export interface UploadResponse {
  file_id: string
  file_name: string
  status: string
  chunk_count: number
}

export interface ChunkListResponse {
  total: number
  chunks: KnowledgeChunk[]
}

export interface SearchResult {
  chunk_id: string
  content: string
  score: number
}

export interface SearchResponse {
  results: SearchResult[]
}

// ============ LLM 配置 ============

export interface LLMConfig {
  base_url: string
  api_key: string
  model: string
}

export interface ASRTokenResponse {
  api_key: string
  ws_url: string
  model: string
}

export interface ASRConfig {
  ws_url: string
  api_key: string
  model: string
}

export const DEFAULT_LLM_CONFIG: LLMConfig = {
  base_url: 'https://api.deepseek.com',
  api_key: '',
  model: 'deepseek-chat',
}

export const DEFAULT_ASR_CONFIG: ASRConfig = {
  ws_url: 'wss://dashscope.aliyuncs.com/api-ws/v1/realtime',
  api_key: '',
  model: 'qwen3-asr-flash-realtime',
}