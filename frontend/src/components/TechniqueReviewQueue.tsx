import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Check, NotebookPen, X } from 'lucide-react'
import { api, ApiError, errorMessage } from '../api/client'
import { STUDENTS, type Tag, useStudentData } from '../api/students'
import type { Page } from '../api/types'
import { Button, PageError, Pagination } from './ui'
import { TechniqueEvidence } from './ReviewedTechniques'

export default function TechniqueReviewQueue({ userId }: { userId: number }) {
  const [page, setPage] = useState(1)
  const [notes, setNotes] = useState<Record<number, string>>({})
  const [message, setMessage] = useState('')
  const cache = useQueryClient()
  const queue = useStudentData<Page<Tag>>(`moderation/?page=${page}`, true, userId)
  const refresh = () => {
    void cache.invalidateQueries({ queryKey: ['students'] })
    void cache.invalidateQueries({ queryKey: ['private', 'students'] })
    void cache.invalidateQueries({ queryKey: ['movie'] })
  }
  const decision = useMutation({
    mutationFn: ({ tag, status }: { tag: Tag; status: 'approved' | 'rejected' }) => api<Tag>(`${STUDENTS}moderation/${tag.id}/`, { method: 'PATCH', body: { status, note: notes[tag.id] ?? '', expected_status: 'pending' } }),
    onSuccess: (_, { tag, status }) => {
      setMessage(`${tag.technique.name} for ${tag.title} ${status}.`)
      setNotes(previous => { const next = { ...previous }; delete next[tag.id]; return next })
      if (page > 1 && queue.data?.results.length === 1) setPage(page - 1)
      refresh()
    },
    onError: error => { if (error instanceof ApiError && error.status === 409) refresh() },
  })
  return <section className="admin-review-section" id="technique-review" aria-labelledby="technique-review-heading">
    <div className="admin-section-header"><div><p className="eyebrow"><NotebookPen size={16} aria-hidden="true" /> The review desk</p><h2 id="technique-review-heading">Cinematic technique submissions</h2><p>Read the observation and check its evidence before publishing it on the film page.</p></div><span className="admin-queue-count">{queue.data?.count ?? '—'} pending</span></div>
    {message && <p role="status" className="admin-review-feedback">{message}</p>}
    {decision.isError && <p role="alert" className="inline-error">{errorMessage(decision.error)}</p>}
    {queue.isPending ? <p role="status">Loading submissions…</p> : queue.isError ? <PageError error={queue.error} retry={() => { void queue.refetch() }} /> : <>
      {!queue.data?.results?.length && <p className="admin-review-empty">All caught up. New submissions will appear here for review.</p>}
      {queue.data?.results?.map(tag => <article key={tag.id} className="admin-review-card"><div className="admin-review-card-heading"><div><Link className="text-link" to={`/films/${tag.tmdb_id}`}>{tag.title}</Link><h3>{tag.technique.name}</h3></div><span className="technique-category">{tag.technique.category}</span></div><TechniqueEvidence tag={tag} /><label className="field">Review note for {tag.technique.name} (optional)<textarea value={notes[tag.id] ?? ''} maxLength={2000} rows={2} onChange={event => setNotes(previous => ({ ...previous, [tag.id]: event.target.value }))} /></label><div className="admin-review-actions"><Button className="button-light" disabled={decision.isPending} onClick={() => decision.mutate({ tag, status: 'approved' })}><Check size={16} aria-hidden="true" /> Approve</Button><Button className="button-outline" disabled={decision.isPending} onClick={() => decision.mutate({ tag, status: 'rejected' })}><X size={16} aria-hidden="true" /> Reject</Button></div></article>)}
      <Pagination page={page} count={queue.data?.count ?? 0} onPage={setPage} disabled={decision.isPending} />
    </>}
  </section>
}
