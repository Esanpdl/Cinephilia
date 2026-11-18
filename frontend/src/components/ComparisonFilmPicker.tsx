import { useEffect, useId, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Check, ChevronDown, Search } from 'lucide-react'
import { api } from '../api/client'
import { STUDENTS } from '../api/students'

interface FilmOption { tmdb_id: number; title: string; year: number | null }
const normalize = (text: string) => text.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLocaleLowerCase()

export function ComparisonFilmPicker({ label, value, onChange, fullCatalog = false }: { label: string; value: number; onChange: (id: number) => void; fullCatalog?: boolean }) {
  const id = useId(), input = useRef<HTMLInputElement>(null), menu = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false), [query, setQuery] = useState(''), [active, setActive] = useState(0)
  const [visible, setVisible] = useState(100)
  const options = useQuery({ queryKey: [fullCatalog ? 'catalogue-film-options' : 'student-film-options'], queryFn: ({ signal }) => api<{ count: number; results: FilmOption[] }>(fullCatalog ? '/api/v1/movies/options/' : STUDENTS + 'film-options/', { signal }), staleTime: 60_000 })
  const films = options.data?.results || []
  const matches = films.filter(film => normalize(`${film.title} ${film.year || ''}`).includes(normalize(query.trim())))
  const selected = films.find(film => film.tmdb_id === value)
  const selectedLabel = selected ? `${selected.title}${selected.year ? ` (${selected.year})` : ''}` : ''
  const show = () => { setOpen(true); setQuery(''); setVisible(100); setActive(Math.max(0, films.findIndex(film => film.tmdb_id === value))) }
  const choose = (film: FilmOption) => { onChange(film.tmdb_id); setOpen(false); setQuery('') }
  useEffect(() => { if (open) menu.current?.querySelector('[data-active="true"]')?.scrollIntoView({ block: 'nearest' }) }, [active, open])
  return <div className="comparison-picker" onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false) }}>
    <label htmlFor={id}>{label}</label>
    <div className={'comparison-picker-field' + (open ? ' is-open' : '')}>
      <Search size={17} aria-hidden="true" />
      <input ref={input} id={id} role="combobox" aria-autocomplete="list" aria-expanded={open} aria-controls={id + '-options'} aria-activedescendant={open && matches[active] ? id + '-option-' + matches[active].tmdb_id : undefined}
        autoComplete="off" placeholder={open ? 'Search title or year…' : options.isPending ? 'Loading films…' : 'Choose a film'} value={open ? query : selectedLabel}
        onFocus={show} onClick={() => { if (!open) show() }} onChange={event => { setQuery(event.target.value); setActive(0); setVisible(100); setOpen(true) }}
        onKeyDown={event => {
          if (event.key === 'Escape') { event.preventDefault(); setOpen(false) }
          else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); if (!open) show(); else setActive(index => Math.max(0, Math.min(matches.length - 1, index + (event.key === 'ArrowDown' ? 1 : -1)))) }
          else if (event.key === 'Enter' && open) { event.preventDefault(); if (matches[active]) choose(matches[active]) }
          else if (event.key === 'Tab') setOpen(false)
        }} />
      <button type="button" aria-label={'Browse all films for ' + label.toLowerCase()} aria-expanded={open} aria-controls={id + '-options'} onMouseDown={event => event.preventDefault()} onClick={() => { if (open && !query) setOpen(false); else { input.current?.focus(); show() } }}><ChevronDown size={18} aria-hidden="true" /></button>
    </div>
    {open && <div className="comparison-picker-popup">
      <div className="comparison-picker-count">{matches.length} {query ? 'matching' : 'available'} films</div>
      {options.isPending && <p role="status">Loading the collection…</p>}
      {options.isError && <p role="alert">Could not load films. <button type="button" onClick={() => { void options.refetch() }}>Retry</button></p>}
      <div ref={menu} id={id + '-options'} role="listbox" aria-label={label + ' options'} className="comparison-picker-options" onScroll={event => { const el = event.currentTarget; if (el.scrollTop + el.clientHeight >= el.scrollHeight - 80) setVisible(n => n + 100) }}>
        {matches.slice(0, fullCatalog ? Math.max(visible, active + 1) : matches.length).map((film, index) => <div key={film.tmdb_id} id={id + '-option-' + film.tmdb_id} role="option" aria-selected={value === film.tmdb_id} data-active={index === active} className="comparison-picker-option" onMouseDown={event => event.preventDefault()} onClick={() => choose(film)}>
          <span>{film.title}<small>{film.year || 'Year unavailable'}</small></span>{value === film.tmdb_id && <Check size={15} aria-hidden="true" />}
        </div>)}
      </div>
      {!options.isPending && !options.isError && !matches.length && <p>No films found. Try another title or year.</p>}
    </div>}
  </div>
}
