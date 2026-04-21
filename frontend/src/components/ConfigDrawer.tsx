// 文件路径：frontend/src/components/ConfigDrawer.tsx
// 用途：配置抽屉 - 行业选择 + 话术风格 + LLM 高级配置
// MVP 范围：US-008 / US-009 + LLM 配置（Q4 决策）
// 变更：新增 handleTestConnection + api_key 格式校验（评审修复）

import React, { useState } from 'react'
import {
  Drawer,
  Select,
  Typography,
  Divider,
  Input,
  Collapse,
  Button,
  Space,
  message,
  Alert,
} from 'antd'
import {
  SettingOutlined,
  ApiOutlined,
  SafetyCertificateOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import { useSessionStore } from '../store'
import { INDUSTRIES, SPEECH_STYLES } from '../types'
import type { Industry, SpeechStyle, LLMConfig, ASRConfig } from '../types'

const { Text } = Typography

interface Props {
  open: boolean
  onClose: () => void
}

const ConfigDrawer: React.FC<Props> = ({ open, onClose }) => {
  const { industry, style, setIndustry, setStyle, llmConfig, setLLMConfig, asrConfig, setASRConfig } =
    useSessionStore()

  const [localLLM, setLocalLLM] = useState<LLMConfig>(llmConfig)
  const [localASR, setLocalASR] = useState<ASRConfig>(asrConfig)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<'success' | 'fail' | null>(null)

  const validateApiKey = (key: string): boolean => {
    if (!key.trim()) return false
    // 常见 API Key 格式校验（sk- 开头，或其他厂商格式）
    // 不做强校验，只检查非空和基本长度
    return key.trim().length >= 8
  }

  const handleTestConnection = async () => {
    if (!validateApiKey(localLLM.api_key)) {
      message.warning('请先填写有效的 API Key')
      return
    }

    setTesting(true)
    setTestResult(null)

    try {
      const baseUrl = localLLM.base_url || 'https://api.deepseek.com'
      const normalizedUrl = baseUrl.endsWith('/v1') ? baseUrl : `${baseUrl}/v1`

      // 调用 models 列表接口验证 Key 有效性
      const response = await fetch(`${normalizedUrl}/models`, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${localLLM.api_key}`,
        },
        signal: AbortSignal.timeout(10000),
      })

      if (response.ok) {
        setTestResult('success')
        message.success('连接成功！API Key 有效')
      } else {
        setTestResult('fail')
        const status = response.status
        if (status === 401) {
          message.error('API Key 无效，请检查后重试')
        } else {
          message.error(`连接失败，HTTP ${status}`)
        }
      }
    } catch (err: any) {
      setTestResult('fail')
      if (err.name === 'TimeoutError') {
        message.error('连接超时，请检查 API Base URL 是否正确')
      } else {
        message.error(`连接失败: ${err.message}`)
      }
    } finally {
      setTesting(false)
    }
  }

  const handleSaveLLM = () => {
    if (!validateApiKey(localLLM.api_key)) {
      message.warning('请填写有效的 API Key（至少 8 个字符）')
      return
    }
    setLLMConfig({ ...localLLM })
    message.success('LLM 配置已保存')
  }

  const handleSaveASR = () => {
    setASRConfig({ ...localASR })
    message.success('ASR 配置已保存')
  }

  React.useEffect(() => {
    if (open) {
      setLocalLLM(llmConfig)
      setLocalASR(asrConfig)
      setTestResult(null)
    }
  }, [open, llmConfig, asrConfig])

  return (
    <Drawer
      title={
        <span>
          <SettingOutlined /> 配置
        </span>
      }
      placement="right"
      width={380}
      open={open}
      onClose={onClose}
    >
      {/* 行业选择 */}
      <div style={{ marginBottom: 20 }}>
        <Text strong style={{ display: 'block', marginBottom: 8 }}>
          客户行业
        </Text>
        <Select
          value={industry}
          onChange={(v: Industry) => setIndustry(v)}
          style={{ width: '100%' }}
          options={INDUSTRIES.map((i) => ({ value: i, label: i }))}
        />
        <Text type="secondary" style={{ fontSize: 12, marginTop: 4, display: 'block' }}>
          选择后系统会优先检索该行业的知识库内容
        </Text>
      </div>

      {/* 话术风格 */}
      <div style={{ marginBottom: 20 }}>
        <Text strong style={{ display: 'block', marginBottom: 8 }}>
          话术风格
        </Text>
        <Select
          value={style}
          onChange={(v: SpeechStyle) => setStyle(v)}
          style={{ width: '100%' }}
          options={SPEECH_STYLES.map((s) => ({ value: s, label: s }))}
        />
      </div>

      <Divider />

      {/* LLM 高级配置 */}
      <Collapse
        ghost
        items={[
          {
            key: 'llm',
            label: (
              <Text strong>
                <ApiOutlined /> LLM 高级配置
              </Text>
            ),
            children: (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div>
                  <Text style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>
                    API Base URL
                  </Text>
                  <Input
                    value={localLLM.base_url}
                    onChange={(e) => {
                      setLocalLLM({ ...localLLM, base_url: e.target.value })
                      setTestResult(null)
                    }}
                    placeholder="https://api.deepseek.com"
                  />
                </div>

                <div>
                  <Text style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>
                    API Key <SafetyCertificateOutlined />
                  </Text>
                  <Input.Password
                    value={localLLM.api_key}
                    onChange={(e) => {
                      setLocalLLM({ ...localLLM, api_key: e.target.value })
                      setTestResult(null)
                    }}
                    placeholder="sk-..."
                    status={
                      localLLM.api_key && !validateApiKey(localLLM.api_key)
                        ? 'error'
                        : undefined
                    }
                  />
                  <Text type="warning" style={{ fontSize: 11, marginTop: 2, display: 'block' }}>
                    API Key 存储在浏览器本地，请勿在公共设备上使用
                  </Text>
                </div>

                <div>
                  <Text style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>
                    模型名称
                  </Text>
                  <Input
                    value={localLLM.model}
                    onChange={(e) => setLocalLLM({ ...localLLM, model: e.target.value })}
                    placeholder="deepseek-chat"
                  />
                </div>

                {/* 测试连接结果 */}
                {testResult === 'success' && (
                  <Alert
                    message="连接成功"
                    type="success"
                    showIcon
                    icon={<CheckCircleOutlined />}
                    closable
                    onClose={() => setTestResult(null)}
                  />
                )}
                {testResult === 'fail' && (
                  <Alert
                    message="连接失败，请检查配置"
                    type="error"
                    showIcon
                    icon={<CloseCircleOutlined />}
                    closable
                    onClose={() => setTestResult(null)}
                  />
                )}

                <Space style={{ width: '100%' }} direction="vertical">
                  <Button
                    block
                    onClick={handleTestConnection}
                    loading={testing}
                    icon={testing ? <LoadingOutlined /> : undefined}
                  >
                    测试连接
                  </Button>
                  <Button type="primary" block onClick={handleSaveLLM}>
                    保存配置
                  </Button>
                </Space>
              </div>
            ),
          },
          {
            key: 'asr',
            label: (
              <Text strong>
                <ApiOutlined /> ASR 配置
              </Text>
            ),
            children: (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div>
                  <Text style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>
                    WebSocket URL
                  </Text>
                  <Input
                    value={localASR.ws_url}
                    onChange={(e) => setLocalASR({ ...localASR, ws_url: e.target.value })}
                    placeholder="wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
                  />
                </div>
                <div>
                  <Text style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>
                    ASR API Key
                  </Text>
                  <Input.Password
                    value={localASR.api_key}
                    onChange={(e) => setLocalASR({ ...localASR, api_key: e.target.value })}
                    placeholder="sk-..."
                  />
                </div>
                <div>
                  <Text style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>
                    ASR 模型
                  </Text>
                  <Input
                    value={localASR.model}
                    onChange={(e) => setLocalASR({ ...localASR, model: e.target.value })}
                    placeholder="qwen3-asr-flash-realtime"
                  />
                </div>
                <Button type="primary" block onClick={handleSaveASR}>
                  保存 ASR 配置
                </Button>
              </div>
            ),
          },
        ]}
      />
    </Drawer>
  )
}

export default ConfigDrawer