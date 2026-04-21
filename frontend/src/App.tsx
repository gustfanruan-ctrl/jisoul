// 文件路径：frontend/src/App.tsx
// 用途：应用主布局 - 顶部栏 + 主区域 + 右侧悬浮窗
// MVP 范围：整合所有组件，页面路由（知识库管理 vs 主页）

import React, { useState } from 'react'
import { Layout, Button, Typography, Space, Tag, Tooltip, message } from 'antd'
import {
  SettingOutlined,
  DatabaseOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import TextInputPanel from './components/TextInputPanel'
import SessionSummaryBar from './components/SessionSummaryBar'
import FloatingAssistantPanel from './components/FloatingAssistantPanel'
import TranscriptBubbleList from './components/TranscriptBubbleList'
import RecordControl from './components/RecordControl'
import ConfigDrawer from './components/ConfigDrawer'
import KnowledgeAdminPage from './pages/KnowledgeAdminPage'
import { useSessionStore } from './store'
import { fetchSuggestions } from './services/api'

const { Header, Content } = Layout
const { Text } = Typography

const App: React.FC = () => {
  const [configOpen, setConfigOpen] = useState(false)
  const [page, setPage] = useState<'main' | 'knowledge'>('main')

  const {
    industry,
    style,
    llmConfig,
    historyInputs,
    sessionSummary,
    bubbles,
    suggestionTasks,
    addHistoryInput,
    setBubbleSelected,
    setTaskLoading,
    setTaskSuccess,
    setTaskError,
  } = useSessionStore()

  const handleBubbleClick = async (bubbleId: string) => {
    const bubble = bubbles.find((b) => b.id === bubbleId)
    if (!bubble) return
    if (bubble.type !== 'asr_final' && bubble.type !== 'manual') return

    const loadingCount = Object.values(suggestionTasks).filter((t) => t.status === 'loading').length
    const sameTaskLoading = suggestionTasks[bubbleId]?.status === 'loading'
    if (!sameTaskLoading && loadingCount >= 3) {
      message.warning('最多同时查询 3 条，请等待前序完成')
      return
    }

    const title = `${bubble.text.slice(0, 15)}${bubble.text.length > 15 ? '…' : ''}`
    setBubbleSelected(bubbleId, true)
    setTaskLoading(bubbleId, title)
    addHistoryInput(bubble.text)

    try {
      const selectedHistory = [...historyInputs, bubble.text].slice(-3)
      const res = await fetchSuggestions({
        input_text: bubble.text,
        industry,
        style,
        history_inputs: selectedHistory,
        session_summary: sessionSummary || undefined,
        llm_base_url: llmConfig.base_url || undefined,
        llm_api_key: llmConfig.api_key || undefined,
        llm_model: llmConfig.model || undefined,
      })
      setTaskSuccess(bubbleId, {
        suggestions: res.suggestions,
        latencyMs: res.latency_ms,
        fallback: res.fallback,
        fallbackReason: res.fallback_reason,
      })
    } catch (err: any) {
      setTaskError(bubbleId, title, err?.message || '请求失败，请重试')
    }
  }

  // ============ 知识库管理页面 ============
  if (page === 'knowledge') {
    return <KnowledgeAdminPage onBack={() => setPage('main')} />
  }

  // ============ 主页面 ============
  return (
    <Layout style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      {/* 顶部栏 */}
      <Header
        style={{
          background: '#fff',
          borderBottom: '1px solid #e8e8e8',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px',
          height: 56,
          position: 'sticky',
          top: 0,
          zIndex: 100,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <ThunderboltOutlined style={{ fontSize: 22, color: '#1677ff' }} />
          <Text strong style={{ fontSize: 18, letterSpacing: 1 }}>
            机魂
          </Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            对话辅助 MVP
          </Text>
        </div>

        <Space size="middle">
          {/* 当前配置标签 */}
          <Tooltip title="当前行业">
            <Tag color="blue">{industry}</Tag>
          </Tooltip>
          <Tooltip title="当前风格">
            <Tag color="green">{style}</Tag>
          </Tooltip>

          {/* 配置按钮 */}
          <Button
            icon={<SettingOutlined />}
            onClick={() => setConfigOpen(true)}
          >
            配置
          </Button>

          {/* 知识库管理入口 */}
          <Button
            icon={<DatabaseOutlined />}
            onClick={() => setPage('knowledge')}
          >
            知识库管理
          </Button>
        </Space>
      </Header>

      {/* 主内容区 */}
      <Content style={{ padding: 24 }}>
        <div
          style={{
            display: 'flex',
            gap: 24,
            maxWidth: 1400,
            margin: '0 auto',
            height: 'calc(100vh - 56px - 48px)',
          }}
        >
          {/* 左侧主区域：气泡流 + 录音 + 备用输入 */}
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              minWidth: 0,
            }}
          >
            <div
              style={{
                background: '#fff',
                borderRadius: 12,
                padding: 24,
                boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
              }}
            >
              {/* 会议摘要栏（新增） */}
              <SessionSummaryBar />
              <div style={{ height: 420 }}>
                <TranscriptBubbleList onBubbleClick={handleBubbleClick} />
              </div>
              <RecordControl />
              <div style={{ marginTop: 12 }}>
                <TextInputPanel onSubmitBubble={handleBubbleClick} />
              </div>
            </div>
          </div>

          {/* 右侧悬浮建议窗 */}
          <div
            style={{
              width: 400,
              flexShrink: 0,
              background: '#fff',
              borderRadius: 12,
              padding: 20,
              boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
              position: 'sticky',
              top: 80,
              maxHeight: 'calc(100vh - 56px - 48px)',
              overflowY: 'auto',
            }}
          >
            <FloatingAssistantPanel />
          </div>
        </div>
      </Content>

      {/* 配置抽屉 */}
      <ConfigDrawer open={configOpen} onClose={() => setConfigOpen(false)} />
    </Layout>
  )
}

export default App