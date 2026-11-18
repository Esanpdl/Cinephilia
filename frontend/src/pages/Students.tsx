import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, Route, Routes, useParams, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowUpRight, Play } from 'lucide-react'
import { api, errorMessage, queryString } from '../api/client'
import type { Page } from '../api/types'
import { useStudentData, STUDENTS, colorLabel, statusLabel, timestamp, mediaUrl } from '../api/students'
import type { Analysis, Comparison, Frame, Overview, Palette, StudentFilm, StudyCard, Tag, Technique } from '../api/students'
import { playbackAt } from '../api/playback'
import { useSession } from '../auth/SessionProvider'
import { Button, PageError, Pagination } from '../components/ui'
import { ComparisonFilmPicker } from '../components/ComparisonFilmPicker'
import { MatchedFramePairs } from '../components/MatchedFramePairs'
import { FilmPalette } from '../components/FilmPalette'
import { EvidenceLink } from '../components/ReviewedTechniques'
import { FrameTechniques } from '../components/FrameTechniques'
import '../students.css'

function Loading() { return <p className="student-loading" role="status">Bringing the frames into focus…</p> }

function PaletteStrip({ palette }: { palette: Palette }) {
  return <div className="palette-strip" aria-label="Dominant colors">{palette.map((color, i) => <span key={i} style={{ backgroundColor: color.hex, flex: color.weight }} title={`${color.hex} · ${(color.weight * 100).toFixed(1)}%`}><span className="sr-only">{color.hex}: {(color.weight * 100).toFixed(1)} percent. </span></span>)}</div>
}

function FilmTile({ film }: { film: StudentFilm }) {
  return <article className="student-film"><Link to={'/students/films/' + film.tmdb_id} className="student-film-image">{film.poster_url ? <img src={film.poster_url} alt={film.title + ' poster'} loading="lazy" /> : <div className="student-no-frame">Poster unavailable</div>}<span className="student-rank">{String(film.selection_rank).padStart(3, '0')}</span></Link><PaletteStrip palette={film.palette} /><div className="student-film-caption"><h3><Link to={'/students/films/' + film.tmdb_id}>{film.title}</Link></h3><span>{film.year} · {film.status === 'ready' ? colorLabel(film.color_mode) : statusLabel(film.status)}</span>{film.style_similarity?.score != null && <span>{film.style_similarity.score}% visual similarity</span>}{film.palette_similarity != null && <span>{film.palette_similarity}% palette similarity</span>}{!!film.shared_observations?.length && <span>Shared observations: {film.shared_observations.map(slug => slug.replace(/^shot:/, '').replaceAll('_', ' ').replaceAll('-', ' ')).join(', ')}</span>}</div></article>
}

function StudyCardView({ card, onPlay }: { card: StudyCard; onPlay?: (time: number) => void }) {
  return <article className="study-card"><img src={mediaUrl(card.image_url)} alt={`${card.technique.name} example from ${card.title}`} loading="lazy" /><div className="study-card-copy"><p className="eyebrow">{card.evidence === 'reviewed' ? 'Human reviewed' : card.evidence === 'model' ? 'Model suggested' : 'Measured colour'} · {timestamp(card.timestamp)}</p><h3>{card.technique.name}</h3><p>{card.explanation}</p><Link className="text-link" to={'/students/films/' + card.tmdb_id}>{card.title} <ArrowUpRight size={14} /></Link>{onPlay && <Button className="button-outline button-small" onClick={() => { if (card.timestamp !== null) onPlay(card.timestamp) }}><Play size={12} /> Watch at {timestamp(card.timestamp)}</Button>}</div></article>
}

function StudentsLayout() {
  const { user } = useSession()
  return <div className="students-page"><div className="section-wrap"><header className="student-header"><p className="eyebrow">The art of looking</p><h1>For film <em>students.</em></h1><p>A closer look at color, light, and composition.</p></header><nav className="student-nav" aria-label="Film student navigation"><NavLink end to="/students">The film collection</NavLink><NavLink to="/students/cards">Study cards</NavLink><NavLink to="/students/compare">Compare films</NavLink><NavLink to="/students/explore">Visual explorer</NavLink><NavLink to="/students/quiz">Train your eye</NavLink><NavLink to="/students/contribute">Contribute</NavLink>{user?.is_staff && <NavLink to="/students/moderation">Review queue</NavLink>}</nav><Outlet /></div></div>
}

