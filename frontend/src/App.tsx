import { useEffect, useMemo, useCallback } from 'react'
import { Link, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { useSelector, useDispatch } from 'react-redux'
import ExplorePage from './pages/ExplorePage'
import EditPage from './pages/EditPage'
import PracticePage from './pages/PracticePage'
import RoadmapPage from './pages/RoadmapPage'
import SettingsPage from './pages/SettingsPage'
import AnalyticsPage from './pages/AnalyticsPage'
import ThemeToggle from './components/ThemeToggle'
import { APP_CONFIG } from './config/appConfig'
import { UI_CONFIG } from './config/uiConfig'
import { setSelectedUid, toggleChat } from './store/appSlice'
import type { RootState } from './store'
import { AIChat } from './components/AIChat'

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
  const dispatch = useDispatch()
  const title = useActiveRouteTitle()

  const { selectedUid, isChatOpen } = useSelector((state: RootState) => state.app)
  
  const handleSelectUid = useCallback((id: string) => {
    dispatch(setSelectedUid(id))
  }, [dispatch])

  const navItems = useMemo(
    () => [
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
    const routes: Record<string, string> = {
      roadmap: '/roadmap',
      construct: '/edit',
      practice: '/practice',
      settings: '/settings'
    }
    if (routes[hash]) navigate(routes[hash], { replace: true })
  }, [navigate])

  return (
    <div className="kb-bg" style={{ height: '100%', display: 'flex' }}>
      <aside className="kb-panel" style={{ width: 300, margin: 16, padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ fontSize: 14, color: 'var(--muted)' }}>KnowledgeBaseAI</div>
          <div style={{ fontSize: 18, fontWeight: 650, letterSpacing: 0.2 }}>Граф знаний</div>
        </div>

        <div className="kb-panel" style={{ padding: 12, borderRadius: 14 }}>
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>Выбранный узел</div>
          <div style={{ marginTop: 6, display: 'flex', gap: 8, alignItems: 'center' }}>
            <div style={{ width: 10, height: 10, borderRadius: 999, background: 'var(--accent-2)', boxShadow: '0 0 0 4px rgba(46, 233, 166, 0.12)' }} />
            <div style={{ fontWeight: 600 }}>{selectedUid}</div>
          </div>
          <div style={{ marginTop: 10, display: 'flex', gap: 8 }}>
            <button className="kb-btn kb-btn-primary" onClick={() => dispatch(toggleChat())} style={{ flex: 1 }}>
              Спросить
            </button>
            <button 
              className="kb-btn" 
              onClick={() => {
                const nodes = APP_CONFIG.testNodes;
                const currentIndex = nodes.indexOf(selectedUid);
                const nextIndex = (currentIndex + 1) % nodes.length;
                dispatch(setSelectedUid(nodes[nextIndex]));
              }}
            >
              Переключить
            </button>
          </div>
        </div>

        <nav style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {navItems.map((item) => (
            <Link key={item.to} to={item.to} className="kb-btn" style={{ textAlign: 'left' }}>{item.title}</Link>
          ))}
        </nav>
        <div style={{ marginTop: 'auto', fontSize: 12, color: 'var(--muted)' }}>API: /v1 • WS: /ws</div>
      </aside>

      <main style={{ flex: 1, padding: 16, paddingLeft: 0 }}>
        <div className="kb-panel" style={{ height: 'calc(100vh - 32px)', padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>Рабочая область</div>
              <div style={{ fontSize: 18, fontWeight: 650 }}>{title}</div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="kb-btn" onClick={() => dispatch(toggleChat())}>Ассистент</button>
              <button className="kb-btn" onClick={() => navigate('/')}>Домой</button>

              <ThemeToggle />  {/* ← здесь */}
            </div>
          </div>

          <div style={{ flex: 1, minHeight: 0 }}>
            <Routes>
              <Route path="/" element={<ExplorePage selectedUid={selectedUid} onSelectUid={handleSelectUid} />} />
              <Route path="/edit" element={<EditPage selectedUid={selectedUid} onSelectUid={handleSelectUid} />} />
              <Route path="/analytics" element={<AnalyticsPage />} />
              <Route path="/roadmap" element={<RoadmapPage selectedUid={selectedUid} />} />
              <Route path="/practice" element={<PracticePage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Routes>
          </div>
        </div>
      </main>
      <button 
        className="kb-btn kb-btn-primary kb-ai-fab" 
        onClick={() => dispatch(toggleChat())}
        style={{ 
          bottom: UI_CONFIG.fabBottomOffset, 
          right: UI_CONFIG.chatRightOffset,
          width: UI_CONFIG.fabSize,
          height: UI_CONFIG.fabSize
        }}
      >
        AI
      </button>

      <AIChat />
    </div>
  )
}