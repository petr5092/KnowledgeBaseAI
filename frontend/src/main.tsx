import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { GraphProvider } from './context/GraphContext'

import { store } from './store'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Provider store={store}>
      <BrowserRouter>
        <GraphProvider>
          <App />
        </GraphProvider>
      </BrowserRouter>
    </Provider>
  </StrictMode>,
)

// Expose store for debugging/simple access in components needing latest state
;(window as any).__STORE__ = store
