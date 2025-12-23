import React, { createContext, useContext, useState, useRef, useCallback } from 'react'
import type { ViewportResponse } from '../api'
import { APP_CONFIG } from '../config/appConfig'

// Что мы храним в "облаке"
type GraphState = {
  viewport: ViewportResponse | null
  selectedUid: string
  camera: {
    position: { x: number; y: number }
    scale: number
  } | null
  positions: { x: number; y: number } | null // Добавили позиции узлов
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
    camera: null,
    positions: null,
  })

  const saveGraphState = useCallback((updates: Partial<GraphState>) => {
    console.log('saveGraphState', updates)    
    setState((prev) => ({ ...prev, ...updates }))
  }, [])

  const clearGraphState = useCallback(() => {
    setState({
      viewport: null,
      selectedUid: APP_CONFIG.defaultStartNode,
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
