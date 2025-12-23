import { createSlice, type PayloadAction } from '@reduxjs/toolkit'
import { type Node, type Edge, type Connection, addEdge, applyNodeChanges, applyEdgeChanges, type NodeChange, type EdgeChange } from 'reactflow'

interface EditState {
  nodes: Node[]
  edges: Edge[]
}

const initialState: EditState = {
  nodes: [],
  edges: [],
}

const editSlice = createSlice({
  name: 'edit',
  initialState,
  reducers: {
    setGraph: (state, action: PayloadAction<{ nodes: Node[]; edges: Edge[] }>) => {
      state.nodes = action.payload.nodes
      state.edges = action.payload.edges
    },
    onNodesChange: (state, action: PayloadAction<NodeChange[]>) => {
      state.nodes = applyNodeChanges(action.payload, state.nodes)
    },
    onEdgesChange: (state, action: PayloadAction<EdgeChange[]>) => {
      state.edges = applyEdgeChanges(action.payload, state.edges)
    },
    onConnect: (state, action: PayloadAction<Connection>) => {
      state.edges = addEdge({ ...action.payload, animated: true, label: 'linked' }, state.edges)
    },
    addNode: (state, action: PayloadAction<Node>) => {
      state.nodes.push(action.payload)
    },
    updateNodeLabel: (state, action: PayloadAction<{ id: string; label: string }>) => {
      const node = state.nodes.find(n => n.id === action.payload.id)
      if (node) node.data = { ...node.data, label: action.payload.label }
    },
    updateEdgeLabel: (state, action: PayloadAction<{ id: string; label: string }>) => {
      const edge = state.edges.find(e => e.id === action.payload.id)
      if (edge) edge.label = action.payload.label
    },
    deleteNode: (state, action: PayloadAction<string>) => {
      state.nodes = state.nodes.filter(n => n.id !== action.payload)
      state.edges = state.edges.filter(e => e.source !== action.payload && e.target !== action.payload)
    },
    deleteEdge: (state, action: PayloadAction<string>) => {
      state.edges = state.edges.filter(e => e.id !== action.payload)
    }
  },
})

export const {
  setGraph, onNodesChange, onEdgesChange, onConnect,
  addNode, updateNodeLabel, updateEdgeLabel, deleteNode, deleteEdge
} = editSlice.actions
export default editSlice.reducer