// 文件路径：frontend/src/pages/KnowledgeAdminPage.tsx
// 用途：知识库管理页 - 上传文档 + 切片列表 + 编辑 + 删除 + 检索测试
// MVP 范围：US-005 / US-006 / US-007 全部验收标准

import React, { useState, useEffect, useCallback } from 'react'
import {
  Upload,
  Button,
  Table,
  Input,
  Card,
  Typography,
  message,
  Modal,
  Popconfirm,
  Tag,
  Space,
  Progress,
  Empty,
  Divider,
} from 'antd'
import {
  UploadOutlined,
  SearchOutlined,
  DeleteOutlined,
  EditOutlined,
  SaveOutlined,
  CloseOutlined,
  ArrowLeftOutlined,
  FileTextOutlined,
} from '@ant-design/icons'
import type { UploadProps } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  uploadDocument,
  importKnowledgeJson,
  fetchChunks,
  updateChunk,
  deleteChunk,
  deleteFile,
  searchKnowledge,
} from '../services/api'
import type { KnowledgeChunk, SearchResult } from '../types'

const { TextArea } = Input
const { Text, Title } = Typography

interface Props {
  onBack: () => void
}

const KnowledgeAdminPage: React.FC<Props> = ({ onBack }) => {
  // ============ 切片列表状态 ============
  const [chunks, setChunks] = useState<KnowledgeChunk[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [listLoading, setListLoading] = useState(false)
  const [filterFileId, setFilterFileId] = useState<string | undefined>()

  // ============ 上传状态 ============
  const [uploading, setUploading] = useState(false)

  // ============ 编辑状态 ============
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingText, setEditingText] = useState('')
  const [saving, setSaving] = useState(false)

  // ============ 检索测试状态 ============
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [showSearch, setShowSearch] = useState(false)

  // ============ 加载切片列表 ============
  const loadChunks = useCallback(async () => {
    setListLoading(true)
    try {
      const res = await fetchChunks(filterFileId, page, pageSize)
      setChunks(res.chunks)
      setTotal(res.total)
    } catch (err: any) {
      message.error(`加载失败: ${err.message}`)
    } finally {
      setListLoading(false)
    }
  }, [filterFileId, page, pageSize])

  useEffect(() => {
    loadChunks()
  }, [loadChunks])

  // ============ 文件上传 ============
  const uploadProps: UploadProps = {
    accept: '.txt,.md,.docx',
    showUploadList: false,
    beforeUpload: () => false, // 阻止自动上传
    onChange: async (info) => {
      const file = info.file as unknown as File
      if (!file) return

      // 大小校验
      if (file.size > 10 * 1024 * 1024) {
        message.error('文件大小不能超过 10MB')
        return
      }

      setUploading(true)
      try {
        const res = await uploadDocument(file)
        message.success(`上传成功: ${res.file_name}，已生成 ${res.chunk_count} 个切片`)
        setPage(1)
        loadChunks()
      } catch (err: any) {
        message.error(`上传失败: ${err.message}`)
      } finally {
        setUploading(false)
      }
    },
  }

  const jsonUploadProps: UploadProps = {
    accept: '.json',
    showUploadList: false,
    beforeUpload: () => false,
    onChange: async (info) => {
      const file = info.file as unknown as File
      if (!file) return
      setUploading(true)
      try {
        const raw = await file.text()
        const parsed = JSON.parse(raw)
        const items = Array.isArray(parsed) ? parsed : parsed?.items
        if (!Array.isArray(items)) {
          message.error('JSON 格式不正确：需为数组或 { items: [...] }')
          return
        }
        const res = await importKnowledgeJson(items)
        message.success(`导入完成：成功 ${res.imported}，失败 ${res.failed}`)
        if (res.errors?.length) {
          Modal.warning({
            title: '部分条目导入失败',
            content: (
              <div style={{ maxHeight: 220, overflowY: 'auto', whiteSpace: 'pre-wrap' }}>
                {res.errors.join('\n')}
              </div>
            ),
          })
        }
        setPage(1)
        loadChunks()
      } catch (err: any) {
        message.error(`JSON 导入失败: ${err.message}`)
      } finally {
        setUploading(false)
      }
    },
  }

  // ============ 编辑切片 ============
  const handleStartEdit = (chunk: KnowledgeChunk) => {
    setEditingId(chunk.chunk_id)
    setEditingText(chunk.content)
  }

  const handleCancelEdit = () => {
    setEditingId(null)
    setEditingText('')
  }

  const handleSaveEdit = async () => {
    if (!editingId || !editingText.trim()) return
    setSaving(true)
    try {
      await updateChunk(editingId, editingText.trim())
      message.success('切片已更新并重新向量化')
      setEditingId(null)
      setEditingText('')
      loadChunks()
    } catch (err: any) {
      message.error(`保存失败: ${err.message}`)
    } finally {
      setSaving(false)
    }
  }

  // ============ 删除切片 ============
  const handleDeleteChunk = async (chunkId: string) => {
    try {
      await deleteChunk(chunkId)
      message.success('切片已删除')
      loadChunks()
    } catch (err: any) {
      message.error(`删除失败: ${err.message}`)
    }
  }

  // ============ 删除文件 ============
  const handleDeleteFile = async (fileId: string) => {
    try {
      const res = await deleteFile(fileId)
      message.success(`文件已删除，共删除 ${res.deleted_chunks} 个切片`)
      setFilterFileId(undefined)
      setPage(1)
      loadChunks()
    } catch (err: any) {
      message.error(`删除失败: ${err.message}`)
    }
  }

  // ============ 检索测试 ============
  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setSearching(true)
    try {
      const res = await searchKnowledge(searchQuery.trim())
      setSearchResults(res.results)
      if (res.results.length === 0) {
        message.info('未检索到相关内容，请检查知识库')
      }
    } catch (err: any) {
      message.error(`检索失败: ${err.message}`)
    } finally {
      setSearching(false)
    }
  }

  // ============ 表格列定义 ============
  const columns: ColumnsType<KnowledgeChunk> = [
    {
      title: '内容',
      dataIndex: 'content',
      key: 'content',
      width: '45%',
      render: (text: string, record: KnowledgeChunk) => {
        if (editingId === record.chunk_id) {
          return (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <TextArea
                value={editingText}
                onChange={(e) => setEditingText(e.target.value)}
                autoSize={{ minRows: 3, maxRows: 8 }}
                maxLength={500}
                showCount
              />
              <Space>
                <Button
                  type="primary"
                  size="small"
                  icon={<SaveOutlined />}
                  loading={saving}
                  onClick={handleSaveEdit}
                >
                  保存
                </Button>
                <Button
                  size="small"
                  icon={<CloseOutlined />}
                  onClick={handleCancelEdit}
                >
                  取消
                </Button>
              </Space>
            </div>
          )
        }
        return (
          <Text style={{ fontSize: 13 }}>
            {text.length > 100 ? text.slice(0, 100) + '...' : text}
          </Text>
        )
      },
    },
    {
      title: '文件',
      dataIndex: 'file_name',
      key: 'file_name',
      width: '18%',
      render: (name: string, record: KnowledgeChunk) => (
        <Button
          type="link"
          size="small"
          onClick={() => {
            setFilterFileId(record.file_id)
            setPage(1)
          }}
          style={{ padding: 0, fontSize: 12 }}
        >
          <FileTextOutlined /> {name.length > 15 ? name.slice(0, 15) + '...' : name}
        </Button>
      ),
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: '12%',
      render: (cat: string) => <Tag>{cat}</Tag>,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: '13%',
      render: (t: string) => (
        <Text type="secondary" style={{ fontSize: 12 }}>
          {t ? t.replace('T', ' ').replace('Z', '') : '-'}
        </Text>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: '12%',
      render: (_: unknown, record: KnowledgeChunk) => (
        <Space size="small">
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleStartEdit(record)}
            disabled={editingId !== null}
          />
          <Popconfirm
            title="确认删除此切片？"
            onConfirm={() => handleDeleteChunk(record.chunk_id)}
          >
            <Button type="text" size="small" icon={<DeleteOutlined />} danger />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div style={{ padding: '24px', maxWidth: 1200, margin: '0 auto' }}>
      {/* 顶部导航 */}
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 20, gap: 12 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={onBack}>
          返回
        </Button>
        <Title level={4} style={{ margin: 0 }}>
          知识库管理
        </Title>
      </div>

      {/* 操作栏 */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
          flexWrap: 'wrap',
          gap: 8,
        }}
      >
        <Space wrap>
          <Upload {...uploadProps}>
            <Button type="primary" icon={<UploadOutlined />} loading={uploading}>
              上传文档
            </Button>
          </Upload>
          <Upload {...jsonUploadProps}>
            <Button icon={<UploadOutlined />} loading={uploading}>
              上传 JSON 知识库
            </Button>
          </Upload>
          <Text type="secondary" style={{ fontSize: 12 }}>
            支持 .txt .md .docx / .json，单文件最大 10MB
          </Text>
          {filterFileId && (
            <Button
              size="small"
              onClick={() => {
                setFilterFileId(undefined)
                setPage(1)
              }}
            >
              清除筛选
            </Button>
          )}
        </Space>

        <Button
          icon={<SearchOutlined />}
          onClick={() => setShowSearch(!showSearch)}
          type={showSearch ? 'primary' : 'default'}
        >
          检索测试
        </Button>
      </div>

      {/* 检索测试面板 */}
      {showSearch && (
        <Card
          size="small"
          title="检索测试"
          style={{ marginBottom: 16, borderColor: '#1677ff' }}
        >
          <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="输入测试文本，查看检索结果..."
              onPressEnter={handleSearch}
              style={{ flex: 1 }}
            />
            <Button
              type="primary"
              icon={<SearchOutlined />}
              loading={searching}
              onClick={handleSearch}
              disabled={!searchQuery.trim()}
            >
              检索
            </Button>
          </div>

          {searchResults.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {searchResults.map((r, idx) => (
                <div
                  key={r.chunk_id}
                  style={{
                    padding: '10px 12px',
                    background: '#fafafa',
                    borderRadius: 6,
                    border: '1px solid #f0f0f0',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      marginBottom: 4,
                    }}
                  >
                    <Tag color="blue">#{idx + 1}</Tag>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      相似度: {(r.score * 100).toFixed(1)}%
                    </Text>
                  </div>
                  <Text style={{ fontSize: 13 }}>{r.content}</Text>
                </div>
              ))}
            </div>
          ) : (
            searching ? null : (
              <Text type="secondary" style={{ fontSize: 13 }}>
                输入文本并点击检索查看结果
              </Text>
            )
          )}
        </Card>
      )}

      {/* 切片列表 */}
      <Table
        dataSource={chunks}
        columns={columns}
        rowKey="chunk_id"
        loading={listLoading}
        pagination={{
          current: page,
          pageSize,
          total,
          onChange: (p) => setPage(p),
          showTotal: (t) => `共 ${t} 个切片`,
          showSizeChanger: false,
        }}
        size="middle"
        locale={{
          emptyText: (
            <Empty description="知识库为空，请上传文档" />
          ),
        }}
      />

      {/* 文件级删除（筛选到某文件时显示） */}
      {filterFileId && chunks.length > 0 && (
        <div style={{ marginTop: 12, textAlign: 'right' }}>
          <Popconfirm
            title={`确认删除此文件及其所有 ${total} 个切片？`}
            onConfirm={() => handleDeleteFile(filterFileId)}
          >
            <Button danger icon={<DeleteOutlined />}>
              删除整个文件
            </Button>
          </Popconfirm>
        </div>
      )}
    </div>
  )
}

export default KnowledgeAdminPage