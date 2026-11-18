import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Check, ChevronDown, Film, Search, X } from 'lucide-react'
import { api, errorMessage } from '../api/client'
import { moviesQuery } from '../api/queries'
import type { MovieSummary } from '../api/types'
import { useSession } from '../auth/SessionProvider'
import { FilmCard, yearOf } from './FilmCard'
import { Button, Pagination } from './ui'
import './SearchRecommendations.css'

interface FilmSuggestions {
  results: { movie: MovieSummary; match_percentage: number; explanations: string[] }[]
  notice: string
  score_note: string
}
type Discovery = 'familiar' | 'balanced' | 'adventurous'
const discoveryModes: { value: Discovery; label: string; detail: string }[] = [
  { value: 'familiar', label: 'Familiar', detail: 'Stay closer to the genres and performers you enjoy, with room for other directors.' },
  { value: 'balanced', label: 'Balanced', detail: 'Follow story connections and audience tastes across a broader mix of directors.' },
  { value: 'adventurous', label: 'Adventurous', detail: 'Explore other directors, eras and languages while keeping story and audience connections.' },
]

export function SearchRecommendations() {
  const { user } = useSession()
  return <RecommendationPicker key={user?.id ?? 'guest'} />
}

function RecommendationPicker() {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<MovieSummary[]>([])
  const [suggestions, setSuggestions] = useState<FilmSuggestions | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const [discovery, setDiscovery] = useState<Discovery>('balanced')
  const activeRequest = useRef<AbortController | null>(null)
  const catalogue = useQuery({ ...moviesQuery({ q: query || undefined, ordering: 'title', page }), enabled: open })
  useEffect(() => () => { activeRequest.current?.abort() }, [])

  function changeSelection(movie: MovieSummary) {
    const exists = selected.some(item => item.tmdb_id === movie.tmdb_id)
    if (!exists && selected.length >= 10) return
    activeRequest.current?.abort()
    activeRequest.current = null
    setPending(false)
    setSuggestions(null)
    setError(null)
    setSelected(previous => exists ? previous.filter(item => item.tmdb_id !== movie.tmdb_id) : [...previous, movie])
  }

  async function recommend() {
    if (selected.length < 3 || selected.length > 10 || pending) return
    const controller = new AbortController()
    activeRequest.current?.abort()
    activeRequest.current = controller
    setPending(true)
    setError(null)
    setSuggestions(null)
    try {
      const result = await api<FilmSuggestions>('/api/v1/recommendations/from-films/', { method: 'POST', body: { movie_ids: selected.map(movie => movie.tmdb_id), discovery }, signal: controller.signal })
      if (activeRequest.current === controller && !controller.signal.aborted) setSuggestions(result)
    } catch (failure) {
      if (activeRequest.current === controller && !controller.signal.aborted) setError(errorMessage(failure))
    } finally {
      if (activeRequest.current === controller) { setPending(false); activeRequest.current = null }
    }
  }

  return <section className="search-trio" aria-labelledby="search-trio-title">
    <div className="search-trio-intro">
      <div><p className="eyebrow"><Film size={15} aria-hidden="true" /> A personal triple bill</p><h2 id="search-trio-title">Your favourites. <em>Your next three.</em></h2><p>Choose 3–10 films you’ve watched and enjoyed. Find three films to explore next.</p></div>
      <Button className="button-outline" aria-expanded={open} aria-controls="search-trio-picker" onClick={() => setOpen(!open)}>{open ? 'Close selection' : 'Find my next three'}<ChevronDown size={16} className={open ? 'trio-chevron-open' : ''} aria-hidden="true" /></Button>
    </div>
    <div id="search-trio-picker" hidden={!open}>
      <div className="search-trio-workspace">
        <div className="search-trio-catalogue">
          <form className="search-trio-search" role="search" aria-label="Choose enjoyed films" onSubmit={event => { event.preventDefault(); setQuery(search.trim()); setPage(1) }}>
            <Search size={18} aria-hidden="true" /><label className="sr-only" htmlFor="trio-film-search">Find films you enjoyed</label><input id="trio-film-search" type="search" maxLength={200} value={search} onChange={event => setSearch(event.target.value)} placeholder="Title, director or actor" /><Button type="submit" className="button-outline button-small">Search</Button>
          </form>
          <p className="search-trio-help">Search the full catalogue. Your selections stay as you browse.</p>
          {catalogue.isPending ? <p role="status" className="search-trio-status">Loading the catalogue…</p> : catalogue.isError ? <div role="alert" className="search-trio-status"><p>{errorMessage(catalogue.error)}</p><Button className="button-outline button-small" onClick={() => { void catalogue.refetch() }}>Retry catalogue</Button></div> : <>
            <div className="search-trio-options" aria-label="Available films">
              {catalogue.data.results.map(movie => {
                const checked = selected.some(item => item.tmdb_id === movie.tmdb_id)
                return <button key={movie.tmdb_id} type="button" className={'search-trio-option' + (checked ? ' selected' : '')} aria-pressed={checked} disabled={!checked && selected.length >= 10} onClick={() => changeSelection(movie)}>
                  <span className="search-trio-choice" aria-hidden="true">{checked && <Check size={14} />}</span><span>{movie.title}<small>{yearOf(movie.release_date)} · {movie.genres.map(genre => genre.name).join(', ') || 'Film'}</small></span>
                </button>
              })}
              {!catalogue.data.results.length && <p className="search-trio-status">No films found. Try another title, director or actor.</p>}
            </div>
            <Pagination page={page} count={catalogue.data.count} onPage={setPage} />
          </>}
        </div>
        <div className="search-trio-selection">
          <p className="eyebrow">Your starting point</p><h3>Films you enjoyed <span aria-live="polite">{selected.length}/10</span></h3>
          {selected.length ? <ul>{selected.map(movie => <li key={movie.tmdb_id}><span>{movie.title} <small>({yearOf(movie.release_date)})</small></span><button type="button" aria-label={'Remove ' + movie.title} onClick={() => changeSelection(movie)}><X size={16} aria-hidden="true" /></button></li>)}</ul> : <p className="search-trio-help">Start with a few favourites from the catalogue.</p>}
          <p className="search-trio-help" aria-live="polite">{selected.length < 3 ? `Choose ${3 - selected.length} more ${selected.length === 2 ? 'film' : 'films'} to get suggestions.` : selected.length === 10 ? 'All 10 places filled. Remove a film to change your selection.' : 'Ready to find your next three. You can add more films for context.'}</p>
          <fieldset className="trio-discovery"><legend>How far would you like to explore?</legend><div>{discoveryModes.map(mode => <button key={mode.value} type="button" aria-pressed={discovery === mode.value} onClick={() => { if (discovery !== mode.value) { activeRequest.current?.abort(); activeRequest.current = null; setPending(false); setSuggestions(null); setError(null); setDiscovery(mode.value) } }}>{mode.label}</button>)}</div><p>{discoveryModes.find(mode => mode.value === discovery)?.detail}</p></fieldset>
          <Button className="button-light full-width" disabled={selected.length < 3 || pending} onClick={() => { void recommend() }}>{pending ? 'Finding your films…' : error ? 'Try suggestions again' : 'Suggest three films'}{!pending && <ArrowRight size={16} aria-hidden="true" />}</Button>
          <p className="search-trio-help">These choices apply here only. They don’t add ratings or change your saved favourites.</p>
          {pending && <p role="status" className="search-trio-help">Comparing your selections with the collection…</p>}
          {error && <p role="alert" className="inline-error">{error}</p>}
        </div>
      </div>
      {suggestions && <div className="search-trio-results" aria-live="polite">
        <div className="search-trio-results-heading"><p className="eyebrow">Made from your selection</p><h3>{suggestions.results.length === 3 ? 'Your next three.' : suggestions.results.length ? `${suggestions.results.length} films to explore.` : 'No suitable matches this time.'}</h3><p>{suggestions.score_note || 'Taste match is a model compatibility score, not a probability that you will enjoy a film.'}</p>{suggestions.notice && <p>{suggestions.notice}</p>}{!suggestions.results.length && <p>Try changing your selection.</p>}</div>
        <div className="search-trio-films">{suggestions.results.map(result => <FilmCard key={result.movie.tmdb_id} movie={result.movie}><p className="search-trio-match"><strong>{Math.round(result.match_percentage)}%</strong> taste match</p><ul className="search-trio-reasons">{result.explanations.map((reason, index) => <li key={index}>{reason}</li>)}</ul></FilmCard>)}</div>
      </div>}
    </div>
  </section>
}
