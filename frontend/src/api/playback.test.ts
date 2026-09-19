import { describe, expect, it } from 'vitest'
import { playbackAt } from './playback'

describe('combined analysis timestamps map to original YouTube clips', () => {
  const parts = [
    { start: 0, end: 135.44, title: 'First clip', source_url: 'https://www.youtube.com/watch?v=pTKfhyj2neg' },
    { start: 135.44, end: 338.685, title: 'Second clip', source_url: 'https://www.youtube.com/watch?v=66gdMLbiS8Y' },
    { start: 338.685, end: 482.726, title: 'Third clip', source_url: '' },
  ]
  it('seeks inside the original clip rather than using the combined timestamp', () => {
    expect(playbackAt(parts, 150)?.embed).toBe('https://www.youtube-nocookie.com/embed/66gdMLbiS8Y?start=14')
    expect(playbackAt(parts, 135.44)?.embed).toContain('66gdMLbiS8Y?start=0')
    expect(playbackAt(parts, 135.43)?.embed).toContain('pTKfhyj2neg?start=135')
  })
  it('does not substitute another clip when the correct source link is missing', () => {
    expect(playbackAt(parts, 350)?.embed).toBe('')
    expect(playbackAt(parts, 350)?.title).toBe('Third clip')
    expect(playbackAt(parts, 500)).toBeNull()
  })
  it('handles normal single-video timestamps and rejects untrusted embed hosts', () => {
    expect(playbackAt([parts[0]], 30)?.embed).toContain('?start=30')
    expect(playbackAt([{ ...parts[0], source_url: 'https://example.com/?v=pTKfhyj2neg' }], 30)?.embed).toBe('')
  })
})
