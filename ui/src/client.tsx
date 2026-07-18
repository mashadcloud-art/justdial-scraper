import { StrictMode, startTransition } from 'react'
import { createRoot } from 'react-dom/client'
import { StartClient } from '@tanstack/react-start/client'
import { getRouter } from './router'
import './styles.css'

const router = getRouter()

startTransition(() => {
  const container = document.getElementById('root')!
  const root = createRoot(container)
  root.render(
    <StrictMode>
      <StartClient router={router} />
    </StrictMode>
  )
})
