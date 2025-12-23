import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { GraphProvider } from './context/GraphContext'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <GraphProvider>
        <App />
      </GraphProvider>
    </BrowserRouter>
  </StrictMode>,
)
