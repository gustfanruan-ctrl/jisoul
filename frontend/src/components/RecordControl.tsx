import React from 'react'
import { Button } from 'antd'
import { AudioOutlined, PauseCircleOutlined, LoadingOutlined } from '@ant-design/icons'
import { useSessionStore } from '../store'
import { useRealtimeAsr } from '../hooks/useRealtimeAsr'

const RecordControl: React.FC = () => {
  const recordingStatus = useSessionStore((s) => s.recordingStatus)
  const { startRecording, stopRecording } = useRealtimeAsr()

  const isBusy = recordingStatus === 'connecting' || recordingStatus === 'stopping'
  const isRecording = recordingStatus === 'recording'

  return (
    <div style={{ display: 'flex', justifyContent: 'center', marginTop: 12 }}>
      <Button
        type={isRecording ? 'default' : 'primary'}
        size="large"
        icon={
          isBusy ? <LoadingOutlined spin /> : isRecording ? <PauseCircleOutlined /> : <AudioOutlined />
        }
        onClick={isRecording ? stopRecording : startRecording}
        disabled={isBusy}
      >
        {isBusy ? '处理中...' : isRecording ? '停止录音' : '开始录音'}
      </Button>
    </div>
  )
}

export default RecordControl
