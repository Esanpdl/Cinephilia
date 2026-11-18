import { useState } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { ArrowRight, Eye, EyeOff } from 'lucide-react'
import { api, ApiError, errorMessage } from '../api/client'
import { useFeaturedFilm } from '../api/featured'
import type { SessionResponse } from '../api/types'
import { useSession } from '../auth/SessionProvider'
import { safeNext } from '../auth/navigation'
import { Button } from '../components/ui'

const PASSWORD_SYMBOLS = "!@#$%^&*()_+-=[]{};':\"\\|,.<>/?~`"

export default function Auth({ register = false }: { register?: boolean }) {
  const session = useSession()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = safeNext(params.get('next'))
  const [show, setShow] = useState(false)
  const [registrationDestination, setRegistrationDestination] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [passwordDraft, setPasswordDraft] = useState('')
  const [localError, setLocalError] = useState('')
  const hasPasswordNumberOrSymbol = /[0-9]/.test(passwordDraft) || [...PASSWORD_SYMBOLS].some(character => passwordDraft.includes(character))
  const fieldError = (name: string) => {
    const value = mutation.error instanceof ApiError ? mutation.error.fields[name] : null
    return Array.isArray(value) ? value.join(' ') : typeof value === 'string' ? value : ''
  }
  const feature = useFeaturedFilm()
  const mutation = useMutation({
    mutationFn: (body: Record<string, string>) => api<SessionResponse>('/api/v1/users/' + (register ? 'register/' : 'login/'), { method: 'POST', body }),
    onSuccess: async response => {
      const welcome = register && response.user.profile.onboarding_status === 'pending'
      const destination = welcome ? '/welcome?next=' + encodeURIComponent(next) : next
      setRegistrationDestination(welcome ? destination : '')
      await session.acceptSession(response)
      navigate(destination, { replace: true })
    },
  })
  if (session.user) return <Navigate to={registrationDestination || next} replace />
  return <div className="auth-page"><div className="auth-image">{feature.data?.backdrop_url && <img src={feature.data.backdrop_url} alt="" />}<div className="auth-image-shade" /><div><p className="eyebrow">A seat is waiting for you</p><h1>For the films<br />that <em>stay.</em></h1><p>A personal collection. A new perspective.<br />An endless conversation with cinema.</p></div></div><div className="auth-form-wrap">
    <p className="eyebrow">{register ? 'Your story starts here' : 'Welcome back'}</p><h2>{register ? 'Take your seat.' : 'Back to the picture.'}</h2><p className="auth-subtitle">{register ? 'Create your free account to rate, save, and discover films.' : 'Sign in to your personal corner of cinema.'}</p>
    <form onSubmit={event => { event.preventDefault(); mutation.reset(); setLocalError(''); if (register && passwordDraft !== confirmation) { setLocalError('Passwords do not match.'); return } const data = new FormData(event.currentTarget); const body = Object.fromEntries([...data.entries()].filter(([key]) => key !== 'confirm_password').map(([key, value]) => [key, String(value)])); mutation.mutate(body) }}>
      {register && <label className="field">Display name <span className="optional">(optional)</span><input name="display_name" maxLength={100} autoComplete="nickname" /></label>}
      <label className="field">Username<input name="username" autoComplete="username" required maxLength={register ? 30 : 150} minLength={register ? 3 : undefined} pattern={register ? '[A-Za-z0-9_-]{3,30}' : undefined} title={register ? 'Use 3–30 letters, numbers, underscores or hyphens.' : undefined} />{fieldError('username') && <span className="field-error">{fieldError('username')}</span>}</label>
      {register && <label className="field">Email <span className="optional">(optional)</span><input name="email" type="email" autoComplete="email" maxLength={254} />{fieldError('email') && <span className="field-error">{fieldError('email')}</span>}</label>}
      <label className="field">Password<div className="password-field"><input name="password" type={show ? 'text' : 'password'} autoComplete={register ? 'new-password' : 'current-password'} minLength={register ? 8 : undefined} maxLength={128} title={register ? 'Use at least 8 characters, including a letter and a number or symbol.' : undefined} required onChange={event => setPasswordDraft(event.target.value)} /><button type="button" aria-label={show ? 'Hide password' : 'Show password'} onClick={() => setShow(!show)}>{show ? <EyeOff size={18} /> : <Eye size={18} />}</button></div>{fieldError('password') && <span className="field-error">{fieldError('password')}</span>}</label>
      {register && <><p className="field-hint">Password requirements: {passwordDraft.length >= 8 ? '✓' : '○'} 8 or more characters · {/[A-Za-z]/.test(passwordDraft) ? '✓' : '○'} a letter · {hasPasswordNumberOrSymbol ? '✓' : '○'} a number or symbol</p><label className="field">Confirm password<input name="confirm_password" type={show ? 'text' : 'password'} autoComplete="new-password" required value={confirmation} onChange={event => { setConfirmation(event.target.value); setLocalError('') }} />{confirmation && passwordDraft !== confirmation && <span className="field-error">Passwords do not match.</span>}</label></>}
      {localError && <p className="inline-error" role="alert">{localError}</p>}
      {mutation.isError && <p className="inline-error" role="alert">{errorMessage(mutation.error)}</p>}
      <Button type="submit" className="button-light full-width" disabled={mutation.isPending}>{mutation.isPending ? 'One moment…' : register ? 'Create account' : 'Sign in'}<ArrowRight size={17} /></Button>
    </form>
    {!register && <p className="auth-switch"><Link to="/reset-password">Forgot your password?</Link></p>}
    <p className="auth-switch">{register ? 'Already part of the picture?' : 'New to Cinephilia?'} <Link to={(register ? '/login' : '/register') + '?next=' + encodeURIComponent(next)}>{register ? 'Sign in' : 'Create an account'}</Link></p>
  </div></div>
}
