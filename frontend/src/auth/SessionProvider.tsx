import { createContext, useContext, useEffect } from 'react'
import type { ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, resetCsrf } from '../api/client'
import { sessionQuery } from '../api/queries'
import type { SessionResponse, User } from '../api/types'

interface SessionContextValue {
  user: User | null | undefined; loading: boolean; error: Error | null;
  acceptSession: (session: SessionResponse) => Promise<void>;
  signOut: () => Promise<void>; retry: () => void;
}
const Context = createContext<SessionContextValue | null>(null)
let channel: BroadcastChannel | undefined
function announce() { channel?.postMessage('changed') }

export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const session = useQuery(sessionQuery())
  const clearPrivate = async () => {
    await queryClient.cancelQueries({ queryKey: ['private'] })
    queryClient.removeQueries({ queryKey: ['private'] })
  }
  useEffect(() => {
    const expired = () => {
      void queryClient.cancelQueries({ queryKey: ['private'] }).then(() => queryClient.removeQueries({ queryKey: ['private'] }))
      queryClient.setQueryData(['session'], null)
    }
    window.addEventListener('cinephilia:session-expired', expired)
    channel = typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('cinephilia-session') : undefined
    if (channel) channel.onmessage = () => {
      resetCsrf()
      expired()
      void queryClient.invalidateQueries({ queryKey: ['session'] })
    }
    return () => { window.removeEventListener('cinephilia:session-expired', expired); channel?.close(); channel = undefined }
  }, [queryClient])
  return <Context.Provider value={{
    user: session.data, loading: session.isPending, error: session.error, retry: () => { void session.refetch() },
    acceptSession: async response => { await clearPrivate(); queryClient.setQueryData(['session'], response.user); announce() },
    signOut: async () => {
      try { await api('/api/v1/users/logout/', { method: 'POST' }) }
      finally { await clearPrivate(); resetCsrf(); queryClient.setQueryData(['session'], null); announce() }
    },
  }}>{children}</Context.Provider>
}

export function useSession() {
  const context = useContext(Context)
  if (!context) throw new Error('SessionProvider is required.')
  return context
}
