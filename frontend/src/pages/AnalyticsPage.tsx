import { useEffect, useMemo } from 'react'
import { useSelector, useDispatch } from 'react-redux'
import { type RootState, type AppDispatch } from '../store'
import { fetchStats } from '../store/analyticsSlice'
import { computeLinearScale } from '../widgets/d3'

export default function AnalyticsPage() {
  const dispatch = useDispatch<AppDispatch>()

  const { data: stats, loading, error } = useSelector((state: RootState) => state.analytics)

  useEffect(() => {
    dispatch(fetchStats())
  }, [dispatch])

  // D3 весы для визуализации
  const densityScale = useMemo(() => computeLinearScale([0, 1], [0, 100]), [])
  const outScale = useMemo(() => computeLinearScale([0, 10], [0, 100]), [])

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <div style={{ fontSize: 12, color: 'var(--muted)' }}>Analytics</div>
        <div style={{ fontSize: 16, fontWeight: 650 }}>Статистика графа</div>
      </div>

      {error && (
        <div className="kb-panel" style={{ padding: 12, borderRadius: 14, border: '1px solid rgba(255, 77, 109, 0.35)' }}>
          <div style={{ color: '#ff4d6d', fontSize: 13 }}>{error}</div>
          <button
            onClick={() => dispatch(fetchStats())}
            style={{ marginTop: 8, background: 'none', border: '1px solid var(--border)', color: 'white', cursor: 'pointer', padding: '4px 8px', borderRadius: 6 }}
          >
            Повторить попытку
          </button>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>

        <div className="kb-panel" style={{ padding: 12, borderRadius: 14 }}>
          <div style={{ fontSize: 13, fontWeight: 650, marginBottom: 8 }}>Граф</div>
          <div style={{ display: 'grid', gap: 8 }}>
            <Metric label="Всего узлов" value={stats?.graph.total_nodes ?? (loading ? '...' : 0)} />
            <BarMetric
              label="Средняя исходящая степень"
              value={stats?.graph.avg_out_degree ?? 0}
              scale={outScale}
              unit=""
              loading={loading}
            />
            <BarMetric
              label="Плотность"
              value={stats?.graph.density ?? 0}
              scale={densityScale}
              unit=""
              loading={loading}
            />
          </div>
        </div>

        <div className="kb-panel" style={{ padding: 12, borderRadius: 14 }}>
          <div style={{ fontSize: 13, fontWeight: 650, marginBottom: 8 }}>AI</div>
          <div style={{ display: 'grid', gap: 8 }}>
            <Metric label="Входные токены" value={stats?.ai.tokens_input ?? (loading ? '...' : 0)} />
            <Metric label="Выходные токены" value={stats?.ai.tokens_output ?? (loading ? '...' : 0)} />
            <Metric label="Стоимость (USD)" value={stats?.ai.cost_usd ?? (loading ? '...' : 0)} />
            <Metric label="Задержка (ms)" value={stats?.ai.latency_ms ?? (loading ? '...' : 0)} />
          </div>
        </div>
      </div>

      {loading && !stats && (
        <div style={{ fontSize: 12, color: 'var(--muted)', textAlign: 'center', marginTop: 10 }}>
          Загрузка актуальных данных...
        </div>
      )}
    </div>
  )
}

function Metric(props: { label: string; value: number | string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
      <div style={{ fontSize: 12, color: 'var(--muted)' }}>{props.label}</div>
      <div style={{ fontSize: 14, fontWeight: 650 }}>{props.value}</div>
    </div>
  )
}

function BarMetric(props: { label: string; value: number; scale: (x: number) => number; unit: string; loading?: boolean }) {
  const pct = Math.max(0, Math.min(100, props.scale(props.value)))
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <div style={{ fontSize: 12, color: 'var(--muted)' }}>{props.label}</div>
        <div style={{ fontSize: 12, color: 'var(--muted)' }}>
          {props.loading ? '...' : props.value}
          {props.unit}
        </div>
      </div>
      <div style={{ position: 'relative', height: 8, background: 'rgba(255,255,255,0.15)', borderRadius: 6, overflow: 'hidden' }}>
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: `${pct}%`,
            background: 'rgba(46,233,166,0.8)',
            transition: 'width 0.4s ease-out'
          }}
        />
      </div>
    </div>
  )
}