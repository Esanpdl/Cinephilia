import { useQuery } from '@tanstack/react-query'
import { api } from './client'
import type { PlaybackSource } from './playback'

export const STUDENTS = '/api/v1/cinematography/'
export function useStudentData<T>(path: string, enabled = true, account?: number) {
  const queryKey = account ? ['private', 'students', path, account] : ['students', path]
  return useQuery({ queryKey, queryFn: ({ signal }) => api<T>(STUDENTS + path, { signal }), enabled, staleTime: 60_000 })
}
export type Palette = { hex: string; weight: number }[]
export interface Technique { slug: string; name: string; category: string; description: string; automatic: boolean }
export interface Metrics { brightness: number; saturation: number; contrast: number; colored_pixel_fraction: number }
export interface Frame { image_url: string; timestamp: number | null; metrics: Metrics; text_excluded_fraction?: number; text_regions?: number[][][]; technique_analysis?: { source: 'human' | 'model'; shot_scale: string | null; tags: string[] } }
export interface StudyCard { id: number | string; tmdb_id: number; title: string; technique: Technique; timestamp: number | null; image_url: string; explanation: string; evidence: string; source_url: string }
export interface StudentFilm { tmdb_id: number; title: string; year: number | null; selection_rank: number; status: string; reason: string; color_mode: string; palette: Palette; preview: string | null; poster_url?: string | null; palette_similarity?: number | null; style_similarity?: Comparison['style_similarity']; shared_observations?: string[] }
export interface Motion { status: string; retained_pairs?: number; mean_percent_diagonal_per_second?: number | null; scope?: string; limitations?: string; samples?: { timestamp: number | null; mean_percent_diagonal_per_second: number }[] }
export interface Analysis extends StudentFilm { motion?: Motion; frames: Frame[]; metrics: Metrics; study_cards: StudyCard[]; source_url: string; playback_sources: PlaybackSource[]; source_title: string; duration: number | null; color_evidence: string; scope: string; quality: { source_kind?: string; display_count?: number; display_excluded_count?: number; retained_count?: number; sample_count?: number; screening?: string; text_masking?: { mean_excluded_fraction: number; frames_with_detected_text: number; limitations: string } } }
export interface Comparison { left: Analysis; right: Analysis; frame_matching?: { pairs: { left: Frame; right: Frame; similarity: number }[]; scope: string; notice: string }; palette_similarity: number | null; metric_difference: Record<string, number>; shared_observations: string[]; similarity_scope: string; left_observations: Tag[]; right_observations: Tag[]; style_similarity: { score: number | null; components: { palette: number | null; techniques: number | null; model_suggestions?: number | null }; weights: Record<string, number>; scope: string } }
export interface Overview { selected: number; status_counts: Record<string, number>; color_counts: Record<string, number>; scatter: (Metrics & { tmdb_id: number; title: string })[]; technique_counts: { technique__name: string; count: number }[]; reviewed_technique_counts: { technique__name: string; technique__slug: string; count: number }[]; scope: string }
export interface Tag { id: number; tmdb_id: number; title: string; technique: Technique; explanation: string; source_url: string; timestamp: number | null; scope: string; status: string }
export const colorLabel = (mode: string) => ({ black_and_white: 'Black & white', color: 'Color', mixed: 'Mixed color / monochrome', unknown: 'Not yet classified' }[mode] || mode)
export const statusLabel = (status: string) => ({ ready: 'Analysis available', review: 'Source under review', missing: 'Source video unavailable', failed: 'Analysis pending' }[status] || status)
export const timestamp = (value: number | null) => value === null ? 'Still frame' : Math.floor(value / 60) + ':' + String(Math.floor(value % 60)).padStart(2, '0')
export const mediaUrl = (path: string) => (import.meta.env.VITE_API_ORIGIN || '').replace(/\/$/, '') + path
