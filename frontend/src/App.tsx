import { useEffect, useMemo, useState } from 'react'
import { Link, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import ExplorePage from './pages/ExplorePage'
import EditPage from './pages/EditPage'
import PracticePage from './pages/PracticePage'
import RoadmapPage from './pages/RoadmapPage'
import SettingsPage from './pages/SettingsPage'
import AnalyticsPage from './pages/AnalyticsPage'
import { assistantChat, type AssistantAction } from './api'
import ThemeToggle from './components/ThemeToggle'

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  text: string
  createdAt: number
}

function uid() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function formatTime(ts: number) {
  const d = new Date(ts)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function useActiveRouteTitle() {
  const location = useLocation()
  const path = location.pathname

  if (path.startsWith('/edit')) return 'Edit'
  if (path.startsWith('/roadmap')) return 'Дорожная карта'
  if (path.startsWith('/practice')) return 'Практика'
  if (path.startsWith('/settings')) return 'Настройки'
  return 'Explore'
}

export default function App() {
  const navigate = useNavigate()
  const title = useActiveRouteTitle()

  const [selectedUid, setSelectedUid] = useState<string>('TOP-DEMO')
  const [chatOpen, setChatOpen] = useState(false)
  const [chatInput, setChatInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    {
      id: uid(),
      role: 'assistant',
      text: 'Привет! Я ассистент KnowledgeBase. Выбери узел и спроси меня про связи, роадмап или генерацию контента.',
      createdAt: Date.now(),
    },
  ])

  const navItems = useMemo(
    () =>
      [
        { to: '/', title: 'Explore (vis-network)' },
        { to: '/edit', title: 'Edit (React Flow)' },
        { to: '/analytics', title: 'Аналитика' },
        { to: '/roadmap', title: 'Дорожная карта' },
        { to: '/practice', title: 'Практика' },
        { to: '/settings', title: 'Настройки' },
      ] as const,
    [],
  )

  useEffect(() => {
    const hash = window.location.hash.replace('#', '')
    if (hash === 'roadmap') navigate('/roadmap', { replace: true })
    if (hash === 'construct') navigate('/edit', { replace: true })
    if (hash === 'practice') navigate('/practice', { replace: true })
    if (hash === 'settings') navigate('/settings', { replace: true })
  }, [navigate])

  const [action, setAction] = useState<AssistantAction | undefined>(undefined)
  async function sendChat() {
    const text = chatInput.trim()
    if (!text) return

    const userMsg: ChatMessage = { id: uid(), role: 'user', text, createdAt: Date.now() }
    setMessages((prev) => [...prev, userMsg])
    setChatInput('')

    try {
      const data = await assistantChat({
        action,
        message: text,
        from_uid: selectedUid,
        to_uid: selectedUid,
        center_uid: selectedUid,
        depth: 1,
        subject_uid: selectedUid,
        progress: {},
        limit: 30,
        count: 10,
        difficulty_min: 1,
        difficulty_max: 5,
        exclude: [],
      })
      const assistantText = typeof data === 'string' ? data : JSON.stringify(data)

      setMessages((prev) => [
        ...prev,
        { id: uid(), role: 'assistant', text: assistantText, createdAt: Date.now() },
      ])
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: uid(),
          role: 'assistant',
          text: 'Не удалось связаться с API. Проверь, что backend доступен и что Vite проксирует /v1 и /ws.',
          createdAt: Date.now(),
        },
      ])
    }
  }

  return (
    <div className="kb-bg" style={{ height: '100%', display: 'flex' }}>
      <aside
        className="kb-panel"
        style={{
          width: 300,
          margin: 16,
          padding: 14,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ fontSize: 14, color: 'var(--muted)' }}>KnowledgeBaseAI</div>
          <div style={{ fontSize: 18, fontWeight: 650, letterSpacing: 0.2 }}>Граф знаний</div>
        </div>

        <div className="kb-panel" style={{ padding: 12, borderRadius: 14 }}>
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>Выбранный узел</div>
          <div style={{ marginTop: 6, display: 'flex', gap: 8, alignItems: 'center' }}>
            <div
              style={{
                width: 10,
                height: 10,
                borderRadius: 999,
                background: 'var(--accent-2)',
                boxShadow: '0 0 0 4px rgba(46, 233, 166, 0.12)',
              }}
            />
            <div style={{ fontWeight: 600 }}>{selectedUid}</div>
          </div>
          <div style={{ marginTop: 10, display: 'flex', gap: 8 }}>
            <button className="kb-btn kb-btn-primary" onClick={() => setChatOpen(true)} style={{ flex: 1 }}>
              Спросить
            </button>
            <button className="kb-btn" onClick={() => setSelectedUid((prev) => (prev === 'TOP-DEMO' ? 'SKL-DEMO' : 'TOP-DEMO'))}>
              Переключить
            </button>
          </div>
        </div>

        <nav style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {navItems.map((item) => (
            <Link key={item.to} to={item.to} className="kb-btn" style={{ textAlign: 'left' }}>
              {item.title}
            </Link>
          ))}
        </nav>

        <div style={{ marginTop: 'auto', fontSize: 12, color: 'var(--muted)' }}>API: /v1 • WS: /ws</div>
      </aside>

      <main style={{ flex: 1, padding: 16, paddingLeft: 0 }}>
        <div
          className="kb-panel"
          style={{
            height: 'calc(100vh - 32px)',
            padding: 16,
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>Рабочая область</div>
              <div style={{ fontSize: 18, fontWeight: 650 }}>{title}</div>
            </div>

            <div style={{ display: 'flex', gap: 8 }}>
              <button className="kb-btn" onClick={() => setChatOpen(true)}>
                Ассистент
              </button>
              <button className="kb-btn" onClick={() => navigate('/')}
              >
                Домой
              </button>

              <ThemeToggle />  {/* ← здесь */}
            </div>
          </div>

          <div style={{ flex: 1, minHeight: 0 }}>
            <Routes>
              <Route path="/" element={<ExplorePage selectedUid={selectedUid} onSelectUid={setSelectedUid} />} />
              <Route path="/edit" element={<EditPage selectedUid={selectedUid} onSelectUid={setSelectedUid} />} />
              <Route path="/analytics" element={<AnalyticsPage />} />
              <Route path="/roadmap" element={<RoadmapPage selectedUid={selectedUid} />} />
              <Route path="/practice" element={<PracticePage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Routes>
          </div>
        </div>
      </main>

      <button
        className="kb-btn kb-btn-primary"
        onClick={() => setChatOpen(true)}
        style={{
          position: 'fixed',
          right: 18,
          bottom: 18,
          width: 56,
          height: 56,
          borderRadius: 999,
          display: 'grid',
          placeItems: 'center',
          boxShadow: '0 18px 40px rgba(0,0,0,0.45)',
        }}
        aria-label="Открыть ассистента"
      >
        AI
      </button>

      {chatOpen && (
        <div
          className="kb-panel"
          style={{
            position: 'fixed',
            right: 18,
            bottom: 86,
            width: 380,
            height: 520,
            borderRadius: 18,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }}
          role="dialog"
          aria-label="Чат ассистента"
        >
          <div
            style={{
              padding: 12,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              borderBottom: '1px solid var(--border)',
              background: 'rgba(0,0,0,0.18)',
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <div style={{ fontSize: 13, fontWeight: 650 }}>ИИ ассистент</div>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>Контекст: {selectedUid}</div>
            </div>
            <button className="kb-btn" onClick={() => setChatOpen(false)}>
              Закрыть
            </button>
          </div>

          <div style={{ flex: 1, padding: 12, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {messages.map((m) => (
              <div
                key={m.id}
                style={{
                  alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '88%',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 4,
                }}
              >
                <div
                  style={{
                    padding: '10px 12px',
                    borderRadius: 14,
                    border: '1px solid var(--border)',
                    background: m.role === 'user' ? 'rgba(124, 92, 255, 0.18)' : 'rgba(255, 255, 255, 0.06)',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    fontSize: 13,
                  }}
                >
                  {m.text}
                </div>
                <div style={{ fontSize: 11, color: 'var(--muted)' }}>{formatTime(m.createdAt)}</div>
              </div>
            ))}
          </div>

          <div style={{ padding: 12, borderTop: '1px solid var(--border)', display: 'flex', gap: 8 }}>
            <select className="kb-input" value={action || ''} onChange={(e) => setAction((e.target.value || undefined) as AssistantAction | undefined)} style={{ maxWidth: 180 }}>
              <option value="">Свободный ответ</option>
              <option value="explain_relation">Объяснить связь</option>
              <option value="viewport">Окрестность узла</option>
              <option value="roadmap">Учебный план</option>
              <option value="analytics">Аналитика</option>
              <option value="questions">Вопросы</option>
            </select>
            <input
              className="kb-input"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="Спроси про узел, связи, роадмап или генерацию"
              onKeyDown={(e) => {
                if (e.key === 'Enter') void sendChat()
              }}
            />
            <button className="kb-btn kb-btn-primary" onClick={() => void sendChat()}>
              Отправить
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
