import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ArrowUpRight, RefreshCw } from 'lucide-react'
import { useSession } from '../auth/SessionProvider'
import { recommendationsQuery } from '../api/queries'
import { FilmCard } from '../components/FilmCard'
import { Button, EmptyState, GridSkeleton, PageError } from '../components/ui'

export default function ForYou() {
  const { user } = useSession()
  const [refreshSeed, setRefreshSeed] = useState<string | undefined>(undefined)
  const recommendations = useQuery(recommendationsQuery(user!.id, refreshSeed))
  const personal = recommendations.data && recommendations.data.profile.mode !== 'popularity'
  return <div className="section-wrap for-you-page">
    <div className="page-heading"><p className="eyebrow">A conversation with your taste</p><h1>Your next <em>obsession.</em></h1><p>{personal ? 'Shaped by the films you rate. Open to something unexpected.' : 'A good film is a good beginning. Rate a few to make this page your own.'}</p></div>
    <div className="recommendation-note"><div><span className="note-marker" aria-hidden="true">✳</span><p>{personal ? 'Inspired by your ratings' : 'Let us get to know your taste'}<small>{personal ? 'Already-rated films and your watchlist are kept out of this selection.' : 'For now, explore popular films from the collection. Your ratings will guide what comes next.'}</small></p></div><Link to="/browse" className="text-link">Find a film to rate <ArrowUpRight size={17} /></Link></div>
    <div className="results-heading"><span>{personal ? 'Selected for you' : 'A place to start'}</span><Button className="muted-action" disabled={recommendations.isFetching} onClick={() => { setRefreshSeed(String(Date.now())) }}><RefreshCw size={14} className={recommendations.isFetching ? 'spin' : ''} /> Refresh selection</Button></div>
    {recommendations.isPending ? <GridSkeleton count={12} /> : recommendations.isError ? <PageError error={recommendations.error} retry={() => { void recommendations.refetch() }} /> : recommendations.data.results.length ? <div className="film-grid">{recommendations.data.results.map(entry => <FilmCard key={entry.movie.tmdb_id} movie={entry.movie} />)}</div> : <EmptyState title="You've reached the end of this reel."><p>Explore the collection or revisit your watchlist.</p><Link to="/collection" className="button button-outline">Your collection</Link></EmptyState>}
  </div>
}