function Collection() {
  const [params, setParams] = useSearchParams()
  const [search, setSearch] = useState(params.get('q') || '')
  const page = Math.max(1, Number(params.get('page')) || 1)
  const films = useStudentData<Page<StudentFilm>>('films/?' + params.toString())
  const taxonomy = useStudentData<Technique[]>('techniques/')
  const overview = useStudentData<Overview>('overview/')
  const spotlight = useStudentData<{ week: string; film: Analysis | null }>('spotlight/')
  const setFilter = (key: string, value: string) => { const next = new URLSearchParams(params); value ? next.set(key, value) : next.delete(key); next.delete('page'); setParams(next) }
  return <>
    {!params.toString() && spotlight.data?.film && <section className="student-spotlight"><Link to={'/students/films/' + spotlight.data.film.tmdb_id}>{spotlight.data.film.poster_url ? <img className="student-cover-poster" src={spotlight.data.film.poster_url} alt={spotlight.data.film.title + ' poster'} /> : <span>Poster unavailable</span>}</Link><div><p className="eyebrow">This week in focus · {spotlight.data.week}</p><h2>{spotlight.data.film.title}</h2><p>{colorLabel(spotlight.data.film.color_mode)}. Explore the palette and study the details in its sampled frames.</p><PaletteStrip palette={spotlight.data.film.palette} /><Link className="button button-outline" to={'/students/films/' + spotlight.data.film.tmdb_id}>Study this film <ArrowUpRight size={15} /></Link></div></section>}
    <div className="student-section-title"><h2>The <em>collection.</em></h2><span>{overview.data?.selected ?? '…'} selected · {overview.data?.status_counts.ready ?? '…'} analyses available</span></div>
    <form className="student-filters" onSubmit={event => { event.preventDefault(); setFilter('q', search) }}><label>Find a film<input type="search" aria-label="Search student films" value={search} onChange={event => setSearch(event.target.value)} placeholder="Film title" /></label><label>Color format<select value={params.get('color_mode') || ''} onChange={event => setFilter('color_mode', event.target.value)}><option value="">All formats</option><option value="color">Color</option><option value="black_and_white">Black & white</option><option value="mixed">Mixed</option></select></label><label>Technique<select value={params.get('technique') || ''} onChange={event => setFilter('technique', event.target.value)}><option value="">All observations</option>{taxonomy.data?.map(t => <option key={t.slug} value={t.slug}>{t.name}</option>)}</select></label><label>Availability<select value={params.get('status') || ''} onChange={event => setFilter('status', event.target.value)}><option value="">All collection films</option><option value="ready">Analysis available</option><option value="review">Needs source review</option><option value="missing">Source video unavailable</option><option value="failed">Analysis pending</option></select></label><Button type="submit" className="button-light">Search</Button></form>
    <p className="student-note">Colors describe the supplied image collection. All supplied frames contribute to measurements, including images hidden from the gallery; image grading may differ from the film.</p>
    {films.isPending ? <Loading /> : films.isError ? <PageError error={films.error} retry={() => { void films.refetch() }} /> : <><p className="student-result-count">{films.data.count} films</p><div className="student-grid">{films.data.results.map(film => <FilmTile key={film.tmdb_id} film={film} />)}</div>{!films.data.count && <p>No films match these filters.</p>}<Pagination page={page} count={films.data.count} onPage={value => { const next = new URLSearchParams(params); next.set('page', String(value)); setParams(next) }} /></>}
  </>
}

function FilmMetrics({ film, chart = false }: { film: Analysis; chart?: boolean }) {
  if (film.status !== 'ready') return <p className="student-note">{film.reason}</p>
  return <div className="film-measurements"><p className="eyebrow">{colorLabel(film.color_mode)} · source frame observation</p>{chart ? <FilmPalette key={film.tmdb_id} palette={film.palette} title={film.title} /> : <><PaletteStrip palette={film.palette} /><div className="palette-values">{film.palette.map((color, index) => <span key={index}>{color.hex}<small>{(color.weight * 100).toFixed(1)}%</small></span>)}</div></>}{(['brightness', 'saturation', 'contrast'] as const).map(key => <div className="metric-row" key={key}><span>{{ brightness: 'Lightness', saturation: 'Colour intensity', contrast: 'Tonal range' }[key]}</span><meter min="0" max="1" value={film.metrics[key]} /> <strong>{Math.round(film.metrics[key] * 100)}%</strong></div>)}<p className="student-note">{film.color_evidence}</p></div>
}

