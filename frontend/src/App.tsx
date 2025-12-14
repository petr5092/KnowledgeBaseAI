import { useEffect, useMemo, useState } from 'react'

type RouteKey = 'map' | 'roadmap' | 'construct' | 'practice' | 'settings'

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  text: string
  createdAt: number
}

function getInitialRoute(): RouteKey {
  const hash = window.location.hash.replace('#', '')
  if (hash === 'roadmap') return 'roadmap'
  if (hash === 'construct') return 'construct'
  if (hash === 'practice') return 'practice'
  if (hash === 'settings') return 'settings'
  return 'map'
}

function setRoute(route: RouteKey) {
  window.location.hash = route === 'map' ? '' : route
}

function uid() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function formatTime(ts: number) {
  const d = new Date(ts)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function App() {
  const [route, setRouteState] = useState<RouteKey>(() => getInitialRoute())
  const [selectedUid, setSelectedUid] = useState<string>('TOP-DEMO')
  const [chatOpen, setChatOpen] = useState(false)
  const [chatInput, setChatInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    {
      id: uid(),
      role: 'assistant',
      text: 'Привет! Я ассистент KnowledgeBase. Выбери узел на карте и спроси меня про связи, роадмап или генерацию контента.',
      createdAt: Date.now(),
    },
  ])

  useEffect(() => {
    const onHashChange = () => setRouteState(getInitialRoute())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const navItems = useMemo(
    () =>
      [
        { key: 'map' as const, title: 'Карта знаний' },
        { key: 'roadmap' as const, title: 'Дорожная карта' },
        { key: 'construct' as const, title: 'Конструктор' },
        { key: 'practice' as const, title: 'Практика' },
        { key: 'settings' as const, title: 'Настройки' },
      ] as const,
    [],
  )

  async function sendChat() {
    const text = chatInput.trim()
    if (!text) return

    const userMsg: ChatMessage = { id: uid(), role: 'user', text, createdAt: Date.now() }
    setMessages((prev) => [...prev, userMsg])
    setChatInput('')

    try {
      const res = await fetch('/v1/graph/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text, from_uid: selectedUid, to_uid: selectedUid }),
      })

      if (!res.ok) {
        const errText = await res.text()
        throw new Error(errText || `HTTP ${res.status}`)
      }

      const data = (await res.json()) as unknown
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
          text: 'Не удалось связаться с API. Проверь, что backend доступен и что Traefik/Vite проксирует /api и /ws.',
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
          width: 280,
          margin: 16,
          padding: 14,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ fontSize: 14, color: 'var(--muted)' }}>KnowledgeBaseAI</div>
          <div style={{ fontSize: 18, fontWeight: 650, letterSpacing: 0.2 }}>Конструктор знаний</div>
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
            <button
              className="kb-btn"
              onClick={() => setSelectedUid((prev) => (prev === 'TOP-DEMO' ? 'SKL-DEMO' : 'TOP-DEMO'))}
            >
              Переключить
            </button>
          </div>
        </div>

        <nav style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {navItems.map((item) => {
            const active = route === item.key
            return (
              <button
                key={item.key}
                className="kb-btn"
                onClick={() => setRoute(item.key)}
                style={{
                  textAlign: 'left',
                  background: active ? 'rgba(124, 92, 255, 0.18)' : undefined,
                  borderColor: active ? 'rgba(124, 92, 255, 0.5)' : undefined,
                }}
              >
                {item.title}
              </button>
            )
          })}
        </nav>

        <div style={{ marginTop: 'auto', fontSize: 12, color: 'var(--muted)' }}>
          API: /api u007f WS: /ws
        </div>
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
              <div style={{ fontSize: 18, fontWeight: 650 }}>
                {route === 'map' && 'Карта знаний'}
                {route === 'roadmap' && 'Дорожная карта'}
                {route === 'construct' && 'Конструктор'}
                {route === 'practice' && 'Практика'}
                {route === 'settings' && 'Настройки'}
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8 }}>
              <button className="kb-btn" onClick={() => setChatOpen(true)}>
                Ассистент
              </button>
              <button className="kb-btn" onClick={() => setRoute('map')}>
                Домой
              </button>
            </div>
          </div>

          {route === 'map' && (
            <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 360px', gap: 12 }}>
              <div
                className="kb-panel"
                style={{
                  borderRadius: 18,
                  position: 'relative',
                  overflow: 'hidden',
                  minHeight: 520,
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    inset: 0,
                    background:
                      'radial-gradient(800px 500px at 50% 40%, rgba(124, 92, 255, 0.18), transparent 60%), linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0))',
                  }}
                />

                <div
                  style={{
                    position: 'absolute',
                    left: 18,
                    top: 18,
                    display: 'flex',
                    gap: 8,
                    alignItems: 'center',
                  }}
                >
                  <button className="kb-btn">Pan</button>
                  <button className="kb-btn">Zoom</button>
                  <button className="kb-btn">Легенда</button>
                </div>

                <div
                  style={{
                    position: 'absolute',
                    right: 18,
                    bottom: 18,
                    width: 180,
                    height: 120,
                    borderRadius: 14,
                    border: '1px solid var(--border)',
                    background: 'rgba(0,0,0,0.25)',
                    backdropFilter: 'blur(10px)',
                  }}
                />

                <div
                  style={{
                    position: 'absolute',
                    left: '50%',
                    top: '50%',
                    transform: 'translate(-50%, -50%)',
                    display: 'grid',
                    gridTemplateColumns: 'repeat(3, 1fr)',
                    gap: 14,
                    padding: 18,
                  }}
                >
                  {[
                    { uid: 'TOP-DEMO', title: 'Тема', state: 'available' },
                    { uid: 'SKL-DEMO', title: 'Навык', state: 'progress' },
                    { uid: 'MTH-DEMO', title: 'Метод', state: 'locked' },
                  ].map((n) => {
                    const active = selectedUid === n.uid
                    const borderColor =
                      n.state === 'locked'
                        ? 'rgba(255,255,255,0.12)'
                        : n.state === 'progress'
                          ? 'rgba(46, 233, 166, 0.45)'
                          : 'rgba(124, 92, 255, 0.55)'

                    const bg =
                      n.state === 'locked'
                        ? 'rgba(255,255,255,0.04)'
                        : n.state === 'progress'
                          ? 'rgba(46, 233, 166, 0.10)'
                          : 'rgba(124, 92, 255, 0.12)'

                    return (
                      <button
                        key={n.uid}
                        className="kb-panel"
                        onClick={() => setSelectedUid(n.uid)}
                        style={{
                          width: 180,
                          height: 110,
                          borderRadius: 18,
                          borderColor: active ? 'rgba(255,255,255,0.22)' : borderColor,
                          background: bg,
                          cursor: 'pointer',
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'flex-start',
                          justifyContent: 'space-between',
                          padding: 12,
                          textAlign: 'left',
                        }}
                      >
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                          <div style={{ fontSize: 12, color: 'var(--muted)' }}>{n.title}</div>
                          <div style={{ fontSize: 14, fontWeight: 650 }}>{n.uid}</div>
                        </div>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                          <div
                            style={{
                              width: 10,
                              height: 10,
                              borderRadius: 999,
                              background:
                                n.state === 'locked'
                                  ? 'rgba(255,255,255,0.25)'
                                  : n.state === 'progress'
                                    ? 'var(--accent-2)'
                                    : 'var(--accent)',
                            }}
                          />
                          <div style={{ fontSize: 12, color: 'var(--muted)' }}>{n.state}</div>
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>

              <div className="kb-panel" style={{ borderRadius: 18, padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div style={{ fontSize: 14, fontWeight: 650 }}>Свойства узла</div>
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                  Здесь будет no-code панель: тип, название, описание, связи, кнопки генерации.
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div style={{ fontSize: 12, color: 'var(--muted)' }}>Название</div>
                  <input className="kb-input" value={selectedUid} readOnly />
                </div>

                <div style={{ display: 'flex', gap: 8 }}>
                  <button className="kb-btn kb-btn-primary" onClick={() => setRoute('roadmap')} style={{ flex: 1 }}>
                    Построить роадмап
                  </button>
                  <button className="kb-btn" onClick={() => setRoute('construct')}>
                    Magic Fill
                  </button>
                </div>

                <div style={{ marginTop: 'auto', display: 'flex', gap: 8 }}>
                  <button className="kb-btn" onClick={() => setChatOpen(true)} style={{ flex: 1 }}>
                    Обсудить с ассистентом
                  </button>
                </div>
              </div>
            </div>
          )}

          {route !== 'map' && (
            <div style={{ flex: 1, display: 'grid', placeItems: 'center' }}>
              <div className="kb-panel" style={{ padding: 18, borderRadius: 18, width: 'min(720px, 100%)' }}>
                <div style={{ fontSize: 14, fontWeight: 650 }}>Экран в разработке</div>
                <div style={{ marginTop: 8, fontSize: 13, color: 'var(--muted)' }}>
                  Следующим шагом подключу реальные данные из backend API и добавлю полноценный редактор карты.
                </div>
              </div>
            </div>
          )}
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
                    background:
                      m.role === 'user' ? 'rgba(124, 92, 255, 0.18)' : 'rgba(255, 255, 255, 0.06)',
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

export default App