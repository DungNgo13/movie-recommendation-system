import React, { useState } from 'react';
import {
  approveEnrichmentJob,
  getMovieEnrichmentJobs,
  rejectEnrichmentJob,
  selectEnrichmentCandidate,
  startMovieEnrichment,
  type MetadataCandidate,
  type MetadataEnrichmentJob,
} from '../../services/metadataEnrichmentService';

interface MetadataEnrichmentPanelProps {
  movieId: string;
  movieMetadataVersion?: number;
  onApplied?: (appliedFields: Record<string, unknown>, newMetadataVersion?: number | null) => void;
}

const DISPLAY_FIELD_ORDER: string[] = [
  'title',
  'overview',
  'release_date',
  'director',
  'genres',
  'cast',
  'keywords',
  'title_vi',
  'overview_vi',
  'poster_path',
  'backdrop_path',
  'tmdb_id',
  'imdb_id',
  'original_title',
  'original_language',
];

function formatValueForPreview(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '— (empty)';
  }
  if (Array.isArray(value)) {
    return value.length === 0 ? '— (empty)' : value.join(', ');
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return String(value);
}

const MetadataEnrichmentPanel: React.FC<MetadataEnrichmentPanelProps> = ({
  movieId,
  movieMetadataVersion,
  onApplied,
}) => {
  const [activeJob, setActiveJob] = useState<MetadataEnrichmentJob | null>(null);
  const [historyJobs, setHistoryJobs] = useState<MetadataEnrichmentJob[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [selectedFields, setSelectedFields] = useState<string[]>([]);
  const [allowOverwrite, setAllowOverwrite] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const initializeSelectionFromJob = (job: MetadataEnrichmentJob) => {
    setActiveJob(job);
    const chosenId =
      job.selected_candidate_id ||
      (job.candidates.length > 0 ? job.candidates[0].id : null);
    setSelectedCandidateId(chosenId);

    const cand = job.candidates.find((c) => c.id === chosenId) || job.candidates[0];
    if (cand) {
      // Pre-select only fields that are currently missing in MovSug (safe default)
      const missingFields = Object.entries(cand.proposed_fields || {})
        .filter(([field, val]) => {
          if (val === null || val === undefined) return false;
          const conflictInfo = cand.field_conflicts?.[field];
          return !conflictInfo?.requires_explicit_overwrite;
        })
        .map(([field]) => field);
      setSelectedFields(missingFields);
      setAllowOverwrite(false);
    } else {
      setSelectedFields([]);
    }
  };

  const handleStartEnrichment = async () => {
    setBusy(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const job = await startMovieEnrichment(movieId, {
        source_language: 'en-US',
        include_vi_localization: true,
        max_candidates: 5,
      });
      initializeSelectionFromJob(job);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start TMDB enrichment');
    } finally {
      setBusy(false);
    }
  };

  const handleLoadHistory = async () => {
    setBusy(true);
    setError(null);
    try {
      const jobs = await getMovieEnrichmentJobs(movieId);
      setHistoryJobs(jobs);
      setShowHistory(true);
      if (!activeJob && jobs.length > 0) {
        initializeSelectionFromJob(jobs[0]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load enrichment history');
    } finally {
      setBusy(false);
    }
  };

  const handleSelectCandidate = async (candidate: MetadataCandidate) => {
    if (!activeJob) return;
    setSelectedCandidateId(candidate.id);
    const missingFields = Object.entries(candidate.proposed_fields || {})
      .filter(([field, val]) => {
        if (val === null || val === undefined) return false;
        const conflictInfo = candidate.field_conflicts?.[field];
        return !conflictInfo?.requires_explicit_overwrite;
      })
      .map(([field]) => field);
    setSelectedFields(missingFields);
    setAllowOverwrite(false);

    if (activeJob.status === 'awaiting_review') {
      try {
        setBusy(true);
        const updated = await selectEnrichmentCandidate(activeJob.id, candidate.id);
        setActiveJob(updated);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to select candidate');
      } finally {
        setBusy(false);
      }
    }
  };

  const toggleField = (fieldName: string) => {
    setSelectedFields((prev) =>
      prev.includes(fieldName) ? prev.filter((f) => f !== fieldName) : [...prev, fieldName],
    );
  };

  const selectedCandidate: MetadataCandidate | undefined = activeJob?.candidates.find(
    (c) => c.id === selectedCandidateId,
  );

  const anyOverwriteSelected = Boolean(
    selectedCandidate &&
      selectedFields.some(
        (f) => selectedCandidate.field_conflicts?.[f]?.requires_explicit_overwrite,
      ),
  );

  const handleApproveAndApply = async () => {
    if (!activeJob || !selectedCandidate) return;
    if (selectedFields.length === 0) {
      setError('Select at least one metadata field to approve.');
      return;
    }
    if (anyOverwriteSelected && !allowOverwrite) {
      setError('Please confirm overwriting existing MovSug values before applying.');
      return;
    }

    setBusy(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const updatedJob = await approveEnrichmentJob(activeJob.id, {
        candidate_id: selectedCandidate.id,
        approved_fields: selectedFields,
        allow_overwrite_existing: allowOverwrite,
        expected_metadata_version: activeJob.movie_metadata_version ?? movieMetadataVersion ?? null,
        apply_immediately: true,
      });
      setActiveJob(updatedJob);
      setSuccessMessage(
        `Applied ${selectedFields.length} field(s) from TMDB #${selectedCandidate.provider_movie_id}.`,
      );

      if (onApplied) {
        const appliedMap: Record<string, unknown> = {};
        for (const field of selectedFields) {
          appliedMap[field] = selectedCandidate.proposed_fields[field];
        }
        onApplied(appliedMap, updatedJob.movie_metadata_version);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve and apply metadata');
    } finally {
      setBusy(false);
    }
  };

  const handleReject = async () => {
    if (!activeJob) return;
    const reason = rejectReason.trim() || 'Rejected by administrator during candidate review';
    setBusy(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const updatedJob = await rejectEnrichmentJob(
        activeJob.id,
        reason,
        selectedCandidate?.id,
      );
      setActiveJob(updatedJob);
      setSuccessMessage('Enrichment job rejected. Movie record was not modified.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reject enrichment job');
    } finally {
      setBusy(false);
    }
  };

  const orderedProposedFields = selectedCandidate
    ? DISPLAY_FIELD_ORDER.filter(
        (f) =>
          f in (selectedCandidate.proposed_fields || {}) &&
          selectedCandidate.proposed_fields[f] !== null &&
          selectedCandidate.proposed_fields[f] !== undefined,
      )
    : [];

  return (
    <section
      className="metadata-enrichment-panel"
      data-testid="metadata-enrichment-panel"
      style={{
        backgroundColor: 'var(--surface-raised, #f8f9fa)',
        padding: '1rem',
        borderRadius: '8px',
        border: '1px solid var(--border, #dee2e6)',
        marginBottom: '1.25rem',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '0.5rem',
          marginBottom: '0.5rem',
        }}
      >
        <div>
          <h3 style={{ margin: 0, fontSize: '1.05rem' }}>
            TMDB Metadata Enrichment (Human-in-the-Loop)
          </h3>
          <p style={{ margin: '2px 0 0', fontSize: '0.8rem', color: '#6c757d' }}>
            Identify candidate TMDB matches, compare staged fields, and approve updates safely.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            type="button"
            className="btn btn--primary"
            onClick={handleStartEnrichment}
            disabled={busy}
            data-testid="start-tmdb-enrichment-btn"
          >
            {busy ? 'Working…' : 'Enrich with TMDB'}
          </button>
          <button
            type="button"
            className="btn btn--secondary"
            onClick={handleLoadHistory}
            disabled={busy}
            data-testid="load-enrichment-history-btn"
          >
            View History
          </button>
        </div>
      </div>

      {error && (
        <div
          role="alert"
          data-testid="enrichment-error"
          style={{
            backgroundColor: '#f8d7da',
            color: '#721c24',
            padding: '0.6rem 0.8rem',
            borderRadius: '6px',
            fontSize: '0.85rem',
            marginBottom: '0.75rem',
          }}
        >
          {error}
        </div>
      )}

      {successMessage && (
        <div
          role="status"
          data-testid="enrichment-success"
          style={{
            backgroundColor: '#d4edda',
            color: '#155724',
            padding: '0.6rem 0.8rem',
            borderRadius: '6px',
            fontSize: '0.85rem',
            marginBottom: '0.75rem',
          }}
        >
          {successMessage}
        </div>
      )}

      {activeJob && (
        <div data-testid="active-enrichment-job" style={{ marginTop: '0.75rem' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              flexWrap: 'wrap',
              fontSize: '0.85rem',
              marginBottom: '0.75rem',
            }}
          >
            <span>
              <strong>Job Status:</strong>{' '}
              <code data-testid="enrichment-job-status">{activeJob.status}</code>
            </span>
            <span>
              <strong>Candidates:</strong> {activeJob.candidates.length}
            </span>
            {activeJob.processing_time_ms != null && (
              <span>
                <strong>Latency:</strong> {Math.round(activeJob.processing_time_ms)} ms
              </span>
            )}
          </div>

          {activeJob.candidates.length === 0 ? (
            <p style={{ fontSize: '0.85rem', color: '#856404', margin: 0 }}>
              No matching TMDB candidates were found for this movie.
            </p>
          ) : (
            <>
              {/* Candidate Identity Selector */}
              <div style={{ marginBottom: '0.85rem' }}>
                <strong style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.4rem' }}>
                  1. Select Candidate TMDB Identity:
                </strong>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                  {activeJob.candidates.map((cand) => {
                    const isSelected = cand.id === selectedCandidateId;
                    return (
                      <div
                        key={cand.id}
                        data-testid={`enrichment-candidate-${cand.provider_movie_id}`}
                        onClick={() => handleSelectCandidate(cand)}
                        style={{
                          padding: '0.55rem 0.75rem',
                          borderRadius: '6px',
                          cursor: 'pointer',
                          border: isSelected ? '2px solid #0d6efd' : '1px solid #ced4da',
                          backgroundColor: isSelected ? '#eef5ff' : '#ffffff',
                          fontSize: '0.85rem',
                        }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            flexWrap: 'wrap',
                            gap: '0.5rem',
                          }}
                        >
                          <div>
                            <strong>{cand.title}</strong>{' '}
                            {cand.release_year ? `(${cand.release_year})` : ''} —{' '}
                            <span>TMDB #{cand.provider_movie_id}</span>
                            {cand.director && <span> • Dir: {cand.director}</span>}
                          </div>
                          <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                            <span
                              style={{
                                padding: '2px 8px',
                                borderRadius: '10px',
                                fontWeight: 600,
                                fontSize: '0.75rem',
                                backgroundColor:
                                  cand.match_status === 'verified_id'
                                    ? '#d4edda'
                                    : cand.match_status === 'ambiguous' ||
                                        cand.match_status === 'conflict'
                                      ? '#fff3cd'
                                      : '#cce5ff',
                                color: '#212529',
                              }}
                            >
                              {cand.match_status} ({Math.round(cand.match_score * 100)}%)
                            </span>
                          </div>
                        </div>
                        {cand.reason_for_review && (
                          <div style={{ fontSize: '0.78rem', color: '#495057', marginTop: '3px' }}>
                            {cand.reason_for_review}
                          </div>
                        )}
                        {cand.conflicts && cand.conflicts.length > 0 && (
                          <div style={{ fontSize: '0.78rem', color: '#856404', marginTop: '3px' }}>
                            Conflicts: {cand.conflicts.join('; ')}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Side-by-side Existing vs Proposed Field Comparison */}
              {selectedCandidate && (
                <div style={{ marginBottom: '0.85rem' }}>
                  <strong style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.4rem' }}>
                    2. Compare Existing vs. Proposed Fields & Choose Fields to Approve:
                  </strong>
                  <div style={{ overflowX: 'auto' }}>
                    <table
                      style={{
                        width: '100%',
                        borderCollapse: 'collapse',
                        fontSize: '0.82rem',
                        backgroundColor: '#ffffff',
                      }}
                    >
                      <thead>
                        <tr style={{ backgroundColor: '#e9ecef', textAlign: 'left' }}>
                          <th style={{ padding: '6px 8px' }}>Approve</th>
                          <th style={{ padding: '6px 8px' }}>Field</th>
                          <th style={{ padding: '6px 8px' }}>Existing MovSug Value</th>
                          <th style={{ padding: '6px 8px' }}>Proposed TMDB Value</th>
                          <th style={{ padding: '6px 8px' }}>Conflict Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {orderedProposedFields.map((field) => {
                          const checked = selectedFields.includes(field);
                          const conflict = selectedCandidate.field_conflicts?.[field];
                          const isOverwrite = Boolean(conflict?.requires_explicit_overwrite);
                          return (
                            <tr
                              key={field}
                              style={{ borderBottom: '1px solid #dee2e6' }}
                              data-testid={`field-diff-row-${field}`}
                            >
                              <td style={{ padding: '6px 8px' }}>
                                <input
                                  type="checkbox"
                                  checked={checked}
                                  disabled={activeJob.status === 'applied' || activeJob.status === 'rejected'}
                                  onChange={() => toggleField(field)}
                                  aria-label={`Approve ${field}`}
                                />
                              </td>
                              <td style={{ padding: '6px 8px', fontWeight: 600 }}>{field}</td>
                              <td style={{ padding: '6px 8px', color: '#495057' }}>
                                {formatValueForPreview(selectedCandidate.existing_values?.[field])}
                              </td>
                              <td style={{ padding: '6px 8px', color: '#0d6efd' }}>
                                {formatValueForPreview(selectedCandidate.proposed_fields?.[field])}
                              </td>
                              <td style={{ padding: '6px 8px' }}>
                                {isOverwrite ? (
                                  <span style={{ color: '#856404', fontWeight: 600 }}>
                                    Replaces existing
                                  </span>
                                ) : conflict?.status === 'identical' ? (
                                  <span style={{ color: '#6c757d' }}>Identical</span>
                                ) : (
                                  <span style={{ color: '#155724' }}>Fills missing</span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>

                  {anyOverwriteSelected && activeJob.status !== 'applied' && (
                    <label
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.4rem',
                        marginTop: '0.6rem',
                        fontSize: '0.83rem',
                        color: '#856404',
                        fontWeight: 600,
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={allowOverwrite}
                        onChange={(e) => setAllowOverwrite(e.target.checked)}
                        data-testid="confirm-overwrite-checkbox"
                      />
                      Confirm overwriting existing MovSug values for selected fields
                    </label>
                  )}

                  {activeJob.status !== 'applied' && activeJob.status !== 'rejected' && (
                    <div
                      style={{
                        display: 'flex',
                        gap: '0.6rem',
                        alignItems: 'center',
                        flexWrap: 'wrap',
                        marginTop: '0.75rem',
                      }}
                    >
                      <button
                        type="button"
                        className="btn btn--primary"
                        onClick={handleApproveAndApply}
                        disabled={busy || selectedFields.length === 0}
                        data-testid="approve-apply-enrichment-btn"
                      >
                        Approve & Apply ({selectedFields.length})
                      </button>

                      <input
                        type="text"
                        value={rejectReason}
                        onChange={(e) => setRejectReason(e.target.value)}
                        placeholder="Optional rejection reason…"
                        aria-label="Rejection reason"
                        style={{ fontSize: '0.82rem', padding: '4px 8px', maxWidth: '220px' }}
                      />
                      <button
                        type="button"
                        className="btn btn--secondary"
                        onClick={handleReject}
                        disabled={busy}
                        data-testid="reject-enrichment-btn"
                      >
                        Reject Match
                      </button>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {showHistory && (
        <div
          data-testid="enrichment-history-list"
          style={{
            marginTop: '0.75rem',
            paddingTop: '0.75rem',
            borderTop: '1px solid #dee2e6',
            fontSize: '0.82rem',
          }}
        >
          <strong>Previous Enrichment Attempts ({historyJobs.length}):</strong>
          {historyJobs.length === 0 ? (
            <p style={{ margin: '4px 0 0', color: '#6c757d' }}>No previous enrichment jobs.</p>
          ) : (
            <ul style={{ margin: '6px 0 0', paddingLeft: '1.2rem' }}>
              {historyJobs.map((j) => (
                <li key={j.id} style={{ marginBottom: '4px' }}>
                  <code>{j.status}</code> • {j.candidates_found} candidate(s) •{' '}
                  {j.approved_fields && j.approved_fields.length > 0
                    ? `Approved: ${j.approved_fields.join(', ')}`
                    : 'No fields applied'}{' '}
                  {j.reviewing_admin_email ? `(by ${j.reviewing_admin_email})` : ''}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
};

export default MetadataEnrichmentPanel;
