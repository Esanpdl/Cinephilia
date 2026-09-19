import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import '@fontsource-variable/oswald'
import '@fontsource-variable/dm-sans'
import './styles.css'
import App from './App'
import { SessionProvider } from './auth/SessionProvider'
import { ApiError } from './api/client'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: (count, error) => count < 1 && !(error instanceof ApiError && error.status < 500), refetchOnWindowFocus: false, gcTime: 10 * 60_000 },
    mutations: { retry: false },
  },
})
createRoot(document.getElementById('root')!).render(
  <StrictMode><QueryClientProvider client={queryClient}><SessionProvider><App /></SessionProvider></QueryClientProvider></StrictMode>,
)
