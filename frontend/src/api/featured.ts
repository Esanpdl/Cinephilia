import { useQuery } from '@tanstack/react-query'
import { api } from './client'
import type { MovieDetail } from './types'

export const HIGHLIGHTS = { page_size: 6, ordering: 'rating', homepage: 'true' } as const

const FEATURE_TTL = 5 * 60_000
function storedFeature(seed?: string): { film: MovieDetail; saved: number } | undefined {
  try {
    const saved = JSON.parse(sessionStorage.getItem('cinephilia-feature:' + (seed || 'tonight')) || 'null')
    if (saved && Number.isInteger(saved.film?.tmdb_id) && Number.isFinite(saved.saved) && Date.now() >= saved.saved && Date.now() - saved.saved < FEATURE_TTL) return saved
  } catch { /* Storage may be unavailable; the server also caches the feature. */ }
}
export const featuredMovieQuery = (seed?: string) => ({
  queryKey: ['featured', seed],
  staleTime: FEATURE_TTL,
  gcTime: FEATURE_TTL,
  initialData: () => storedFeature(seed)?.film,
  initialDataUpdatedAt: () => storedFeature(seed)?.saved,
  queryFn: async ({ signal }: { signal?: AbortSignal }) => {
    const cached = storedFeature(seed)
    if (cached) return cached.film
    const url = '/api/v1/movies/featured/' + (seed ? `?seed=${encodeURIComponent(seed)}` : '')
    const film = await api<MovieDetail>(url, { signal })
    try { sessionStorage.setItem('cinephilia-feature:' + (seed || 'tonight'), JSON.stringify({ film, saved: Date.now() })) } catch { /* Cache remains in memory. */ }
    return film
  },
})

/** Keep the analysis collection's feature stable through navigation and reloads for five minutes. */
export function useFeaturedFilm() {
  const query = useQuery(featuredMovieQuery())
  return {
    data: query.data,
    isPending: query.isPending,
    isError: query.isError,
    error: query.error,
    refetch: () => query.refetch(),
  }
}
