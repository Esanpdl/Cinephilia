import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { KeyRound, Lock, LogOut, ShieldCheck, User as UserIcon } from 'lucide-react'
import { useSession } from '../auth/SessionProvider'
import { api, errorMessage } from '../api/client'
import { genresQuery } from '../api/queries'
import type { Profile, User } from '../api/types'
import { Button } from '../components/ui'

export default function Account() {
  const { user, signOut } = useSession()
  const navigate = useNavigate()
  const cache = useQueryClient()
  const genres = useQuery(genresQuery())

  // Profile mutation
  const saveProfile = useMutation({
    mutationFn: (profile: Profile) => api<Profile>('/api/v1/users/me/profile/', { method: 'PATCH', body: profile }),
    onSuccess: profile => { cache.setQueryData(['session'], { ...user!, profile } satisfies User) },
  })

  // Credentials mutation (username, email)
  const [credError, setCredError] = useState<string | null>(null)
  const [credSuccess, setCredSuccess] = useState<string | null>(null)
  const [usernameInput, setUsernameInput] = useState(user?.username || '')
  const [emailInput, setEmailInput] = useState(user?.email || '')

  useEffect(() => {
    if (user) {
      setUsernameInput(user.username)
      setEmailInput(user.email || '')
    }
  }, [user?.username, user?.email])
  const saveCredentials = useMutation({
    mutationFn: (data: { username?: string; email?: string }) =>
      api<User>('/api/v1/users/me/', { method: 'PATCH', body: data }),
    onSuccess: updatedUser => {
      cache.setQueryData(['session'], { ...user!, ...updatedUser })
      setCredSuccess('Your account credentials have been updated successfully.')
      setCredError(null)
    },
    onError: err => {
      setCredError(errorMessage(err))
      setCredSuccess(null)
    },
  })

  // Password mutation
  const [pwError, setPwError] = useState<string | null>(null)
  const [pwSuccess, setPwSuccess] = useState<string | null>(null)
  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')

  const changePassword = useMutation({
    mutationFn: (data: { current_password: string; new_password: string; confirm_password: string }) =>
      api<{ detail: string; user: User; csrf_token: string }>('/api/v1/users/me/password/', { method: 'POST', body: data }),
    onSuccess: res => {
      cache.setQueryData(['session'], { ...user!, ...res.user })
      setPwSuccess('Your password has been changed successfully.')
      setPwError(null)
      setCurrentPw('')
      setNewPw('')
      setConfirmPw('')
    },
    onError: err => {
      setPwError(errorMessage(err))
      setPwSuccess(null)
    },
  })

  const logout = useMutation({ mutationFn: signOut, onSuccess: () => navigate('/') })

  return (
    <div className="section-wrap account-page">
      <div className="page-heading">
        <p className="eyebrow">Behind the collection</p>
        <h1>Your <em>account & profile.</em></h1>
        <p>Signed in as <strong>{user!.username}</strong> {user!.email ? `(${user!.email})` : ''}</p>
      </div>

      <div className="account-layout">
        <div className="account-main-sections">
          {/* Account Credentials Section */}
          <section className="account-card">
            <div className="card-header">
              <UserIcon size={18} className="gold-icon" />
              <h2>Account credentials</h2>
            </div>
            <p className="section-help">Update your username or email address anytime. Username must be 3–30 alphanumeric characters.</p>

            <form
              className="profile-form"
              onSubmit={event => {
                event.preventDefault()
                setCredError(null)
                setCredSuccess(null)
                const username = usernameInput.trim()
                const email = emailInput.trim()

                if (!username) {
                  setCredError('Username cannot be empty.')
                  return
                }
                if (!/^[a-zA-Z0-9_-]{3,30}$/.test(username)) {
                  setCredError('Username must be 3–30 characters and contain only letters, numbers, underscores, or hyphens.')
                  return
                }
                if (email && /@gmail\./i.test(email) && !email.toLowerCase().endsWith('@gmail.com')) {
                  setCredError('Gmail addresses must end with @gmail.com.')
                  return
                }

                saveCredentials.mutate({ username, email })
              }}
            >
              <label className="field">
                Username
                <input
                  name="username"
                  value={usernameInput}
                  onChange={e => setUsernameInput(e.target.value)}
                  maxLength={30}
                  required
                  autoComplete="username"
                />
              </label>

              <label className="field">
                Email address
                <input
                  type="email"
                  name="email"
                  value={emailInput}
                  onChange={e => setEmailInput(e.target.value)}
                  placeholder="name@example.com"
                  autoComplete="email"
                />
              </label>

              {credError && <p className="inline-error" role="alert">{credError}</p>}
              {credSuccess && <p className="save-notice" role="status">{credSuccess}</p>}

              <Button
                type="submit"
                className="button-light"
                disabled={saveCredentials.isPending}
              >
                {saveCredentials.isPending ? 'Updating credentials…' : 'Save credentials'}
              </Button>
            </form>
          </section>

          {/* Change Password Section */}
          <section className="account-card">
            <div className="card-header">
              <KeyRound size={18} className="gold-icon" />
              <h2>Change password</h2>
            </div>
            <p className="section-help">Must be at least 8 characters with at least one letter and one number or special character.</p>

            <form
              className="profile-form"
              onSubmit={event => {
                event.preventDefault()
                setPwError(null)
                setPwSuccess(null)

                if (!currentPw) {
                  setPwError('Please enter your current password.')
                  return
                }
                if (newPw.length < 8) {
                  setPwError('New password must be at least 8 characters long.')
                  return
                }
                if (!/[a-zA-Z]/.test(newPw) || !/[0-9!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?~`]/.test(newPw)) {
                  setPwError('New password must contain at least one letter and at least one number or special character.')
                  return
                }
                if (newPw !== confirmPw) {
                  setPwError('New passwords do not match.')
                  return
                }

                changePassword.mutate({
                  current_password: currentPw,
                  new_password: newPw,
                  confirm_password: confirmPw,
                })
              }}
            >
              <label className="field">
                Current password
                <input
                  type="password"
                  value={currentPw}
                  onChange={e => setCurrentPw(e.target.value)}
                  required
                  autoComplete="current-password"
                />
              </label>

              <label className="field">
                New password
                <input
                  type="password"
                  value={newPw}
                  onChange={e => setNewPw(e.target.value)}
                  required
                  autoComplete="new-password"
                />
              </label>

              <label className="field">
                Confirm new password
                <input
                  type="password"
                  value={confirmPw}
                  onChange={e => setConfirmPw(e.target.value)}
                  required
                  autoComplete="new-password"
                />
              </label>

              {pwError && <p className="inline-error" role="alert">{pwError}</p>}
              {pwSuccess && <p className="save-notice" role="status">{pwSuccess}</p>}

              <Button
                type="submit"
                className="button-light"
                disabled={changePassword.isPending}
              >
                {changePassword.isPending ? 'Updating password…' : 'Update password'}
              </Button>
            </form>
          </section>

          {/* Profile Details Section */}
          <section className="account-card">
            <div className="card-header">
              <Lock size={18} className="gold-icon" />
              <h2>Cinema profile</h2>
            </div>
            <form
              className="profile-form"
              onSubmit={event => {
                event.preventDefault()
                saveProfile.reset()
                const form = new FormData(event.currentTarget)
                saveProfile.mutate({
                  display_name: String(form.get('display_name') || ''),
                  bio: String(form.get('bio') || ''),
                  is_film_student: form.get('is_film_student') === 'on',
                  favorite_genres: form.getAll('favorite_genres').map(Number),
                })
              }}
            >
              <label className="field">
                Display name
                <input
                  name="display_name"
                  maxLength={100}
                  defaultValue={user!.profile?.display_name || ''}
                  autoComplete="nickname"
                />
              </label>
              <label className="field">
                A little about you
                <textarea
                  name="bio"
                  maxLength={2000}
                  rows={4}
                  defaultValue={user!.profile?.bio || ''}
                />
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  name="is_film_student"
                  defaultChecked={user!.profile?.is_film_student || false}
                />
                I study film
              </label>
              <fieldset className="genre-preferences">
                <legend>Favorite genres <span className="optional">(optional)</span></legend>
                {genres.isPending ? (
                  <p>Loading genres…</p>
                ) : genres.isError ? (
                  <p className="inline-error">Genres could not be loaded.</p>
                ) : (
                  <div>
                    {genres.data.map(genre => (
                      <label key={genre.tmdb_id}>
                        <input
                          type="checkbox"
                          name="favorite_genres"
                          value={genre.tmdb_id}
                          defaultChecked={Boolean(user?.profile?.favorite_genres?.includes(genre.tmdb_id))}
                        />
                        <span>{genre.name}</span>
                      </label>
                    ))}
                  </div>
                )}
              </fieldset>

              {saveProfile.isError && <p className="inline-error" role="alert">{errorMessage(saveProfile.error)}</p>}
              {saveProfile.isSuccess && <p className="save-notice" role="status">Your profile is saved.</p>}

              <Button
                type="submit"
                className="button-light"
                disabled={saveProfile.isPending || genres.isPending || genres.isError}
              >
                {saveProfile.isPending ? 'Saving…' : 'Save profile'}
              </Button>
            </form>
          </section>
        </div>

        {/* Sidebar */}
        <aside className="account-note">
          {user!.is_staff && (
            <div className="admin-access-card">
              <div className="admin-badge-row">
                <ShieldCheck size={20} className="gold-icon" />
                <span className="admin-status-pill">
                  {user!.is_main_admin ? 'Main Administrator' : 'Staff Admin'}
                </span>
              </div>
              <h3>Admin Dashboard</h3>
              <p>
                {user!.is_main_admin
                  ? 'You are the primary administrator. You can add, promote, and manage other administrators.'
                  : 'You have staff administration privileges.'}
              </p>
              <Link to="/admin" className="button button-gold">
                Open Admin Dashboard
              </Link>
            </div>
          )}

          <span className="eyebrow">Your point of view</span>
          <h2>A collection<br /><em>only you could make.</em></h2>
          <p>Your film ratings shape your recommendations. These profile details are just a little more about you.</p>

          <Button
            className="button-outline"
            disabled={logout.isPending}
            onClick={() => logout.mutate()}
          >
            <LogOut size={16} /> {logout.isPending ? 'Signing out…' : 'Sign out'}
          </Button>
          {logout.isError && <p role="alert" className="inline-error">{errorMessage(logout.error)}</p>}
        </aside>
      </div>
    </div>
  )
}
