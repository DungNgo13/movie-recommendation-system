import React, { useState, useEffect, useRef } from 'react';
import type { KeyboardEvent } from 'react';
import type { Movie, MovieAsset } from '../../models';
import type { MovieFormData } from '../../services/movieService';
import { uploadMovieImage, uploadMovieVideo, processMovieVideo, getMovieProcessingStatus } from '../../services/movieService';
import { API_BASE_URL } from '../../config';
import { getToken } from '../../services/authService';

// ─── TagInput ─────────────────────────────────────────────────────────────────

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
      e.preventDefault();
      addTag(inputValue);
    } else if (e.key === 'Backspace' && inputValue === '') {
      removeTag(tags.length - 1);
    }
  };

  const handleBlur = () => {
    if (inputValue.trim()) addTag(inputValue);
  };

  return (
    <div className="tag-input-container" onClick={() => inputRef.current?.focus()}>
      {tags.map((tag, i) => (
        <span key={i} className="tag-chip">
          {tag}
          {!disabled && (
            <button type="button" className="tag-chip-remove" onClick={(e) => { e.stopPropagation(); removeTag(i); }} aria-label={`Remove ${tag}`}>
              ×
            </button>
          )}
        </span>
      ))}
      <input ref={inputRef} id={id} type="text" className="tag-input-text" value={inputValue} placeholder={tags.length === 0 ? placeholder : ''} disabled={disabled} onChange={(e) => setInputValue(e.target.value)} onKeyDown={handleKeyDown} onBlur={handleBlur} />
    </div>
  );
};

// ─── Genre Checkbox Grid ──────────────────────────────────────────────────────

const STANDARD_GENRES: string[] = [
  'Action', 'Adventure', 'Animation', 'Comedy',
  'Crime', 'Documentary', 'Drama', 'Family',
  'Fantasy', 'History', 'Horror', 'Music',
  'Mystery', 'Romance', 'Sci-Fi', 'Thriller',
  'War', 'Western',
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
          <label key={genre} className={`genre-checkbox-item ${isChecked ? 'genre-checkbox-item--active' : ''}`}>
            <input type="checkbox" checked={isChecked} onChange={() => toggle(genre)} />
            <span className="genre-checkbox-label">{genre}</span>
          </label>
        );
      })}
    </div>
  );
};

// ─── Source Presets ────────────────────────────────────────────────────────────

interface SourcePreset {
  label: string;
  source_name: string;
  license_type: string;
  media_rights_status: string;
  is_public_domain: boolean;
}

const SOURCE_PRESETS: SourcePreset[] = [
  { label: 'Library of Congress / Public Domain', source_name: 'Library of Congress', license_type: 'Public Domain', media_rights_status: 'safe_to_use', is_public_domain: true },
  { label: 'Wikimedia Commons / CC BY 4.0', source_name: 'Wikimedia Commons', license_type: 'CC BY 4.0', media_rights_status: 'attribution_required', is_public_domain: false },
  { label: 'Wikimedia Commons / CC BY-SA 4.0', source_name: 'Wikimedia Commons', license_type: 'CC BY-SA 4.0', media_rights_status: 'attribution_required', is_public_domain: false },
  { label: 'Pexels / Pexels License', source_name: 'Pexels', license_type: 'Pexels License', media_rights_status: 'safe_to_use', is_public_domain: false },
  { label: 'Unsplash / Unsplash License', source_name: 'Unsplash', license_type: 'Unsplash License', media_rights_status: 'safe_to_use', is_public_domain: false },
  { label: 'Pixabay / Pixabay License', source_name: 'Pixabay', license_type: 'Pixabay License', media_rights_status: 'safe_to_use', is_public_domain: false },
  { label: 'Unknown', source_name: '', license_type: '', media_rights_status: 'unknown', is_public_domain: false },
  { label: 'Blocked', source_name: '', license_type: '', media_rights_status: 'blocked', is_public_domain: false },
];

