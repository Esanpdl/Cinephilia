import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ExternalLink } from 'lucide-react'
import { type Tag, timestamp, useStudentData } from '../api/students'
import type { Page } from '../api/types'
import { PageError, Pagination } from './ui'
import '../techniques.css'

export function EvidenceLink({ url }: { url: string }) {
  let safe = false
  try { safe = ['http:', 'https:'].includes(new URL(url).protocol) } catch { /* Invalid evidence is never linked. */ }
  return safe ? <a className="text-link technique-evidence" href={url} target="_blank" rel="noopener noreferrer">View evidence <ExternalLink size={14} aria-hidden="true" /></a> : null
}

export function TechniqueEvidence({ tag }: { tag: Tag }) {
  return <>
    <p className="technique-scope">{tag.scope === 'trailer' ? 'Trailer observation' : 'Film observation'}{tag.timestamp !== null && ` · ${timestamp(tag.timestamp)}`}</p>
    <p className="technique-explanation">{tag.explanation}</p>
    <EvidenceLink url={tag.source_url} />
  </>
}

export default function ReviewedTechniques({ movieId }: { movieId: number }) {
  const [page, setPage] = useState(1)
  const tags = useStudentData<Page<Tag>>(`films/${movieId}/tags/?page=${page}`)
  const approved = tags.data?.results.filter(tag => tag.status === 'approved') ?? []
  return <section className="reviewed-techniques" aria-labelledby="reviewed-techniques-heading">
    <div className="section-heading compact"><div><p className="eyebrow">A closer look</p><h2 id="reviewed-techniques-heading">Reviewed cinematic <em>techniques.</em></h2></div></div>
    <p className="technique-intro">Community observations reviewed by our curators. Trailer observations describe the cited footage only.</p>
    {tags.isPending ? <p role="status">Loading reviewed observations…</p> : tags.isError ? <PageError error={tags.error} retry={() => { void tags.refetch() }} /> : <>
      {!approved.length && <p className="technique-empty">No reviewed observations yet. <Link className="text-link" to="/students/contribute">Contribute an observation</Link></p>}
      <div className="technique-grid">{approved.map(tag => <article className="technique-observation" key={tag.id}><span className="technique-category">{tag.technique.category}</span><h3>{tag.technique.name}</h3><TechniqueEvidence tag={tag} /></article>)}</div>
      <Pagination page={page} count={tags.data?.count ?? 0} onPage={setPage} />
    </>}
  </section>
}
