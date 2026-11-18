import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Clapperboard, SlidersHorizontal, X } from 'lucide-react'
import { api, errorMessage, queryString } from '../api/client'
import type { PreferenceInput, PreferenceOption, TastePreferences, User } from '../api/types'
import { useSession } from '../auth/SessionProvider'
import { safeNext } from '../auth/navigation'
import { Button, PageError } from '../components/ui'

type Kind = 'movie' | 'actor' | 'director' | 'genre' | 'era' | 'language'
type OptionsPage = { results: PreferenceOption[]; page: number; has_more: boolean }
const steps = ['Your films', 'The people', 'Genres & eras', 'Your comfort zone']
const same = (left: PreferenceOption, right: PreferenceOption) => String(left.id) === String(right.id)

function CataloguePicker({ kind, label, selected, onChange, limit = 5 }: {
  kind: Kind; label: string; selected: PreferenceOption[]; onChange: (value: PreferenceOption[]) => void; limit?: number;
}) {
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState({ q: '', page: 1 })
  useEffect(() => {
    const timer = window.setTimeout(() => setQuery({ q: search.trim(), page: 1 }), 250)
    return () => window.clearTimeout(timer)
  }, [search])
  const options = useQuery({
    queryKey: ['preference-options', kind, query], staleTime: 5 * 60_000,
    queryFn: ({ signal }) => api<OptionsPage>('/api/v1/users/preferences/options/?' + queryString({ kind, ...query }), { signal }),
  })
  const changingSearch = search.trim() !== query.q
  return <fieldset className="taste-picker">
    <legend>{label} <span>{selected.length} / {limit}</span></legend>
    <p className="field-hint">Choose up to {limit}. Search the entire catalogue.</p>
    <div className="taste-selections" aria-label={`Selected ${label.toLowerCase()}`}>
      {selected.map(item => <button key={item.id} type="button" className="taste-chip" onClick={() => onChange(selected.filter(value => !same(value, item)))} aria-label={`Remove ${item.name}`}>
        {item.name}<X size={13} aria-hidden="true" />
      </button>)}
    </div>
    <label className="field"><span className="sr-only">Search {label.toLowerCase()}</span><input type="search" value={search} placeholder={`Search ${label.toLowerCase()}`} onChange={event => setSearch(event.target.value)} maxLength={100} /></label>
    {options.isError ? <div className="taste-picker-error" role="alert"><p>{errorMessage(options.error)}</p><Button type="button" className="button-outline button-small" onClick={() => void options.refetch()}>Retry {label.toLowerCase()}</Button></div> : options.isPending || changingSearch ? <p className="taste-picker-status" role="status">Loading {label.toLowerCase()}…</p> : <>
      <div className="taste-options">
        {options.data.results.length ? options.data.results.map(item => {
          const checked = selected.some(value => same(value, item))
          return <label key={item.id} className={'taste-option' + (checked ? ' selected' : '')}>
            <input type="checkbox" checked={checked} disabled={!checked && selected.length >= limit} onChange={() => onChange(checked ? selected.filter(value => !same(value, item)) : [...selected, item])} />
            <span>{item.name}{item.detail && <small>{item.detail}</small>}</span>
          </label>
        }) : <p className="taste-picker-status">No matches. Try another name.</p>}
      </div>
      <nav className="taste-pagination" aria-label={`${label} pages`}>
        <Button type="button" className="muted-action" disabled={query.page === 1 || options.isFetching} onClick={() => setQuery(value => ({ ...value, page: value.page - 1 }))}><ArrowLeft size={14} /> Previous</Button>
        <span>Page {options.data.page}</span>
        <Button type="button" className="muted-action" disabled={!options.data.has_more || options.isFetching} onClick={() => setQuery(value => ({ ...value, page: value.page + 1 }))}>Next <ArrowRight size={14} /></Button>
      </nav>
    </>}
    <p className="field-hint" aria-live="polite">{selected.length >= limit ? `You have chosen ${limit}. Remove a selection to choose another.` : `${selected.length} selected`}</p>
  </fieldset>
}