const MEDIA_RIGHTS_OPTIONS = ['safe_to_use', 'attribution_required', 'non_commercial_only', 'unknown', 'blocked'];
const ASSET_TYPE_OPTIONS = ['poster', 'backdrop', 'banner', 'trailer', 'full_video', 'actor_image', 'director_image', 'placeholder'];

// ─── Asset Row ────────────────────────────────────────────────────────────────

interface AssetEntry {
  id?: string;
  asset_type: string;
  url: string;
  source_name: string;
  source_url: string;
  license_type: string;
  license_url: string;
  attribution: string;
  media_rights_status: string;
  is_public_domain: boolean;
  _isNew?: boolean;
}

const emptyAsset = (): AssetEntry => ({
  asset_type: 'poster',
  url: '',
  source_name: '',
  source_url: '',
  license_type: '',
  license_url: '',
  attribution: '',
  media_rights_status: 'unknown',
  is_public_domain: false,
  _isNew: true,
});

// ─── MovieForm ────────────────────────────────────────────────────────────────

interface MovieFormProps {
  movie: Movie | null;
  onSubmit: (data: MovieFormData) => void;
  onCancel: () => void;
}

const MovieForm: React.FC<MovieFormProps> = ({ movie, onSubmit, onCancel }) => {

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

  // ── Source/license state (movie-level) ───────────────────────────────────
  const [sourceName, setSourceName]               = useState('');
  const [sourceUrl, setSourceUrl]                 = useState('');
  const [licenseType, setLicenseType]             = useState('');
  const [licenseUrl, setLicenseUrl]               = useState('');
  const [attribution, setAttribution]             = useState('');
  const [mediaRightsStatus, setMediaRightsStatus] = useState('unknown');
  const [isPublicDomain, setIsPublicDomain]       = useState(false);

  // ── Assets state ─────────────────────────────────────────────────────────
  const [assets, setAssets]             = useState<AssetEntry[]>([]);
  const [assetSaving, setAssetSaving]   = useState(false);
  const [assetError, setAssetError]     = useState<string | null>(null);

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

  // ── Populate from existing movie ─────────────────────────────────────────
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
      setVideoUrl(movie.video_url || '');
      setVideoStatus(movie.video_status || 'pending');
      setHlsUrl(movie.hls_playlist_url || '');
      setAvailableQualities(movie.available_qualities || null);
      setProcessingError(movie.processing_error || null);

      // Source fields
      setSourceName(movie.source_name || '');
      setSourceUrl(movie.source_url || '');
      setLicenseType(movie.license_type || '');
      setLicenseUrl(movie.license_url || '');
      setAttribution(movie.attribution || '');
      setMediaRightsStatus(movie.media_rights_status || 'unknown');
      setIsPublicDomain(movie.is_public_domain || false);

      // Fetch assets
      fetchAssets(movie.id);
    }
  }, [movie]);

  const fetchAssets = async (movieId: string) => {
    try {
      const token = getToken();
      const res = await fetch(`${API_BASE_URL}/movies/${movieId}/assets`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const data = await res.json();
        setAssets((data.items || []).map((a: MovieAsset) => ({
          id: a.id,
          asset_type: a.asset_type,
          url: a.url || '',
          source_name: a.source_name || '',
          source_url: a.source_url || '',
          license_type: a.license_type || '',
          license_url: a.license_url || '',
          attribution: a.attribution || '',
          media_rights_status: a.media_rights_status,
          is_public_domain: a.is_public_domain,
          _isNew: false,
        })));
      }
    } catch {
      // non-blocking
    }
  };

  // ── Apply source preset ─────────────────────────────────────────────────
  const applyPreset = (preset: SourcePreset) => {
    setSourceName(preset.source_name);
    setLicenseType(preset.license_type);
    setMediaRightsStatus(preset.media_rights_status);
    setIsPublicDomain(preset.is_public_domain);
  };

  const applyAssetPreset = (index: number, preset: SourcePreset) => {
    setAssets(prev => prev.map((a, i) => i === index ? {
      ...a,
      source_name: preset.source_name,
      license_type: preset.license_type,
      media_rights_status: preset.media_rights_status,
      is_public_domain: preset.is_public_domain,
    } : a));
  };

  // ── Asset CRUD ──────────────────────────────────────────────────────────
  const addAssetRow = () => {
    setAssets(prev => [...prev, emptyAsset()]);
  };

  const removeAssetRow = async (index: number) => {
    const asset = assets[index];
    if (asset.id && movie) {
      // Delete from server
      try {
        const token = getToken();
        await fetch(`${API_BASE_URL}/movies/${movie.id}/assets/${asset.id}`, {
          method: 'DELETE',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
      } catch {
        setAssetError('Failed to delete asset.');
        return;
      }
    }
    setAssets(prev => prev.filter((_, i) => i !== index));
  };

  const updateAssetField = (index: number, field: keyof AssetEntry, value: string | boolean) => {
    setAssets(prev => prev.map((a, i) => i === index ? { ...a, [field]: value } : a));
  };

  const saveAsset = async (index: number) => {
    const asset = assets[index];
    if (!movie) return;

    // Validate: if attribution_required, attribution must be present
    if (asset.media_rights_status === 'attribution_required' && !asset.attribution.trim()) {
      setAssetError(`Asset #${index + 1}: Attribution is required when status is "attribution_required".`);
      return;
    }

    setAssetSaving(true);
    setAssetError(null);
    try {
      const token = getToken();
      const res = await fetch(`${API_BASE_URL}/movies/${movie.id}/assets`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          asset_type: asset.asset_type,
          url: asset.url || null,
          source_name: asset.source_name || null,
          source_url: asset.source_url || null,
          license_type: asset.license_type || null,
          license_url: asset.license_url || null,
          attribution: asset.attribution || null,
          media_rights_status: asset.media_rights_status,
          is_public_domain: asset.is_public_domain,
        }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || 'Failed to save asset');
      }

      const saved = await res.json();
      setAssets(prev => prev.map((a, i) => i === index ? { ...a, id: saved.id, _isNew: false } : a));
    } catch (err) {
      setAssetError(err instanceof Error ? err.message : 'Failed to save asset');
    } finally {
      setAssetSaving(false);
    }
  };

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

  const handleVideoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!movie || !e.target.files?.[0]) return;
    try {
      setUploading(true);
      setError(null);
      setUploadPercent(0);
      const updatedMovie = await uploadMovieVideo(movie.id, e.target.files[0], (pct) => setUploadPercent(pct));
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

    // Validate: if attribution_required, attribution must be present
    if (mediaRightsStatus === 'attribution_required' && !attribution.trim()) {
      setError('Attribution is required when media rights status is "attribution_required".');
      return;
    }

    onSubmit({
      title:        title.trim(),
      overview:     overview.trim() || null,
      release_date: releaseDate ? `${releaseDate.trim()}-01-01` : null,
      director:     director.trim() || null,
      genres:       genres.length   > 0 ? genres   : null,
      cast:         cast.length     > 0 ? cast     : null,
      keywords:     keywords.length > 0 ? keywords : null,
      poster_url:   posterUrl.trim()   || null,
      backdrop_url: backdropUrl.trim() || null,
      source_name:         sourceName.trim()   || null,
      source_url:          sourceUrl.trim()     || null,
      license_type:        licenseType.trim()   || null,
      license_url:         licenseUrl.trim()    || null,
      attribution:         attribution.trim()   || null,
      media_rights_status: mediaRightsStatus    || null,
      is_public_domain:    isPublicDomain,
    });
  };

  const missingAiFields = genres.length === 0 && cast.length === 0 && keywords.length === 0;

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <form className="admin-form" onSubmit={handleSubmit}>
      <h2>{movie ? 'Edit Movie' : 'Add Movie'}</h2>

      {error && <p className="admin-form-error">{error}</p>}

      {/* ── Basic metadata ───────────────────────────────────────────── */}
      <div className="admin-form-group">
        <label htmlFor="title">Title *</label>
        <input id="title" type="text" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Movie title" />
      </div>

      <div className="admin-form-group">
        <label htmlFor="overview">Overview</label>
        <textarea id="overview" value={overview} onChange={(e) => setOverview(e.target.value)} placeholder="Movie description" rows={3} />
      </div>

      <div className="admin-form-row">
        <div className="admin-form-group">
          <label htmlFor="release_date">Release Year</label>
          <input id="release_date" type="number" min="1888" max="2100" value={releaseDate} onChange={(e) => setReleaseDate(e.target.value)} placeholder="e.g. 2024" />
        </div>
        <div className="admin-form-group">
          <label htmlFor="director">Director</label>
          <input id="director" type="text" value={director} onChange={(e) => setDirector(e.target.value)} placeholder="Director name" />
        </div>
      </div>

      {/* ── AI Recommendation Fields ─────────────────────────────────── */}
      <div className="ai-fields-section">
        <div className="ai-fields-header">
          <span className="ai-fields-icon"></span>
          <div>
            <strong>AI Recommendation Data</strong>
            <span className="ai-fields-desc">
              Used directly by the TF-IDF recommendation engine. Filling these fields improves personalisation accuracy.
            </span>
          </div>
        </div>

        {missingAiFields && (
          <div className="ai-fields-warning">
            <strong>Genres, Cast, and Keywords are all empty.</strong> Missing data
            reduces recommendation accuracy — the engine will rely on title and
            overview text alone.
          </div>
        )}

        <div className="admin-form-group">
          <label>Genres <span className="field-hint">Select all applicable genres</span></label>
          <GenreCheckboxGrid selected={genres} onChange={setGenres} />
          {genres.length > 0 && (
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: '6px 0 0' }}>
              Selected: <strong>{genres.join(', ')}</strong>
            </p>
          )}
        </div>

        <div className="admin-form-group">
          <label htmlFor="cast">Cast / Actors <span className="field-hint">Press Enter or comma to add</span></label>
          <TagInput id="cast" tags={cast} onChange={setCast} placeholder="e.g. Tom Hanks, Scarlett Johansson…" />
        </div>

        <div className="admin-form-group">
          <label htmlFor="keywords">Keywords / Tags <span className="field-hint">Thematic tags</span></label>
          <TagInput id="keywords" tags={keywords} onChange={setKeywords} placeholder="e.g. heist, space, based on true story…" />
        </div>
      </div>

      {/* ── Legal Source (movie-level) ────────────────────────────────── */}
      <div className="legal-source-section">
        <div className="legal-source-header">
          <div>
            <strong>Legal Source</strong>
            <span className="ai-fields-desc">
              Movie-level metadata source and license. This covers who provided the title, overview, genres, cast, and director data.
            </span>
          </div>
        </div>

        <div className="legal-source-warning">
          Do not upload copyrighted movie posters, trailers, or full movies unless you own the rights or the asset is public domain / free licensed.
        </div>

        <div className="admin-form-group">
          <label htmlFor="source_preset">Quick Preset</label>
          <select
            id="source_preset"
            onChange={(e) => {
              const idx = parseInt(e.target.value);
              if (!isNaN(idx)) applyPreset(SOURCE_PRESETS[idx]);
            }}
            defaultValue=""
          >
            <option value="" disabled>Select a preset…</option>
            {SOURCE_PRESETS.map((p, i) => (
              <option key={i} value={i}>{p.label}</option>
            ))}
          </select>
        </div>

        <div className="admin-form-row">
          <div className="admin-form-group">
            <label htmlFor="source_name">Source Name</label>
            <input id="source_name" type="text" value={sourceName} onChange={(e) => setSourceName(e.target.value)} placeholder="e.g. Library of Congress" />
          </div>
          <div className="admin-form-group">
            <label htmlFor="source_url">Source URL</label>
            <input id="source_url" type="text" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} placeholder="https://..." />
          </div>
        </div>

        <div className="admin-form-row">
          <div className="admin-form-group">
            <label htmlFor="license_type">License Type</label>
            <input id="license_type" type="text" value={licenseType} onChange={(e) => setLicenseType(e.target.value)} placeholder="e.g. CC BY 4.0, Public Domain" />
          </div>
          <div className="admin-form-group">
            <label htmlFor="license_url">License URL</label>
            <input id="license_url" type="text" value={licenseUrl} onChange={(e) => setLicenseUrl(e.target.value)} placeholder="https://creativecommons.org/..." />
          </div>
        </div>

        <div className="admin-form-row">
          <div className="admin-form-group">
            <label htmlFor="media_rights_status">Media Rights Status</label>
            <select id="media_rights_status" value={mediaRightsStatus} onChange={(e) => setMediaRightsStatus(e.target.value)}>
              {MEDIA_RIGHTS_OPTIONS.map(s => (
                <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
              ))}
            </select>
          </div>
          <div className="admin-form-group">
            <label className="checkbox-label-row">
              <input type="checkbox" checked={isPublicDomain} onChange={(e) => setIsPublicDomain(e.target.checked)} />
              Public Domain
            </label>
          </div>
        </div>

        <div className="admin-form-group">
          <label htmlFor="attribution">
            Attribution
            {mediaRightsStatus === 'attribution_required' && <span className="field-required"> *</span>}
          </label>
          <textarea
            id="attribution"
            value={attribution}
            onChange={(e) => setAttribution(e.target.value)}
            placeholder="Required attribution text (e.g. 'Photo by …, CC BY-SA 4.0')"
            rows={2}
          />
        </div>
      </div>

      {/* ── Image fields ─────────────────────────────────────────────── */}
      <div className="admin-form-group">
        <label htmlFor="poster_url">Poster URL</label>
        <input id="poster_url" type="text" value={posterUrl} onChange={(e) => setPosterUrl(e.target.value)} placeholder="https://..." />
        {movie && (
          <div style={{ marginTop: '8px' }}>
            <label style={{ fontSize: '0.85rem' }}>Or Upload File: </label>
            <input type="file" accept="image/jpeg, image/png, image/webp" onChange={(e) => handleUpload(e, 'poster')} disabled={uploading} />
          </div>
        )}
      </div>

      <div className="admin-form-group">
        <label htmlFor="backdrop_url">Backdrop URL</label>
        <input id="backdrop_url" type="text" value={backdropUrl} onChange={(e) => setBackdropUrl(e.target.value)} placeholder="https://..." />
        {movie && (
          <div style={{ marginTop: '8px' }}>
            <label style={{ fontSize: '0.85rem' }}>Or Upload File: </label>
            <input type="file" accept="image/jpeg, image/png, image/webp" onChange={(e) => handleUpload(e, 'backdrop')} disabled={uploading} />
          </div>
        )}
      </div>

      {/* ── Video pipeline ────────────────────────────────────────────── */}
      <div className="admin-form-group" style={{ backgroundColor: 'var(--surface-raised)', padding: '1rem', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border)' }}>
        <h3 style={{ marginTop: 0, marginBottom: '0.5rem', fontSize: '1.1rem' }}>Source Video</h3>
        {movie ? (
          <>
            <div style={{ marginBottom: '1rem', fontSize: '0.9rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                <strong>Status:</strong>
                <span className={`video-status-badge video-status-badge--${videoStatus}`}>
                  {videoStatus.toUpperCase()}
                </span>
                {videoStatus === 'processing' && (
                  <span style={{ display: 'inline-block', width: '14px', height: '14px', border: '2px solid var(--text-secondary)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
                )}
              </div>

              {uploadPercent !== null && (
                <div style={{ marginBottom: '8px' }}>
                  <div style={{ fontSize: '0.8rem', marginBottom: '4px' }}>Uploading… {uploadPercent}%</div>
                  <div style={{ height: '6px', background: 'var(--border)', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${uploadPercent}%`, background: 'var(--accent)', transition: 'width 0.2s ease', borderRadius: '3px' }} />
                  </div>
                </div>
              )}

              {videoStatus === 'processing' && uploadPercent === null && (
                <div style={{ marginBottom: '8px' }}>
                  <div style={{ fontSize: '0.8rem', marginBottom: '4px' }}>{pollStep} — {pollProgress}%</div>
                  <div style={{ height: '6px', background: 'var(--border)', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${pollProgress}%`, background: 'var(--accent)', borderRadius: '3px', transition: 'width 0.5s ease-out' }} />
                  </div>
                </div>
              )}

              {availableQualities && (
                <div style={{ marginTop: '6px', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                  <strong style={{ fontSize: '0.85rem' }}>Qualities:</strong>
                  {availableQualities.split(',').map((q) => (
                    <span key={q} className="quality-badge">{q.trim()}</span>
                  ))}
                </div>
              )}

              {videoUrl && <div style={{ wordBreak: 'break-all', marginTop: '4px', opacity: 0.8, fontSize: '0.85rem' }}><em>Source: {videoUrl}</em></div>}
              {hlsUrl && <div style={{ wordBreak: 'break-all', marginTop: '4px', fontSize: '0.85rem' }}><em>HLS: <a href={hlsUrl} target="_blank" rel="noopener noreferrer">{hlsUrl}</a></em></div>}
              {processingError && (
                <div className="admin-form-error" style={{ marginTop: '6px' }}>
                  <strong>Error:</strong> {processingError}
                </div>
              )}
            </div>

            <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
              <input type="file" accept="video/mp4,video/x-matroska,video/webm,video/avi,video/quicktime,.mp4,.mkv,.webm,.avi,.mov" onChange={handleVideoUpload} disabled={uploading} />
              {(videoStatus === 'uploaded' || videoStatus === 'failed' || videoStatus === 'ready') && (
                <button type="button" className="btn btn--primary" onClick={handleProcessHls} disabled={uploading} title={videoStatus === 'ready' ? 'Re-encode with current settings' : 'Start multi-quality HLS encoding'}>
                  {videoStatus === 'ready' ? 'Re-encode' : 'Start Multi-Quality Encoding'}
                </button>
              )}
            </div>
          </>
        ) : (
          <p style={{ fontSize: '0.9rem', color: 'var(--text-tertiary)', margin: 0 }}>
            <em>Please create the movie first before uploading the primary video payload.</em>
          </p>
        )}
      </div>

      {/* ── Movie Assets (per-asset) ─────────────────────────────────── */}
      {movie && (
        <div className="assets-section">
          <div className="assets-section-header">
            <div>
              <strong>Movie Assets</strong>
              <span className="ai-fields-desc">
                Per-asset license tracking. Each poster, backdrop, trailer, or video can have its own source and license.
              </span>
            </div>
            <button type="button" className="btn btn--secondary btn--sm" onClick={addAssetRow}>+ Add Asset</button>
          </div>

          {assetError && <p className="admin-form-error">{assetError}</p>}

          {assets.length === 0 && (
            <p className="assets-empty">No assets attached to this movie.</p>
          )}

          {assets.map((asset, idx) => (
            <div key={asset.id || `new-${idx}`} className={`asset-card ${asset._isNew ? 'asset-card--new' : ''}`}>
              <div className="asset-card-header">
                <strong>Asset #{idx + 1}{asset._isNew ? ' (unsaved)' : ''}</strong>
                <div className="asset-card-actions">
                  {asset._isNew && (
                    <button type="button" className="btn btn--primary btn--sm" onClick={() => saveAsset(idx)} disabled={assetSaving}>
                      Save
                    </button>
                  )}
                  <button type="button" className="btn btn--delete btn--sm" onClick={() => removeAssetRow(idx)}>
                    Delete
                  </button>
                </div>
              </div>

              <div className="admin-form-row">
                <div className="admin-form-group">
                  <label>Asset Type</label>
                  <select value={asset.asset_type} onChange={(e) => updateAssetField(idx, 'asset_type', e.target.value)} disabled={!asset._isNew}>
                    {ASSET_TYPE_OPTIONS.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
                  </select>
                </div>
                <div className="admin-form-group">
                  <label>URL</label>
                  <input type="text" value={asset.url} onChange={(e) => updateAssetField(idx, 'url', e.target.value)} placeholder="https://..." disabled={!asset._isNew} />
                </div>
              </div>

              <div className="admin-form-group">
                <label>Quick Preset</label>
                <select
                  onChange={(e) => {
                    const i = parseInt(e.target.value);
                    if (!isNaN(i)) applyAssetPreset(idx, SOURCE_PRESETS[i]);
                  }}
                  defaultValue=""
                  disabled={!asset._isNew}
                >
                  <option value="" disabled>Select a preset…</option>
                  {SOURCE_PRESETS.map((p, i) => (
                    <option key={i} value={i}>{p.label}</option>
                  ))}
                </select>
              </div>

              <div className="admin-form-row">
                <div className="admin-form-group">
                  <label>Source Name</label>
                  <input type="text" value={asset.source_name} onChange={(e) => updateAssetField(idx, 'source_name', e.target.value)} placeholder="e.g. Wikimedia Commons" disabled={!asset._isNew} />
                </div>
                <div className="admin-form-group">
                  <label>Source URL</label>
                  <input type="text" value={asset.source_url} onChange={(e) => updateAssetField(idx, 'source_url', e.target.value)} placeholder="https://..." disabled={!asset._isNew} />
                </div>
              </div>

              <div className="admin-form-row">
                <div className="admin-form-group">
                  <label>License Type</label>
                  <input type="text" value={asset.license_type} onChange={(e) => updateAssetField(idx, 'license_type', e.target.value)} placeholder="e.g. CC BY-SA 4.0" disabled={!asset._isNew} />
                </div>
                <div className="admin-form-group">
                  <label>License URL</label>
                  <input type="text" value={asset.license_url} onChange={(e) => updateAssetField(idx, 'license_url', e.target.value)} placeholder="https://..." disabled={!asset._isNew} />
                </div>
              </div>

              <div className="admin-form-row">
                <div className="admin-form-group">
                  <label>Rights Status</label>
                  <select value={asset.media_rights_status} onChange={(e) => updateAssetField(idx, 'media_rights_status', e.target.value)} disabled={!asset._isNew}>
                    {MEDIA_RIGHTS_OPTIONS.map(s => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}
                  </select>
                </div>
                <div className="admin-form-group">
                  <label className="checkbox-label-row">
                    <input type="checkbox" checked={asset.is_public_domain} onChange={(e) => updateAssetField(idx, 'is_public_domain', e.target.checked)} disabled={!asset._isNew} />
                    Public Domain
                  </label>
                </div>
              </div>

              <div className="admin-form-group">
                <label>
                  Attribution
                  {asset.media_rights_status === 'attribution_required' && <span className="field-required"> *</span>}
                </label>
                <input type="text" value={asset.attribution} onChange={(e) => updateAssetField(idx, 'attribution', e.target.value)} placeholder="Required attribution text" disabled={!asset._isNew} />
              </div>

              {!asset._isNew && (
                <div className="asset-card-status">
                  <span className={`rights-badge rights-badge--${asset.media_rights_status}`}>
                    {asset.media_rights_status.replace(/_/g, ' ')}
                  </span>
                  {asset.is_public_domain && <span className="rights-badge rights-badge--pd">Public Domain</span>}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ── Form actions ──────────────────────────────────────────────── */}
      <div className="admin-form-actions">
        <button type="submit" className="btn btn--primary">
          {movie ? 'Save Changes' : 'Create Movie'}
        </button>
        <button type="button" className="btn btn--secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
};

export default MovieForm;
