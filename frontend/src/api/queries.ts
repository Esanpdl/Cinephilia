import { queryOptions } from '@tanstack/react-query'
import { api, ApiError, queryString } from './client'
import type { Genre, MovieDetail, MovieSummary, Page, Rating, Recommendations, User, WatchlistItem } from './types'

export const sessionQuery = () => queryOptions({
  queryKey: ['session'], retry: false, staleTime: 60_000,
  queryFn: async ({ signal }) => {
    try { return await api<User>('/api/v1/users/me/', { signal }) }
    catch (error) { if (error instanceof ApiError && error.status === 403) return null; throw error }
  },
})
export const moviesQuery = (params: Record<string, string | number | undefined>) => queryOptions({
  queryKey: ['movies', params], staleTime: 5 * 60_000,
  queryFn: ({ signal }) => api<Page<MovieSummary>>('/api/v1/movies/?' + queryString(params), { signal }),
})
export const movieQuery = (id: number) => queryOptions({
  queryKey: ['movie', id], staleTime: 5 * 60_000,
  queryFn: ({ signal }) => api<MovieDetail>('/api/v1/movies/' + id + '/', { signal }),
})
export const genresQuery = () => queryOptions({
  queryKey: ['genres'], staleTime: 60 * 60_000,
  queryFn: ({ signal }) => api<Genre[]>('/api/v1/movies/genres/', { signal }),
})
export const recommendationsQuery = (userId: number) => queryOptions({
  queryKey: ['private', userId, 'recommendations'], staleTime: 60_000,
  queryFn: ({ signal }) => api<Recommendations>('/api/v1/recommendations/?limit=24', { signal }),
})
export const libraryQuery = (userId: number, tab: 'watchlist' | 'ratings', page: number) => queryOptions({
  queryKey: ['private', userId, tab, page], staleTime: 60_000,
  queryFn: ({ signal }) => api<Page<WatchlistItem | Rating>>('/api/v1/ratings/' + (tab === 'watchlist' ? 'watchlist/' : '') + '?page=' + page, { signal }),
})
export const filmStateQuery = (userId: number, movieId: number, kind: 'rating' | 'watchlist') => queryOptions({
  queryKey: ['private', userId, kind, 'film', movieId], staleTime: 30_000,
  queryFn: async ({ signal }) => {
    try { return await api<Rating | WatchlistItem>('/api/v1/ratings/' + (kind === 'watchlist' ? 'watchlist/' : '') + movieId + '/', { signal }) }
    catch (error) { if (error instanceof ApiError && error.status === 404) return null; throw error }
  },
})
