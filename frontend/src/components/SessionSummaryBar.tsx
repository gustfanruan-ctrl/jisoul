// 文件路径：frontend/src/components/SessionSummaryBar.tsx
// 用途：会议摘要展示 + 手动编辑组件
// MVP 功能：每累积5轮对话自动生成摘要，用户可随时查看和修改

import React, { useState } from 'react'
import { Input, Button, Tag, Tooltip, message } from 'antd'
import {
  EditOutlined,
  CheckOutlined,
  CloseOutlined,
  FileTextOutlined,
  DeleteOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import { useSessionStore } from '../store'

const { TextArea } = Input

const SessionSummaryBar: React.FC = () => {
  const {
    sessionSummary,
    setSessionSummary,
    isSummarizing,
    summaryRound,
    unsummarizedInputs,
    clearSession,
  } = useSessionStore()

  const [isEditing, setIsEditing] = useState(false)
  const [editText, setEditText] = useState('')

  // 没有摘要且没在生成，不显示
  if (!sessionSummary && !isSummarizing && unsummarizedInputs.length === 0) {
    return null
  }

  const handleEdit = () => {
    setEditText(sessionSummary)
    setIsEditing(true)
  }

  const handleSave = () => {
    const trimmed = editText.trim().slice(0, 200)
    setSessionSummary(trimmed)
    setIsEditing(false)
    message.success('摘要已更新')
  }

  const handleCancel = () => {
    setIsEditing(false)
  }

  const handleClear = () => {
    clearSession()
    message.info('会议上下文已清空')
  }

  return (
    <div
      style={{
        background: '#e6f7ff',
        border: '1px solid #91d5ff',
        borderRadius: 8,
        padding: '12px 16px',
        marginBottom: 12,
      }}
    >
      {/* 标题栏 */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 8,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <FileTextOutlined style={{ color: '#1677ff' }} />
          <span style={{ fontWeight: 500, fontSize: 13 }}>会议摘要</span>
          {summaryRound > 0 && (
            <Tag color="blue" style={{ fontSize: 11 }}>
              已覆盖 {summaryRound} 轮
            </Tag>
          )}
          {unsummarizedInputs.length > 0 && (
            <Tag color="orange" style={{ fontSize: 11 }}>
              待摘要 {unsummarizedInputs.length} 轮
            </Tag>
          )}
          {isSummarizing && (
            <Tag color="processing" style={{ fontSize: 11 }}>
              <LoadingOutlined /> 摘要生成中...
            </Tag>
          )}
        </div>

        <div style={{ display: 'flex', gap: 4 }}>
          {!isEditing && sessionSummary && (
            <Tooltip title="编辑摘要">
              <Button
                type="text"
                size="small"
                icon={<EditOutlined />}
                onClick={handleEdit}
              />
            </Tooltip>
          )}
          <Tooltip title="清空会议上下文">
            <Button
              type="text"
              size="small"
              icon={<DeleteOutlined />}
              onClick={handleClear}
            />
          </Tooltip>
        </div>
      </div>

      {/* 编辑模式 */}
      {isEditing && (
        <div style={{ marginTop: 8 }}>
          <TextArea
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            maxLength={200}
            autoSize={{ minRows: 2, maxRows: 4 }}
            showCount
            placeholder="手动编辑会议背景摘要..."
            style={{ fontSize: 13 }}
          />
          <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
            <Button size="small" icon={<CloseOutlined />} onClick={handleCancel}>
              取消
            </Button>
            <Button
              type="primary"
              size="small"
              icon={<CheckOutlined />}
              onClick={handleSave}
            >
              保存
            </Button>
          </div>
        </div>
      )}

      {/* 展示模式 */}
      {!isEditing && sessionSummary && (
        <div
          style={{
            fontSize: 13,
            color: '#595959',
            lineHeight: 1.6,
            whiteSpace: 'pre-wrap',
          }}
        >
          {sessionSummary}
        </div>
      )}
    </div>
  )
}

export default SessionSummaryBar