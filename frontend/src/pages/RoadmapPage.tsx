import { useEffect, useMemo } from 'react'
import { useSelector, useDispatch } from 'react-redux'
import { type RootState, type AppDispatch } from '../store'
import { fetchRoadmap } from '../store/roadmapSlice'
import { computeLinearScale } from '../widgets/d3'

type RoadmapPageProps = {
  selectedUid: string
}

export default function RoadmapPage({ selectedUid }: RoadmapPageProps) {
  const dispatch = useDispatch<AppDispatch>()

  const { items, loading, error } = useSelector((state: RootState) => state.roadmap)

  useEffect(() => {
    dispatch(fetchRoadmap(selectedUid))
  }, [dispatch, selectedUid])

  const scaleDemo = useMemo(() => {
    const s = computeLinearScale([0, 1], [0, 100])
    return [0, 0.25, 0.5, 0.75, 1].map((v) => ({ v, px: s(v) }))
  }, [])

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <div style={{ fontSize: 12, color: 'var(--muted)' }}>Roadmap</div>
        <div style={{ fontSize: 16, fontWeight: 650 }}>План обучения: {selectedUid}</div>
      </div>
      {error && (
        <div className="kb-panel" style={{ padding: 12, borderRadius: 14, borderColor: 'rgba(255, 77, 109, 0.35)', borderStyle: 'solid', borderWidth: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 650, color: '#ff4d6d' }}>Ошибка</div>
          <div style={{ marginTop: 6, fontSize: 12, color: 'var(--muted)' }}>{error}</div>
        </div>
      )}

      <div className="kb-panel" style={{ padding: 12, borderRadius: 14 }}>
        <div style={{ fontSize: 12, color: 'var(--muted)' }}>D3 Scale Visualization</div>
        <div style={{ marginTop: 8, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          {scaleDemo.map((p) => (
            <div key={p.v} className="kb-panel" style={{ padding: '8px 10px', borderRadius: 12, background: 'rgba(255,255,255,0.03)' }}>
              <div style={{ fontSize: 10, color: 'var(--muted)' }}>{p.v}</div>
              <div style={{ fontSize: 13, fontWeight: 650 }}>{p.px.toFixed(0)}px</div>
            </div>
          ))}
        </div>
      </div>

      <div className="kb-panel" style={{ flex: 1, borderRadius: 18, padding: 14, overflow: 'auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div style={{ fontSize: 14, fontWeight: 650 }}>Шаги обучения</div>
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>
            {loading ? 'Обновление...' : `Всего этапов: ${items.length}`}
          </div>
        </div>

        {loading && items.length === 0 ? (
          <div style={{ padding: 20, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
            Генерация дорожной карты...
          </div>
        ) : items.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {items.map((item: any, idx) => (
              <div key={item.uid || idx} className="kb-panel" style={{ padding: 12, background: 'rgba(255,255,255,0.05)', borderRadius: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{item.title || item.uid}</div>
                  <div style={{ fontSize: 10, color: 'rgba(46, 233, 166, 0.8)', textTransform: 'uppercase', fontWeight: 700 }}>
                    {item.kind || 'step'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          !loading && <div style={{ color: 'var(--muted)', fontSize: 13 }}>План пока не построен</div>
        )}
      </div>
    </div>
  )
}