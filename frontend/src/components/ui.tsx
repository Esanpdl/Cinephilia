import { motion, useReducedMotion } from 'motion/react'
import type { HTMLMotionProps } from 'motion/react'
import type { ReactNode } from 'react'
import { ArrowLeft, ArrowRight, RotateCcw } from 'lucide-react'
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
    <span>Page <strong>{page}</strong> of {pages.toLocaleString()}</span>
    <Button className="button-outline" disabled={page >= pages || disabled} onClick={() => onPage(page + 1)}>Next <ArrowRight size={16} /></Button>
  </nav>
}
