import { useState } from 'react'
import { useSelector, useDispatch } from 'react-redux'
import { assistantChat, HttpError } from '../api'
import { UI_CONFIG } from '../config/uiConfig'
import { ASSISTANT_CONFIG } from '../config/assistantConfig'
import { toggleChat, addMessage } from '../store/appSlice'
import { addTransaction, markSuccess, markFailed } from '../store/transactionsSlice'
import type { RootState } from '../store'
import { KBSelect } from './KBSelect'
import { generateUid, formatTime } from '../utils/commonUtils'

export function AIChat() {
  const dispatch = useDispatch()
  const { selectedUid, messages, isChatOpen } = useSelector((state: RootState) => state.app)
  
  const [chatInput, setChatInput] = useState('')
  const [action, setAction] = useState<string | undefined>(undefined)
  const [isSending, setIsSending] = useState(false)

  async function sendChat() {
    const text = chatInput.trim()
    if (!text) return

    const txId = generateUid()
    dispatch(addTransaction({ txId, type: 'assistant_query', text, action }))

    dispatch(addMessage({ id: generateUid(), role: 'user', text, createdAt: Date.now() }))
    setChatInput('')
    setIsSending(true)

    try {
      const data = await assistantChat({
        action,
        message: text,
        from_uid: selectedUid,
        to_uid: selectedUid,
        center_uid: selectedUid,
        depth: ASSISTANT_CONFIG.defaults.depth,
        subject_uid: selectedUid,
        progress: {},
        limit: ASSISTANT_CONFIG.defaults.limit,
        count: ASSISTANT_CONFIG.defaults.count,
        difficulty_min: ASSISTANT_CONFIG.defaults.difficultyMin,
        difficulty_max: ASSISTANT_CONFIG.defaults.difficultyMax,
        exclude: [],
      })

      const assistantText = typeof data === 'string' ? data : JSON.stringify(data)
      dispatch(markSuccess(txId))
      dispatch(addMessage({ id: generateUid(), role: 'assistant', text: assistantText, createdAt: Date.now() }))

    } catch (error: unknown) {
      let message = 'Неизвестная ошибка'
      if (error instanceof HttpError) {
        message = error.message
        if (error.details) console.error('[AIChat] Error details:', error.details)
      } else if (error instanceof Error) {
        message = error.message
      }

      dispatch(markFailed({ txId, error: message }))
      dispatch(addMessage({
        id: generateUid(),
        role: 'assistant',
        text: `Ошибка: ${message}. Проверь подключение к бэкенду.`,
        createdAt: Date.now(),
      }))
    } finally {
      setIsSending(false)
    }
  }

  return (
    <div 
      className={`kb-panel kb-chat-window ${isChatOpen ? 'open' : ''}`}
      style={{ 
        width: UI_CONFIG.chatWidth, 
        height: UI_CONFIG.chatHeight,
        bottom: UI_CONFIG.chatBottomOffset,
        right: UI_CONFIG.chatRightOffset
      }}
    >
      <div className="kb-chat-header">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <div style={{ fontSize: 13, fontWeight: 650 }}>ИИ ассистент</div>
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>Контекст: {selectedUid}</div>
        </div>
        <button className="kb-btn" onClick={() => dispatch(toggleChat())}>Закрыть</button>
      </div>

      <div className="kb-chat-messages">
        {messages.map((m) => (
          <div key={m.id} style={{ alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '88%' }}>
            <div className={`kb-chat-bubble ${m.role}`}>
              {m.text}
            </div>
            <div className="kb-chat-time" style={{ textAlign: m.role === 'user' ? 'right' : 'left' }}>
              {formatTime(m.createdAt)}
            </div>
          </div>
        ))}
      </div>

      <div className="kb-chat-footer">
        <KBSelect
          label=""
          value={action || ''}
          onChange={(v: string | number) => setAction(v ? String(v) : undefined)}
          options={ASSISTANT_CONFIG.actionOptions}
          width={100}
          dropUp={true}
        />
        <input 
          className="kb-input" 
          value={chatInput} 
          onChange={(e) => setChatInput(e.target.value)} 
          placeholder="Спроси..." 
          onKeyDown={(e) => e.key === 'Enter' && void sendChat()} 
        />
        <button 
          className="kb-btn kb-btn-primary" 
          style={{ padding: '0 16px', height: 34 }} 
          onClick={() => void sendChat()}
          disabled={isSending}
        >
          {isSending ? '...' : 'Go'}
        </button>
      </div>
    </div>
  )
}

