import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ArrowDown, ArrowRight, ArrowUpRight, Play } from 'lucide-react'
import { useSession } from '../auth/SessionProvider'
import { moviesQuery, recommendationsQuery } from '../api/queries'
import { HIGHLIGHTS, useFeaturedFilm } from '../api/featured'
import { FilmCard, yearOf } from '../components/FilmCard'
import { GridSkeleton, PageError } from '../components/ui'

export default function Home() {
  const { user } = useSession()
  const feature = useFeaturedFilm()
  const cinema = useQuery(moviesQuery(HIGHLIGHTS))
  const essentials = useQuery(moviesQuery({ page_size: 6, ordering: 'popularity', homepage: 'true' }))
  const personal = useQuery({ ...recommendationsQuery(user?.id || 0), enabled: !!user })
  const film = feature.data
  return <>
    <section className={'feature-hero ' + (!film ? 'feature-loading' : '')} aria-label="Tonight's featured film">
      {film?.backdrop_url && <img className="feature-backdrop" src={film.backdrop_url} alt="" fetchPriority="high" />}
      <div className="hero-shade" />
      <div className="feature-content">
        <div className="eyebrow feature-label"><span className="live-dot" /> Tonight's feature <span className="feature-number">01 / THE SCREENING ROOM</span></div>
        {feature.isError ? <PageError error={feature.error} retry={() => { void feature.refetch() }} /> : film ? <>
          {film.directors.length > 0 && <p className="feature-director">A film by {film.directors.map(person => person.name).join(' & ')}</p>}
          <h1>{film.title}</h1>
          <div className="film-metadata"><span>{yearOf(film.release_date)}</span>{film.runtime && <span>{film.runtime} min</span>}<span>{film.genres.map(genre => genre.name).join(' / ')}</span></div>
          <p className="feature-overview">{film.overview}</p>
          <div className="feature-buttons"><Link to={'/films/' + film.tmdb_id + '#trailer'} className="button button-light"><Play size={15} fill="currentColor" /> {film.trailer_embed_url ? 'Watch trailer' : 'Explore film'}</Link><Link className="text-link" to={'/films/' + film.tmdb_id}>About the film <ArrowUpRight size={18} /></Link></div>
        </> : <div role="status" className="hero-placeholder"><div className="skeleton skeleton-title" /><p>Bringing the picture into focus…</p></div>}
      </div>
      <a className="hero-scroll" href="#essentials">There is more to see <ArrowDown size={15} /></a>
      <span className="hero-side-note" aria-hidden="true">A WORLD BEYOND THE ORDINARY</span>
    </section>
    <section className="section-wrap essentials-section" id="essentials">
      <div className="section-heading"><div><p className="eyebrow"><span>01</span> Essential viewing</p><h2>Every frame.<br /><em>A new possibility.</em></h2></div><p className="section-intro">Start with the collection's highest-rated films. Stay for whatever moves you.</p></div>
      {cinema.isPending ? <GridSkeleton /> : cinema.isError ? <PageError error={cinema.error} retry={() => { void cinema.refetch() }} /> : <div className="film-grid">{cinema.data.results.map(movie => <FilmCard key={movie.tmdb_id} movie={movie} />)}</div>}
      <div className="section-end"><span>Highest rated in the collection</span><Link to="/browse">Explore all films <ArrowRight size={16} /></Link></div>
    </section>
    <section className="section-wrap essentials-section">
      <div className="section-heading compact"><div><p className="eyebrow"><span>02</span> {user ? 'Your next discovery' : 'In the conversation'}</p><h2>{user ? 'A little more' : 'For the love'} <em>{user ? 'like you.' : 'of cinema.'}</em></h2></div><Link className="text-link" to={user ? '/for-you' : '/browse?ordering=popularity'}>View all <ArrowUpRight size={17} /></Link></div>
      {user ? personal.isPending ? <GridSkeleton /> : personal.isError ? <PageError error={personal.error} retry={() => { void personal.refetch() }} /> : <div className="film-grid">{personal.data?.results.slice(0, 6).map(entry => <FilmCard key={entry.movie.tmdb_id} movie={entry.movie} />)}</div> : essentials.isPending ? <GridSkeleton /> : essentials.isError ? <PageError error={essentials.error} retry={() => { void essentials.refetch() }} /> : <div className="film-grid">{essentials.data.results.map(movie => <FilmCard key={movie.tmdb_id} movie={movie} />)}</div>}
    </section>
    {[
      { theme: 'drama', title: 'Drama', note: 'Lives unfolding' },
      { theme: 'horror', title: 'Horror', note: 'Stay with the shadows' },
      { theme: 'blackwhite', title: 'Black & White', note: 'Light, shadow, silver' },
      { theme: 'animation', title: 'Animation', note: 'Worlds drawn into being' },
      { theme: 'international', title: 'International Cinema', note: 'Beyond one language' },
    ].map((section, index) => <ThemedRow key={section.theme} {...section} number={index + 3} />)}
    <section className="membership-panel"><div><p className="eyebrow">Make it personal</p><h2>Cinema doesn't end<br /><em>when the credits roll.</em></h2><p>Keep a watchlist. Record what moved you. Find the next film that will.</p></div><Link className="button button-light" to={user ? '/collection' : '/register'}>{user ? 'Open your collection' : 'Begin your collection'} <ArrowUpRight size={18} /></Link><span aria-hidden="true" className="membership-c">C.</span></section>
  </>
}

function ThemedRow({ theme, title, note, number }: { theme: string; title: string; note: string; number: number }) {
  const films = useQuery(moviesQuery({ homepage: 'true', theme, page_size: 6, ordering: 'rating' }))
  return <section className="section-wrap essentials-section" aria-label={title}><div className="section-heading compact"><div><p className="eyebrow"><span>{String(number).padStart(2, '0')}</span> {note}</p><h2><em>{title}.</em></h2></div><Link className="text-link" to={'/browse?homepage=true&theme=' + theme}>View all <ArrowUpRight size={17} /></Link></div>{films.isPending ? <GridSkeleton /> : films.isError ? <PageError error={films.error} retry={() => { void films.refetch() }} /> : <div className="film-grid">{films.data.results.map(movie => <FilmCard key={movie.tmdb_id} movie={movie} />)}</div>}</section>
}
