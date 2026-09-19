import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { LogOut } from 'lucide-react'
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
  const save = useMutation({
    mutationFn: (profile: Profile) => api<Profile>('/api/v1/users/me/profile/', { method: 'PATCH', body: profile }),
    onSuccess: profile => { cache.setQueryData(['session'], { ...user!, profile } satisfies User) },
  })
  const logout = useMutation({ mutationFn: signOut, onSuccess: () => navigate('/') })
  return <div className="section-wrap account-page"><div className="page-heading"><p className="eyebrow">Behind the collection</p><h1>Your <em>profile.</em></h1><p>Signed in as {user!.username}</p></div><div className="account-layout">
    <form className="profile-form" onSubmit={event => {
      event.preventDefault(); save.reset()
      const form = new FormData(event.currentTarget)
      save.mutate({ display_name: String(form.get('display_name') || ''), bio: String(form.get('bio') || ''), is_film_student: form.get('is_film_student') === 'on', favorite_genres: form.getAll('favorite_genres').map(Number) })
    }}>
      <label className="field">Display name<input name="display_name" maxLength={100} defaultValue={user!.profile?.display_name || ''} autoComplete="nickname" /></label>
      <label className="field">A little about you<textarea name="bio" maxLength={2000} rows={5} defaultValue={user!.profile?.bio || ''} /></label>
      <label className="checkbox-label"><input type="checkbox" name="is_film_student" defaultChecked={user!.profile?.is_film_student || false} /> I study film</label>
      <fieldset className="genre-preferences"><legend>Favorite genres <span className="optional">(optional)</span></legend>{genres.isPending ? <p>Loading genres…</p> : genres.isError ? <p className="inline-error">Genres could not be loaded.</p> : <div>{genres.data.map(genre => <label key={genre.tmdb_id}><input type="checkbox" name="favorite_genres" value={genre.tmdb_id} defaultChecked={user!.profile?.favorite_genres.includes(genre.tmdb_id)} /><span>{genre.name}</span></label>)}</div>}</fieldset>
      {save.isError && <p className="inline-error" role="alert">{errorMessage(save.error)}</p>}
      <Button type="submit" className="button-light" disabled={save.isPending || genres.isPending || genres.isError}>{save.isPending ? 'Saving…' : 'Save profile'}</Button><p className="save-notice" role="status">{save.isSuccess ? 'Your profile is saved.' : ''}</p>
    </form>
    <aside className="account-note"><span className="eyebrow">Your point of view</span><h2>A collection<br /><em>only you could make.</em></h2><p>Your film ratings shape your recommendations. These profile details are just a little more about you.</p><Button className="button-outline" disabled={logout.isPending} onClick={() => logout.mutate()}><LogOut size={16} /> {logout.isPending ? 'Signing out…' : 'Sign out'}</Button>{logout.isError && <p role="alert" className="inline-error">{errorMessage(logout.error)}</p>}</aside>
  </div></div>
}