function EvidenceFrame({ frame, title }: { frame: Frame; title: string }) {
  const [mask, setMask] = useState(false)
  return <figure className="evidence-frame"><div><img src={mediaUrl(frame.image_url)} alt={frame.timestamp === null ? `${title}, supplied still frame` : `${title}, source video at ${timestamp(frame.timestamp)}`} loading="lazy" />{mask && <svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-label="Excluded text regions">{frame.text_regions?.map((box, i) => <polygon key={i} points={box.map(point => point.join(',')).join(' ')} />)}</svg>}</div><figcaption><span>{frame.timestamp === null ? 'Still frame' : `${timestamp(frame.timestamp)} · ${Math.round((frame.text_excluded_fraction || 0) * 100)}% text masked`}</span>{!!frame.text_regions?.length && <button type="button" className="muted-action" aria-pressed={mask} onClick={() => setMask(!mask)}>{mask ? 'Hide' : 'Show'} text regions</button>}</figcaption><FrameTechniques frame={frame} /></figure>
}

function FrameGallery({ frames, title }: { frames: Frame[]; title: string }) {
  const { id } = useParams()
  return <><div className="student-frame-grid">{frames.slice(0, 10).map(frame => <EvidenceFrame key={frame.image_url} frame={frame} title={title} />)}</div>{frames.length > 0 && <><p className="student-note">Showing {Math.min(10, frames.length)} of {frames.length} frames</p><Link className="button button-outline" to={'/students/films/' + id + '/gallery'}>{frames.length > 10 ? 'Show more frames' : 'Open frame gallery'} <ArrowUpRight size={15} /></Link></>}</>
}

function StudentGallery() {
  const { id = '' } = useParams()
  const film = useStudentData<Analysis>('films/' + id + '/')
  if (film.isPending) return <Loading />
  if (film.isError) return <PageError error={film.error} />
  const item = film.data
  const frames = item.status === 'ready' ? item.frames : []
  return <article className="student-gallery"><Link className="text-link" to={'/students/films/' + id}>← Back to film study</Link><div className="student-section-title"><div><p className="eyebrow">Frame gallery · {item.year}</p><h2>{item.title}</h2></div><span>{frames.length} frames</span></div><p className="student-note">{item.scope}</p>{frames.length ? <div className="student-frame-grid">{frames.map(frame => <EvidenceFrame key={frame.image_url} frame={frame} title={item.title} />)}</div> : <p>{item.reason || 'No frames are available for display yet.'}</p>}<Link className="text-link" to={'/films/' + id}>Film details & reviews <ArrowUpRight size={15} /></Link></article>
}

