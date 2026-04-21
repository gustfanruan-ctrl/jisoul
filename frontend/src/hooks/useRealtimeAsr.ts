import { useCallback, useRef } from 'react'
import { message } from 'antd'
import { useSessionStore } from '../store'

type ASREvent =
  | { type: 'session.created' }
  | { type: 'session.updated' }
  | { type: 'session.finished' }
  | { type: 'input_audio_buffer.speech_started'; item_id?: string }
  | { type: 'conversation.item.input_audio_transcription.text'; item_id?: string; text?: string; stash?: string }
  | { type: 'conversation.item.input_audio_transcription.completed'; item_id?: string; transcript?: string }
  | { type: 'error'; error?: { message?: string } }

function toBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.byteLength; i += 1) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary)
}

export function useRealtimeAsr() {
  const wsRef = useRef<WebSocket | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null)

  const {
    setRecordingStatus,
    upsertDraftBubble,
    finalizeBubble,
    asrConfig,
  } = useSessionStore()

  const cleanupAudio = useCallback(() => {
    if (processorRef.current) {
      processorRef.current.disconnect()
      processorRef.current.onaudioprocess = null
      processorRef.current = null
    }
    if (sourceRef.current) {
      sourceRef.current.disconnect()
      sourceRef.current = null
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close()
      audioCtxRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
  }, [])

  const sendEvent = useCallback((payload: Record<string, unknown>) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
    wsRef.current.send(JSON.stringify(payload))
  }, [])

  const startMic = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, sampleRate: 16000 },
      video: false,
    })
    streamRef.current = stream

    const audioCtx = new AudioContext({ sampleRate: 16000 })
    audioCtxRef.current = audioCtx
    const source = audioCtx.createMediaStreamSource(stream)
    sourceRef.current = source
    const processor = audioCtx.createScriptProcessor(1600, 1, 1)
    processorRef.current = processor

    processor.onaudioprocess = (event) => {
      const float32 = event.inputBuffer.getChannelData(0)
      const int16 = new Int16Array(float32.length)
      for (let i = 0; i < float32.length; i += 1) {
        int16[i] = Math.max(-32768, Math.min(32767, float32[i] * 32768))
      }
      sendEvent({
        event_id: `evt_${Date.now()}`,
        type: 'input_audio_buffer.append',
        audio: toBase64(int16.buffer),
      })
    }

    source.connect(processor)
    processor.connect(audioCtx.destination)
  }, [sendEvent])

  const handleServerEvent = useCallback((event: ASREvent) => {
    switch (event.type) {
      case 'session.updated':
        setRecordingStatus('recording')
        break
      case 'input_audio_buffer.speech_started':
        if (event.item_id) {
          upsertDraftBubble(event.item_id, '', '')
        }
        break
      case 'conversation.item.input_audio_transcription.text':
        if (event.item_id) {
          upsertDraftBubble(event.item_id, event.text || '', event.stash || '')
        }
        break
      case 'conversation.item.input_audio_transcription.completed':
        if (event.item_id && event.transcript) {
          finalizeBubble(event.item_id, event.transcript)
        }
        break
      case 'session.finished':
        setRecordingStatus('idle')
        cleanupAudio()
        break
      case 'error':
        setRecordingStatus('error')
        message.error(event.error?.message || '语音连接中断，请重试')
        break
      default:
        break
    }
  }, [cleanupAudio, finalizeBubble, setRecordingStatus, upsertDraftBubble])

  const startRecording = useCallback(async () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return
    setRecordingStatus('connecting')
    try {
      const model = asrConfig.model?.trim() || 'qwen3-asr-flash-realtime'
      const wsUrl = asrConfig.ws_url?.trim() || 'wss://dashscope.aliyuncs.com/api-ws/v1/realtime'
      const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(
        `${wsProtocol}://${window.location.host}/api/v1/asr/ws?model=${encodeURIComponent(model)}&ws_url=${encodeURIComponent(wsUrl)}`
      )
      wsRef.current = ws

      ws.onopen = async () => {
        sendEvent({
          event_id: `evt_${Date.now()}`,
          type: 'session.update',
          session: {
            modalities: ['text'],
            input_audio_format: 'pcm',
            sample_rate: 16000,
            input_audio_transcription: { language: 'zh' },
            turn_detection: {
              type: 'server_vad',
              threshold: 0.0,
              silence_duration_ms: 400,
            },
          },
        })
        await startMic()
      }

      ws.onmessage = (msg) => {
        try {
          const payload = JSON.parse(msg.data) as ASREvent
          handleServerEvent(payload)
        } catch {
          // ignore unknown payload
        }
      }

      ws.onerror = () => {
        setRecordingStatus('error')
        message.error('语音连接中断，请重试')
      }

      ws.onclose = () => {
        cleanupAudio()
        setRecordingStatus('idle')
      }
    } catch (error: any) {
      setRecordingStatus('error')
      if (error?.name === 'NotAllowedError') {
        message.error('请允许麦克风权限后重试')
      } else {
        message.error(error?.message || '语音连接中断，请重试')
      }
    }
  }, [asrConfig.model, cleanupAudio, handleServerEvent, sendEvent, setRecordingStatus, startMic])

  const stopRecording = useCallback(() => {
    if (!wsRef.current) return
    setRecordingStatus('stopping')
    sendEvent({
      event_id: `evt_${Date.now()}`,
      type: 'session.finish',
    })
    window.setTimeout(() => {
      wsRef.current?.close()
      wsRef.current = null
      cleanupAudio()
      setRecordingStatus('idle')
    }, 350)
  }, [cleanupAudio, sendEvent, setRecordingStatus])

  return { startRecording, stopRecording }
}
