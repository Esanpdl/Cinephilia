import { Navigate, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useSession } from '../auth/SessionProvider'
import { PageError } from './ui'

export function ProtectedPage({ children }: { children: ReactNode }) {
  const session = useSession()
  const location = useLocation()
  if (session.loading) return <div className="state-panel" role="status">Opening your collection…</div>
  if (session.error) return <PageError error={session.error} retry={session.retry} />
  if (!session.user) return <Navigate to={'/login?next=' + encodeURIComponent(location.pathname + location.search)} replace />
  return children
}