function StudentDetail() {
  const { id = '' } = useParams()
  const film = useStudentData<Analysis>('films/' + id + '/')
  const similar = useStudentData<{ results: StudentFilm[] }>('films/' + id + '/similar/')
  const tags = useStudentData<Page<Tag>>('films/' + id + '/tags/')
  const [playTime, setPlayTime] = useState<number | null>(null)
  useEffect(() => setPlayTime(null), [id])
  if (film.isPending) return <Loading />
  if (film.isError) return <PageError error={film.error} />
  const item = film.data
  const sources = item.playback_sources || [{ source_url: item.source_url, title: item.source_title, start: 0, end: item.duration || 0 }]
  const initialTime = sources.find(source => source.source_url)?.start || 0
  const playback = playbackAt(sources, playTime ?? initialTime)
  const embed = playback?.embed || ''
  const isStill = item.quality.source_kind === 'owner-supplied-stills'
  return <article><Link to="/students" className="text-link">← The film collection</Link><div className="student-section-title"><div><p className="eyebrow">Film study · {item.year}</p><h2>{item.title}</h2></div><Link className="button button-outline" to={'/students/compare?left=' + id}>Compare this film</Link></div><p className="student-note">{item.scope}</p><div className="student-detail-overview">{item.poster_url && <img className="student-feature-poster" src={item.poster_url} alt={item.title + ' poster'} />}<FilmMetrics film={item} chart /></div>{item.status === 'ready' && <><div className="student-section-title"><h2>Inside the <em>frame.</em></h2><span>{item.quality.retained_count} {isStill ? 'frames measured' : 'retained samples'}</span></div><div className="student-card-grid">{item.study_cards.map(card => <StudyCardView key={card.id} card={card} onPlay={card.timestamp !== null && playbackAt(sources, card.timestamp)?.embed ? setPlayTime : undefined} />)}</div>{!isStill && <section className="student-trailer"><h3>See the observation in context</h3>{sources.length > 1 && <label className="student-select">Source clip<select value={playback?.start ?? initialTime} onChange={event => setPlayTime(Number(event.target.value))}>{sources.map((source, index) => <option key={source.start} value={source.start} disabled={!source.source_url}>{index + 1}. {source.title.replace(/\.mp4$/i, '')}</option>)}</select></label>}{embed && playTime !== null ? <div className="trailer-player"><iframe key={embed} src={embed} title={item.title + ' study video'} allow="fullscreen; picture-in-picture" allowFullScreen /></div> : embed ? <Button className="button-outline" onClick={() => setPlayTime(initialTime)}><Play size={15} /> Open source video</Button> : <p>YouTube link pending for this clip.</p>}{playback?.source_url ? <a className="text-link" href={playback.watchUrl} target="_blank" rel="noreferrer">{playback?.title || item.source_title || 'Video source'} ↗</a> : <p className="student-note">{item.source_title}</p>}</section>}{isStill && item.source_url && <p><a className="text-link" href={item.source_url} target="_blank" rel="noreferrer">View frame source <ArrowUpRight size={14} /></a></p>}<div className="student-section-title"><h2>Representative <em>frames.</em></h2></div><FrameGallery key={item.tmdb_id} frames={item.frames} title={item.title} /><details className="student-method"><summary>How these colors were measured</summary><p>{item.quality.screening}</p><p>{item.quality.text_masking?.limitations}</p><p>Every pixel is counted and each frame contributes equally, regardless of resolution. Similar colours are grouped into eight representative CIELAB tones; percentages describe their combined area. Lightness, perceptual colour intensity and tonal range are measured separately. Embedded borders and genuine shadows remain included. Automatic labels describe conservative measurements, not the entire film.</p></details></>}
    {!!similar.data?.results.length && <><div className="student-section-title"><h2>Related <em>visual styles.</em></h2></div><p className="student-note">Visual matches combine colour distributions and available published technique evidence, independent of your main recommendations.</p><div className="student-grid">{similar.data.results.map(result => <FilmTile key={result.tmdb_id} film={result} />)}</div></>}
    <section className="student-community"><h3>Community observations</h3>{tags.data?.results.map(tag => <div className="community-observation" key={tag.id}><strong>{tag.technique.name}</strong><p>{tag.explanation}</p><small>Reviewed community contribution · {tag.scope}{tag.timestamp !== null ? ' · ' + timestamp(tag.timestamp) : ''}</small><EvidenceLink url={tag.source_url} /></div>)}{!tags.data?.count && <p>No approved community observations yet.</p>}<Link className="button button-outline" to={'/students/contribute?movie=' + id}>Contribute an observation</Link><Link className="text-link" to={'/films/' + id}>Film details & reviews ↗</Link></section>
  </article>
}

function Observation({ tag }: { tag: Tag }) {
  return <article className="community-observation"><p className="eyebrow">Reviewed community observation · {tag.scope}{tag.timestamp !== null ? ' · ' + timestamp(tag.timestamp) : ''}</p><h3>{tag.technique.name}</h3><p>{tag.explanation}</p><Link className="text-link" to={'/films/' + tag.tmdb_id}>{tag.title}</Link><EvidenceLink url={tag.source_url} /></article>
}

