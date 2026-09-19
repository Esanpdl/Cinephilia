import { useQuery } from '@tanstack/react-query'
import { movieQuery, moviesQuery } from './queries'

export const HIGHLIGHTS = { page_size: 6, ordering: 'rating', homepage: 'true' } as const

/** Preserve rating order inside the approved homepage pool. */
export function useFeaturedFilm() {
  const catalog = useQuery(moviesQuery(HIGHLIGHTS))
  const id = catalog.data?.results[0]?.tmdb_id
  const detail = useQuery({ ...movieQuery(id || 0), enabled: !!id })
  return { data: detail.data, isPending: catalog.isPending || (!!id && detail.isPending), isError: catalog.isError || detail.isError, error: catalog.error || detail.error, refetch: () => catalog.isError ? catalog.refetch() : detail.refetch() }
}
