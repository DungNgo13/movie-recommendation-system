import React from 'react';
import type { Movie, MovieAsset } from '../models';

interface SourceData {
  source_name?: string | null;
  source_url?: string | null;
  license_type?: string | null;
  license_url?: string | null;
  attribution?: string | null;
  is_public_domain?: boolean;
}

interface SourceAttributionProps {
  /** Pass either a movie or an individual asset — both carry the same source fields */
  movie?: Movie;
  asset?: MovieAsset;
  /** Optional label shown as the heading (default: "Source and License") */
  label?: string;
}

/**
 * Displays source, license, and attribution information.
 * Accepts either a Movie or a MovieAsset — renders nothing if all source fields are empty.
 */
const SourceAttribution: React.FC<SourceAttributionProps> = ({ movie, asset, label }) => {
  const data: SourceData = asset ?? movie ?? {};

  const {
    source_name,
    source_url,
    license_type,
    license_url,
    attribution,
    is_public_domain,
  } = data;

  // Don't render anything if there is no source data at all
  const hasAnyData = source_name || license_type || attribution || is_public_domain;
  if (!hasAnyData) return null;

  const isTmdb = source_name?.toLowerCase().includes('tmdb') ||
                 source_name?.toLowerCase().includes('the movie database');

  return (
    <aside className="source-attribution" id="source-attribution">
      <h3 className="source-attribution__heading">{label || 'Source and License'}</h3>

      <dl className="source-attribution__list">
        {source_name && (
          <>
            <dt>Source</dt>
            <dd>
              {source_url ? (
                <a
                  href={source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="source-attribution__link"
                >
                  {source_name}
                </a>
              ) : (
                source_name
              )}
            </dd>
          </>
        )}

        {license_type && (
          <>
            <dt>License</dt>
            <dd>
              {license_url ? (
                <a
                  href={license_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="source-attribution__link"
                >
                  {license_type}
                </a>
              ) : (
                license_type
              )}
              {is_public_domain && (
                <span className="source-attribution__badge">Public Domain</span>
              )}
            </dd>
          </>
        )}

        {!license_type && is_public_domain && (
          <>
            <dt>License</dt>
            <dd>
              <span className="source-attribution__badge">Public Domain</span>
            </dd>
          </>
        )}

        {attribution && (
          <>
            <dt>Attribution</dt>
            <dd className="source-attribution__text">{attribution}</dd>
          </>
        )}
      </dl>

      {isTmdb && (
        <p className="source-attribution__disclaimer">
          This product uses the TMDB API but is not endorsed or certified by TMDB.
        </p>
      )}
    </aside>
  );
};

export default SourceAttribution;
