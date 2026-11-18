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
  community_rating: number | null; community_rating_count: number;
}
export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[] }
export type OnboardingStatus = 'not_required' | 'pending' | 'completed'
export interface Profile { display_name: string; bio: string; is_film_student: boolean; favorite_genres: number[]; onboarding_status?: OnboardingStatus; watchlist_public?: boolean; email_public?: boolean }
export interface PreferenceOption { id: number | string; name: string; detail?: string }
export interface TastePreferences {
  favorite_genres: number[]; favorite_actors: number[]; favorite_directors: number[]; favorite_movies: number[]; favorite_eras: string[];
  exploration: 'familiar' | 'balanced' | 'adventurous'; language_openness: 'any' | 'prefer'; preferred_languages: string[];
  onboarding_status: OnboardingStatus;
  selections: { genres: PreferenceOption[]; actors: PreferenceOption[]; directors: PreferenceOption[]; movies: PreferenceOption[] };
}
export type PreferenceInput = Omit<TastePreferences, 'selections' | 'onboarding_status'>
export interface User { id: number; username: string; email: string; is_staff: boolean; is_superuser?: boolean; is_main_admin?: boolean; profile: Profile }
export interface AdminUser {
  id: number; username: string; email: string; is_staff: boolean;
  is_superuser: boolean; is_main_admin: boolean; is_active: boolean; display_name: string;
  is_film_student: boolean; date_joined: string; last_login: string | null;
}
export interface AdminStats {
  total_users: number; total_admins: number; total_movies: number; total_ratings: number;
}
export interface SessionResponse { user: User; csrf_token: string }
export interface Rating { movie: MovieSummary; score: number; stars: number; created_at: string; updated_at: string }
export interface Review { id: number; author: string; author_id?: number; stars: number; text: string; updated_at: string; review_hidden?: boolean }
export interface PublicProfile { id: number; username: string; display_name: string; bio: string; is_film_student: boolean; favorite_genres: Genre[]; watchlist_public: boolean; email?: string }
export interface WatchlistItem { movie: MovieSummary; created_at: string }
export interface Recommendations {
  results: { movie: MovieSummary; score: number; components: { content: number | null; collaborative: number | null; popularity: number; preferences?: number | null }; effective_weights: Record<string, number>; reasons?: string[] }[];
  profile: { rated_movies: number; watchlist_movies?: number; preference_weight?: number; content_seed_count: number; collaborative_history_count: number; collaborative_available: boolean; mode: 'hybrid' | 'content' | 'collaborative' | 'popularity' | 'preferences' };
  models: { content: boolean; collaborative: boolean }; candidate_count: number;
}
