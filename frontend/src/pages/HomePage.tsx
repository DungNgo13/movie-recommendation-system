import React, { useState, useEffect, useMemo } from 'react';
import MovieCard from '../components/MovieCard';
import RecommendationCard from '../components/RecommendationCard';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import { useMovies } from '../hooks/useMovies';
import { useFavorites } from '../hooks/useFavorites';
import { useAuth } from '../hooks/useAuth';
import { getWatchHistory } from '../services/continueWatchingService';
import { getRecommendations } from '../services/recommendationService';
import type { HistoryItem } from '../services/continueWatchingService';
import type { RecommendedMovie } from '../services/recommendationService';
import type { MovieFilters } from '../services/movieService';

type SortOption = 'title-asc' | 'title-desc' | 'year-desc' | 'year-asc';

const DEBOUNCE_MS = 500;

const HomePage: React.FC = () => {
  const { isFavorite, toggleFavorite } = useFavorites();
  const { user } = useAuth();
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [recommendations, setRecommendations] = useState<RecommendedMovie[]>([]);

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

  useEffect(() => {
    if (!user) {
      setHistoryItems([]);
      setRecommendations([]);
      return;
    }
    const fetchUserData = async () => {
      const [history, recs] = await Promise.all([
        getWatchHistory(5),
        getRecommendations(6),
      ]);
      setHistoryItems(history);
      setRecommendations(recs);
    };
    fetchUserData();
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

  if (loading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <ErrorMessage message={error} />;
  }

  return (
    <div className="home-page">
      <div className="sticky-controls">
        <div className="movie-controls">
          <input
            id="search-input"
            type="text"
            placeholder="Search by title..."
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
            <option value="">All Genres</option>
            {availableGenres.map((genre) => (
              <option key={genre} value={genre}>
                {genre}
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
            <option value="">All Years</option>
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
            <option value="title-asc">Title A–Z</option>
            <option value="title-desc">Title Z–A</option>
            <option value="year-desc">Newest First</option>
            <option value="year-asc">Oldest First</option>
          </select>
        </div>
      </div>

      {historyItems.filter(item => !item.is_completed && (item.playback_position_seconds ?? 0) >= 30).length > 0 && (
        <section className="continue-watching-section">
          <h2>Continue Watching</h2>
          <div className="movie-list movie-row">
            {historyItems
              .filter(item => !item.is_completed && (item.playback_position_seconds ?? 0) >= 30)
              .map((item) => (
                <div key={item.id} style={{ position: 'relative' }}>
                  <MovieCard
                    movie={item}
                    isFavorite={isFavorite(item.id)}
                    onToggleFavorite={toggleFavorite}
                  />
                  {/* Progress bar shown at bottom of the card thumbnail */}
                  {item.progress_percent != null && item.progress_percent > 0 && (
                    <div style={{
                      position: 'absolute', bottom: '2.2rem', left: 0, right: 0,
                      height: '4px', background: 'rgba(0,0,0,0.4)',
                    }}>
                      <div style={{
                        height: '100%',
                        width: `${Math.min(item.progress_percent, 100)}%`,
                        background: '#e50914',
                        borderRadius: '0 2px 2px 0',
                        transition: 'width 0.3s ease',
                      }} />
                    </div>
                  )}
                </div>
              ))}
          </div>
        </section>
      )}

      {recommendations.length > 0 && (
        <section className="recommendations-section recommendations-home">
          <h2>🤖 Recommended for You</h2>
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

      <h1>Movies by Genre</h1>

      {moviesByGenre.length === 0 ? (
        <p className="no-results">No movies found.</p>
      ) : (
        moviesByGenre.map(([genre, genreMovies]) => (
          <section key={genre} className="genre-section" style={{ marginBottom: '2rem' }}>
            <h2 style={{ paddingLeft: '1rem' }}>{genre}</h2>
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
    </div>
  );
};

export default HomePage;
