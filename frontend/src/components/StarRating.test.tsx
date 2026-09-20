import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { StarRating } from './ui'

describe('StarRating', () => {
  it('renders 5 stars with proper full and half star increments for 4.5 rating', () => {
    const { container } = render(<StarRating value={4.5} />)
    const slots = container.querySelectorAll('.star-slot')
    expect(slots.length).toBe(5)

    // Full stars (first 4 slots) have .star-filled directly
    const fullStars = container.querySelectorAll('.star-slot > .star-filled')
    expect(fullStars.length).toBe(4)

    // Half star (5th slot) has .star-half-clip containing .star-filled
    const halfClips = container.querySelectorAll('.star-half-clip')
    expect(halfClips.length).toBe(1)
  })

  it('renders 5 full stars for a 5.0 rating', () => {
    const { container } = render(<StarRating value={5} />)
    const fullStars = container.querySelectorAll('.star-slot > .star-filled')
    expect(fullStars.length).toBe(5)
    const halfClips = container.querySelectorAll('.star-half-clip')
    expect(halfClips.length).toBe(0)
  })

  it('renders 5 empty stars for 0 rating', () => {
    const { container } = render(<StarRating value={0} />)
    const fullStars = container.querySelectorAll('.star-slot > .star-filled')
    expect(fullStars.length).toBe(0)
    const halfClips = container.querySelectorAll('.star-half-clip')
    expect(halfClips.length).toBe(0)
    const emptyStars = container.querySelectorAll('.star-empty')
    expect(emptyStars.length).toBe(5)
  })

  it('renders 1 half star and 4 empty stars for 0.5 rating', () => {
    const { container } = render(<StarRating value={0.5} />)
    const fullStars = container.querySelectorAll('.star-slot > .star-filled')
    expect(fullStars.length).toBe(0)
    const halfClips = container.querySelectorAll('.star-half-clip')
    expect(halfClips.length).toBe(1)
    const emptyStars = container.querySelectorAll('.star-empty')
    expect(emptyStars.length).toBe(5)
  })

  it('rounds continuous community ratings to nearest half star', () => {
    // 4.8 should round to 5.0 (5 full stars)
    const { container: c48 } = render(<StarRating value={4.8} />)
    expect(c48.querySelectorAll('.star-slot > .star-filled').length).toBe(5)
    expect(c48.querySelectorAll('.star-half-clip').length).toBe(0)

    // 4.3 should round to 4.5 (4 full stars + 1 half star)
    const { container: c43 } = render(<StarRating value={4.3} />)
    expect(c43.querySelectorAll('.star-slot > .star-filled').length).toBe(4)
    expect(c43.querySelectorAll('.star-half-clip').length).toBe(1)

    // 4.2 should round to 4.0 (4 full stars + 0 half stars)
    const { container: c42 } = render(<StarRating value={4.2} />)
    expect(c42.querySelectorAll('.star-slot > .star-filled').length).toBe(4)
    expect(c42.querySelectorAll('.star-half-clip').length).toBe(0)
  })

  it('clamps values below 0 and above max', () => {
    const { container: cNeg } = render(<StarRating value={-1} />)
    expect(cNeg.querySelectorAll('.star-slot > .star-filled').length).toBe(0)
    expect(cNeg.querySelectorAll('.star-half-clip').length).toBe(0)

    const { container: cOver } = render(<StarRating value={6} />)
    expect(cOver.querySelectorAll('.star-slot > .star-filled').length).toBe(5)
    expect(cOver.querySelectorAll('.star-half-clip').length).toBe(0)
  })
})