function Cards() {
  const [params, setParams] = useSearchParams()
  const taxonomy = useStudentData<Technique[]>('techniques/')
  const cards = useStudentData<Page<StudyCard>>('cards/?' + params.toString())
  const observations = useStudentData<Page<Tag>>('observations/?' + queryString({ technique: params.get('technique') || '', page: params.get('observations_page') || '1' }))
  const turnPage = (key: string, page: number) => { const next = new URLSearchParams(params); next.set(key, String(page)); setParams(next) }
  return <>
    <div className="student-section-title"><h2>Learn through <em>looking.</em></h2></div>
    <p className="student-note">Explore human reviews, published model suggestions and measured colour observations. Each card identifies its source.</p>
    <div className="study-source-filters"><label className="student-select">Evidence source<select value={params.get('source') || 'all'} onChange={event => { const next = new URLSearchParams(params); next.set('source', event.target.value); next.delete('page'); setParams(next) }}><option value="all">All sources</option><option value="human">Human reviewed</option><option value="model">Model suggested</option><option value="measured">Measured colour</option></select></label>
    <label className="student-select">Explore a technique<select value={params.get('technique') || ''} onChange={event => { const next = new URLSearchParams(params); event.target.value ? next.set('technique', event.target.value) : next.delete('technique'); next.delete('page'); setParams(next) }}><option value="">All techniques</option>{taxonomy.data?.map(t => <option key={t.slug} value={t.slug}>{t.name}</option>)}</select></label></div>
    {taxonomy.data?.filter(t => t.slug === params.get('technique')).map(t => <p className="student-note" key={t.slug}>{t.description}</p>)}
    {cards.isPending ? <Loading /> : cards.isError ? <PageError error={cards.error} /> : <>
      <div className="student-card-grid">{cards.data.results.map(card => <StudyCardView key={card.id} card={card} />)}</div>
      {!cards.data.count && <p>There are no published frame cards for this technique yet.</p>}
      <Pagination page={Number(params.get('page')) || 1} count={cards.data.count} onPage={page => turnPage('page', page)} />
    </>}
    <section className="student-community"><h2>Reviewed observations across the catalog</h2>
      {observations.isPending ? <Loading /> : observations.isError ? <PageError error={observations.error} /> : <>
        {observations.data.results.map(tag => <Observation key={tag.id} tag={tag} />)}
        {!observations.data.count && <p>No approved community observations for this selection yet.</p>}
        <Pagination page={Number(params.get('observations_page')) || 1} count={observations.data.count} onPage={page => turnPage('observations_page', page)} />
      </>}
      <Link className="button button-outline" to="/students/contribute">Contribute an observation</Link>
    </section>
  </>
}

function Compare() {
  const [params, setParams] = useSearchParams()
  const left = Number(params.get('left')) || 15
  const right = Number(params.get('right')) || (left === 238 ? 15 : 238)
  const result = useStudentData<Comparison>(`compare/?left=${left}&right=${right}`, left !== right)
  const change = (side: string, value: number) => { const next = new URLSearchParams(params); next.set('left', String(left)); next.set('right', String(right)); next.set(side, String(value)); setParams(next) }
  return <>
    <div className="student-section-title"><div><p className="eyebrow">A study in contrast</p><h2>Two films. <em>Two visual worlds.</em></h2></div></div>
    <div className="student-two-column comparison-pickers"><ComparisonFilmPicker label="Left film" value={left} onChange={id => change('left', id)} /><ComparisonFilmPicker label="Right film" value={right} onChange={id => change('right', id)} /></div>
    {left === right ? <p role="alert">Choose two different films.</p> : result.isPending ? <Loading /> : result.isError ? <PageError error={result.error} /> : <>
      {result.data.palette_similarity !== null && <p className="comparison-score"><strong>{result.data.palette_similarity}%</strong> palette similarity <span>{result.data.similarity_scope}</span></p>}
      <div className="student-two-column comparison-columns">{[result.data.left, result.data.right].map(film => <section key={film.tmdb_id}><h3><Link to={'/students/films/' + film.tmdb_id}>{film.title}</Link></h3><FilmMetrics film={film} /></section>)}</div>
      <MatchedFramePairs comparison={result.data} />
      <details className="student-method comparison-observations"><summary>Shared observations ({result.data.shared_observations.length})</summary>
        {result.data.shared_observations.length ? result.data.shared_observations.map(slug => <div className="student-two-column" key={slug}>{[result.data.left, result.data.right].map((film, side) => {
          const card = film.study_cards.find(c => c.technique.slug === slug)
          const tags = (side === 0 ? result.data.left_observations : result.data.right_observations).filter(t => t.technique.slug === slug)
          return <section key={film.tmdb_id}><h3>{film.title} · {card?.technique.name || slug.replace(/^shot:/, '').replaceAll('_', ' ').replaceAll('-', ' ')}</h3>{card && <p>{card.explanation}</p>}{tags.map(tag => <Observation key={tag.id} tag={tag} />)}</section>
        })}</div>) : <p>No shared published technique observations yet.</p>}
      </details>
    </>}
  </>
}

