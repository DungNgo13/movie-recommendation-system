import React, { useState, useEffect, useMemo } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { getLocalizedTitle } from '../utils/localizedMovie';
import type { AppLanguage } from '../i18n/languageStorage';
import MovieCard from '../components/MovieCard';
import ContinueWatchingCard from '../components/ContinueWatchingCard';
import RecommendationCard from '../components/RecommendationCard';
import SkeletonCard from '../components/SkeletonCard';
import ErrorMessage from '../components/ErrorMessage';
import { useMovies } from '../hooks/useMovies';
import { useFavorites } from '../hooks/useFavorites';
import { useAuth } from '../hooks/useAuthHook';
import {
  getWatchHistory,
  getGuestWatchHistory,
  isWatchCompleted,
  GUEST_HISTORY_EVENT,
} from '../services/continueWatchingService';
import type { HistoryItem } from '../services/continueWatchingService';
import { getRecommendations } from '../services/recommendationService';
import type { RecommendedMovie } from '../services/recommendationService';
import type { MovieFilters } from '../services/movieService';
import type { MovieListItem } from '../models';

type SortOption = 'title-asc' | 'title-desc' | 'year-desc' | 'year-asc';

const DEBOUNCE_MS = 500;
const SKELETON_COUNT = 12;

/** Pick a random hero movie from those that have a backdrop image. */
const pickHeroMovie = (movies: MovieListItem[]): MovieListItem | null => {
  const withBackdrop = movies.filter((m) => m.backdrop_url);
  if (withBackdrop.length === 0) return movies[0] ?? null;
  return withBackdrop[Math.floor(Math.random() * withBackdrop.length)];
};

/** Guest CW item: guest entry enriched with movie metadata from catalog. */
interface GuestContinueItem extends MovieListItem {
  playback_position_seconds: number;
  progress_percent: number;
  is_completed: boolean;
  updated_at: string;
}

