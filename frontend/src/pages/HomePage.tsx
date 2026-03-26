import React, { useState, useEffect, useMemo } from 'react';
import MovieCard from '../components/MovieCard';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import { useMovies } from '../hooks/useMovies';
import { useFavorites } from '../hooks/useFavorites';
import { useAuth } from '../hooks/useAuth';
import { getWatchHistory } from '../services/continueWatchingService';
import type { HistoryItem } from '../services/continueWatchingService';
import { applyFilters, getUniqueYears } from '../utils/movieFilters';
import type { SortOption } from '../utils/movieFilters';

const HomePage: React.FC = () => {
  const { movies, loading, error } = useMovies();
  const { isFavorite, toggleFavorite } = useFavorites();
  const { user } = useAuth();
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);

  // Search / Filter / Sort state
  const [searchQuery, setSearchQuery] = useState('');
  const [yearFilter, setYearFilter] = useState<number | null>(null);
  const [sortOption, setSortOption] = useState<SortOption>('title-asc');

  useEffect(() => {
    if (!user) {
      setHistoryItems([]);
      return;
    }
    const fetchHistory = async () => {
      const items = await getWatchHistory(5);
      setHistoryItems(items);
    };
    fetchHistory();
  }, [user]);

  const availableYears = useMemo(() => getUniqueYears(movies), [movies]);

  const filteredMovies = useMemo(
    () => applyFilters(movies, searchQuery, yearFilter, sortOption),
    [movies, searchQuery, yearFilter, sortOption],
  );

  if (loading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <ErrorMessage message={error} />;
  }

  return (
    <div className="home-page">
      {historyItems.length > 0 && (
        <section className="continue-watching-section">
          <h2>Continue Watching</h2>
          <div className="movie-list">
            {historyItems.map((item) => (
              <MovieCard
                key={item.id}
                movie={item}
                isFavorite={isFavorite(item.id)}
                onToggleFavorite={toggleFavorite}
              />
            ))}
          </div>
        </section>
      )}

      <h1>Movies</h1>

      <div className="movie-controls">
        <input
          id="search-input"
          type="text"
          placeholder="Search by title..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="search-input"
        />

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

      {filteredMovies.length === 0 ? (
        <p className="no-results">No movies found.</p>
      ) : (
        <div className="movie-list">
          {filteredMovies.map((movie) => (
            <MovieCard
              key={movie.id}
              movie={movie}
              isFavorite={isFavorite(movie.id)}
              onToggleFavorite={toggleFavorite}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default HomePage;
