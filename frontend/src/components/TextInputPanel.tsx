// 文件路径：frontend/src/components/TextInputPanel.tsx
// 用途：客户话语输入面板 - 输入框 + 获取建议按钮 + 历史记录展示
// MVP 范围：US-001 全部验收标准

import React, { useState } from 'react'
import { Input, Button, message } from 'antd'
import { SendOutlined } from '@ant-design/icons'
import { useSessionStore } from '../store'
import { generateSummary } from '../services/api'

const { TextArea } = Input

const MAX_LENGTH = 500
const SUMMARY_THRESHOLD = 5 // 每累积 5 轮触发摘要

const TextInputPanel: React.FC<{ onSubmitBubble: (bubbleId: string) => void }> = ({ onSubmitBubble }) => {
  const [inputText, setInputText] = useState('')

  const {
    addManualBubble,
    llmConfig,
    recordingStatus,
    // ===== 新增摘要相关 =====
    sessionSummary,
    unsummarizedInputs,
    addUnsummarizedInput,
    isSummarizing,
    setSummarizing,
    onSummaryComplete,
  } = useSessionStore()

  const canSubmit = inputText.trim().length > 0 && recordingStatus !== 'connecting' && recordingStatus !== 'stopping'

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
        onSummaryComplete(res.summary, inputs.length)
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

    try {
      const bubbleId = addManualBubble(finalText)
      onSubmitBubble(bubbleId)
      setInputText('')

      const newUnsummarized = [...unsummarizedInputs, finalText]
      if (newUnsummarized.length >= SUMMARY_THRESHOLD && !isSummarizing) {
        triggerSummary(newUnsummarized)
      }
    } catch (err) {
      message.error('请求失败，请重试')
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
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
        <TextArea
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入客户说的话..."
          autoSize={{ minRows: 2, maxRows: 6 }}
          maxLength={MAX_LENGTH}
          showCount
          style={{ flex: 1, fontSize: 14 }}
          disabled={recordingStatus === 'connecting' || recordingStatus === 'stopping'}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSubmit}
          disabled={!canSubmit}
          size="large"
          style={{ height: 'auto', minHeight: 56 }}
        >
          发送为气泡
        </Button>
      </div>
    </div>
  )
}

export default TextInputPanel