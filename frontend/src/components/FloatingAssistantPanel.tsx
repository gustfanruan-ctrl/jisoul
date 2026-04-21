// 文件路径：frontend/src/components/FloatingAssistantPanel.tsx
// 用途：右侧悬浮建议窗 - 话术卡片 + 复制按钮 + 状态展示
// MVP 范围：US-004 全部验收标准

import React, { useMemo, useState } from 'react'
import { Card, Button, Typography, Skeleton, Empty, Alert, Tag, Tooltip, Tabs } from 'antd'
import {
  CopyOutlined,
  CheckOutlined,
  ThunderboltOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  BulbOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import { useSessionStore } from '../store'
import type { Suggestion } from '../types'

const { Text, Paragraph } = Typography

const FloatingAssistantPanel: React.FC = () => {
  const {
    suggestionTasks,
    activeTabBubbleId,
    setActiveTabBubbleId,
  } = useSessionStore()

  const tabItems = useMemo(() => {
    return Object.values(suggestionTasks).map((task) => {
      const statusIcon = task.status === 'loading' ? '⏳' : task.status === 'success' ? '✅' : '❌'
      const label = `${statusIcon} ${task.title}`
      return {
        key: task.bubbleId,
        label,
        children: <TaskContent task={task} />,
      }
    })
  }, [suggestionTasks])

  const currentKey = activeTabBubbleId || tabItems[0]?.key

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        gap: 12,
      }}
    >
      {/* 标题栏 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <Text strong style={{ fontSize: 16 }}>
          <BulbOutlined style={{ marginRight: 6 }} />
          建议话术
        </Text>
        <Tag icon={<ClockCircleOutlined />} color="default">并发模式</Tag>
      </div>

      {tabItems.length === 0 ? (
        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="点击左侧已定稿气泡生成建议"
          />
        </div>
      ) : (
        <Tabs
          activeKey={currentKey}
          onChange={(key) => setActiveTabBubbleId(key)}
          items={tabItems}
          size="small"
        />
      )}
    </div>
  )
}

const TaskContent: React.FC<{ task: any }> = ({ task }) => {
  if (task.status === 'loading') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {[1, 2, 3].map((i) => (
          <Card key={i} size="small" style={{ borderRadius: 8 }}>
            <Skeleton active paragraph={{ rows: 2 }} title={false} />
          </Card>
        ))}
      </div>
    )
  }

  if (task.status === 'error') {
    return (
      <Alert
        type="error"
        showIcon
        message="生成失败，点击左侧气泡可重试"
        description={task.error || '未知错误'}
      />
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxHeight: 520, overflowY: 'auto' }}>
      {task.fallback && (
        <Alert
          type="warning"
          showIcon
          message={
            task.fallbackReason === 'llm_timeout'
              ? 'AI 响应超时，以下为知识库原文参考'
              : task.fallbackReason === 'no_knowledge'
                ? '未检索到相关知识'
                : 'AI 生成异常，以下为备选建议'
          }
          style={{ fontSize: 12 }}
        />
      )}
      <Tooltip title="端到端响应时间">
        <Tag icon={<ClockCircleOutlined />} color={task.latencyMs <= 5000 ? 'green' : 'orange'}>
          {(task.latencyMs / 1000).toFixed(1)}s
        </Tag>
      </Tooltip>
      {task.suggestions.map((s: Suggestion, idx: number) => (
        <SuggestionCard key={s.id} suggestion={s} index={idx} />
      ))}
    </div>
  )
}

// ============ 单条建议卡片 ============

const SuggestionCard: React.FC<{ suggestion: Suggestion; index: number }> = ({
  suggestion,
  index,
}) => {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(suggestion.text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // fallback: 兼容非 HTTPS 环境
      const textarea = document.createElement('textarea')
      textarea.value = suggestion.text
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <Card
      size="small"
      style={{
        borderRadius: 8,
        border: '1px solid #e8e8e8',
        transition: 'box-shadow 0.2s',
      }}
      hoverable
      styles={{
        body: { padding: '12px 16px' },
      }}
    >
      {/* 卡片头部 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 8,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Tag color="blue" style={{ margin: 0, fontSize: 11 }}>
            建议 {index + 1}
          </Tag>
          {suggestion.source === 'knowledge_base' ? (
            <Tooltip title="基于知识库生成">
              <Tag
                icon={<DatabaseOutlined />}
                color="green"
                style={{ margin: 0, fontSize: 11 }}
              >
                知识库
              </Tag>
            </Tooltip>
          ) : (
            <Tooltip title="基于通用知识生成">
              <Tag
                icon={<ThunderboltOutlined />}
                color="default"
                style={{ margin: 0, fontSize: 11 }}
              >
                通用
              </Tag>
            </Tooltip>
          )}
        </div>
        <Button
          type={copied ? 'default' : 'text'}
          size="small"
          icon={copied ? <CheckOutlined style={{ color: '#52c41a' }} /> : <CopyOutlined />}
          onClick={handleCopy}
          style={{ fontSize: 12 }}
        >
          {copied ? '已复制' : '复制'}
        </Button>
      </div>

      {/* 话术正文 */}
      <Paragraph
        style={{
          margin: 0,
          fontSize: 14,
          lineHeight: 1.7,
          color: '#262626',
        }}
      >
        {suggestion.text}
      </Paragraph>
    </Card>
  )
}

export default FloatingAssistantPanel