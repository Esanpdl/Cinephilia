import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams, Link } from 'react-router-dom'
import { Search, X, SlidersHorizontal } from 'lucide-react'
import { genresQuery, moviesQuery } from '../api/queries'
import { FilmCard } from '../components/FilmCard'
import { Button, EmptyState, GridSkeleton, PageError, Pagination } from '../components/ui'

export default function Browse() {
  const [params, setParams] = useSearchParams()
  const [search, setSearch] = useState(params.get('q') || '')
  const genres = useQuery(genresQuery())
  const rawPage = Number(params.get('page') || 1)
  const page = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1
  const latestYear = new Date().getUTCFullYear()
  const years = Array.from({ length: latestYear - 1895 + 1 }, (_, index) => latestYear - index)
  const values = { q: params.get('q') || undefined, genre: params.get('genre') || undefined, year_from: params.get('year_from') || params.get('year') || undefined, year_to: params.get('year_to') || params.get('year') || undefined, homepage: params.get('homepage') || undefined, theme: params.get('theme') || undefined, ordering: params.get('ordering') || 'rating', page }
  const movies = useQuery(moviesQuery(values))
  useEffect(() => { setSearch(params.get('q') || '') }, [params])
  function update(key: string, value: string) {
    setParams(current => {
      const next = new URLSearchParams(current)
      if (key === 'year_from' || key === 'year_to') {
        const legacy = next.get('year')
        if (legacy) { next.set('year_from', legacy); next.set('year_to', legacy); next.delete('year') }
      }
      if (value) next.set(key, value); else next.delete(key)
      if (key !== 'page') next.delete('page')
      return next
    })
  }
  const filtered = !!(values.q || values.genre || values.year_from || values.year_to || values.homepage || values.theme)
  return <div className="section-wrap browse-page">
    <div className="page-heading"><p className="eyebrow">An open invitation</p><h1>The <em>collection.</em></h1><p>A world of cinema. Find your way in.</p></div>
    <form className="search-form" role="search" onSubmit={event => { event.preventDefault(); update('q', search.trim()) }}><Search size={21} /><label className="sr-only" htmlFor="film-search">Search films</label><input id="film-search" type="search" maxLength={200} value={search} onChange={event => setSearch(event.target.value)} placeholder="Film title, director, or actor…" /><Button type="submit" className="button-light">Search</Button></form>
    <div className="filter-bar"><span className="filter-label"><SlidersHorizontal size={16} /> Refine</span><label><span className="sr-only">Genre</span><select aria-label="Genre" value={values.genre || ''} onChange={event => update('genre', event.target.value)}><option value="">All genres</option>{genres.data?.map(genre => <option key={genre.tmdb_id} value={genre.tmdb_id}>{genre.name}</option>)}</select></label><label className="year-filter"><span className="sr-only">From year</span><select aria-label="From year" value={values.year_from || ''} onChange={event => update('year_from', event.target.value)}><option value="">From year</option>{years.map(year => <option key={year} value={year} disabled={!!values.year_to && year > Number(values.year_to)}>{year}</option>)}</select></label><label className="year-filter"><span className="sr-only">To year</span><select aria-label="To year" value={values.year_to || ''} onChange={event => update('year_to', event.target.value)}><option value="">To year</option>{years.map(year => <option key={year} value={year} disabled={!!values.year_from && year < Number(values.year_from)}>{year === latestYear ? `Latest (${year})` : year}</option>)}</select></label><label className="sort-filter"><span className="sr-only">Sort films</span><select aria-label="Sort films" value={values.ordering} onChange={event => update('ordering', event.target.value)}><option value="rating">Highest rated</option><option value="popularity">Most popular</option><option value="newest">Latest releases</option><option value="title">Title A–Z</option></select></label>{filtered && <Button className="clear-filters" onClick={() => { setParams({}); setSearch('') }}><X size={15} /> Clear</Button>}</div>
    {genres.isError && <p className="inline-error">Genres could not be loaded. <button onClick={() => { void genres.refetch() }}>Retry</button></p>}
    {values.q && <p className="search-hint">Title matches first, then directors, then actors.</p>}
    {values.homepage && <p className="search-hint">Selected from our curated collection{values.theme ? ': ' + ({ drama: 'Drama', horror: 'Horror', blackwhite: 'Black & White', animation: 'Animation', international: 'International Cinema' }[values.theme] || values.theme) : ''}.</p>}
    <div className="results-heading" aria-live="polite"><span>{movies.data ? movies.data.count.toLocaleString() + ' films' : 'Finding films…'}</span>{values.q && <span>Results for “{values.q}”</span>}</div>
    {movies.isPending ? <GridSkeleton count={12} /> : movies.isError ? <PageError error={movies.error} retry={() => { void movies.refetch() }} /> : movies.data.results.length ? <><div className="film-grid">{movies.data.results.map(movie => <FilmCard key={movie.tmdb_id} movie={movie} />)}</div><Pagination page={page} count={movies.data.count} onPage={number => { update('page', String(number)); window.scrollTo({ top: 0, behavior: 'smooth' }) }} /></> : <EmptyState title="No films in this frame."><p>Try another title, director, or actor, or open up your filters.</p><Link className="button button-outline" to="/browse">Browse all films</Link></EmptyState>}
  </div>
}