function Explorer() {
  const overview = useStudentData<Overview>('overview/')
  const taxonomy = useStudentData<Technique[]>('techniques/')
  const [hover, setHover] = useState('Select a point to study its film.')
  if (overview.isPending) return <Loading />
  if (overview.isError) return <PageError error={overview.error} />
  const data = overview.data
  const total = Object.values(data.color_counts).reduce((a, b) => a + b, 0)
  let cursor = 0
  const colors = ['#bf8060', '#d8d3c8', '#6d7e86']
  const segments = Object.entries(data.color_counts).map(([name, count], i) => { const from = cursor; cursor += count / (total || 1) * 100; return { name, count, color: colors[i % colors.length], gradient: `${colors[i % colors.length]} ${from}% ${cursor}%` } })
  return <><div className="student-section-title"><h2>The visual <em>landscape.</em></h2></div><p className="student-note">{data.scope}</p><div className="student-two-column"><section className="student-chart"><h3>Color formats</h3><div className="pie-layout"><div className="student-pie" role="img" aria-label={segments.map(s => `${colorLabel(s.name)}: ${s.count}`).join(', ')} style={{ background: total ? `conic-gradient(${segments.map(s => s.gradient).join(', ')})` : '#39352f' }} /><ul>{segments.map(s => <li key={s.name}><span style={{ background: s.color }} />{colorLabel(s.name)} <strong>{s.count}</strong></li>)}</ul></div></section><section className="student-chart"><h3>Published observations</h3><p className="student-note">Films with at least one published example, not technique frequency within films.</p>{data.technique_counts.map(t => <Link className="student-bar-row" to={'/students/cards?technique=' + (taxonomy.data?.find(item => item.name === t.technique__name)?.slug || '')} key={t.technique__name}><span>{t.technique__name}</span><div><i style={{ width: `${t.count / Math.max(1, total) * 100}%` }} /></div><strong>{t.count}</strong></Link>)}</section></div>{data.reviewed_technique_counts.length > 0 && <section className="student-chart"><h3>Reviewed techniques across the catalog</h3><p className="student-note">Distinct films with approved community observations, including films outside the analysis collection.</p>{data.reviewed_technique_counts.map(t => <Link className="student-bar-row" to={'/students/cards?technique=' + t.technique__slug} key={t.technique__slug}><span>{t.technique__name}</span><div><i style={{ width: `${t.count / Math.max(1, ...data.reviewed_technique_counts.map(row => row.count)) * 100}%` }} /></div><strong>{t.count}</strong></Link>)}</section>}<section className="student-chart scatter-chart"><h3>Lightness & colour intensity</h3><p className="student-note">Each point represents one film’s analysed source frames. Hover or focus for the film title.</p><svg viewBox="0 0 700 360" role="img" aria-label="Interactive lightness versus colour intensity plot"><line x1="55" y1="310" x2="670" y2="310" /><line x1="55" y1="20" x2="55" y2="310" /><text x="310" y="350">Lightness →</text><text x="5" y="15">Colour intensity ↑</text>{[0, .25, .5, .75, 1].map(n => <g key={n}><text x={55 + n * 615} y="330">{n}</text><text x="20" y={315 - n * 285}>{n}</text></g>)}{data.scatter.map(point => <a key={point.tmdb_id} href={'/students/films/' + point.tmdb_id} aria-label={point.title} onFocus={() => setHover(point.title)} onMouseEnter={() => setHover(point.title)}><circle cx={55 + point.brightness * 615} cy={310 - point.saturation * 285} r="4"><title>{point.title}: lightness {point.brightness}, colour intensity {point.saturation}</title></circle></a>)}</svg><p aria-live="polite">{hover}</p><details><summary>View chart data as a table</summary><div className="student-table-scroll"><table><thead><tr><th>Film</th><th>Lightness</th><th>Colour intensity</th></tr></thead><tbody>{data.scatter.map(p => <tr key={p.tmdb_id}><td><Link to={'/students/films/' + p.tmdb_id}>{p.title}</Link></td><td>{p.brightness}</td><td>{p.saturation}</td></tr>)}</tbody></table></div></details></section><div className="student-section-title"><h2>A vocabulary for <em>seeing.</em></h2></div><div className="technique-grid">{taxonomy.data?.map(t => <Link to={'/students/cards?technique=' + t.slug} key={t.slug}><p className="eyebrow">{t.category}</p><h3>{t.name}</h3><p>{t.description}</p><span>{t.automatic ? 'Measured frame observations' : 'Reviewed visual evidence'}</span></Link>)}</div></>
}