function PreferenceForm({ initial, user, onboarding }: { initial: TastePreferences; user: User; onboarding: boolean }) {
  const cache = useQueryClient()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = safeNext(params.get('next'))
  const [step, setStep] = useState(0)
  const stepHeading = useRef<HTMLHeadingElement>(null)
  const [movies, setMovies] = useState(initial.selections.movies)
  const [actors, setActors] = useState(initial.selections.actors)
  const [directors, setDirectors] = useState(initial.selections.directors)
  const [genres, setGenres] = useState(initial.selections.genres)
  const [eras, setEras] = useState<PreferenceOption[]>(initial.favorite_eras.map(id => {
    const [start, end] = id.split('-').map(Number)
    return { id, name: `${start}–${Math.min(end, new Date().getFullYear())}` }
  }))
  const [languages, setLanguages] = useState<PreferenceOption[]>(initial.preferred_languages.map(id => ({ id, name: new Intl.DisplayNames(['en'], { type: 'language' }).of(id) || id })))
  const [exploration, setExploration] = useState(initial.exploration)
  const [openness, setOpenness] = useState(initial.language_openness)
  const hasTaste = movies.length + actors.length + directors.length + genres.length + eras.length > 0
  const valid = hasTaste && (openness !== 'prefer' || languages.length > 0)
  const changeStep = (next: number) => { setStep(next); window.setTimeout(() => stepHeading.current?.focus(), 0) }
  const save = useMutation({
    mutationFn: (body: PreferenceInput) => api<TastePreferences>('/api/v1/users/me/preferences/', { method: 'PUT', body }),
    onSuccess: async preferences => {
      // Cancel earlier responses before clearing personalized caches.
      await cache.cancelQueries({ queryKey: ['private', user.id] })
      cache.removeQueries({ queryKey: ['private', user.id] })
      cache.setQueryData(['session'], { ...user, profile: { ...user.profile, favorite_genres: preferences.favorite_genres, onboarding_status: preferences.onboarding_status } })
      void cache.invalidateQueries({ queryKey: ['session'] })
      navigate(onboarding ? next : '/for-you', { replace: true })
    },
  })
  return <div className="section-wrap taste-page">
    <header className="page-heading"><p className="eyebrow"><Clapperboard size={18} aria-hidden="true" />{onboarding ? 'Before the opening scene' : 'Your point of view'}</p>
      <h1>{onboarding ? 'Make yourself ' : 'Refine your '}<em>{onboarding ? 'at home.' : 'taste.'}</em></h1>
      <p>Tell us what you love. Your choices will shape your film suggestions from the first frame.</p>
    </header>
    <div className="taste-layout">
      <aside className="taste-intro"><SlidersHorizontal size={25} aria-hidden="true" /><h2>A programme <br /><em>with you in mind.</em></h2><p>Pick up to 10 films and up to 5 in each other category. A few favourites are enough; you can leave the rest open.</p><p>Your choices give us a starting point. As you rate films and build your watchlist, that activity takes the lead. You can edit your starting choices in your account.</p><Link to={onboarding ? next : '/for-you'} className="text-link">{onboarding ? 'Finish later' : 'Cancel changes'} <ArrowRight size={15} /></Link></aside>
      <form className="taste-form" onSubmit={event => {
        event.preventDefault()
        if (step < steps.length - 1) { changeStep(step + 1); return }
        if (!valid || save.isPending) return
        save.mutate({ favorite_movies: movies.map(item => Number(item.id)), favorite_actors: actors.map(item => Number(item.id)), favorite_directors: directors.map(item => Number(item.id)), favorite_genres: genres.map(item => Number(item.id)), favorite_eras: eras.map(item => String(item.id)), exploration, language_openness: openness, preferred_languages: openness === 'prefer' ? languages.map(item => String(item.id)) : [] })
      }}>
        <nav className="taste-steps" aria-label="Preference steps">{steps.map((name, index) => <button type="button" key={name} aria-current={index === step ? 'step' : undefined} onClick={() => changeStep(index)} disabled={save.isPending}><span>{String(index + 1).padStart(2, '0')}</span>{name}</button>)}</nav>
        <h2 className="taste-step-heading" ref={stepHeading} tabIndex={-1}>{steps[step]}</h2>
        <fieldset disabled={save.isPending} className="taste-step-content">
          {step === 0 && <CataloguePicker kind="movie" label="Favourite films" selected={movies} onChange={setMovies} limit={10} />}
          {step === 1 && <div className="taste-picker-grid"><CataloguePicker kind="actor" label="Favourite actors" selected={actors} onChange={setActors} /><CataloguePicker kind="director" label="Favourite directors" selected={directors} onChange={setDirectors} /></div>}
          {step === 2 && <div className="taste-picker-grid"><CataloguePicker kind="genre" label="Favourite genres" selected={genres} onChange={setGenres} /><CataloguePicker kind="era" label="Favourite eras" selected={eras} onChange={setEras} /></div>}
          {step === 3 && <>
            <fieldset className="taste-comfort"><legend>How far would you like to wander?</legend>{([
              ['familiar', 'Stay close to my favourites', 'More of the genres, people and eras I already enjoy.'],
              ['balanced', 'A familiar place, a new perspective', 'A balance of my favourites and nearby discoveries.'],
              ['adventurous', 'Take me somewhere unexpected', 'More variety, with my taste as the starting point.'],
            ] as const).map(([value, name, detail]) => <label className="taste-option" key={value}><input type="radio" name="exploration" value={value} checked={exploration === value} onChange={() => setExploration(value)} /><span>{name}<small>{detail}</small></span></label>)}</fieldset>
            <fieldset className="taste-comfort"><legend>Languages <span className="optional">(optional)</span></legend><label className="taste-option"><input type="radio" name="openness" checked={openness === 'any'} onChange={() => setOpenness('any')} /><span>I am open to films in any language</span></label><label className="taste-option"><input type="radio" name="openness" checked={openness === 'prefer'} onChange={() => setOpenness('prefer')} /><span>Lean towards languages I choose<small>Other languages may still appear.</small></span></label></fieldset>
            {openness === 'prefer' && <CataloguePicker kind="language" label="Preferred languages" selected={languages} onChange={setLanguages} />}
            <div className="taste-summary"><p>Your starting points</p><span>{movies.length} films · {actors.length} actors · {directors.length} directors · {genres.length} genres · {eras.length} eras</span></div>
            {!hasTaste && <p className="field-hint">Choose at least one film, actor, director, genre or era in the earlier steps to make these suggestions personal.</p>}
            {openness === 'prefer' && !languages.length && <p className="field-hint">Choose at least one preferred language, or stay open to all languages.</p>}
          </>}
        </fieldset>
        {save.isError && <p role="alert" className="inline-error">{errorMessage(save.error)} Your selections are still here; try saving again.</p>}
        <footer className="taste-footer"><Button type="button" className="button-outline" onClick={() => changeStep(step - 1)} disabled={step === 0 || save.isPending}><ArrowLeft size={15} /> Back</Button><span>{step + 1} of {steps.length}</span><Button type="submit" className="button-light" disabled={save.isPending || (step === steps.length - 1 && !valid)}>{save.isPending ? 'Saving your taste…' : step === steps.length - 1 ? 'Find my films' : 'Continue'}<ArrowRight size={15} /></Button></footer>
      </form>
    </div>
  </div>
}

export default function Preferences({ onboarding = false }: { onboarding?: boolean }) {
  const { user } = useSession()
  const preferences = useQuery({
    queryKey: ['private', user!.id, 'preferences'],
    enabled: !onboarding || user!.profile.onboarding_status === 'pending',
    queryFn: ({ signal }) => api<TastePreferences>('/api/v1/users/me/preferences/', { signal }),
  })
  if (onboarding && user!.profile.onboarding_status !== 'pending') return <Navigate to="/for-you" replace />
  if (preferences.isPending) return <div className="route-loading" role="status">Preparing your programme…</div>
  if (preferences.isError) return <PageError error={preferences.error} retry={() => void preferences.refetch()} />
  if (onboarding && preferences.data.onboarding_status !== 'pending') return <Navigate to="/for-you" replace />
  return <PreferenceForm key={user!.id} initial={preferences.data} user={user!} onboarding={onboarding} />
}
