export interface Genre { tmdb_id: number; name: string }
export interface MovieSummary {
  tmdb_id: number; title: string; release_date: string | null; original_language: string;
  vote_average: string; vote_count: number; genres: Genre[]; poster_url: string | null;
  trailer_embed_url: string | null; is_technique_source: boolean; is_homepage_eligible: boolean;
}
export interface Person { tmdb_id: number; name: string }
export interface MovieDetail extends MovieSummary {
  imdb_id: string; original_title: string; overview: string; tagline: string; runtime: number | null;
  cast: (Person & { character: string; order: number | null })[]; directors: Person[];
  backdrop_url: string | null; trailer_key: string; trailer_name: string; trailer_official: boolean;
  letterboxd_embed_url: string;
  source_tags: string[]; catalog_rank: number | null;
}
export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[] }
export interface Profile { display_name: string; bio: string; is_film_student: boolean; favorite_genres: number[] }
export interface User { id: number; username: string; email: string; is_staff?: boolean; profile: Profile }
export interface SessionResponse { user: User; csrf_token: string }
export interface Rating { movie: MovieSummary; score: number; stars: number; created_at: string; updated_at: string }
export interface Review { id: number; author: string; stars: number; text: string; updated_at: string; review_hidden?: boolean }
export interface WatchlistItem { movie: MovieSummary; created_at: string }
export interface Recommendations {
  results: { movie: MovieSummary; score: number; components: { content: number | null; collaborative: number | null; popularity: number }; effective_weights: Record<string, number> }[];
  profile: { rated_movies: number; content_seed_count: number; collaborative_history_count: number; collaborative_available: boolean; mode: 'hybrid' | 'content' | 'collaborative' | 'popularity' };
  models: { content: boolean; collaborative: boolean }; candidate_count: number;
}
