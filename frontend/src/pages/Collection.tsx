import { Link, useSearchParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bookmark, Star, X } from 'lucide-react'
import { useSession } from '../auth/SessionProvider'
import { api, errorMessage } from '../api/client'
import { filmStateQuery, libraryQuery } from '../api/queries'
import type { Profile } from '../api/types'
import { FilmCard } from '../components/FilmCard'
import { Button, EmptyState, GridSkeleton, PageError, Pagination } from '../components/ui'

export default function Collection() {
  const { user } = useSession()
  const [publicWatchlist, setPublicWatchlist] = useState(!!user?.profile.watchlist_public)
  useEffect(() => { setPublicWatchlist(!!user?.profile.watchlist_public) }, [user?.id, user?.profile.watchlist_public])
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') === 'ratings' ? 'ratings' : 'watchlist'
  const rawPage = Number(params.get('page') || 1)
  const page = Number.isSafeInteger(rawPage) && rawPage > 0 ? rawPage : 1
  const cache = useQueryClient()
  const items = useQuery(libraryQuery(user!.id, tab, page))
  const visibility = useMutation({
    mutationFn: (watchlist_public: boolean) => api<Profile>('/api/v1/users/me/profile/', { method: 'PATCH', body: { watchlist_public } }),
    onError: () => setPublicWatchlist(!!user?.profile.watchlist_public),
    onSuccess: profile => { cache.setQueryData(['session'], { ...user!, profile }); void cache.invalidateQueries({ queryKey: ['public-profile', user!.id] }); void cache.invalidateQueries({ queryKey: ['public-watchlist', user!.id] }) },
  })
  const remove = useMutation({
    mutationFn: (movieId: number) => api('/api/v1/ratings/watchlist/' + movieId + '/', { method: 'DELETE' }),
    onSuccess: (_, movieId) => {
      cache.setQueryData(filmStateQuery(user!.id, movieId, 'watchlist').queryKey, null)
      void cache.invalidateQueries({ queryKey: ['private', user!.id, 'watchlist'] })
      void cache.invalidateQueries({ queryKey: ['private', user!.id, 'recommendations'] })
      if (items.data?.results.length === 1 && page > 1) setParams({ tab, page: String(page - 1) })
    },
  })
  return <div className="section-wrap collection-page"><div className="page-heading"><p className="eyebrow">Your personal film archive</p><h1>A collection <em>of moments.</em></h1><p>The films ahead of you. The ones that stayed.</p></div>
    <nav className="collection-tabs" aria-label="Collection sections"><Link className={tab === 'watchlist' ? 'active' : ''} to="/collection"><Bookmark size={16} /> Watchlist</Link><Link className={tab === 'ratings' ? 'active' : ''} to="/collection?tab=ratings"><Star size={16} /> Your ratings</Link></nav>
    {tab === 'watchlist' && <div className="collection-visibility"><label className="checkbox-label"><input type="checkbox" checked={publicWatchlist} disabled={visibility.isPending} onChange={event => { setPublicWatchlist(event.target.checked); visibility.mutate(event.target.checked) }} /> Public watchlist</label><p>{user!.profile.watchlist_public ? 'Anyone can see these films on your cinema profile.' : 'Only you can see your watchlist.'}</p><Link className="text-link" to={'/people/' + user!.id}>View cinema profile</Link>{visibility.isError && <p role="alert">{errorMessage(visibility.error)}</p>}</div>}
    <div className="results-heading"><span>{items.data ? items.data.count.toLocaleString() + ' films' : 'Opening your collection…'}</span><Link className="text-link" to="/browse">Add a discovery</Link></div>
    {remove.isError && <p className="inline-error" role="alert">{errorMessage(remove.error)}</p>}
    {items.isPending ? <GridSkeleton count={6} /> : items.isError ? <PageError error={items.error} retry={() => { void items.refetch() }} /> : items.data.results.length ? <><div className="film-grid">{items.data.results.map(item => <FilmCard key={item.movie.tmdb_id} movie={item.movie}>{'score' in item ? <div className="collection-card-action"><span><Star size={13} /> Your rating: {item.score / 2}/5</span><Link to={'/films/' + item.movie.tmdb_id}>Edit</Link></div> : <Button className="collection-remove" disabled={remove.isPending && remove.variables === item.movie.tmdb_id} aria-label={'Remove ' + item.movie.title + ' from watchlist'} onClick={() => remove.mutate(item.movie.tmdb_id)}><X size={13} /> {remove.isPending && remove.variables === item.movie.tmdb_id ? 'Removing…' : 'Remove'}</Button>}</FilmCard>)}</div><Pagination count={items.data.count} page={page} onPage={number => setParams({ tab, page: String(number) })} /></> : <EmptyState title={tab === 'watchlist' ? 'A blank screen. Endless possibilities.' : 'Which films stayed with you?'}><p>{tab === 'watchlist' ? 'Save a film from its detail page. It will be waiting here.' : 'Rate a film to begin your personal archive and shape your recommendations.'}</p><Link className="button button-light" to="/browse">Explore the collection</Link></EmptyState>}
  </div>
}
