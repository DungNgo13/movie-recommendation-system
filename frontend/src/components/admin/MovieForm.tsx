import React, { useState, useEffect, useRef } from 'react';
import type { KeyboardEvent } from 'react';
import type { Movie } from '../../models';
import type { MovieFormData } from '../../services/movieService';
import { uploadMovieImage, uploadMovieVideo, processMovieVideo, getMovieProcessingStatus } from '../../services/movieService';
import { useTranslation } from 'react-i18next';

// ─── TagInput ─────────────────────────────────────────────────────────────────
// Self-contained chip/tag input — no external library needed.
//
// Keyboard UX (defensible in a thesis viva):
//   Enter or comma → confirm the typed text as a new tag
//   Backspace on empty input → remove the last tag
//   Clicking × on a chip → remove that chip
//   Duplicate tags are silently ignored

interface TagInputProps {
  id: string;
  tags: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  disabled?: boolean;
}

const TagInput: React.FC<TagInputProps> = ({ id, tags, onChange, placeholder, disabled }) => {
  const [inputValue, setInputValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const addTag = (raw: string) => {
    const value = raw.trim();
    if (!value || tags.includes(value)) return;
    onChange([...tags, value]);
    setInputValue('');
  };

  const removeTag = (index: number) => {
    onChange(tags.filter((_, i) => i !== index));
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();          // prevent form submit on Enter
      addTag(inputValue);
    } else if (e.key === 'Backspace' && inputValue === '') {
      removeTag(tags.length - 1); // delete last chip on Backspace
    }
  };

  const handleBlur = () => {
    if (inputValue.trim()) addTag(inputValue); // commit pending text on blur
  };

  return (
    <div
      className="tag-input-container"
      onClick={() => inputRef.current?.focus()}
    >
      {tags.map((tag, i) => (
        <span key={i} className="tag-chip">
          {tag}
          {!disabled && (
            <button
              type="button"
              className="tag-chip-remove"
              onClick={(e) => { e.stopPropagation(); removeTag(i); }}
              aria-label={`Remove ${tag}`}
            >
              ×
            </button>
          )}
        </span>
      ))}
      <input
        ref={inputRef}
        id={id}
        type="text"
        className="tag-input-text"
        value={inputValue}
        placeholder={tags.length === 0 ? placeholder : ''}
        disabled={disabled}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
      />
    </div>
  );
};

// ─── Genre Checkbox Grid ──────────────────────────────────────────────────────
// Restricts genres to a predefined list for TF-IDF data consistency.
// The engine's movie_profile.py joins genres into the corpus string — free-text
// would introduce spelling variants that fragment the vocabulary.

const STANDARD_GENRES: string[] = [
  'Action',      'Adventure',   'Animation',  'Comedy',
  'Crime',       'Documentary', 'Drama',      'Family',
  'Fantasy',     'History',     'Horror',     'Music',
  'Mystery',     'Romance',     'Sci-Fi',     'Thriller',
  'War',         'Western',
];

interface GenreCheckboxGridProps {
  selected: string[];
  onChange: (genres: string[]) => void;
}

const GenreCheckboxGrid: React.FC<GenreCheckboxGridProps> = ({ selected, onChange }) => {
  const toggle = (genre: string) => {
    if (selected.includes(genre)) {
      onChange(selected.filter((g) => g !== genre));
    } else {
      onChange([...selected, genre]);
    }
  };

  return (
    <div className="genre-checkbox-grid">
      {STANDARD_GENRES.map((genre) => {
        const isChecked = selected.includes(genre);
        return (
          <label
            key={genre}
            className={`genre-checkbox-item ${isChecked ? 'genre-checkbox-item--active' : ''}`}
          >
            <input
              type="checkbox"
              checked={isChecked}
              onChange={() => toggle(genre)}
            />
            <span className="genre-checkbox-label">{genre}</span>
          </label>
        );
      })}
    </div>
  );
};

interface MovieFormProps {
  movie: Movie | null;
  onSubmit: (data: MovieFormData) => void;
  onCancel: () => void;
}

