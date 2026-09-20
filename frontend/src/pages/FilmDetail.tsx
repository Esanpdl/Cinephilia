import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useLocation, useParams } from 'react-router-dom'
import { ArrowLeft, Play } from 'lucide-react'
import { movieQuery } from '../api/queries'
import { ApiError } from '../api/client'
import { FilmActions } from '../components/FilmActions'
import { FilmReviews } from '../components/FilmReviews'
import { FilmCard, yearOf } from '../components/FilmCard'
import { Button, EmptyState, PageError, StarRating } from '../components/ui'

export default function FilmDetail() {
  const { id = '' } = useParams()
  const location = useLocation()
  const movieId = Number(id)
  const validId = Number.isSafeInteger(movieId) && movieId > 0
  const movie = useQuery({ ...movieQuery(movieId), enabled: validId })
  const [play, setPlay] = useState(false)
  useEffect(() => { setPlay(false) }, [id])
  useEffect(() => {
    if (movie.data) {
      document.title = movie.data.title + ' — Cinephilia'
      if (location.hash === '#trailer') document.getElementById('trailer')?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [movie.data, location.hash])
  if (!validId || movie.error instanceof ApiError && movie.error.status === 404) return <EmptyState title="This film is outside the frame."><p>It may not be in our collection.</p><Link to="/browse" className="button button-outline">Explore the collection</Link></EmptyState>
  if (movie.isPending) return <div className="detail-loading section-wrap" role="status"><div className="skeleton skeleton-title" /><p>Opening the film…</p></div>
  if (movie.isError) return <PageError error={movie.error} retry={() => { void movie.refetch() }} />
  const film = movie.data!
  return <article className="detail-page">
    <div className="detail-backdrop">{film.backdrop_url && <img src={film.backdrop_url} alt="" />}<div /></div>
    <div className="section-wrap detail-content"><Link className="text-link back-link" to="/browse"><ArrowLeft size={16} /> The collection</Link>
      <div className="detail-layout"><aside className="detail-poster"><FilmCard movie={film} /></aside><div className="detail-main">
        <p className="eyebrow">The screening room</p><h1>{film.title}</h1>
        {film.directors.length > 0 && <p className="detail-director">Directed by {film.directors.map(person => person.name).join(' & ')}</p>}
        <div className="film-metadata"><span>{yearOf(film.release_date)}</span>{film.runtime !== null && <span>{film.runtime} min</span>}<span>{film.genres.map(genre => genre.name).join(' / ')}</span></div>
        {film.tagline && <p className="film-tagline">{film.tagline}</p>}
        <p className="detail-overview">{film.overview || 'A synopsis is not available for this film.'}</p>
        <div className="detail-ratings-row">
          <div className="tmdb-rating"><strong>{Number(film.vote_average).toFixed(1)}<small>/10</small></strong><span>TMDB audience rating<br /><small>{film.vote_count.toLocaleString()} votes</small></span></div>
          <div className="community-rating">
            <div className="community-rating-stars">
              <StarRating value={film.community_rating ?? 0} size={18} />
              {film.community_rating !== null && film.community_rating !== undefined ? <strong>{Number(film.community_rating).toFixed(1)}<small>/5</small></strong> : <strong>—<small>/5</small></strong>}
            </div>
            <span>Cinephilia community<br /><small>{film.community_rating_count ? `${film.community_rating_count.toLocaleString()} ${film.community_rating_count === 1 ? 'rating' : 'ratings'}` : 'No ratings yet'}</small></span>
          </div>
        </div>
        <div className="letterboxd-rating"><iframe src={film.letterboxd_embed_url} title={film.title + ' — Letterboxd ratings'} loading="lazy" width="100%" height="100" referrerPolicy="strict-origin-when-cross-origin" /><a className="text-link" href={'https://letterboxd.com/tmdb/' + film.tmdb_id + '/'} target="_blank" rel="noopener noreferrer">View on Letterboxd</a></div>
        <FilmActions movieId={film.tmdb_id} />
      </div></div>
      <section className="trailer-section" id="trailer"><div className="section-heading compact"><div><p className="eyebrow">A first glimpse</p><h2>The <em>trailer.</em></h2></div><span className="muted-label">{film.trailer_official ? 'Official trailer' : 'Trailer'}</span></div>
        {film.trailer_embed_url ? play ? <div className="trailer-player"><iframe src={film.trailer_embed_url} title={film.title + ' trailer'} allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerPolicy="strict-origin-when-cross-origin" allowFullScreen /></div> : <Button className="trailer-preview" onClick={() => setPlay(true)} aria-label={'Play ' + film.title + ' trailer'}>{film.backdrop_url && <img src={film.backdrop_url} alt="" loading="lazy" />}<span className="trailer-play-icon"><Play size={24} fill="currentColor" /></span><span>Watch the trailer</span></Button> : <div className="unavailable-media"><p>A trailer isn't available for this film.</p><span>You can still rate it or keep it on your watchlist.</span></div>}
      </section>
      {film.cast.length > 0 && <section className="cast-section"><div className="section-heading compact"><div><p className="eyebrow">The faces in the frame</p><h2>Cast & <em>characters.</em></h2></div></div><div className="cast-grid">{film.cast.slice(0, 12).map((person, index) => <div key={person.tmdb_id + '-' + index}><strong>{person.name}</strong><span>{person.character || 'Role unlisted'}</span></div>)}</div></section>}
      <FilmReviews key={film.tmdb_id} movieId={film.tmdb_id} />
    </div>
  </article>
}
