import { Link } from 'react-router-dom'
import { ArrowUpRight } from 'lucide-react'
import type { Comparison } from '../api/students'
import { FrameTechniques } from './FrameTechniques'
import { mediaUrl } from '../api/students'

export function MatchedFramePairs({ comparison }: { comparison: Comparison }) {
  const matching = comparison.frame_matching
  return <section className="matched-frames" aria-labelledby="matched-frames-heading">
    <div className="student-section-title"><div><p className="eyebrow">A closer look</p><h2 id="matched-frames-heading">Frames in <em>conversation.</em></h2></div><span>{matching?.pairs.length || 0} matched pairs</span></div>
    <p className="student-note">Colour and framing receive equal weight, with each frame shown once.</p>
    {matching?.notice && <p role="status" className="student-note">{matching.notice}</p>}
    <div className="matched-frame-titles"><strong>{comparison.left.title}</strong><strong>{comparison.right.title}</strong></div>
    <ol className="matched-frame-list">{matching?.pairs.slice(0, 10).map((pair, index) => <li key={pair.left.image_url + pair.right.image_url}>
      <div className="matched-pair-meta"><span>Pair {String(index + 1).padStart(2, '0')}</span></div>
      <div className="matched-pair-images">{(['left', 'right'] as const).map(side => <a key={side} href={mediaUrl(pair[side].image_url)} target="_blank" rel="noreferrer" aria-label={`Enlarge ${comparison[side].title} frame in pair ${index + 1}`}><img src={mediaUrl(pair[side].image_url)} alt={`${comparison[side].title}, matched frame ${index + 1}`} loading="lazy" /><span>{comparison[side].title} <ArrowUpRight size={14} aria-hidden="true" /></span><FrameTechniques frame={pair[side]} /></a>)}</div>
    </li>)}</ol>
    <div className="matched-gallery-links">{[comparison.left, comparison.right].map(film => <Link key={film.tmdb_id} className="text-link" to={'/students/films/' + film.tmdb_id + '/gallery'}>Explore {film.title} gallery <ArrowUpRight size={14} /></Link>)}</div>
  </section>
}
