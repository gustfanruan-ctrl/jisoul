// 文件路径：frontend/src/components/TextInputPanel.tsx
// 用途：客户话语输入面板 - 输入框 + 获取建议按钮 + 历史记录展示
// MVP 范围：US-001 全部验收标准

import React, { useState, useRef } from 'react'
import { Input, Button, Typography, Tag, message } from 'antd'
import { SendOutlined, HistoryOutlined } from '@ant-design/icons'
import { useSessionStore } from '../store'
import { fetchSuggestions, generateSummary } from '../services/api'

const { TextArea } = Input
const { Text } = Typography

const MAX_LENGTH = 500
const SUMMARY_THRESHOLD = 5 // 每累积 5 轮触发摘要

const TextInputPanel: React.FC = () => {
  const [inputText, setInputText] = useState('')
  const textAreaRef = useRef<any>(null)

  const {
    industry,
    style,
    historyInputs,
    addHistoryInput,
    loading,
    llmConfig,
    setLoading,
    setSuggestions,
    setError,
    // ===== 新增摘要相关 =====
    sessionSummary,
    unsummarizedInputs,
    addUnsummarizedInput,
    isSummarizing,
    setSummarizing,
    onSummaryComplete,
  } = useSessionStore()

  const canSubmit = inputText.trim().length > 0 && !loading

  // 摘要生成（异步，不阻塞主流程）
  const triggerSummary = async (inputs: string[]) => {
    setSummarizing(true)
    try {
      const res = await generateSummary({
        inputs,
        existing_summary: sessionSummary,
        llm_base_url: llmConfig.base_url || undefined,
        llm_api_key: llmConfig.api_key || undefined,
        llm_model: llmConfig.model || undefined,
      })
      if (res.summary) {
        onSummaryComplete(res.summary)
      }
    } catch (e) {
      console.warn("摘要生成失败，不影响主流程", e)
    } finally {
      setSummarizing(false)
    }
  }

  const handleSubmit = async () => {
    const trimmed = inputText.trim()
    if (!trimmed) return

    // 截断提示
    let finalText = trimmed
    if (finalText.length > MAX_LENGTH) {
      finalText = finalText.slice(0, MAX_LENGTH)
      message.warning(`输入已截断至 ${MAX_LENGTH} 字`)
    }

    // 1. 记录到未摘要列表
    addUnsummarizedInput(finalText)

    setLoading(true)

    try {
      // 2. 调用建议接口（携带摘要）
      const res = await fetchSuggestions({
        input_text: finalText,
        industry,
        style,
        session_id: undefined,
        history_inputs: historyInputs.length > 0 ? historyInputs : undefined,
        session_summary: sessionSummary || undefined, // ← 新增
        llm_base_url: llmConfig.base_url || undefined,
        llm_api_key: llmConfig.api_key || undefined,
        llm_model: llmConfig.model || undefined,
      })

      setSuggestions(
        res.suggestions,
        res.latency_ms,
        res.fallback,
        res.fallback_reason,
      )

      // 3. 更新历史（保留最近3条）
      addHistoryInput(finalText)
      // 不清空输入框（PRD 要求）

      // 4. 检查是否需要生成摘要（每累积5轮触发一次）
      const newUnsummarized = [...unsummarizedInputs, finalText]
      if (newUnsummarized.length >= SUMMARY_THRESHOLD && !isSummarizing) {
        triggerSummary(newUnsummarized)
      }
    } catch (err: any) {
      setError(err.message || '请求失败，请重试')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Enter 提交，Shift+Enter 换行
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (canSubmit) handleSubmit()
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* 历史输入记录 */}
      {historyInputs.length > 0 && (
        <div
          style={{
            background: '#fafafa',
            borderRadius: 8,
            padding: '12px 16px',
            maxHeight: 200,
            overflowY: 'auto',
          }}
        >
          <Text type="secondary" style={{ fontSize: 12, marginBottom: 8, display: 'block' }}>
            <HistoryOutlined /> 对话历史（最近 {historyInputs.length} 轮）
          </Text>
          {historyInputs.map((text, idx) => (
            <div
              key={idx}
              style={{
                padding: '6px 10px',
                marginBottom: 4,
                background: '#fff',
                borderRadius: 6,
                border: '1px solid #f0f0f0',
                fontSize: 13,
                color: '#595959',
              }}
            >
              <Tag color="blue" style={{ fontSize: 11, marginRight: 6 }}>
                第{idx + 1}轮
              </Tag>
              {text.length > 80 ? text.slice(0, 80) + '...' : text}
            </div>
          ))}
        </div>
      )}

      {/* 输入区域 */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
        <TextArea
          ref={textAreaRef}
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入客户说的话..."
          autoSize={{ minRows: 2, maxRows: 6 }}
          maxLength={MAX_LENGTH}
          showCount
          style={{ flex: 1, fontSize: 14 }}
          disabled={loading}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSubmit}
          loading={loading}
          disabled={!canSubmit}
          size="large"
          style={{ height: 'auto', minHeight: 56 }}
        >
          获取建议
        </Button>
      </div>
    </div>
  )
}

export default TextInputPanel