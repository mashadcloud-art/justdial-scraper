import { StrictMode, startTransition } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from '@tanstack/react-router'
import { getRouter } from './router'
import './styles.css'

const router = getRouter()

startTransition(() => {
  const container = document.getElementById('root')!
  const root = createRoot(container)
  root.render(
    <StrictMode>
      <RouterProvider router={router} />
    </StrictMode>
  )
})
