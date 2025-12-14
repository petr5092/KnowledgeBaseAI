import { useEffect, useMemo, useRef, useState } from 'react'
import { DataSet } from 'vis-data'
import { Network, type Edge as VisNetworkEdge, type Node as VisNetworkNode } from 'vis-network'
import type { ViewportResponse } from '../api'
import { getViewport } from '../api'

type ExplorePageProps = {
  selectedUid: string
  onSelectUid: (uid: string) => void
}

type VisNode = VisNetworkNode

type VisEdge = VisNetworkEdge

function toVisData(viewport: ViewportResponse) {
  const nodes = viewport.nodes.map((n): VisNode => ({
    id: n.uid,
    label: n.title ? `${n.title}\n${n.uid}` : n.uid,
    group: n.kind,
  }))

  const edges = viewport.edges.map((e, idx): VisEdge => ({
    id: `${e.source}->${e.target}:${idx}`,
    from: e.source,
    to: e.target,
    label: e.kind,
    value: e.weight,
  }))

  return { nodes, edges }
}

export default function ExplorePage(props: ExplorePageProps) {
  const { selectedUid, onSelectUid } = props

  const containerRef = useRef<HTMLDivElement | null>(null)
  const networkRef = useRef<Network | null>(null)

  const [depth, setDepth] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [viewport, setViewport] = useState<ViewportResponse | null>(null)

  const visData = useMemo(() => {
    if (!viewport) return null
    return toVisData(viewport)
  }, [viewport])

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await getViewport({ center_uid: props.selectedUid, depth })
        if (cancelled) return
        setViewport(data)
      } catch (e) {
        if (cancelled) return
        setError(e instanceof Error ? e.message : 'Ошибка загрузки viewport')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void load()

    return () => {
      cancelled = true
    }
  }, [props.selectedUid, depth])

  useEffect(() => {
    const el = containerRef.current
    if (!el || !visData) return

    const nodes = new DataSet(visData.nodes)
    const edges = new DataSet(visData.edges)

    const network = new Network(
      el,
      { nodes, edges },
      {
        autoResize: true,
        interaction: {
          hover: true,
          multiselect: false,
          navigationButtons: false,
        },
        physics: {
          enabled: true,
          solver: 'forceAtlas2Based',
          forceAtlas2Based: {
            gravitationalConstant: -50,
            centralGravity: 0.01,
            springLength: 120,
            springConstant: 0.08,
          },
          stabilization: { iterations: 250 },
        },
        nodes: {
          shape: 'dot',
          size: 14,
          font: { color: '#ffffff', size: 12, face: 'ui-sans-serif' },
          borderWidth: 1,
          color: {
            border: 'rgba(255,255,255,0.25)',
            background: 'rgba(124, 92, 255, 0.35)',
            highlight: { border: 'rgba(255,255,255,0.6)', background: 'rgba(124, 92, 255, 0.55)' },
          },
        },
        edges: {
          arrows: { to: { enabled: true, scaleFactor: 0.6 } },
          color: { color: 'rgba(255,255,255,0.25)', highlight: 'rgba(46, 233, 166, 0.8)' },
          font: { color: 'rgba(255,255,255,0.7)', size: 10, align: 'middle' },
          smooth: { enabled: true, type: 'dynamic', roundness: 0.35 },
        },
      },
    )

    network.on('selectNode', (params) => {
      const id = params.nodes?.[0]
      if (typeof id === 'string') onSelectUid(id)
    })

    networkRef.current = network

    return () => {
      network.destroy()
      networkRef.current = null
    }
  }, [visData, onSelectUid])

  useEffect(() => {
    const network = networkRef.current
    if (!network) return
    network.selectNodes([selectedUid])
    network.focus(selectedUid, { scale: 1.1, animation: { duration: 350, easingFunction: 'easeInOutQuad' } })
  }, [selectedUid])

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>Explore (vis-network)</div>
          <div style={{ fontSize: 16, fontWeight: 650 }}>Большой граф + физика</div>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>Depth</div>
          <select
            className="kb-input"
            value={depth}
            onChange={(e) => setDepth(Number(e.target.value))}
            style={{ width: 120 }}
          >
            {[1, 2, 3].map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="kb-panel" style={{ padding: 12, borderRadius: 14, borderColor: 'rgba(255, 77, 109, 0.35)' }}>
          <div style={{ fontSize: 13, fontWeight: 650 }}>Ошибка</div>
          <div style={{ marginTop: 6, fontSize: 12, color: 'var(--muted)', whiteSpace: 'pre-wrap' }}>{error}</div>
        </div>
      )}

      <div className="kb-panel" style={{ flex: 1, borderRadius: 18, position: 'relative', overflow: 'hidden' }}>
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background:
              'radial-gradient(800px 500px at 50% 40%, rgba(124, 92, 255, 0.18), transparent 60%), linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0))',
          }}
        />

        <div ref={containerRef} style={{ position: 'absolute', inset: 0 }} />

        {loading && (
          <div
            className="kb-panel"
            style={{
              position: 'absolute',
              left: 14,
              bottom: 14,
              padding: '10px 12px',
              borderRadius: 14,
              background: 'rgba(0,0,0,0.35)',
            }}
          >
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>Загрузка…</div>
          </div>
        )}

        {viewport && (
          <div
            className="kb-panel"
            style={{
              position: 'absolute',
              right: 14,
              bottom: 14,
              padding: '10px 12px',
              borderRadius: 14,
              background: 'rgba(0,0,0,0.35)',
            }}
          >
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>Nodes: {viewport.nodes.length}</div>
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>Edges: {viewport.edges.length}</div>
          </div>
        )}
      </div>
    </div>
  )
}
