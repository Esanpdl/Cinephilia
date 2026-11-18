import type { Frame } from '../api/students'

const names: Record<string, string> = {
  extreme_close_up: 'Extreme close-up', close_up: 'Close-up', medium_close_up: 'Medium close-up',
  medium: 'Medium shot', full: 'Full shot', wide: 'Wide shot',
  'close-up': 'Close-up', 'wide-framing': 'Wide framing', 'deep-staging': 'Deep staging',
  symmetry: 'Symmetrical framing', 'negative-space': 'Negative space', silhouette: 'Silhouette',
  'frame-within-frame': 'Frame within a frame', 'low-key-lighting': 'Low-key lighting',
}

export function FrameTechniques({ frame }: { frame: Frame }) {
  const evidence = frame.technique_analysis
  if (!evidence) return null
  const labels = [...new Set([...(evidence.shot_scale ? [names[evidence.shot_scale]] : []),
    ...evidence.tags.map(tag => names[tag] || tag)])]
  if (evidence.source === 'model' && !labels.length) return <p className="frame-technique-empty">No confident technique suggestion</p>
  return <div className={'frame-techniques frame-techniques-' + evidence.source}>
    <span className="frame-technique-provenance" title={evidence.source === 'human' ? 'Labels reviewed by a person.' : 'An automatic suggestion; not independently verified.'}>
      {evidence.source === 'human' ? 'Human reviewed' : 'Model suggested'}
    </span>
    <span>{labels.length ? labels.join(' · ') : 'No positive technique label'}</span>
    {!evidence.shot_scale && <small>Framing unlabelled</small>}
  </div>
}
