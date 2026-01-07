import React, { createContext, useCallback, useContext, useState } from 'react'
import type { ViewportResponse } from '../api'
import { APP_CONFIG } from '../config/appConfig'

// Что мы храним в "облаке"
type GraphState = {
  viewport: ViewportResponse | null
  selectedUid: string
  depth: number // Сохраняем глубину запроса
  camera: {
    position: { x: number; y: number }
    scale: number
  } | null
  positions: Record<string, { x: number; y: number }> | null // Позиции узлов по id
}

type GraphContextType = {
  graphState: GraphState
  saveGraphState: (state: Partial<GraphState>) => void
  clearGraphState: () => void
}

const GraphContext = createContext<GraphContextType | null>(null)

export function GraphProvider({ children }: { children: React.ReactNode }) {
  // Начальное состояние
  const [state, setState] = useState<GraphState>({
    viewport: null,
    selectedUid: APP_CONFIG.defaultStartNode,
    depth: APP_CONFIG.defaultDepth,
    camera: null,
    positions: null,
  })

  const saveGraphState = useCallback((updates: Partial<GraphState>) => {
    setState((prev) => ({ ...prev, ...updates }))
  }, [])

  const clearGraphState = useCallback(() => {
    setState({
      viewport: null,
      selectedUid: APP_CONFIG.defaultStartNode,
      depth: APP_CONFIG.defaultDepth,
      camera: null,
      positions: null,
    })
  }, [])

  return (
    <GraphContext.Provider value={{ graphState: state, saveGraphState, clearGraphState }}>
      {children}
    </GraphContext.Provider>
  )
}

export function useGraphContext() {
  const ctx = useContext(GraphContext)
  if (!ctx) throw new Error('useGraphContext must be used within GraphProvider')
  return ctx
}
