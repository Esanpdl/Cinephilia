import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Star } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api, ApiError, errorMessage } from '../api/client'
import { useSession } from '../auth/SessionProvider'
import type { Page, Review } from '../api/types'
import { Button, PageError, Pagination } from './ui'

const reviewPath = (movieId: number) => '/api/v1/ratings/reviews/' + movieId + '/'

export function ReviewEditor({ movieId, score, refresh }: { movieId: number; score: number | null; refresh: () => void }) {
  const { user } = useSession()
  const cache = useQueryClient()
  const key = ['private', user!.id, 'review', movieId]
  const saved = useQuery({ queryKey: key, queryFn: async ({ signal }) => {
    try { return await api<Review>(reviewPath(movieId) + 'mine/', { signal }) }
    catch (error) { if (error instanceof ApiError && error.status === 404) return null; throw error }
  } })
  const [text, setText] = useState('')
  const [notice, setNotice] = useState('')
  useEffect(() => { setText(saved.data?.text || '') }, [saved.data?.text])
  const mutation = useMutation({
    mutationFn: (remove: boolean) => api<Review | undefined>(reviewPath(movieId) + 'mine/', { method: remove ? 'DELETE' : 'PUT', body: remove ? undefined : { stars: score! / 2, text: text.trim() } }),
    onSuccess: (data, remove) => {
      cache.setQueryData(key, data || null)
      setNotice(remove ? 'Review removed. Your star rating is kept.' : 'Your review is saved.')
      void cache.invalidateQueries({ queryKey: ['reviews', movieId] })
      void cache.invalidateQueries({ queryKey: ['private', user!.id, 'rating', 'film', movieId] })
      refresh()
    },
  })
  const hidden = !!saved.data?.review_hidden
  return <div className="review-editor">
    <label htmlFor={'review-' + movieId}>Your review <span className="muted-label">Optional</span></label>
    <p className="review-guidance">A rating is enough. If you write a review, your words and username will be public.</p>
    {hidden && <p role="status">This review has been hidden by a moderator and cannot be edited.</p>}
    <textarea id={'review-' + movieId} rows={5} minLength={10} maxLength={3000} value={text} onChange={event => setText(event.target.value)} disabled={saved.isPending || saved.isError || mutation.isPending || hidden} placeholder="What stayed with you after the credits?" aria-describedby={'review-help-' + movieId} />
    <p className="review-guidance" id={'review-help-' + movieId}>10–3,000 characters. No links or copied reviews across films. One review per film; you can edit it. {text.length.toLocaleString()}/3,000</p>
    <div className="rating-buttons"><Button className="button-light button-small" disabled={saved.isPending || saved.isError || mutation.isPending || hidden || score === null || text.trim().length < 10 || text.trim().length > 3000 || text.trim() === saved.data?.text && score / 2 === saved.data?.stars} onClick={() => mutation.mutate(false)}>{mutation.isPending ? 'Saving…' : saved.data ? 'Update review' : 'Publish review'}</Button>{saved.data && <Button className="muted-action" disabled={mutation.isPending} onClick={() => mutation.mutate(true)}>Delete review</Button>}</div>
    {score === null && <p className="review-guidance">Choose a star rating above to publish a review.</p>}
    {saved.isError && <p className="inline-error" role="alert">Your review could not be loaded. <button onClick={() => { void saved.refetch() }}>Retry</button></p>}
    {mutation.error && <p className="inline-error" role="alert">{errorMessage(mutation.error)}</p>}
    <p className="save-notice" role="status">{notice}</p>
  </div>
}

export function FilmReviews({ movieId }: { movieId: number }) {
  const [page, setPage] = useState(1)
  const reviews = useQuery({ queryKey: ['reviews', movieId, page], queryFn: ({ signal }) => api<Page<Review>>(reviewPath(movieId) + '?page=' + page, { signal }) })
  useEffect(() => { setPage(1) }, [movieId])
  // Removing the final review on a later page should return to an existing page.
  useEffect(() => { if (reviews.error instanceof ApiError && reviews.error.status === 404 && page > 1) setPage(page - 1) }, [reviews.error, page])
  return <section className="film-reviews" aria-label="Film reviews"><div className="section-heading compact"><div><p className="eyebrow">After the credits</p><h2>What <em>stayed.</em></h2></div><span className="muted-label">{reviews.data ? `${reviews.data.count} reviews` : 'Film reviews'}</span></div>
    {reviews.isPending ? <p role="status">Opening the conversation…</p> : reviews.isError ? <PageError error={reviews.error} retry={() => { void reviews.refetch() }} /> : reviews.data.results.length ? <><div className="review-list">{reviews.data.results.map(review => <article className="review-card" key={review.id}><header><strong>{review.author_id ? <Link to={'/people/' + review.author_id}>{review.author}</Link> : review.author}</strong><span className="review-stars" aria-label={review.stars + ' out of 5 stars'}><Star size={15} fill="currentColor" /> {review.stars}/5</span><time dateTime={review.updated_at}>{new Date(review.updated_at).toLocaleDateString()}</time></header><p>{review.text}</p></article>)}</div><Pagination page={page} count={reviews.data.count} onPage={setPage} /></> : <p className="review-guidance">No written reviews yet. Sign in to share what this film meant to you.</p>}
  </section>
}
