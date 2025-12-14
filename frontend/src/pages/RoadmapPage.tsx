import { useEffect, useMemo, useState } from 'react'
import { postRoadmap } from '../api'
import { computeLinearScale } from '../widgets/d3'

type RoadmapPageProps = {
  selectedUid: string
}

export default function RoadmapPage(props: RoadmapPageProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [items, setItems] = useState<unknown[]>([])

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const res = await postRoadmap({ subject_uid: null, progress: {}, limit: 30 })
        if (cancelled) return
        setItems(res.items)
      } catch (e) {
        if (cancelled) return
        setError(e instanceof Error ? e.message : 'Ошибка загрузки roadmap')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void load()

    return () => {
      cancelled = true
    }
  }, [props.selectedUid])

  const scaleDemo = useMemo(() => {
    const s = computeLinearScale([0, 1], [0, 100])
    return [0, 0.25, 0.5, 0.75, 1].map((v) => ({ v, px: s(v) }))
  }, [])

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <div style={{ fontSize: 12, color: 'var(--muted)' }}>Roadmap</div>
        <div style={{ fontSize: 16, fontWeight: 650 }}>План обучения</div>
      </div>

      {error && (
        <div className="kb-panel" style={{ padding: 12, borderRadius: 14, borderColor: 'rgba(255, 77, 109, 0.35)' }}>
          <div style={{ fontSize: 13, fontWeight: 650 }}>Ошибка</div>
          <div style={{ marginTop: 6, fontSize: 12, color: 'var(--muted)', whiteSpace: 'pre-wrap' }}>{error}</div>
        </div>
      )}

      <div className="kb-panel" style={{ padding: 12, borderRadius: 14 }}>
        <div style={{ fontSize: 12, color: 'var(--muted)' }}>D3 (точечно): scale demo</div>
        <div style={{ marginTop: 8, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          {scaleDemo.map((p) => (
            <div key={p.v} className="kb-panel" style={{ padding: '8px 10px', borderRadius: 12 }}>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>{p.v}</div>
              <div style={{ fontSize: 13, fontWeight: 650 }}>{p.px.toFixed(0)}px</div>
            </div>
          ))}
        </div>
      </div>

      <div className="kb-panel" style={{ flex: 1, borderRadius: 18, padding: 14, overflow: 'auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ fontSize: 14, fontWeight: 650 }}>Items</div>
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>{loading ? 'Загрузка…' : `Всего: ${items.length}`}</div>
        </div>

        <pre style={{ marginTop: 12, fontSize: 12, color: 'var(--muted)', whiteSpace: 'pre-wrap' }}>
          {items.length ? JSON.stringify(items.slice(0, 5), null, 2) : 'Пока пусто'}
        </pre>
      </div>
    </div>
  )
}
