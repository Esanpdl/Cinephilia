import { useId, useState } from 'react'
import type { Palette } from '../api/students'

// Largest-remainder rounding keeps the displayed percentages at exactly 100.0%.
export function palettePercentages(palette: Palette) {
  const total = palette.reduce((sum, colour) => sum + Math.max(0, colour.weight), 0)
  if (!total) return palette.map(() => 0)
  const exact = palette.map(colour => Math.max(0, colour.weight) / total * 1000)
  const tenths = exact.map(Math.floor)
  const order = exact.map((value, i) => ({ i, remainder: value - tenths[i] })).sort((a, b) => b.remainder - a.remainder || a.i - b.i)
  const missing = 1000 - tenths.reduce((sum, value) => sum + value, 0)
  order.slice(0, missing).forEach(({ i }) => { tenths[i]++ })
  return tenths.map(value => value / 10)
}

export function FilmPalette({ palette, title }: { palette: Palette; title: string }) {
  const id = useId()
  const [active, setActive] = useState<number | null>(null)
  const total = palette.reduce((sum, colour) => sum + colour.weight, 0)
  if (!palette.length || total <= 0) return null
  const percentages = palettePercentages(palette)
  let start = -Math.PI / 2
  return <section className="film-palette" aria-labelledby={id}>
    <div className="film-palette-heading"><h3 id={id}>The colour distribution</h3><span>{palette.length} representative tones</span></div>
    <div className="film-palette-layout">
      <svg className="film-palette-pie" viewBox="0 0 220 220" role="img" aria-label={`${title}: ${palette.length} representative colours. Percentages are listed alongside the chart.`}>
        {palette.map((colour, index) => {
          const angle = colour.weight / total * Math.PI * 2
          const end = start + angle
          const point = (a: number) => `${110 + 102 * Math.cos(a)},${110 + 102 * Math.sin(a)}`
          const d = `M110,110 L${point(start)} A102,102 0 ${angle > Math.PI ? 1 : 0},1 ${point(end)} Z`
          start = end
          const style = { opacity: active !== null && active !== index ? .35 : 1 }
          return angle >= Math.PI * 2 - 1e-9
            ? <circle key={index} cx="110" cy="110" r="102" fill={colour.hex} style={style}><title>{colour.hex}: {percentages[index].toFixed(1)}%</title></circle>
            : <path key={index} d={d} fill={colour.hex} style={style}><title>{colour.hex}: {percentages[index].toFixed(1)}%</title></path>
        })}
      </svg>
      <ol className="film-palette-legend">{palette.map((colour, index) => <li key={index}>
        <button type="button" aria-pressed={active === index} onClick={() => setActive(active === index ? null : index)} onMouseEnter={() => setActive(index)} onMouseLeave={() => setActive(null)} onFocus={() => setActive(index)} onBlur={() => setActive(null)} aria-label={`Highlight ${colour.hex}, ${percentages[index].toFixed(1)} percent`}>
          <span className="film-palette-swatch" style={{ backgroundColor: colour.hex }} aria-hidden="true" /><span>{colour.hex.toUpperCase()}</span><strong>{percentages[index].toFixed(1)}%</strong>
        </button>
      </li>)}</ol>
    </div>
    <p className="student-note">Every pixel contributes; each frame has equal weight. The slices show colour coverage across the supplied frames, including gallery exclusions.</p>
  </section>
}