function Quiz() {
  const [category, setCategory] = useState('all')
  const [previous, setPrevious] = useState('')
  const [turn, setTurn] = useState(0)
  type Question = { question: { card_id: number | string; image_url: string; prompt: string; options: { slug: string; name: string }[] } | null }
  const client = useQueryClient()
  const quizQuery = (previousId: string, turnId: number) => ({ queryKey: ['students', 'quiz', category, turnId, previousId], staleTime: Infinity,
    queryFn: async ({ signal }: { signal: AbortSignal }) => {
      const data = await api<Question>(STUDENTS + 'quiz/?' + queryString({ category, previous: previousId }), { signal })
      if (data.question) { const image = new Image(); image.src = mediaUrl(data.question.image_url); await image.decode().catch(() => {}) }
      return data
    } })
  const quiz = useQuery(quizQuery(previous, turn))
  useEffect(() => {
    const current = quiz.data?.question?.card_id
    if (current !== undefined) void client.prefetchQuery(quizQuery(String(current), turn + 1))
  }, [quiz.data?.question?.card_id, category, turn, client])
  const answer = useMutation({ mutationFn: (slug: string) => api<{ correct: boolean; card: StudyCard }>(STUDENTS + 'quiz/', { method: 'POST', body: { card_id: quiz.data?.question?.card_id, answer: slug } }) })
  return <><div className="student-section-title"><h2>Train your <em>eye.</em></h2></div><div className="quiz-categories" role="group" aria-label="Quiz category">{[['all', 'All'], ['framing', 'Framing Techniques'], ['color', 'Colour']].map(([value, label]) => <Button key={value} className={category === value ? 'button-light' : 'button-outline'} aria-pressed={category === value} disabled={answer.isPending} onClick={() => { answer.reset(); setPrevious(''); setTurn(0); setCategory(value) }}>{label}</Button>)}</div><p className="student-note">Match the observation to its visual term. A frame can show several techniques; each question asks about one specific observation.</p>{quiz.isPending ? <Loading /> : quiz.isError ? <PageError error={quiz.error} /> : !quiz.data.question ? <p>No quiz frames are available yet.</p> : <div className="student-quiz"><img src={mediaUrl(quiz.data.question.image_url)} alt="Film frame for the visual observation question" /><h3>{quiz.data.question.prompt}</h3><div className="quiz-options">{quiz.data.question.options.map(option => <Button key={option.slug} className="button-outline" disabled={answer.isPending || answer.isSuccess} onClick={() => answer.mutate(option.slug)}>{option.name}</Button>)}</div>{answer.isError && <p role="alert">{errorMessage(answer.error)}</p>}{answer.data && <div className="quiz-answer" aria-live="polite"><strong>{answer.data.correct ? 'Correct.' : 'Look again: ' + answer.data.card.technique.name + '.'}</strong><p>{answer.data.card.explanation}</p><Link to={'/students/films/' + answer.data.card.tmdb_id}>{answer.data.card.title} · {timestamp(answer.data.card.timestamp)} ↗</Link><Button className="button-light" onClick={() => { answer.reset(); setTurn(n => n + 1); setPrevious(String(quiz.data?.question?.card_id || '')) }}>Next frame</Button></div>}</div>}</>
}

