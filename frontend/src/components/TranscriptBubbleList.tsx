import React, { useEffect, useMemo, useRef } from 'react'
import { Button, Empty, Tag } from 'antd'
import { useSessionStore } from '../store'

function formatTime(ts: number): string {
  const d = new Date(ts)
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  const ss = String(d.getSeconds()).padStart(2, '0')
  return `${hh}:${mm}:${ss}`
}

const TranscriptBubbleList: React.FC<{
  onBubbleClick: (bubbleId: string) => void
}> = ({ onBubbleClick }) => {
  const { bubbles, autoScroll, setAutoScroll } = useSessionStore()
  const listRef = useRef<HTMLDivElement | null>(null)

  const sorted = useMemo(() => [...bubbles].sort((a, b) => a.created_at - b.created_at), [bubbles])

  useEffect(() => {
    if (!autoScroll || !listRef.current) return
    listRef.current.scrollTop = listRef.current.scrollHeight
  }, [autoScroll, sorted])

  const onScroll = () => {
    const el = listRef.current
    if (!el) return
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 32
    setAutoScroll(nearBottom)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, height: '100%' }}>
      <div
        ref={listRef}
        onScroll={onScroll}
        style={{
          flex: 1,
          overflowY: 'auto',
          border: '1px solid #f0f0f0',
          borderRadius: 10,
          background: '#fafafa',
          padding: 12,
        }}
      >
        {sorted.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="点击“开始录音”或使用下方手动输入"
          />
        ) : (
          sorted.map((bubble) => {
            const clickable = bubble.type === 'asr_final' || bubble.type === 'manual'
            const bgColor =
              bubble.type === 'asr_draft' ? '#fffbe6' : bubble.type === 'manual' ? '#f5f5f5' : '#e6f4ff'
            const borderColor = bubble.selected ? '#52c41a' : '#d9d9d9'
            return (
              <div
                key={bubble.id}
                onClick={() => clickable && onBubbleClick(bubble.id)}
                style={{
                  marginBottom: 10,
                  padding: 10,
                  borderRadius: 8,
                  background: bgColor,
                  border: `1px solid ${borderColor}`,
                  cursor: clickable ? 'pointer' : 'not-allowed',
                }}
              >
                <div style={{ marginBottom: 6 }}>
                  <Tag color={bubble.type === 'asr_draft' ? 'gold' : bubble.type === 'manual' ? 'default' : 'blue'}>
                    {bubble.type === 'asr_draft' ? '识别中' : bubble.type === 'manual' ? '手动输入' : '已定稿'}
                  </Tag>
                  <span style={{ color: '#8c8c8c', fontSize: 12 }}>{formatTime(bubble.created_at)}</span>
                </div>
                <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                  {bubble.stable_text}
                  {bubble.stash_text ? (
                    <span style={{ color: '#bfbfbf' }}>{bubble.stash_text}</span>
                  ) : (
                    bubble.text
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>
      {!autoScroll && (
        <div style={{ textAlign: 'center' }}>
          <Button size="small" onClick={() => setAutoScroll(true)}>
            回到底部
          </Button>
        </div>
      )}
    </div>
  )
}

export default TranscriptBubbleList
