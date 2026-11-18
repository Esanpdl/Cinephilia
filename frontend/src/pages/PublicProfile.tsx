import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Mail, Star } from 'lucide-react'
import { api, ApiError } from '../api/client'
import type { PublicProfile as Profile, Page, Review, MovieSummary, WatchlistItem } from '../api/types'
import { FilmCard } from '../components/FilmCard'
import { PageError, Pagination } from '../components/ui'

export default function PublicProfile() {
  const { id } = useParams()
  return <CinemaProfile key={id} id={Number(id)} />
}

function CinemaProfile({ id }: { id: number }) {
  const [reviewPage, setReviewPage] = useState(1), [watchPage, setWatchPage] = useState(1)
  const base = `/api/v1/users/profiles/${id}/`
  // Revalidate on every visit/focus: visibility can change on another device.
  const profile = useQuery({ queryKey: ['public-profile', id], queryFn: ({ signal }) => api<Profile>(base, { signal }), staleTime: 0, gcTime: 0, refetchInterval: 30_000, retry: false })
  const reviews = useQuery({ queryKey: ['public-reviews', id, reviewPage], queryFn: ({ signal }) => api<Page<Review & { movie: MovieSummary }>>(base + `reviews/?page=${reviewPage}`, { signal }), enabled: !!profile.data, gcTime: 0, retry: false })
  const watchlist = useQuery({ queryKey: ['public-watchlist', id, watchPage], queryFn: ({ signal }) => api<Page<WatchlistItem>>(base + `watchlist/?page=${watchPage}`, { signal }), enabled: !!profile.data?.watchlist_public, gcTime: 0, refetchInterval: 30_000, retry: false })
  if (profile.isPending) return <div className="section-wrap" role="status">Opening cinema profile…</div>
  if (profile.isError) return <div className="section-wrap"><PageError error={profile.error} /></div>
  const person = profile.data
  return <div className="section-wrap public-cinema-profile">
    <div className="page-heading"><p className="eyebrow">Cinema profile</p><h1>{person.display_name || person.username}</h1><p>@{person.username}{person.is_film_student ? ' · Film student' : ''}</p>
      {person.bio && <p style={{ whiteSpace: 'pre-wrap' }}>{person.bio}</p>}
      {!!person.favorite_genres?.length && <p>{person.favorite_genres.map(g => g.name).join(' / ')}</p>}
      {person.email && <a className="text-link" href={'mailto:' + person.email}><Mail size={16} /> {person.email}</a>}
    </div>
    <section aria-label="Public reviews"><div className="section-heading compact"><h2>What <em>stayed.</em></h2><span>{reviews.data?.count || 0} reviews</span></div>
      {reviews.isPending ? <p role="status">Loading reviews…</p> : reviews.isError ? <PageError error={reviews.error} /> : !reviews.data?.count ? <p>No public reviews yet.</p> : <><div className="review-list">{reviews.data.results.map(review => <article className="review-card" key={review.id}><header><Link to={'/films/' + review.movie.tmdb_id}><strong>{review.movie.title}</strong></Link><span className="review-stars"><Star size={15} /> {review.stars}/5</span><time dateTime={review.updated_at}>{new Date(review.updated_at).toLocaleDateString()}</time></header><p>{review.text}</p></article>)}</div><Pagination page={reviewPage} count={reviews.data.count} onPage={setReviewPage} /></>}
    </section>
    <section aria-label="Public watchlist"><div className="section-heading compact"><h2>Still to <em>discover.</em></h2></div>
      {!person.watchlist_public || (watchlist.error instanceof ApiError && watchlist.error.status === 404) ? <p>This watchlist is private.</p> : watchlist.isPending ? <p role="status">Loading watchlist…</p> : watchlist.isError ? <PageError error={watchlist.error} /> : !watchlist.data?.count ? <p>No films saved yet.</p> : <><div className="film-grid">{watchlist.data.results.map(item => <FilmCard key={item.movie.tmdb_id} movie={item.movie} />)}</div><Pagination page={watchPage} count={watchlist.data.count} onPage={setWatchPage} /></>}
    </section>
  </div>
}
