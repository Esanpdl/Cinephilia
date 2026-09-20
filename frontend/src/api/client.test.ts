import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, resetCsrf } from './client'
import { safeNext } from '../auth/navigation'
import { featuredMovieQuery } from './featured'
import { recommendationsQuery } from './queries'

/** Protocol-only fixtures. No fabricated film metadata or model results. */
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
beforeEach(() => { resetCsrf(); vi.restoreAllMocks() })

describe('Session API transport', () => {
  it('bootstraps CSRF and uses the rotated token after authentication', async () => {
    const fetcher = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(json({ csrf_token: 'before-login' }))
      .mockResolvedValueOnce(json({ csrf_token: 'after-login' }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    await api('/api/v1/users/login/', { method: 'POST', body: {} })
    await api('/api/v1/users/logout/', { method: 'POST' })
    expect(fetcher.mock.calls[1][1]?.headers).toMatchObject({ 'X-CSRFToken': 'before-login' })
    expect(fetcher.mock.calls[2][1]?.headers).toMatchObject({ 'X-CSRFToken': 'after-login' })
    expect(fetcher.mock.calls.every(call => call[1]?.credentials === 'include')).toBe(true)
  })
  it('retries a rejected CSRF request once, using a fresh token', async () => {
    const fetcher = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(json({ csrf_token: 'expired' }))
      .mockResolvedValueOnce(json({ detail: 'CSRF Failed: token incorrect' }, 403))
      .mockResolvedValueOnce(json({ csrf_token: 'fresh' }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    await api('/api/v1/ratings/238/', { method: 'DELETE' })
    expect(fetcher).toHaveBeenCalledTimes(4)
    expect(fetcher.mock.calls[3][1]?.headers).toMatchObject({ 'X-CSRFToken': 'fresh' })
  })
  it('does not retry a write after a network failure', async () => {
    const fetcher = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(json({ csrf_token: 'token' })).mockRejectedValueOnce(new TypeError('network'))
    await expect(api('/api/v1/users/login/', { method: 'POST', body: {} })).rejects.toThrow()
    expect(fetcher).toHaveBeenCalledTimes(2)
  })
  it('rejects external paths before sending any credentials', async () => {
    const fetcher = vi.spyOn(globalThis, 'fetch')
    await expect(api('https://untrusted.example/api')).rejects.toThrow('Expected')
    expect(fetcher).not.toHaveBeenCalled()
  })
  it('notifies the app when its session has expired', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(json({ detail: 'Authentication credentials were not provided.' }, 403))
    const listener = vi.fn()
    window.addEventListener('cinephilia:session-expired', listener)
    await expect(api('/api/v1/users/me/')).rejects.toBeInstanceOf(ApiError)
    expect(listener).toHaveBeenCalledOnce()
    window.removeEventListener('cinephilia:session-expired', listener)
  })
  it('sends the cancellation signal through to fetch', async () => {
    const fetcher = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json({}))
    const controller = new AbortController()
    await api('/api/v1/movies/', { signal: controller.signal })
    expect(fetcher.mock.calls[0][1]?.signal).toBe(controller.signal)
  })
})
describe('Post-login navigation', () => {
  it('keeps valid local return paths', () => { expect(safeNext('/films/238')).toBe('/films/238') })
  it('rejects external URLs, protocol-relative URLs, backslashes, and auth loops', () => {
    for (const value of ['https://example.com', '//example.com', '/\\example.com', '/login', '/register', null]) expect(safeNext(value)).toBe('/for-you')
  })
})

describe('Featured and recommendation queries', () => {
  it('featuredMovieQuery requests /api/v1/movies/featured/', async () => {
    const fetcher = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json({ tmdb_id: 278, title: 'The Shawshank Redemption' }))
    const query = featuredMovieQuery()
    expect(query.queryKey).toEqual(['featured', undefined])
    expect(query.staleTime).toBe(0)
    await query.queryFn({})
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/movies/featured/')
  })

  it('featuredMovieQuery passes seed parameter when provided', async () => {
    const fetcher = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json({ tmdb_id: 278, title: 'The Shawshank Redemption' }))
    const query = featuredMovieQuery('seed123')
    expect(query.queryKey).toEqual(['featured', 'seed123'])
    await query.queryFn({})
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/movies/featured/?seed=seed123')
  })

  it('recommendationsQuery passes refresh_seed when provided', async () => {
    const fetcher = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json({ results: [] }))
    const query = recommendationsQuery(1, 'seed456')
    expect(query.queryKey).toEqual(['private', 1, 'recommendations', 'seed456', 0])
    await (query.queryFn as any)({})
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/recommendations/?limit=24&refresh_seed=seed456')
  })

  it('recommendationsQuery omits refresh_seed on initial load', async () => {
    const fetcher = vi.spyOn(globalThis, 'fetch').mockResolvedValue(json({ results: [] }))
    const query = recommendationsQuery(1)
    expect(query.queryKey).toEqual(['private', 1, 'recommendations', undefined, 0])
    await (query.queryFn as any)({})
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/recommendations/?limit=24')
  })
})
