import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bookmark, Check } from 'lucide-react'
import { useSession } from '../auth/SessionProvider'
import { api, errorMessage } from '../api/client'
import { filmStateQuery } from '../api/queries'
import type { Rating, WatchlistItem } from '../api/types'
import { Button, StarRating } from './ui'
import { ReviewEditor } from './FilmReviews'

export function FilmActions({ movieId }: { movieId: number }) {
  const { user, loading } = useSession()
  const location = useLocation()
  const cache = useQueryClient()
  const [draft, setDraft] = useState<number | null>(null)
  const [notice, setNotice] = useState('')
  const id = user?.id || 0
  const rating = useQuery({ ...filmStateQuery(id, movieId, 'rating'), enabled: !!user })
  const watchlist = useQuery({ ...filmStateQuery(id, movieId, 'watchlist'), enabled: !!user })
  const existing = rating.data && 'score' in rating.data ? Number(rating.data.score) : null
  useEffect(() => { setDraft(existing) }, [existing, movieId])
  useEffect(() => { setNotice('') }, [movieId, id])
  function refresh() {
    void cache.invalidateQueries({ queryKey: ['movie', movieId] })
    void cache.invalidateQueries({ queryKey: ['reviews', movieId] })
    void cache.invalidateQueries({ queryKey: ['private', id, 'review', movieId] })
    void cache.invalidateQueries({ queryKey: ['private', id, 'recommendations'] })
    void cache.invalidateQueries({ predicate: query => query.queryKey[0] === 'private' && query.queryKey[1] === id && ['ratings', 'watchlist'].includes(String(query.queryKey[2])) && query.queryKey[3] !== 'film' })
  }
  const saveRating = useMutation({
    mutationFn: (score: number | null) => api<Rating | undefined>('/api/v1/ratings/' + movieId + '/', { method: score === null ? 'DELETE' : 'PUT', body: score === null ? undefined : { score } }),
    onSuccess: (data, score) => { cache.setQueryData(filmStateQuery(id, movieId, 'rating').queryKey, data || null); setDraft(score); setNotice(score === null ? 'Rating removed.' : 'Your rating is saved.'); refresh() },
  })
  const saveWatchlist = useMutation({
    mutationFn: (remove: boolean) => api<WatchlistItem | undefined>('/api/v1/ratings/watchlist/' + movieId + '/', { method: remove ? 'DELETE' : 'PUT' }),
    onSuccess: (data, remove) => { cache.setQueryData(filmStateQuery(id, movieId, 'watchlist').queryKey, data || null); setNotice(remove ? 'Removed from your watchlist.' : 'Saved to your watchlist.'); refresh() },
  })
  if (loading) return <div className="film-actions" role="status">Opening your film notes…</div>
  if (!user) return <div className="film-actions guest-actions"><p>Some films deserve a place in your collection.</p><Link className="button button-light" to={'/login?next=' + encodeURIComponent(location.pathname)}>Sign in to rate & save</Link></div>
  return <section className="film-actions" aria-label="Your film collection">
    <Button className={watchlist.data ? 'button-saved' : 'button-outline'} disabled={watchlist.isPending || watchlist.isError || saveWatchlist.isPending} aria-pressed={!!watchlist.data} onClick={() => saveWatchlist.mutate(!!watchlist.data)}>{watchlist.data ? <Check size={18} /> : <Bookmark size={18} />}{saveWatchlist.isPending ? 'Saving…' : watchlist.data ? 'In your watchlist' : 'Add to watchlist'}</Button>
    <fieldset className="rating-control" disabled={rating.isPending || rating.isError || saveRating.isPending}><legend className="rating-legend"><div className="rating-legend-left"><span className="rating-legend-title">Your rating</span><StarRating value={existing !== null ? existing / 2 : 0} size={15} /></div><span className="rating-legend-score">{existing !== null ? existing / 2 + ' / 5 stars' : 'Not rated yet'}</span></legend><div className="rating-options">{Array.from({ length: 10 }, (_, i) => i + 1).map(score => <label key={score} className={draft === score ? 'selected' : ''}><input type="radio" name={'rating-' + movieId} value={score} checked={draft === score} onChange={() => setDraft(score)} aria-label={score / 2 + ' out of 5 stars'} /><span>{score / 2}</span></label>)}</div><div className="rating-buttons"><Button className="button-light button-small" disabled={draft === null || draft === existing || saveRating.isPending} onClick={() => { if (draft !== null) saveRating.mutate(draft) }}>{saveRating.isPending ? 'Saving…' : 'Save rating'}</Button>{existing !== null && <button className="muted-action" onClick={() => saveRating.mutate(null)}>Remove rating</button>}</div></fieldset>
    {(rating.isError || watchlist.isError) && <p className="inline-error" role="alert">Your saved film information could not be loaded. <button onClick={() => { void rating.refetch(); void watchlist.refetch() }}>Retry</button></p>}
    {(saveRating.error || saveWatchlist.error) && <p className="inline-error" role="alert">{errorMessage(saveRating.error || saveWatchlist.error)}</p>}
    <p className="save-notice" role="status">{notice}</p>
    <ReviewEditor key={movieId + '-' + id} movieId={movieId} score={draft} refresh={refresh} />
  </section>
}
