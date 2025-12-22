import { useEffect, useState } from 'react'
import { getNodeDetails, type NodeDetails } from '../api'

type Props = {
  uid: string | null
  onClose: () => void
  onAskAI: (uid: string) => void
}

// --- Sub-components ---

type SidebarActionProps = {
  label: string
  icon?: string
  primary?: boolean
  onClick: () => void
}

function SidebarAction({ label, icon, primary, onClick }: SidebarActionProps) {
  return (
    <button
      className={`kb-btn ${primary ? 'kb-btn-primary' : ''}`}
      style={{ flex: 1, justifyContent: 'center' }}
      onClick={onClick}
    >
      {icon && <span style={{ marginRight: 6 }}>{icon}</span>}
      {label}
    </button>
  )
}

function RelationsList({ title, color, items }: { title: string; color: string; items: Array<{ rel: string; title?: string; uid: string }> }) {
  if (items.length === 0) return null
  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color }}>{title}</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {items.map((rel, i) => (
          <div key={i} className="kb-panel" style={{ padding: 8, fontSize: 12, borderRadius: 6 }}>
            <div style={{ color: 'var(--muted)', marginBottom: 2 }}>{rel.rel}</div>
            <div style={{ fontWeight: 500 }}>{rel.title || rel.uid}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function PropertiesList({ data }: { data: NodeDetails }) {
  const props = Object.entries(data).filter(
    ([k]) => !['uid', 'title', 'kind', 'labels', 'incoming', 'outgoing'].includes(k),
  )

  if (props.length === 0) return null

  return (
    <div className="kb-panel" style={{ padding: 12, borderRadius: 8 }}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: '#2ec4b6' }}>Свойства</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {props.map(([k, v]) => (
          <div key={k} style={{ fontSize: 12, display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--muted)' }}>{k}:</span>
            <span
              style={{ color: '#fff', maxWidth: '60%', textAlign: 'right', wordBreak: 'break-word' }}
            >
              {String(v)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// --- Main Component ---

export function NodeDetailsSidebar({ uid, onClose, onAskAI }: Props) {
  const [data, setData] = useState<NodeDetails | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!uid) return

    let cancelled = false
    setLoading(true)
    setError(null)

    getNodeDetails(uid)
      .then((res) => {
        if (!cancelled) setData(res)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [uid])

  // Анимация: панель всегда рендерится, но уезжает за экран
  const isVisible = !!uid

  return (
    <div
      style={{
        position: 'absolute',
        top: 0,
        right: 0,
        bottom: 0,
        width: 350,
        background: 'rgba(20, 20, 30, 0.95)',
        backdropFilter: 'blur(10px)',
        borderLeft: '1px solid rgba(255, 255, 255, 0.1)',
        padding: 20,
        overflowY: 'auto',
        zIndex: 10,
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
        boxShadow: '-4px 0 20px rgba(0,0,0,0.5)',
        transform: isVisible ? 'translateX(0)' : 'translateX(100%)', // Анимация выезда
        transition: 'transform 0.3s cubic-bezier(0.16, 1, 0.3, 1)', // Плавная кривая (easeOut)
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontSize: 12, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1 }}>
          {loading ? 'Loading...' : data?.kind || 'Node Details'}
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--muted)',
            cursor: 'pointer',
            fontSize: 20,
          }}
        >
          &times;
        </button>
      </div>

      {loading && <div style={{ color: '#fff' }}>Загрузка данных...</div>}

      {error && <div style={{ color: '#ff4d6d' }}>Ошибка: {error}</div>}

      {data && !loading && (
        <>
          <div>
            <div style={{ fontSize: 24, fontWeight: 700, color: '#fff', marginBottom: 4 }}>
              {data.title || data.uid}
            </div>
            <div style={{ fontSize: 12, color: 'var(--muted)', fontFamily: 'monospace' }}>{data.uid}</div>
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <SidebarAction
              label="Спросить AI"
              icon="✨"
              onClick={() => onAskAI(data.uid)}
            />
            <SidebarAction
              label="Начать учить"
              icon="🚀"
              primary
              onClick={() => alert(`Start learning ${data.title || data.uid}`)}
            />
          </div>

          <PropertiesList data={data} />

          <RelationsList title="Входящие связи" color="#ff9f1c" items={data.incoming} />
          <RelationsList title="Исходящие связи" color="#7c5cff" items={data.outgoing} />
        </>
      )}
    </div>
  )
}
