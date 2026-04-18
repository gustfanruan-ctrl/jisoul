// 文件路径：frontend/src/App.tsx
// 用途：应用主布局 - 顶部栏 + 主区域 + 右侧悬浮窗
// MVP 范围：整合所有组件，页面路由（知识库管理 vs 主页）

import React, { useState } from 'react'
import { Layout, Button, Typography, Space, Tag, Tooltip } from 'antd'
import {
  SettingOutlined,
  DatabaseOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import TextInputPanel from './components/TextInputPanel'
import SessionSummaryBar from './components/SessionSummaryBar'
import FloatingAssistantPanel from './components/FloatingAssistantPanel'
import ConfigDrawer from './components/ConfigDrawer'
import KnowledgeAdminPage from './pages/KnowledgeAdminPage'
import { useSessionStore } from './store'

const { Header, Content } = Layout
const { Text } = Typography

const App: React.FC = () => {
  const [configOpen, setConfigOpen] = useState(false)
  const [page, setPage] = useState<'main' | 'knowledge'>('main')

  const { industry, style } = useSessionStore()

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
          {/* 左侧主区域 */}
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'flex-end',
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
              <TextInputPanel />
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