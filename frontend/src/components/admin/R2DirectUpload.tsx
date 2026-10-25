import React, { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import type { Movie } from '../../models';
import { displayPercent, useR2DirectUpload } from '../../hooks/useR2DirectUpload';
import type { R2UploadFailure } from '../../hooks/useR2DirectUpload';
import { R2_ACCEPT_ATTRIBUTE, R2_CLIENT_MAX_UPLOAD_BYTES } from '../../services/r2UploadService';
import { formatBytes } from '../../utils/formatBytes';

interface R2DirectUploadProps {
  movieId: string;
  /** Disable while another (local) upload or encode request is running. */
  disabled?: boolean;
  onBusyChange?: (busy: boolean) => void;
  onCompleted?: (movie: Movie | null) => void;
  onUnauthorized?: () => void;
  maxBytes?: number;
}

/** Errors whose server message is safe and useful to show verbatim. */
const SHOW_SERVER_DETAIL = new Set(['too_large', 'validation', 'mismatch']);

const R2DirectUpload: React.FC<R2DirectUploadProps> = ({
  movieId, disabled = false, onBusyChange, onCompleted, onUnauthorized, maxBytes = R2_CLIENT_MAX_UPLOAD_BYTES,
}) => {
  const { t } = useTranslation(['admin', 'common']);
  const { state, start, cancel, retryCompletion } = useR2DirectUpload({
    movieId, onCompleted, onUnauthorized, maxBytes,
  });

  const { phase } = state;
  const busy = phase === 'requesting_url' || phase === 'uploading' || phase === 'verifying';
  const lastBusyRef = useRef(false);
  useEffect(() => {
    if (lastBusyRef.current !== busy) {
      lastBusyRef.current = busy;
      onBusyChange?.(busy);
    }
  }, [busy, onBusyChange]);

  const percent = displayPercent(state);
  const showProgress = phase === 'uploading' || phase === 'verifying' || phase === 'completed';

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (file) void start(file);
  };

  const errorText = (failure: R2UploadFailure): string => {
    const base = t(`admin:r2Upload.errors.${failure.kind}`, {
      max: formatBytes(maxBytes),
    });
    return SHOW_SERVER_DETAIL.has(failure.kind) && failure.stage !== 'validation'
      ? `${base} (${failure.message})`
      : base;
  };

  const statusText: Record<typeof phase, string> = {
    idle: t('admin:r2Upload.status.idle'),
    requesting_url: t('admin:r2Upload.status.requestingUrl'),
    uploading: t('admin:r2Upload.status.uploading', {
      percent,
      loaded: formatBytes(state.loaded),
      total: formatBytes(state.total),
    }),
    verifying: t('admin:r2Upload.status.verifying'),
    completed: t('admin:r2Upload.status.completed'),
    failed: state.error?.stage === 'complete'
      ? t('admin:r2Upload.status.verifyFailed')
      : t('admin:r2Upload.status.uploadFailed'),
    cancelled: t('admin:r2Upload.status.cancelled'),
  };

  return (
    <section
      className="r2-direct-upload"
      data-testid="r2-direct-upload"
      data-phase={phase}
      aria-labelledby="r2-upload-heading"
      style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px dashed var(--border, #dee2e6)' }}
    >
      <h4 id="r2-upload-heading" style={{ margin: '0 0 0.25rem', fontSize: '1rem' }}>
        {t('admin:r2Upload.title')}
      </h4>
      <p style={{ margin: '0 0 0.5rem', fontSize: '0.8rem', color: 'var(--text-secondary, #6c757d)' }}>
        {t('admin:r2Upload.hint', { max: formatBytes(maxBytes) })}
      </p>

      <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <input
          id="r2-video-input"
          type="file"
          accept={R2_ACCEPT_ATTRIBUTE}
          aria-label={t('admin:r2Upload.selectFile')}
          onChange={handleChange}
          disabled={disabled || busy}
        />
        {(phase === 'requesting_url' || phase === 'uploading') && (
          <button id="r2-upload-cancel" type="button" className="btn btn--secondary" onClick={cancel}>
            {t('admin:r2Upload.cancel')}
          </button>
        )}
        {phase === 'failed' && state.canRetryCompletion && (
          <button
            id="r2-upload-retry-verify"
            type="button"
            className="btn btn--primary"
            onClick={() => void retryCompletion()}
          >
            {t('admin:r2Upload.retryVerify')}
          </button>
        )}
      </div>

      <div role="status" aria-live="polite" style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}>
        {phase !== 'idle' && state.fileName && (
          <span style={{ marginRight: '0.5rem', fontWeight: 600 }}>{state.fileName}</span>
        )}
        <span data-testid="r2-upload-status">{statusText[phase]}</span>
      </div>

      {showProgress && (
        <div
          role="progressbar"
          aria-label={t('admin:r2Upload.progressLabel')}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
          style={{ height: '6px', background: '#dee2e6', borderRadius: '3px', overflow: 'hidden', marginTop: '6px' }}
        >
          <div
            style={{
              height: '100%',
              width: `${percent}%`,
              background: phase === 'completed' ? '#198754' : '#0d6efd',
              transition: 'width 0.2s ease',
              borderRadius: '3px',
            }}
          />
        </div>
      )}

      {phase === 'failed' && state.error && (
        <div
          role="alert"
          style={{ color: '#721c24', marginTop: '6px', fontSize: '0.85rem', background: '#f8d7da', padding: '8px', borderRadius: '4px' }}
        >
          {errorText(state.error)}
          {state.error.stage === 'complete' && !state.canRetryCompletion && (
            <div style={{ marginTop: '4px' }}>{t('admin:r2Upload.newUploadRequired')}</div>
          )}
        </div>
      )}

      {phase === 'completed' && (
        <p style={{ margin: '6px 0 0', fontSize: '0.8rem', color: '#155724' }}>
          {t('admin:r2Upload.hlsNotAvailable')}
        </p>
      )}
    </section>
  );
};

export default R2DirectUpload;
