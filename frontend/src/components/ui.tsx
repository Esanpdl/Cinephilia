import { motion, useReducedMotion } from 'motion/react'
import type { HTMLMotionProps } from 'motion/react'
import type { ReactNode } from 'react'
import { ArrowLeft, ArrowRight, RotateCcw, Star } from 'lucide-react'
import { errorMessage } from '../api/client'

/** Be UI-inspired spring press feedback; original styles for Cinephilia.
 * Reference: https://beui.dev/components/motion/button */
export function Button({ className = '', children, ...props }: HTMLMotionProps<'button'>) {
  const reduced = useReducedMotion()
  return <motion.button className={'button ' + className} whileTap={reduced ? undefined : { scale: 0.97 }} transition={{ type: 'spring', stiffness: 420, damping: 30 }} {...props}>{children}</motion.button>
}
export function PageError({ error, retry }: { error: unknown; retry?: () => void }) {
  return <div className="state-panel" role="alert"><span className="eyebrow">A brief intermission</span><h2>Something interrupted the picture.</h2><p>{errorMessage(error)}</p>{retry && <Button onClick={retry} className="button-outline"><RotateCcw size={16} /> Try again</Button>}</div>
}
export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return <div className="state-panel"><span className="empty-mark" aria-hidden="true">C.</span><h2>{title}</h2>{children}</div>
}
export function GridSkeleton({ count = 6 }: { count?: number }) {
  return <div className="film-grid" aria-label="Loading films" aria-busy="true">{Array.from({ length: count }, (_, i) => <div className="skeleton-card" key={i}><div className="skeleton poster-placeholder" /><div className="skeleton skeleton-line" /><div className="skeleton skeleton-line short" /></div>)}</div>
}
export function Pagination({ page, count, pageSize = 20, onPage, disabled = false }: { page: number; count: number; pageSize?: number; onPage: (page: number) => void; disabled?: boolean }) {
  const pages = Math.ceil(count / pageSize)
  if (pages <= 1) return null
  return <nav className="pagination" aria-label="Pagination">
    <Button className="button-outline" disabled={page <= 1 || disabled} onClick={() => onPage(page - 1)}><ArrowLeft size={16} /> Previous</Button>
    <form className="page-jump" onSubmit={event => { event.preventDefault(); const value = Number(new FormData(event.currentTarget).get('page')); if (Number.isInteger(value) && value >= 1 && value <= pages) onPage(value) }}>
      <label>Page <input key={`${page}-${pages}`} aria-label="Page number" name="page" type="number" min={1} max={pages} step={1} defaultValue={page} required disabled={disabled} /></label>
      <span>of {pages.toLocaleString()}</span>
    </form>
    <Button className="button-outline" disabled={page >= pages || disabled} onClick={() => onPage(page + 1)}>Next <ArrowRight size={16} /></Button>
  </nav>
}

export function StarRating({ value, max = 5, size = 15, className = '' }: { value: number; max?: number; size?: number; className?: string }) {
  const clamped = Math.max(0, Math.min(max, value))
  const rounded = Math.round(clamped * 2) / 2
  return (
    <span className={'star-rating-display ' + className} aria-label={`${value} out of ${max} stars`}>
      {Array.from({ length: max }, (_, index) => {
        const starIndex = index + 1
        const isFull = rounded >= starIndex
        const isHalf = !isFull && rounded >= starIndex - 0.5
        return (
          <span key={index} className="star-slot" style={{ position: 'relative', display: 'inline-flex', width: size, height: size }}>
            <Star size={size} className="star-empty" />
            {isFull ? (
              <Star size={size} fill="currentColor" className="star-filled" style={{ position: 'absolute', top: 0, left: 0 }} />
            ) : isHalf ? (
              <span className="star-half-clip" style={{ position: 'absolute', top: 0, left: 0, width: '50%', height: size, overflow: 'hidden' }}>
                <Star size={size} fill="currentColor" className="star-filled" />
              </span>
            ) : null}
          </span>
        )
      })}
    </span>
  )
}
