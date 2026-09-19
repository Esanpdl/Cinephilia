import { useState } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { ArrowRight, Eye, EyeOff } from 'lucide-react'
import { api, errorMessage } from '../api/client'
import { useFeaturedFilm } from '../api/featured'
import type { SessionResponse } from '../api/types'
import { useSession } from '../auth/SessionProvider'
import { safeNext } from '../auth/navigation'
import { Button } from '../components/ui'

export default function Auth({ register = false }: { register?: boolean }) {
  const session = useSession()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = safeNext(params.get('next'))
  const [show, setShow] = useState(false)
  const feature = useFeaturedFilm()
  const mutation = useMutation({
    mutationFn: (body: Record<string, string>) => api<SessionResponse>('/api/v1/users/' + (register ? 'register/' : 'login/'), { method: 'POST', body }),
    onSuccess: async response => { await session.acceptSession(response); navigate(next, { replace: true }) },
  })
  if (session.user) return <Navigate to={next} replace />
  return <div className="auth-page"><div className="auth-image">{feature.data?.backdrop_url && <img src={feature.data.backdrop_url} alt="" />}<div className="auth-image-shade" /><div><p className="eyebrow">A seat is waiting for you</p><h1>For the films<br />that <em>stay.</em></h1><p>A personal collection. A new perspective.<br />An endless conversation with cinema.</p></div></div><div className="auth-form-wrap">
    <p className="eyebrow">{register ? 'Your story starts here' : 'Welcome back'}</p><h2>{register ? 'Take your seat.' : 'Back to the picture.'}</h2><p className="auth-subtitle">{register ? 'Create your free account to rate, save, and discover films.' : 'Sign in to your personal corner of cinema.'}</p>
    <form onSubmit={event => { event.preventDefault(); mutation.reset(); const data = new FormData(event.currentTarget); mutation.mutate(Object.fromEntries([...data.entries()].map(([key, value]) => [key, String(value)]))) }}>
      {register && <label className="field">Display name <span className="optional">(optional)</span><input name="display_name" maxLength={100} autoComplete="nickname" /></label>}
      <label className="field">Username<input name="username" autoComplete="username" required maxLength={150} pattern={register ? '[A-Za-z0-9_@.+-]+' : undefined} /></label>
      {register && <label className="field">Email <span className="optional">(optional)</span><input name="email" type="email" autoComplete="email" /></label>}
      <label className="field">Password<div className="password-field"><input name="password" type={show ? 'text' : 'password'} autoComplete={register ? 'new-password' : 'current-password'} minLength={register ? 8 : undefined} maxLength={128} required /><button type="button" aria-label={show ? 'Hide password' : 'Show password'} onClick={() => setShow(!show)}>{show ? <EyeOff size={18} /> : <Eye size={18} />}</button></div></label>
      {register && <p className="field-hint">Use at least 8 characters. Avoid common passwords and your username.</p>}
      {mutation.isError && <p className="inline-error" role="alert">{errorMessage(mutation.error)}</p>}
      <Button type="submit" className="button-light full-width" disabled={mutation.isPending}>{mutation.isPending ? 'One moment…' : register ? 'Create account' : 'Sign in'}<ArrowRight size={17} /></Button>
    </form>
    <p className="auth-switch">{register ? 'Already part of the picture?' : 'New to Cinephilia?'} <Link to={(register ? '/login' : '/register') + '?next=' + encodeURIComponent(next)}>{register ? 'Sign in' : 'Create an account'}</Link></p>
  </div></div>
}
