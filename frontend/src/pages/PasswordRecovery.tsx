import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { ArrowRight } from 'lucide-react'
import { api, errorMessage } from '../api/client'
import { Button } from '../components/ui'

export default function PasswordRecovery() {
  const [params] = useSearchParams()
  const uid = params.get('uid') || ''
  const token = params.get('token') || ''
  const confirm = !!uid && !!token
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [message, setMessage] = useState('')
  const mutation = useMutation({
    mutationFn: () => confirm
      ? api<{ detail: string }>('/api/v1/users/password-reset/confirm/', { method: 'POST', body: { uid, token, password, confirm_password: confirmation } })
      : api<{ detail: string }>('/api/v1/users/password-reset/', { method: 'POST', body: { email } }),
    onSuccess: result => setMessage(result.detail),
  })
  return <main className="section-wrap auth-form-wrap password-recovery">
    <p className="eyebrow">Account access</p><h1>{confirm ? 'Choose a new password.' : 'Find your way back.'}</h1>
    {confirm ? <form onSubmit={event => { event.preventDefault(); mutation.mutate() }}>
      <label className="field">New password<input type="password" autoComplete="new-password" minLength={8} maxLength={128} required value={password} onChange={event => setPassword(event.target.value)} /></label>
      <label className="field">Confirm new password<input type="password" autoComplete="new-password" minLength={8} maxLength={128} required value={confirmation} onChange={event => setConfirmation(event.target.value)} /></label>
      {password !== confirmation && confirmation && <p className="field-error">Passwords do not match.</p>}
      <p className="field-hint">Use at least 8 characters, with a letter and a number or symbol.</p>
      <Button className="button-light full-width" disabled={mutation.isPending || password !== confirmation}>{mutation.isPending ? 'Saving…' : 'Change password'}<ArrowRight size={16} /></Button>
    </form> : <form onSubmit={event => { event.preventDefault(); mutation.mutate() }}>
      <p className="auth-subtitle">Enter the email on your account. If it matches, we’ll send a one-time reset link.</p>
      <label className="field">Email<input type="email" autoComplete="email" maxLength={254} required value={email} onChange={event => setEmail(event.target.value)} /></label>
      <Button className="button-light full-width" disabled={mutation.isPending || !email}>{mutation.isPending ? 'Sending…' : 'Send reset link'}<ArrowRight size={16} /></Button>
    </form>}
    {message && <p role="status" className="field-hint">{message}</p>}
    {mutation.isError && <p role="alert" className="inline-error">{errorMessage(mutation.error)}</p>}
    <p className="auth-switch"><Link to="/login">Return to sign in</Link></p>
  </main>
}