const HomePage: React.FC = () => {
  const { t, i18n } = useTranslation(['movies', 'recommendation']);
  const { isFavorite, toggleFavorite } = useFavorites();
  const { user } = useAuth();
  const location = useLocation();
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [recommendations, setRecommendations] = useState<RecommendedMovie[]>([]);
  const [guestEventVersion, setGuestEventVersion] = useState(0);

  // Search / Filter / Sort state
  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [genreFilter, setGenreFilter] = useState('');
  const [yearFilter, setYearFilter] = useState<number | null>(null);
  const [sortOption, setSortOption] = useState<SortOption>('title-asc');

  // Debounce the search input: only update debouncedSearch after 500ms of inactivity
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchInput.trim());
    }, DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [searchInput]);

  // Build filter object for the hook (server-side filtering)
  const filters: MovieFilters = useMemo(() => ({
    search: debouncedSearch || undefined,
    genre: genreFilter || undefined,
    year: yearFilter,
  }), [debouncedSearch, genreFilter, yearFilter]);

  const { movies, loading, error } = useMovies(1, 100, filters);

  // Pick hero movie once when movies first load (unfiltered).
  // The effect is idempotent: it only calls setHeroMovie when heroMovie is
  // still null, so it fires exactly once and cannot cascade.
  const [heroMovie, setHeroMovie] = useState<MovieListItem | null>(null);
  useEffect(() => {
    if (movies.length > 0 && !heroMovie) {
      // Idempotent: fires once (heroMovie goes from null → value), then the
      // guard prevents further calls. No cascading renders possible.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setHeroMovie(pickHeroMovie(movies));
    }
  }, [movies, heroMovie]);

  // Client-side sort on the already-filtered results from the server
  const sortedMovies = useMemo(() => {
    const sorted = [...movies];
    switch (sortOption) {
      case 'title-asc':
        sorted.sort((a, b) => a.title.localeCompare(b.title));
        break;
      case 'title-desc':
        sorted.sort((a, b) => b.title.localeCompare(a.title));
        break;
      case 'year-desc':
        sorted.sort((a, b) => (b.release_year ?? 0) - (a.release_year ?? 0));
        break;
      case 'year-asc':
        sorted.sort((a, b) => (a.release_year ?? 0) - (b.release_year ?? 0));
        break;
    }
    return sorted;
  }, [movies, sortOption]);

  // Extract unique genres from the current results for the genre dropdown
  const availableGenres = useMemo(() => {
    const genreSet = new Set<string>();
    movies.forEach((m) => {
      m.genres?.forEach((g) => genreSet.add(g));
    });
    return Array.from(genreSet).sort();
  }, [movies]);

  // Extract unique years from the current results for the year dropdown
  const availableYears = useMemo(() => {
    const years = new Set<number>();
    movies.forEach((m) => {
      if (m.release_year != null) {
        years.add(m.release_year);
      }
    });
    return Array.from(years).sort((a, b) => b - a);
  }, [movies]);

  // ── Authenticated: fetch watch history + recommendations ────────────────
  useEffect(() => {
    if (!user) return;

    let cancelled = false;
    const fetchUserData = async () => {
      const [history, recs] = await Promise.all([
        getWatchHistory(5),
        getRecommendations(6),
      ]);
      if (!cancelled) {
        setHistoryItems(history);
        setRecommendations(recs);
      }
    };
    fetchUserData();
    return () => { cancelled = true; };
    // location.key changes on every navigation, so returning from a movie
    // detail page triggers a fresh fetch of watch history.
  }, [user, location.key]);

  // ── Guest: derive Continue Watching from localStorage + movie catalog ───
  // Recomputes when movies load, user changes, external events fire
  // (guestEventVersion), or navigation occurs (location.key changes trigger
  // a re-render from useLocation, and location.key is listed as a dependency).
  const guestContinueItems = useMemo<GuestContinueItem[]>(() => {
    // Invalidation signals — referencing them ensures useMemo recomputes when
    // navigation occurs (location.key) or external events fire (guestEventVersion).
    void guestEventVersion;
    void location.key;

    if (user || movies.length === 0) return [];

    const guestEntries = getGuestWatchHistory();
    const movieMap = new Map<string, MovieListItem>();
    for (const m of movies) {
      movieMap.set(m.id, m);
    }

    const items: GuestContinueItem[] = [];
    for (const entry of guestEntries) {
      if (isWatchCompleted(entry.progress_percent)) continue;
      if (entry.is_completed) continue;
      if (entry.progress_percent <= 0) continue;
      if (entry.playback_position_seconds <= 0) continue;

      const movieData = movieMap.get(entry.movie_id);
      if (!movieData) continue;

      items.push({
        ...movieData,
        playback_position_seconds: entry.playback_position_seconds,
        progress_percent: entry.progress_percent,
        is_completed: entry.is_completed,
        updated_at: entry.updated_at,
      });
    }

    items.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    return items;
    // location.key: forces re-read from localStorage on navigation back to Home
    // guestEventVersion: forces re-read on custom events and cross-tab storage
  }, [user, movies, guestEventVersion, location.key]);

  // Listen for guest-watch-history-updated custom event + cross-tab storage event
  useEffect(() => {
    if (user) return; // Only for guests

    const handleGuestUpdate = () => setGuestEventVersion((v) => v + 1);
    const handleStorage = (e: StorageEvent) => {
      if (e.key === 'guest_watch_history') setGuestEventVersion((v) => v + 1);
    };

    window.addEventListener(GUEST_HISTORY_EVENT, handleGuestUpdate);
    window.addEventListener('storage', handleStorage);

    return () => {
      window.removeEventListener(GUEST_HISTORY_EVENT, handleGuestUpdate);
      window.removeEventListener('storage', handleStorage);
    };
  }, [user]);

  const moviesByGenre = useMemo(() => {
    const grouped: Record<string, typeof sortedMovies> = {};
    sortedMovies.forEach(movie => {
      const genres = movie.genres && movie.genres.length > 0 ? movie.genres : ['Uncategorized'];
      genres.forEach(genre => {
        if (!grouped[genre]) grouped[genre] = [];
        grouped[genre].push(movie);
      });
    });
    return Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b));
  }, [sortedMovies]);

  if (error) {
    return <ErrorMessage message={error} />;
  }

  // ── Authenticated Continue Watching items (filtered) ────────────────────
  const authContinueItems = historyItems.filter(
    (item) => !item.is_completed && (item.playback_position_seconds ?? 0) > 0,
  );

  return (
    <div className="home-page">
      {/* ===== Hero Section ===== */}
      {heroMovie && (() => {
        const heroTitle = getLocalizedTitle(heroMovie, i18n.language as AppLanguage);
        return (
        <section className="hero-section">
          <div
            className="hero-backdrop"
            role="img"
            aria-label={t("movies:hero.backdropAlt", { title: heroTitle })}
            style={{
              backgroundImage: `url(${heroMovie.backdrop_url || heroMovie.poster_url || ''})`,
            }}
          />
          <div className="hero-gradient" />
          <div className="hero-content">
            <h1 className="hero-title">{heroTitle}</h1>
            <div className="hero-actions">
              <Link
                to={`/movie/${heroMovie.id}`}
                className="hero-btn hero-btn--primary"
                aria-label={t("movies:hero.watchMovie", { title: heroTitle })}
              >
                {t("movies:hero.watchNow")}
              </Link>
              <Link
                to={`/movie/${heroMovie.id}`}
                className="hero-btn hero-btn--secondary"
                aria-label={t("movies:hero.moreInfoMovie", { title: heroTitle })}
              >
                {t("movies:hero.moreInfo")}
              </Link>
            </div>
          </div>
        </section>
        );
      })()}

      {/* ===== Sticky Filter Controls ===== */}
      <div className="sticky-controls">
        <div className="movie-controls">
          <input
            id="search-input"
            type="text"
            placeholder={t("movies:home.searchPlaceholder")}
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="search-input"
          />

          <select
            id="genre-filter"
            value={genreFilter}
            onChange={(e) => setGenreFilter(e.target.value)}
            className="filter-select"
          >
            <option value="">{t("movies:home.allGenres")}</option>
            {availableGenres.map((genre) => (
              <option key={genre} value={genre}>
                {t(`movies:genres.${genre}`, genre)}
              </option>
            ))}
          </select>

          <select
            id="year-filter"
            value={yearFilter ?? ''}
            onChange={(e) =>
              setYearFilter(e.target.value ? Number(e.target.value) : null)
            }
            className="filter-select"
          >
            <option value="">{t("movies:home.allYears")}</option>
            {availableYears.map((year) => (
              <option key={year} value={year}>
                {year}
              </option>
            ))}
          </select>

          <select
            id="sort-select"
            value={sortOption}
            onChange={(e) => setSortOption(e.target.value as SortOption)}
            className="filter-select"
          >
            <option value="title-asc">{t("movies:home.sort.titleAsc")}</option>
            <option value="title-desc">{t("movies:home.sort.titleDesc")}</option>
            <option value="year-desc">{t("movies:home.sort.yearDesc")}</option>
            <option value="year-asc">{t("movies:home.sort.yearAsc")}</option>
          </select>
        </div>
      </div>

      {/* ===== Skeleton Loading State ===== */}
      {loading && (
        <>
          <div className="skeleton-section-title" />
          <div className="skeleton-row">
            {Array.from({ length: SKELETON_COUNT }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
          <div className="skeleton-section-title" />
          <div className="skeleton-row">
            {Array.from({ length: SKELETON_COUNT }).map((_, i) => (
              <SkeletonCard key={`b-${i}`} />
            ))}
          </div>
        </>
      )}

      {/* ===== Content (shown when not loading) ===== */}
      {!loading && (
        <>
          {/* ── Authenticated Continue Watching ── */}
          {user && authContinueItems.length > 0 && (
            <section className="continue-watching-section">
              <h2>{t("movies:continueWatching.title")}</h2>
              <div className="movie-list movie-row">
                {authContinueItems.map((item) => (
                  <ContinueWatchingCard
                    key={item.id}
                    movie={item}
                    progressPercent={item.progress_percent ?? 0}
                    playbackPositionSeconds={item.playback_position_seconds ?? 0}
                    isFavorite={isFavorite(item.id)}
                    onToggleFavorite={toggleFavorite}
                  />
                ))}
              </div>
            </section>
          )}

          {/* ── Guest Continue Watching ── */}
          {!user && guestContinueItems.length > 0 && (
            <section className="continue-watching-section" data-testid="guest-continue-watching">
              <h2>{t("movies:continueWatching.title")}</h2>
              <div className="movie-list movie-row">
                {guestContinueItems.map((item) => (
                  <ContinueWatchingCard
                    key={item.id}
                    movie={item}
                    progressPercent={item.progress_percent}
                    playbackPositionSeconds={item.playback_position_seconds}
                    isFavorite={isFavorite(item.id)}
                    onToggleFavorite={toggleFavorite}
                  />
                ))}
              </div>
            </section>
          )}

          {user && recommendations.length > 0 && (
            <section className="recommendations-section recommendations-home">
              <h2>{t("recommendation:title")}</h2>
              <div className="movie-list movie-row">
                {recommendations.map((rec) => (
                  <RecommendationCard
                    key={rec.id}
                    movie={rec}
                    isFavorite={isFavorite(rec.id)}
                    onToggleFavorite={toggleFavorite}
                  />
                ))}
              </div>
            </section>
          )}

          <h1>{t("movies:home.moviesByGenre")}</h1>

          {moviesByGenre.length === 0 ? (
            <div className="empty-state">
              <span className="empty-state__icon"></span>
              <h3 className="empty-state__title">{t("movies:home.noMoviesFound")}</h3>
              <p className="empty-state__description">
                {t("movies:home.noMoviesDesc")}
              </p>
              {(searchInput || genreFilter || yearFilter) && (
                <button
                  className="btn btn--primary"
                  onClick={() => {
                    setSearchInput('');
                    setGenreFilter('');
                    setYearFilter(null);
                    setSortOption('title-asc');
                  }}
                >
                  {t("movies:home.resetFilters")}
                </button>
              )}
            </div>
          ) : (
            moviesByGenre.map(([genre, genreMovies]) => (
              <section key={genre} className="genre-section" style={{ marginBottom: '2rem' }}>
                <h2 style={{ paddingLeft: '1rem' }}>{t(`movies:genres.${genre}`, genre)}</h2>
                <div className="movie-list movie-row">
                  {genreMovies.map((movie) => (
                    <MovieCard
                      key={movie.id}
                      movie={movie}
                      isFavorite={isFavorite(movie.id)}
                      onToggleFavorite={toggleFavorite}
                      enableImageSwap={true}
                    />
                  ))}
                </div>
              </section>
            ))
          )}
        </>
      )}
    </div>
  );
};

export default HomePage;
