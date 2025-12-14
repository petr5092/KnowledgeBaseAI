import { useMemo, useState } from 'react'
import ReactFlow, { Background, Controls, MiniMap, type Edge, type Node } from 'reactflow'
import 'reactflow/dist/style.css'

type EditPageProps = {
  selectedUid: string
  onSelectUid: (uid: string) => void
}

function makeInitialGraph(selectedUid: string) {
  const nodes: Node[] = [
    {
      id: selectedUid,
      position: { x: 0, y: 0 },
      data: { label: selectedUid },
      type: 'default',
    },
    {
      id: 'SKL-DEMO',
      position: { x: 240, y: 120 },
      data: { label: 'SKL-DEMO' },
      type: 'default',
    },
  ]

  const edges: Edge[] = [
    {
      id: `${selectedUid}->SKL-DEMO`,
      source: selectedUid,
      target: 'SKL-DEMO',
      label: 'USES_SKILL',
      animated: true,
      style: { stroke: 'rgba(46, 233, 166, 0.8)' },
    },
  ]

  return { nodes, edges }
}

export default function EditPage(props: EditPageProps) {
  const initial = useMemo(() => makeInitialGraph(props.selectedUid), [props.selectedUid])
  const [nodes, setNodes] = useState<Node[]>(initial.nodes)
  const [edges] = useState<Edge[]>(initial.edges)

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>Edit (React Flow)</div>
          <div style={{ fontSize: 16, fontWeight: 650 }}>Аккуратный UX редактирования</div>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className="kb-btn"
            onClick={() => {
              const id = `NEW-${Date.now().toString(16)}`
              setNodes((prev) => [
                ...prev,
                {
                  id,
                  position: { x: 120 + prev.length * 30, y: 120 + prev.length * 20 },
                  data: { label: id },
                },
              ])
            }}
          >
            Добавить узел
          </button>
          <button className="kb-btn kb-btn-primary" onClick={() => void 0}>
            Сохранить
          </button>
        </div>
      </div>

      <div className="kb-panel" style={{ flex: 1, borderRadius: 18, overflow: 'hidden' }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={(changes) => {
            setNodes((nds) => {
              let next = nds
              for (const c of changes) {
                if (c.type === 'position' && c.id) {
                  next = next.map((n) => (n.id === c.id ? { ...n, position: c.position ?? n.position } : n))
                }
                if (c.type === 'select' && c.id && c.selected) props.onSelectUid(c.id)
              }
              return next
            })
          }}
          onEdgesChange={() => void 0}
          fitView
        >
          <Background gap={18} color="rgba(255,255,255,0.08)" />
          <MiniMap pannable zoomable />
          <Controls />
        </ReactFlow>
      </div>

      <div className="kb-panel" style={{ padding: 12, borderRadius: 14 }}>
        <div style={{ fontSize: 12, color: 'var(--muted)' }}>Выбранный UID</div>
        <div style={{ marginTop: 6, fontSize: 14, fontWeight: 650 }}>{props.selectedUid}</div>
      </div>
    </div>
  )
}
