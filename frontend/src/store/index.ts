// 文件路径：frontend/src/store/index.ts
// 用途：全局状态管理（Zustand）
// MVP 范围：会话状态 + 配置状态 + 知识库页面状态

import { create } from 'zustand'
import type {
  Suggestion,
  SuggestionTask,
  TranscriptBubble,
  Industry,
  SpeechStyle,
  LLMConfig,
  ASRConfig,
} from '../types'
import { DEFAULT_ASR_CONFIG, DEFAULT_LLM_CONFIG } from '../types'

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

  // 语音转写气泡
  bubbles: TranscriptBubble[]
  recordingStatus: 'idle' | 'connecting' | 'recording' | 'stopping' | 'error'
  autoScroll: boolean
  addManualBubble: (text: string) => string
  upsertDraftBubble: (itemId: string, text: string, stash?: string) => void
  finalizeBubble: (itemId: string, transcript: string) => void
  setRecordingStatus: (status: SessionState['recordingStatus']) => void
  setAutoScroll: (enabled: boolean) => void
  clearBubbles: () => void

  // 并发建议任务（最多 3 条）
  suggestionTasks: Record<string, SuggestionTask>
  activeTabBubbleId: string | null
  clickOrder: string[]
  setBubbleSelected: (bubbleId: string, selected: boolean) => void
  setTaskLoading: (bubbleId: string, title: string) => void
  setTaskSuccess: (
    bubbleId: string,
    payload: {
      suggestions: Suggestion[]
      latencyMs: number
      fallback: boolean
      fallbackReason: string
    }
  ) => void
  setTaskError: (bubbleId: string, title: string, error: string) => void
  setActiveTabBubbleId: (bubbleId: string) => void

  // LLM 配置
  llmConfig: LLMConfig
  setLLMConfig: (c: LLMConfig) => void
  asrConfig: ASRConfig
  setASRConfig: (c: ASRConfig) => void

  // ===== 新增：会议摘要 =====
  sessionSummary: string           // 当前摘要文本
  unsummarizedInputs: string[]     // 还未被摘要的输入
  isSummarizing: boolean           // 正在生成摘要
  summaryRound: number             // 已摘要的总轮次

  setSessionSummary: (s: string) => void
  addUnsummarizedInput: (text: string) => void
  setSummarizing: (b: boolean) => void
  clearSession: () => void
  onSummaryComplete: (newSummary: string, summarizedCount: number) => void
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

  bubbles: [],
  recordingStatus: 'idle',
  autoScroll: true,
  addManualBubble: (text) => {
    const id = `manual_${Date.now()}_${Math.random().toString(16).slice(2, 6)}`
    set((state) => ({
      bubbles: [
        ...state.bubbles,
        {
          id,
          text,
          type: 'manual',
          created_at: Date.now(),
          selected: false,
        },
      ],
    }))
    return id
  },
  upsertDraftBubble: (itemId, text, stash = '') =>
    set((state) => {
      const next = [...state.bubbles]
      const idx = next.findIndex((b) => b.item_id === itemId)
      const composed = `${text || ''}${stash || ''}`
      if (idx >= 0) {
        next[idx] = {
          ...next[idx],
          type: 'asr_draft',
          stable_text: text,
          stash_text: stash,
          text: composed,
        }
      } else {
        next.push({
          id: `asr_${itemId}`,
          item_id: itemId,
          text: composed,
          stable_text: text,
          stash_text: stash,
          type: 'asr_draft',
          created_at: Date.now(),
          selected: false,
        })
      }
      return { bubbles: next }
    }),
  finalizeBubble: (itemId, transcript) =>
    set((state) => ({
      bubbles: state.bubbles.map((b) =>
        b.item_id === itemId
          ? {
              ...b,
              text: transcript,
              stable_text: transcript,
              stash_text: '',
              type: 'asr_final',
            }
          : b
      ),
    })),
  setRecordingStatus: (status) => set({ recordingStatus: status }),
  setAutoScroll: (enabled) => set({ autoScroll: enabled }),
  clearBubbles: () =>
    set({
      bubbles: [],
      suggestionTasks: {},
      activeTabBubbleId: null,
      clickOrder: [],
    }),

  suggestionTasks: {},
  activeTabBubbleId: null,
  clickOrder: [],
  setBubbleSelected: (bubbleId, selected) =>
    set((state) => ({
      bubbles: state.bubbles.map((b) => (b.id === bubbleId ? { ...b, selected } : b)),
    })),
  setTaskLoading: (bubbleId, title) =>
    set((state) => ({
      suggestionTasks: {
        ...state.suggestionTasks,
        [bubbleId]: {
          bubbleId,
          title,
          status: 'loading',
          suggestions: state.suggestionTasks[bubbleId]?.suggestions || [],
          error: null,
          fallback: false,
          fallbackReason: 'none',
          latencyMs: 0,
        },
      },
      activeTabBubbleId: bubbleId,
    })),
  setTaskSuccess: (bubbleId, payload) =>
    set((state) => ({
      suggestionTasks: {
        ...state.suggestionTasks,
        [bubbleId]: {
          ...(state.suggestionTasks[bubbleId] || {
            bubbleId,
            title: '建议',
          }),
          status: 'success',
          suggestions: payload.suggestions,
          error: null,
          fallback: payload.fallback,
          fallbackReason: payload.fallbackReason,
          latencyMs: payload.latencyMs,
        } as SuggestionTask,
      },
      activeTabBubbleId: bubbleId,
    })),
  setTaskError: (bubbleId, title, error) =>
    set((state) => ({
      suggestionTasks: {
        ...state.suggestionTasks,
        [bubbleId]: {
          bubbleId,
          title,
          status: 'error',
          suggestions: [],
          error,
          fallback: false,
          fallbackReason: 'none',
          latencyMs: 0,
        },
      },
      activeTabBubbleId: bubbleId,
    })),
  setActiveTabBubbleId: (bubbleId) => set({ activeTabBubbleId: bubbleId }),

  // LLM 配置
  llmConfig: loadFromStorage<LLMConfig>('jisoul_llm_config', DEFAULT_LLM_CONFIG),
  setLLMConfig: (c) => {
    localStorage.setItem('jisoul_llm_config', JSON.stringify(c))
    set({ llmConfig: c })
  },
  asrConfig: loadFromStorage<ASRConfig>('jisoul_asr_config', DEFAULT_ASR_CONFIG),
  setASRConfig: (c) => {
    localStorage.setItem('jisoul_asr_config', JSON.stringify(c))
    set({ asrConfig: c })
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
      bubbles: [],
      suggestionTasks: {},
      activeTabBubbleId: null,
      clickOrder: [],
    }),

  onSummaryComplete: (newSummary, summarizedCount) =>
    set((state) => {
      const safeCount = Math.max(0, Math.min(summarizedCount, state.unsummarizedInputs.length))
      return {
        sessionSummary: newSummary,
        unsummarizedInputs: state.unsummarizedInputs.slice(safeCount),
        summaryRound: state.summaryRound + safeCount,
      }
    }),
}))