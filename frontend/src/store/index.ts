// 文件路径：frontend/src/store/index.ts
// 用途：全局状态管理（Zustand）
// MVP 范围：会话状态 + 配置状态 + 知识库页面状态

import { create } from 'zustand'
import type {
  Suggestion,
  Industry,
  SpeechStyle,
  LLMConfig,
} from '../types'
import { DEFAULT_LLM_CONFIG } from '../types'

// ============ 会话 & 建议状态 ============

interface SessionState {
  // 配置
  industry: Industry
  style: SpeechStyle
  setIndustry: (v: Industry) => void
  setStyle: (v: SpeechStyle) => void

  // 历史输入（最近 3 轮）
  historyInputs: string[]
  addHistoryInput: (text: string) => void
  clearHistory: () => void

  // 建议结果
  suggestions: Suggestion[]
  loading: boolean
  error: string | null
  fallback: boolean
  fallbackReason: string
  latencyMs: number
  setSuggestions: (s: Suggestion[], latency: number, fallback: boolean, reason: string) => void
  setLoading: (v: boolean) => void
  setError: (e: string | null) => void
  clearSuggestions: () => void

  // LLM 配置
  llmConfig: LLMConfig
  setLLMConfig: (c: LLMConfig) => void

  // ===== 新增：会议摘要 =====
  sessionSummary: string           // 当前摘要文本
  unsummarizedInputs: string[]     // 还未被摘要的输入
  isSummarizing: boolean           // 正在生成摘要
  summaryRound: number             // 已摘要的总轮次

  setSessionSummary: (s: string) => void
  addUnsummarizedInput: (text: string) => void
  setSummarizing: (b: boolean) => void
  clearSession: () => void
  onSummaryComplete: (newSummary: string) => void
}

// 从 localStorage 恢复配置
function loadFromStorage<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

export const useSessionStore = create<SessionState>((set) => ({
  // 配置（从 localStorage 恢复）
  industry: loadFromStorage<Industry>('jisoul_industry', '通用'),
  style: loadFromStorage<SpeechStyle>('jisoul_style', '专业严谨'),
  setIndustry: (v) => {
    localStorage.setItem('jisoul_industry', JSON.stringify(v))
    set({ industry: v })
  },
  setStyle: (v) => {
    localStorage.setItem('jisoul_style', JSON.stringify(v))
    set({ style: v })
  },

  // 历史输入
  historyInputs: [],
  addHistoryInput: (text) =>
    set((state) => ({
      historyInputs: [...state.historyInputs, text].slice(-3), // 保留最近 3 条
    })),
  clearHistory: () => set({ historyInputs: [] }),

  // 建议结果
  suggestions: [],
  loading: false,
  error: null,
  fallback: false,
  fallbackReason: 'none',
  latencyMs: 0,
  setSuggestions: (s, latency, fallback, reason) =>
    set({
      suggestions: s,
      latencyMs: latency,
      fallback,
      fallbackReason: reason,
      loading: false,
      error: null,
    }),
  setLoading: (v) => set({ loading: v, error: null }),
  setError: (e) => set({ error: e, loading: false }),
  clearSuggestions: () =>
    set({ suggestions: [], fallback: false, fallbackReason: 'none', latencyMs: 0 }),

  // LLM 配置
  llmConfig: loadFromStorage<LLMConfig>('jisoul_llm_config', DEFAULT_LLM_CONFIG),
  setLLMConfig: (c) => {
    localStorage.setItem('jisoul_llm_config', JSON.stringify(c))
    set({ llmConfig: c })
  },

  // ===== 新增：会议摘要 =====
  sessionSummary: "",
  unsummarizedInputs: [],
  isSummarizing: false,
  summaryRound: 0,

  setSessionSummary: (s) => set({ sessionSummary: s }),

  addUnsummarizedInput: (text) =>
    set((state) => ({
      unsummarizedInputs: [...state.unsummarizedInputs, text],
    })),

  setSummarizing: (b) => set({ isSummarizing: b }),

  clearSession: () =>
    set({
      sessionSummary: "",
      unsummarizedInputs: [],
      historyInputs: [],
      summaryRound: 0,
    }),

  onSummaryComplete: (newSummary) =>
    set((state) => ({
      sessionSummary: newSummary,
      unsummarizedInputs: [],
      summaryRound: state.summaryRound + state.unsummarizedInputs.length,
    })),
}))