import { useMemo, useState, useEffect } from 'react'
import { useSelector, useDispatch } from 'react-redux'
import ReactFlow, { Background, Controls, MiniMap, type Node, type Connection } from 'reactflow'
import 'reactflow/dist/style.css'

import { type RootState, type AppDispatch } from '../store'
import * as actions from '../store/editSlice'

type EditPageProps = {
  selectedUid: string
  onSelectUid: (uid: string) => void
}

export default function EditPage(props: EditPageProps) {
  const dispatch = useDispatch<AppDispatch>()

  const { nodes, edges } = useSelector((state: RootState) => state.edit)

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(props.selectedUid || null)
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null)
  const [canSave, setCanSave] = useState(false);
  const selectedNode = useMemo(() => nodes.find((n) => n.id === selectedNodeId) || null, [nodes, selectedNodeId])
  const selectedEdge = useMemo(() => edges.find((e) => e.id === selectedEdgeId) || null, [edges, selectedEdgeId])

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
              setCanSave(true)
            }}
          >
            Добавить узел
          </button>
          <button className="kb-btn kb-btn-primary" onClick={() => {void 0;setCanSave(false)}} disabled={!canSave}>
            Сохранить
          </button>
        </div>
      </div>

      <div className="kb-panel" style={{ flex: 1, borderRadius: 18, overflow: 'hidden' }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={(changes) => dispatch(actions.onNodesChange(changes))}
          onEdgesChange={(changes) => dispatch(actions.onEdgesChange(changes))}
          onConnect={(c: Connection) => dispatch(actions.onConnect(c))}
          onSelectionChange={(sel) => {
            const n = sel.nodes?.[0]
            const e = sel.edges?.[0]
            setSelectedNodeId(n ? n.id : null)
            setSelectedEdgeId(e ? e.id : null)
            if (n) props.onSelectUid(n.id)
          }}
          fitView
        >
          <Background gap={18} color="rgba(255,255,255,0.08)" />
          <MiniMap pannable zoomable />
          <Controls />
        </ReactFlow>
      </div>

      <div className="kb-panel" style={{ padding: 12, borderRadius: 14, display: 'grid', gap: 10 }}>
        <div style={{ fontSize: 12, color: 'var(--muted)' }}>Свойства</div>

        {selectedNode && (
          <div style={{ display: 'grid', gap: 8 }}>
            <div style={{ fontSize: 13, fontWeight: 650 }}>Узел</div>
            <div style={{ display: 'grid', gap: 6 }}>
              <label style={{ display: 'grid', gap: 6 }}>
                <span style={{ fontSize: 12, color: 'var(--muted)' }}>ID</span>
                <input className="kb-input" value={selectedNode.id} readOnly />
              </label>
              <label style={{ display: 'grid', gap: 6 }}>
                <span style={{ fontSize: 12, color: 'var(--muted)' }}>Label</span>
                <input
                  className="kb-input"
                  value={String((selectedNode.data as any)?.label || '')}
                  onChange={(e) => dispatch(actions.updateNodeLabel({ id: selectedNode.id, label: e.target.value }))}
                />
              </label>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  className="kb-btn"
                  onClick={() => {
                    dispatch(actions.deleteNode(selectedNode.id))
                    setSelectedNodeId(null)
                  }}
                >
                  Удалить узел
                </button>
              </div>
            </div>
          </div>
        )}

        {selectedEdge && (
          <div style={{ display: 'grid', gap: 8 }}>
            <div style={{ fontSize: 13, fontWeight: 650 }}>Ребро</div>
            <div style={{ display: 'grid', gap: 6 }}>
              <label style={{ display: 'grid', gap: 6 }}>
                <span style={{ fontSize: 12, color: 'var(--muted)' }}>ID</span>
                <input className="kb-input" value={selectedEdge.id} readOnly />
              </label>
              <label style={{ display: 'grid', gap: 6 }}>
                <span style={{ fontSize: 12, color: 'var(--muted)' }}>Тип</span>
                <input
                  className="kb-input"
                  value={String((selectedEdge.label as any) || '')}
                  onChange={(e) => dispatch(actions.updateEdgeLabel({ id: selectedEdge.id, label: e.target.value }))}
                />
              </label>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  className="kb-btn"
                  onClick={() => {
                    dispatch(actions.deleteEdge(selectedEdge.id))
                    setSelectedEdgeId(null)
                  }}
                >
                  Удалить ребро
                </button>
              </div>
            </div>
          </div>
        )}

        {!selectedNode && !selectedEdge && <div style={{ fontSize: 12, color: 'var(--muted)' }}>Выберите узел или ребро</div>}

        <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
          <button
            className="kb-btn"
            onClick={() => {
              const payload = { nodes, edges }
              try {
                localStorage.setItem('kb_edit_draft', JSON.stringify(payload))
              } catch { }
            }}
          >
            Сохранить черновик
          </button>
          <button
            className="kb-btn"
            onClick={() => {
              try {
                const raw = localStorage.getItem('kb_edit_draft')
                if (!raw) return
                const data = JSON.parse(raw)
                dispatch(actions.setGraph(data))
              } catch { }
            }}
          >
            Загрузить черновик
          </button>
          <button
            className="kb-btn"
            onClick={() => {
              try {
                localStorage.removeItem('kb_edit_draft')
              } catch { }
            }}
          >
            Очистить черновик
          </button>
        </div>
      </div>
    </div>
  )
}