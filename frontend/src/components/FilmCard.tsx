import { Link } from 'react-router-dom'
import { useState } from 'react'
import { ArrowUpRight, Film } from 'lucide-react'
import type { MovieSummary } from '../api/types'

export function yearOf(date: string | null) { return date ? date.slice(0, 4) : 'Year unavailable' }

export function FilmCard({ movie, children, interactive = true }: { movie: MovieSummary; children?: React.ReactNode; interactive?: boolean }) {
  const [failed, setFailed] = useState(false)
  return <article className="film-card">
    {interactive ? <Link to={'/films/' + movie.tmdb_id} className="poster-link" aria-label={movie.title + ', ' + yearOf(movie.release_date)}>
      {movie.poster_url && !failed ? <img src={movie.poster_url} alt={movie.title + ' poster'} loading="lazy" decoding="async" onError={() => setFailed(true)} /> : <div className="poster-fallback"><Film size={28} /><span>{movie.title}</span><small>Poster unavailable</small></div>}
      <span className="poster-overlay"><span>Explore film</span><ArrowUpRight size={21} /></span>
    </Link> : <div className="poster-link" aria-label={movie.title + ', ' + yearOf(movie.release_date)}>
      {movie.poster_url && !failed ? <img src={movie.poster_url} alt={movie.title + ' poster'} loading="lazy" decoding="async" onError={() => setFailed(true)} /> : <div className="poster-fallback"><Film size={28} /><span>{movie.title}</span><small>Poster unavailable</small></div>}
    </div>}
    <div className="film-caption"><Link to={'/films/' + movie.tmdb_id}>{movie.title}</Link><span>{yearOf(movie.release_date)}</span></div>
    {children}
  </article>
}
