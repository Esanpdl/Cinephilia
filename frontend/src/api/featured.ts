import { useQuery } from '@tanstack/react-query'
import { api } from './client'
import type { MovieDetail } from './types'

export const HIGHLIGHTS = { page_size: 6, ordering: 'rating', homepage: 'true' } as const

export const featuredMovieQuery = (seed?: string) => ({
  queryKey: ['featured', seed],
  staleTime: 0,
  gcTime: 0,
  queryFn: ({ signal }: { signal?: AbortSignal }) => {
    const url = '/api/v1/movies/featured/' + (seed ? `?seed=${encodeURIComponent(seed)}` : '')
    return api<MovieDetail>(url, { signal })
  },
})

/** Tonight's feature is randomly selected from the 500 film analysis movies each refresh. */
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