function Contribute() {
  const { user } = useSession()
  const [params] = useSearchParams()
  const [movie, setMovie] = useState(Number(params.get('movie')) || 0)
  const taxonomy = useStudentData<Technique[]>('techniques/')
  const mine = useStudentData<Page<Tag>>('tags/', !!user, user?.id)
  const client = useQueryClient()
  const mutation = useMutation({ mutationFn: (body: unknown) => api<Tag>(STUDENTS + 'tags/', { method: 'POST', body }), onSuccess: () => { void client.invalidateQueries({ queryKey: ['private', 'students', 'tags/'] }) } })
  if (!user) return <div className="student-community"><h2>Add what <em>you see.</em></h2><p>Signed-in members can contribute technique observations for any film in the catalog. Each submission is reviewed before publication.</p><Link className="button button-outline" to="/login?next=/students/contribute">Sign in to contribute</Link></div>
  return <><div className="student-section-title"><h2>Add what <em>you see.</em></h2></div><p className="student-note">Contributions cover the full film catalog, including films outside the analysis collection. Describe visible evidence, identify whether it comes from the film or its trailer, and add a source where possible. Submissions appear publicly after admin approval.</p><form className="student-contribution" onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); mutation.mutate({ tmdb_id: movie, technique: form.get('technique'), explanation: form.get('explanation'), source_url: form.get('source_url'), timestamp: form.get('timestamp') ? Number(form.get('timestamp')) : null, scope: form.get('scope') }) }}><ComparisonFilmPicker fullCatalog label="Film to annotate" value={movie} onChange={setMovie} /><label>Technique<select name="technique" required>{taxonomy.data?.map(t => <option key={t.slug} value={t.slug}>{t.name}</option>)}</select></label><label>Evidence comes from<select name="scope"><option value="film">The film</option><option value="trailer">The trailer</option></select></label><label>Your observation<textarea name="explanation" minLength={30} maxLength={2000} required rows={5} placeholder="Describe the visible evidence and where it appears…" /></label><div className="student-two-column"><label>Evidence link<input name="source_url" type="url" placeholder="https://…" /></label><label>Timestamp in seconds (optional)<input name="timestamp" type="number" min="0" max="100000" step="0.1" /></label></div><Button type="submit" className="button-light" disabled={!movie || mutation.isPending}>{mutation.isPending ? 'Submitting…' : 'Submit for review'}</Button>{mutation.isError && <p role="alert">{errorMessage(mutation.error)}</p>}{mutation.isSuccess && <p role="status">Your observation is awaiting review.</p>}</form><section className="student-community"><h3>Your submissions</h3>{mine.data?.results.map(tag => <div className="community-observation" key={tag.id}><strong>{tag.title} · {tag.technique.name}</strong><span>{tag.status}</span><p>{tag.explanation}</p></div>)}{!mine.data?.count && <p>You haven’t submitted an observation yet.</p>}</section></>
}

function Moderation() {
  const { user } = useSession()
  const [page, setPage] = useState(1)
  const queue = useStudentData<Page<Tag>>('moderation/?page=' + page, !!user?.is_staff, user?.id)
  const client = useQueryClient()
  const mutation = useMutation({ mutationFn: ({ id, status }: { id: number; status: string }) => api(STUDENTS + 'moderation/' + id + '/', { method: 'PATCH', body: { status } }), onSuccess: () => { void client.invalidateQueries({ queryKey: ['students'] }); void client.invalidateQueries({ queryKey: ['private', 'students'] }) } })
  if (!user?.is_staff) return <p>Admin access is required to review submissions.</p>
  return <><div className="student-section-title"><h2>Review <em>observations.</em></h2></div>{queue.isPending ? <Loading /> : queue.isError ? <PageError error={queue.error} /> : <>{!queue.data.count && <p>The review queue is empty.</p>}{queue.data.results.map(tag => <article className="moderation-card" key={tag.id}><h3>{tag.title} · {tag.technique.name}</h3><p>{tag.explanation}</p><p>{tag.scope}{tag.timestamp !== null && ' · ' + timestamp(tag.timestamp)}</p><EvidenceLink url={tag.source_url} /><div><Button className="button-light" disabled={mutation.isPending} onClick={() => mutation.mutate({ id: tag.id, status: 'approved' })}>Approve</Button><Button className="button-outline" disabled={mutation.isPending} onClick={() => mutation.mutate({ id: tag.id, status: 'rejected' })}>Reject</Button></div></article>)}<Pagination page={page} count={queue.data.count} onPage={setPage} /></>}{mutation.isError && <p role="alert">{errorMessage(mutation.error)}</p>}</>
}

export default function Students() {
  return <Routes><Route element={<StudentsLayout />}><Route index element={<Collection />} /><Route path="films/:id" element={<StudentDetail />} /><Route path="films/:id/gallery" element={<StudentGallery />} /><Route path="cards" element={<Cards />} /><Route path="compare" element={<Compare />} /><Route path="explore" element={<Explorer />} /><Route path="quiz" element={<Quiz />} /><Route path="contribute" element={<Contribute />} /><Route path="moderation" element={<Moderation />} /><Route path="*" element={<p>This study page could not be found. <Link to="/students">Back to the collection.</Link></p>} /></Route></Routes>
}
