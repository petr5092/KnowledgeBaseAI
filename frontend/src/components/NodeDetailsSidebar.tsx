import { useEffect, useState } from 'react'
import { getNodeDetails, type NodeDetails } from '../api'

type Props = {
  uid: string | null
  onClose: () => void
  onAskAI: (uid: string) => void
}

export function NodeDetailsSidebar({ uid, onClose, onAskAI }: Props) {
  const [data, setData] = useState<NodeDetails | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!uid) {
      setData(null)
      return
    }

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

  if (!uid) return null

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
        transition: 'transform 0.3s ease',
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

          <button
            className="kb-btn"
            style={{ width: '100%', justifyContent: 'center' }}
            onClick={() => onAskAI(data.uid)}
          >
            ✨ Спросить AI об этом
          </button>

          <div className="kb-panel" style={{ padding: 12, borderRadius: 8 }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: '#2ec4b6' }}>Свойства</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {Object.entries(data)
                .filter(([k]) => !['uid', 'title', 'kind', 'labels', 'incoming', 'outgoing'].includes(k))
                .map(([k, v]) => (
                  <div key={k} style={{ fontSize: 12, display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--muted)' }}>{k}:</span>
                    <span style={{ color: '#fff', maxWidth: '60%', textAlign: 'right', wordBreak: 'break-word' }}>
                      {String(v)}
                    </span>
                  </div>
                ))}
            </div>
          </div>

          {data.incoming.length > 0 && (
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: '#ff9f1c' }}>Входящие связи</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {data.incoming.map((rel, i) => (
                  <div key={i} className="kb-panel" style={{ padding: 8, fontSize: 12, borderRadius: 6 }}>
                    <div style={{ color: 'var(--muted)', marginBottom: 2 }}>{rel.rel}</div>
                    <div style={{ fontWeight: 500 }}>{rel.title || rel.uid}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {data.outgoing.length > 0 && (
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: '#7c5cff' }}>Исходящие связи</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {data.outgoing.map((rel, i) => (
                  <div key={i} className="kb-panel" style={{ padding: 8, fontSize: 12, borderRadius: 6 }}>
                    <div style={{ color: 'var(--muted)', marginBottom: 2 }}>{rel.rel}</div>
                    <div style={{ fontWeight: 500 }}>{rel.title || rel.uid}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