const MovieForm: React.FC<MovieFormProps> = ({ movie, onSubmit, onCancel }) => {
  const { t } = useTranslation(['admin', 'common']);

  // ── Metadata state ───────────────────────────────────────────────────────
  const [title, setTitle]               = useState('');
  const [overview, setOverview]         = useState('');
  const [releaseDate, setReleaseDate]   = useState('');
  const [director, setDirector]         = useState('');
  const [genres, setGenres]             = useState<string[]>([]);
  const [cast, setCast]                 = useState<string[]>([]);
  const [keywords, setKeywords]         = useState<string[]>([]);
  const [posterUrl, setPosterUrl]       = useState('');
  const [backdropUrl, setBackdropUrl]   = useState('');

  const [titleVi, setTitleVi]           = useState('');
  const [overviewVi, setOverviewVi]     = useState('');
  const [keywordLabelsVi, setKeywordLabelsVi] = useState<Record<string, string>>({});

  // ── Advanced source info (collapsed by default) ─────────────────────────
  const [sourceName, setSourceName]     = useState('');
  const [sourceUrl, setSourceUrl]       = useState('');
  const [licenseType, setLicenseType]   = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);

  // ── Video pipeline state ─────────────────────────────────────────────────
  const [videoStatus, setVideoStatus]             = useState('pending');
  const [videoUrl, setVideoUrl]                   = useState('');
  const [hlsUrl, setHlsUrl]                       = useState('');
  const [availableQualities, setAvailableQualities] = useState<string | null>(null);
  const [processingError, setProcessingError]     = useState<string | null>(null);

  // ── UI state ─────────────────────────────────────────────────────────────
  const [error, setError]                 = useState<string | null>(null);
  const [uploading, setUploading]         = useState(false);
  const [uploadPercent, setUploadPercent] = useState<number | null>(null);
  const [pollProgress, setPollProgress]   = useState<number>(0);
  const [pollStep, setPollStep]           = useState<string>('Processing');

  // ── Populate from existing movie when editing ────────────────────────────
  useEffect(() => {
    if (movie) {
      setTitle(movie.title);
      setOverview(movie.overview || '');
      setReleaseDate(movie.release_date ? movie.release_date.split('-')[0] : '');
      setDirector(movie.director || '');
      setGenres(movie.genres ?? []);
      setCast(movie.cast ?? []);
      setKeywords(movie.keywords ?? []);
      setPosterUrl(movie.poster_url || '');
      setBackdropUrl(movie.backdrop_url || '');
      setTitleVi(movie.title_vi || '');
      setOverviewVi(movie.overview_vi || '');
      setKeywordLabelsVi(movie.keyword_labels_vi || {});
      setVideoUrl(movie.video_url || '');
      setVideoStatus(movie.video_status || 'pending');
      setHlsUrl(movie.hls_playlist_url || '');
      setAvailableQualities(movie.available_qualities || null);
      setProcessingError(movie.processing_error || null);
      setSourceName(movie.source_name || '');
      setSourceUrl(movie.source_url || '');
      setLicenseType(movie.license_type || '');
      // Auto-expand advanced if the movie already has source data
      if (movie.source_name || movie.source_url || movie.license_type) {
        setShowAdvanced(true);
      }
    }
  }, [movie]);

  // ── Image upload ─────────────────────────────────────────────────────────
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>, type: 'poster' | 'backdrop') => {
    if (!movie || !e.target.files?.[0]) return;
    try {
      setUploading(true);
      setError(null);
      const updatedMovie = await uploadMovieImage(movie.id, e.target.files[0], type);
      if (type === 'poster')   setPosterUrl(updatedMovie.poster_url || '');
      if (type === 'backdrop') setBackdropUrl(updatedMovie.backdrop_url || '');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  // ── Video processing status poll ─────────────────────────────────────────
  useEffect(() => {
    let interval: number;
    if (movie && videoStatus === 'processing') {
      interval = window.setInterval(async () => {
        try {
          const res = await getMovieProcessingStatus(movie.id);
          setVideoStatus(res.video_status);
          setPollProgress(res.video_progress ?? 0);
          setPollStep(res.video_step || 'Processing');
          if (res.hls_playlist_url)    setHlsUrl(res.hls_playlist_url);
          if (res.processing_error)    setProcessingError(res.processing_error);
          if (res.available_qualities) setAvailableQualities(res.available_qualities);
        } catch (e) {
          console.warn('Polling error', e);
        }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [movie, videoStatus]);

  // ── Start HLS encoding ───────────────────────────────────────────────────
  const handleProcessHls = async () => {
    if (!movie) return;
    try {
      setUploading(true);
      setError(null);
      await processMovieVideo(movie.id);
      setVideoStatus('processing');
    } catch (err) {
      const status = (err as Error & { status?: number }).status;
      if (status === 401) { window.location.href = '/login'; return; }
      setError(err instanceof Error ? err.message : 'Processing failed');
    } finally {
      setUploading(false);
    }
  };

  // ── Video file upload ────────────────────────────────────────────────────
  const handleVideoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!movie || !e.target.files?.[0]) return;
    try {
      setUploading(true);
      setError(null);
      setUploadPercent(0);
      const updatedMovie = await uploadMovieVideo(movie.id, e.target.files[0], (pct) => {
        setUploadPercent(pct);
      });
      setVideoUrl(updatedMovie.video_url || '');
      setVideoStatus(updatedMovie.video_status || 'uploaded');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Video upload failed');
    } finally {
      setUploading(false);
      setUploadPercent(null);
      e.target.value = '';
    }
  };

  // ── Form submit ──────────────────────────────────────────────────────────
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!title.trim()) {
      setError('Title is required.');
      return;
    }

    onSubmit({
      title:        title.trim(),
      overview:     overview.trim() || null,
      release_date: releaseDate ? `${releaseDate.trim()}-01-01` : null,
      director:     director.trim() || null,
      // Send empty arrays as null so the backend treats them as "not provided"
      genres:       genres.length   > 0 ? genres   : null,
      cast:         cast.length     > 0 ? cast     : null,
      keywords:     keywords.length > 0 ? keywords : null,
      poster_url:   posterUrl.trim()   || null,
      backdrop_url: backdropUrl.trim() || null,
      // Advanced source fields (sent only if filled)
      source_name:  sourceName.trim()  || null,
      source_url:   sourceUrl.trim()   || null,
      license_type: licenseType.trim() || null,
      
      title_vi:     titleVi.trim() || null,
      overview_vi:  overviewVi.trim() || null,
      keyword_labels_vi: Object.keys(keywordLabelsVi).length > 0 ? keywordLabelsVi : null,
    });
  };

  // Show the AI warning banner when all three signal fields are still empty
  const missingAiFields = genres.length === 0 && cast.length === 0 && keywords.length === 0;

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <form className="admin-form" onSubmit={handleSubmit}>
      <h2>{movie ? t("admin:movieForm.editMovie", "Edit Movie") : t("admin:movieForm.addMovie", "Add Movie")}</h2>

      {error && <p className="admin-form-error">{error}</p>}

      {/* ── Basic metadata ───────────────────────────────────────────── */}
      <div className="admin-form-group">
        <label htmlFor="title">{t("admin:movieForm.fields.title", "Title (English)")} *</label>
        <input
          id="title"
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Movie title"
        />
      </div>

      <div className="admin-form-group">
        <label htmlFor="overview">{t("admin:movieForm.fields.overview", "Overview (English)")}</label>
        <textarea
          id="overview"
          value={overview}
          onChange={(e) => setOverview(e.target.value)}
          placeholder="Movie description"
          rows={3}
        />
      </div>

      <div className="admin-form-row">
        <div className="admin-form-group">
          <label htmlFor="release_date">{t("admin:movieForm.fields.releaseDate", "Release Year")}</label>
          <input
            id="release_date"
            type="number"
            min="1888"
            max="2100"
            value={releaseDate}
            onChange={(e) => setReleaseDate(e.target.value)}
            placeholder="e.g. 2024"
          />
        </div>

        <div className="admin-form-group">
          <label htmlFor="director">{t("admin:movieForm.fields.director", "Director")}</label>
          <input
            id="director"
            type="text"
            value={director}
            onChange={(e) => setDirector(e.target.value)}
            placeholder="Director name"
          />
        </div>
      </div>

      {/* ── AI Recommendation Fields ─────────────────────────────────── */}
      <div className="ai-fields-section">

        {/* Section header */}
        <div className="ai-fields-header">
          <span className="ai-fields-icon"></span>
          <div>
            <strong>{t("admin:movieForm.aiMetadataLabel", "English / AI metadata")}</strong>
            <span className="ai-fields-desc">
              {t("admin:movieForm.aiMetadataDescription", "These English fields are used by the recommendation engine.")}
            </span>
          </div>
        </div>

        {/* Warning — only visible when ALL three fields are empty */}
        {missingAiFields && (
          <div className="ai-fields-warning">
            <strong>Genres, Cast, and Keywords are all empty.</strong> Missing data
            reduces recommendation accuracy — the engine will rely on title and
            overview text alone.
          </div>
        )}

        {/* Genres */}
        <div className="admin-form-group">
          <label>
            {t("admin:movieForm.fields.genres", "Genres")}
            <span className="field-hint">Select all applicable genres from the list below</span>
          </label>
          <GenreCheckboxGrid
            selected={genres}
            onChange={setGenres}
          />
          {genres.length > 0 && (
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary, #555)', margin: '6px 0 0' }}>
              Selected: <strong>{genres.join(', ')}</strong>
            </p>
          )}
        </div>

        {/* Cast */}
        <div className="admin-form-group">
          <label htmlFor="cast">
            {t("admin:movieForm.fields.cast", "Cast")}
            <span className="field-hint">Press Enter or comma to add each actor</span>
          </label>
          <TagInput
            id="cast"
            tags={cast}
            onChange={setCast}
            placeholder="e.g. Tom Hanks, Scarlett Johansson…"
          />
        </div>

        {/* Keywords */}
        <div className="admin-form-group">
          <label htmlFor="keywords">
            {t("admin:movieForm.fields.keywords", "Keywords (English)")}
            <span className="field-hint">Thematic tags — press Enter or comma to add each</span>
          </label>
          <TagInput
            id="keywords"
            tags={keywords}
            onChange={setKeywords}
            placeholder="e.g. heist, space, based on true story…"
          />
        </div>
      </div>

      {/* ── Vietnamese Display Metadata ─────────────────────────────────── */}
      <div className="ai-fields-section" style={{ marginTop: '20px' }}>
        <div className="ai-fields-header">
          <span className="ai-fields-icon" style={{ filter: 'hue-rotate(120deg)' }}></span>
          <div>
            <strong>{t("admin:movieForm.viMetadataLabel", "Vietnamese display metadata")}</strong>
            <span className="ai-fields-desc">
              {t("admin:movieForm.viMetadataDescription", "These fields are used only for Vietnamese display and do not affect recommendations.")}
            </span>
          </div>
        </div>

        <div className="admin-form-group">
          <label htmlFor="title_vi">{t("admin:movieForm.fields.titleVi", "Title (Vietnamese)")}</label>
          <input
            id="title_vi"
            type="text"
            value={titleVi}
            onChange={(e) => setTitleVi(e.target.value)}
            placeholder="Vietnamese title (optional)"
          />
        </div>

        <div className="admin-form-group">
          <label htmlFor="overview_vi">{t("admin:movieForm.fields.overviewVi", "Overview (Vietnamese)")}</label>
          <textarea
            id="overview_vi"
            value={overviewVi}
            onChange={(e) => setOverviewVi(e.target.value)}
            placeholder="Vietnamese overview (optional)"
            rows={3}
          />
        </div>

        {/* Dynamic Keyword Label Inputs */}
        {keywords.length > 0 && (
          <div className="admin-form-group">
            <label>{t("admin:movieForm.fields.keywordLabelsVi", "Vietnamese Keyword Labels")}</label>
            <div className="keyword-labels-grid" style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '8px' }}>
              {keywords.map(kw => (
                <div key={kw} className="keyword-label-row" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span className="keyword-label-key" style={{ minWidth: '150px', fontWeight: 600, color: 'var(--text-secondary)' }}>#{kw}</span>
                  <input
                    type="text"
                    value={keywordLabelsVi[kw] || ''}
                    onChange={(e) => setKeywordLabelsVi({...keywordLabelsVi, [kw]: e.target.value})}
                    placeholder={`${t("admin:movieForm.keywordLabel", "Vietnamese label for")} ${kw}`}
                    style={{ flex: 1 }}
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── Image fields ─────────────────────────────────────────────── */}
      <div className="admin-form-group">
        <label htmlFor="poster_url">Poster URL</label>
        <input
          id="poster_url"
          type="text"
          value={posterUrl}
          onChange={(e) => setPosterUrl(e.target.value)}
          placeholder="https://..."
        />
        {movie && (
          <div style={{ marginTop: '8px' }}>
            <label style={{ fontSize: '0.85rem' }}>Or Upload File: </label>
            <input
              type="file"
              accept="image/jpeg, image/png, image/webp"
              onChange={(e) => handleUpload(e, 'poster')}
              disabled={uploading}
            />
          </div>
        )}
      </div>

      <div className="admin-form-group">
        <label htmlFor="backdrop_url">Backdrop URL</label>
        <input
          id="backdrop_url"
          type="text"
          value={backdropUrl}
          onChange={(e) => setBackdropUrl(e.target.value)}
          placeholder="https://..."
        />
        {movie && (
          <div style={{ marginTop: '8px' }}>
            <label style={{ fontSize: '0.85rem' }}>Or Upload File: </label>
            <input
              type="file"
              accept="image/jpeg, image/png, image/webp"
              onChange={(e) => handleUpload(e, 'backdrop')}
              disabled={uploading}
            />
          </div>
        )}
      </div>

      {/* ── Video pipeline ────────────────────────────────────────────── */}
      <div className="admin-form-group" style={{ backgroundColor: 'var(--surface-raised, #f8f9fa)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border, #dee2e6)' }}>
        <h3 style={{ marginTop: 0, marginBottom: '0.5rem', fontSize: '1.1rem' }}>Source Video</h3>
        {movie ? (
          <>
            <div style={{ marginBottom: '1rem', fontSize: '0.9rem' }}>

              {/* Status badge */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                <strong>Status:</strong>
                <span style={{
                  display: 'inline-block', padding: '2px 10px', borderRadius: '12px',
                  fontSize: '0.8rem', fontWeight: 600,
                  backgroundColor:
                    videoStatus === 'ready'      ? '#d4edda' :
                    videoStatus === 'processing' ? '#fff3cd' :
                    videoStatus === 'failed'     ? '#f8d7da' :
                    videoStatus === 'uploaded'   ? '#d1ecf1' :
                    videoStatus === 'no_video'   ? '#e2e3e5' : '#e9ecef',
                  color:
                    videoStatus === 'ready'      ? '#155724' :
                    videoStatus === 'processing' ? '#856404' :
                    videoStatus === 'failed'     ? '#721c24' :
                    videoStatus === 'uploaded'   ? '#0c5460' :
                    videoStatus === 'no_video'   ? '#383d41' : '#6c757d',
                }}>
                  {videoStatus.toUpperCase()}
                </span>
                {videoStatus === 'processing' && (
                  <span style={{ display: 'inline-block', width: '14px', height: '14px', border: '2px solid #856404', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
                )}
              </div>

              {/* Upload progress */}
              {uploadPercent !== null && (
                <div style={{ marginBottom: '8px' }}>
                  <div style={{ fontSize: '0.8rem', marginBottom: '4px', color: '#495057' }}>Uploading… {uploadPercent}%</div>
                  <div style={{ height: '6px', background: '#dee2e6', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${uploadPercent}%`, background: '#0d6efd', transition: 'width 0.2s ease', borderRadius: '3px' }} />
                  </div>
                </div>
              )}

              {/* Encode progress */}
              {videoStatus === 'processing' && uploadPercent === null && (
                <div style={{ marginBottom: '8px' }}>
                  <div style={{ fontSize: '0.8rem', marginBottom: '4px', color: '#856404' }}>{pollStep} — {pollProgress}%</div>
                  <div style={{ height: '6px', background: '#dee2e6', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${pollProgress}%`, background: 'linear-gradient(90deg, #ffc107, #fd7e14)', borderRadius: '3px', transition: 'width 0.5s ease-out' }} />
                  </div>
                </div>
              )}

              {/* Quality badges */}
              {availableQualities && (
                <div style={{ marginTop: '6px', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                  <strong style={{ fontSize: '0.85rem' }}>Qualities:</strong>
                  {availableQualities.split(',').map((q) => (
                    <span key={q} style={{
                      display: 'inline-block', padding: '2px 8px', borderRadius: '10px',
                      fontSize: '0.75rem', fontWeight: 700,
                      background: q.trim() === '1080p' ? '#cce5ff' : q.trim() === '720p' ? '#d4edda' : '#e2e3e5',
                      color:      q.trim() === '1080p' ? '#004085' : q.trim() === '720p' ? '#155724' : '#383d41',
                    }}>{q.trim()}</span>
                  ))}
                </div>
              )}

              {videoUrl && <div style={{ wordBreak: 'break-all', marginTop: '4px', opacity: 0.8, fontSize: '0.85rem' }}><em>Source: {videoUrl}</em></div>}
              {hlsUrl   && <div style={{ wordBreak: 'break-all', marginTop: '4px', color: '#155724', fontSize: '0.85rem' }}><em>HLS: <a href={hlsUrl} target="_blank" rel="noopener noreferrer">{hlsUrl}</a></em></div>}
              {processingError && (
                <div style={{ color: '#721c24', marginTop: '6px', fontSize: '0.85rem', background: '#f8d7da', padding: '8px', borderRadius: '4px' }}>
                  <strong>Error:</strong> {processingError}
                </div>
              )}
            </div>

            <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
              <input
                type="file"
                accept="video/mp4,video/x-matroska,video/webm,video/avi,video/quicktime,.mp4,.mkv,.webm,.avi,.mov"
                onChange={handleVideoUpload}
                disabled={uploading}
              />
              {(videoStatus === 'uploaded' || videoStatus === 'failed' || videoStatus === 'ready') && (
                <button
                  type="button"
                  className="btn btn--primary"
                  onClick={handleProcessHls}
                  disabled={uploading}
                  title={videoStatus === 'ready' ? 'Re-encode with current settings' : 'Start multi-quality HLS encoding'}
                >
                  {videoStatus === 'ready' ? 'Re-encode' : 'Start Multi-Quality Encoding'}
                </button>
              )}
            </div>
          </>
        ) : (
          <p style={{ fontSize: '0.9rem', color: '#6c757d', margin: 0 }}>
            <em>Please create the movie first before uploading the primary video payload.</em>
          </p>
        )}
      </div>

      {/* ── Advanced Source Information (collapsed) ─────────────────────── */}
      <div className="advanced-source-section">
        <button
          type="button"
          className="advanced-source-toggle"
          onClick={() => setShowAdvanced(!showAdvanced)}
          aria-expanded={showAdvanced}
        >
          <span className="advanced-source-arrow">{showAdvanced ? '▾' : '▸'}</span>
          Advanced Source Information (Optional)
        </button>

        {showAdvanced && (
          <div className="advanced-source-body">
            <p className="advanced-source-hint">
              Optional metadata about where this movie's data was sourced from.
              These fields are not required for the recommendation engine.
            </p>
            <div className="admin-form-group">
              <label htmlFor="source_name">Source Name</label>
              <input
                id="source_name"
                type="text"
                value={sourceName}
                onChange={(e) => setSourceName(e.target.value)}
                placeholder="e.g. TMDB, Library of Congress"
              />
            </div>
            <div className="admin-form-group">
              <label htmlFor="source_url">Source URL</label>
              <input
                id="source_url"
                type="text"
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                placeholder="https://..."
              />
            </div>
            <div className="admin-form-group">
              <label htmlFor="license_type">License Type</label>
              <input
                id="license_type"
                type="text"
                value={licenseType}
                onChange={(e) => setLicenseType(e.target.value)}
                placeholder="e.g. Public Domain, CC BY 4.0"
              />
            </div>
          </div>
        )}
      </div>

      {/* ── Form actions ──────────────────────────────────────────────── */}
      <div className="admin-form-actions">
        <button type="submit" className="btn btn--primary">
          {movie ? t("admin:movieForm.submit", "Save Changes") : t("admin:movieForm.submit", "Create Movie")}
        </button>
        <button type="button" className="btn btn--secondary" onClick={onCancel}>
          {t("admin:movieForm.cancel", "Cancel")}
        </button>
      </div>
    </form>
  );
};

export default MovieForm;
