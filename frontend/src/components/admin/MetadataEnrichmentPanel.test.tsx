import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import MetadataEnrichmentPanel from './MetadataEnrichmentPanel';
import type { MetadataEnrichmentJob } from '../../services/metadataEnrichmentService';

const startMovieEnrichmentMock = vi.fn();
const getMovieEnrichmentJobsMock = vi.fn();
const selectEnrichmentCandidateMock = vi.fn();
const approveEnrichmentJobMock = vi.fn();
const rejectEnrichmentJobMock = vi.fn();

vi.mock('../../services/metadataEnrichmentService', () => ({
  startMovieEnrichment: (...args: unknown[]) => startMovieEnrichmentMock(...args),
  getMovieEnrichmentJobs: (...args: unknown[]) => getMovieEnrichmentJobsMock(...args),
  selectEnrichmentCandidate: (...args: unknown[]) => selectEnrichmentCandidateMock(...args),
  approveEnrichmentJob: (...args: unknown[]) => approveEnrichmentJobMock(...args),
  rejectEnrichmentJob: (...args: unknown[]) => rejectEnrichmentJobMock(...args),
}));

function makeStagedJob(overrides: Partial<MetadataEnrichmentJob> = {}): MetadataEnrichmentJob {
  return {
    id: 'job-1',
    movie_id: 'movie-1',
    provider: 'tmdb',
    source_language: 'en-US',
    status: 'awaiting_review',
    selected_candidate_id: 'cand-1',
    review_state: 'pending_review',
    application_status: 'not_applied',
    candidates_found: 2,
    retry_count: 0,
    http_429_count: 0,
    processing_time_ms: 85.4,
    is_mocked: true,
    created_at: '2026-11-04T07:00:00Z',
    updated_at: '2026-11-04T07:00:00Z',
    movie_metadata_version: 1,
    candidates: [
      {
        id: 'cand-1',
        job_id: 'job-1',
        movie_id: 'movie-1',
        provider: 'tmdb',
        provider_movie_id: '278',
        source_language: 'en-US',
        title: 'The Shawshank Redemption',
        original_title: 'The Shawshank Redemption',
        release_date: '1994-09-23',
        release_year: 1994,
        original_language: 'en',
        director: 'Frank Darabont',
        match_score: 0.96,
        match_status: 'review_required',
        is_verified_id_match: false,
        match_evidence: {},
        conflicts: [],
        reason_for_review: 'High-confidence title & year match awaiting human confirmation.',
        proposed_fields: {
          title: 'The Shawshank Redemption',
          overview: 'TMDB proposed overview',
          cast: ['Tim Robbins', 'Morgan Freeman'],
          keywords: ['prison', 'hope'],
        },
        existing_values: {
          title: 'The Shawshank Redemption 1994',
          overview: 'Existing manual overview',
          cast: [],
          keywords: [],
        },
        field_conflicts: {
          title: {
            status: 'conflict_overwrite',
            existing_value: 'The Shawshank Redemption 1994',
            proposed_value: 'The Shawshank Redemption',
            requires_explicit_overwrite: true,
          },
          overview: {
            status: 'conflict_overwrite',
            existing_value: 'Existing manual overview',
            proposed_value: 'TMDB proposed overview',
            requires_explicit_overwrite: true,
          },
          cast: {
            status: 'missing_in_movsug',
            existing_value: [],
            proposed_value: ['Tim Robbins', 'Morgan Freeman'],
            requires_explicit_overwrite: false,
          },
          keywords: {
            status: 'missing_in_movsug',
            existing_value: [],
            proposed_value: ['prison', 'hope'],
            requires_explicit_overwrite: false,
          },
        },
        review_state: 'selected',
        retrieved_at: '2026-11-04T07:00:00Z',
      },
      {
        id: 'cand-2',
        job_id: 'job-1',
        movie_id: 'movie-1',
        provider: 'tmdb',
        provider_movie_id: '999278',
        source_language: 'en-US',
        title: 'Shawshank Documentary',
        release_year: 2014,
        match_score: 0.52,
        match_status: 'ambiguous',
        is_verified_id_match: false,
        match_evidence: {},
        conflicts: ['release_year_mismatch:1994!=2014'],
        proposed_fields: {
          title: 'Shawshank Documentary',
          cast: ['Doc Narrator'],
        },
        existing_values: {
          title: 'The Shawshank Redemption 1994',
          cast: [],
        },
        field_conflicts: {
          title: {
            status: 'conflict_overwrite',
            existing_value: 'The Shawshank Redemption 1994',
            proposed_value: 'Shawshank Documentary',
            requires_explicit_overwrite: true,
          },
          cast: {
            status: 'missing_in_movsug',
            existing_value: [],
            proposed_value: ['Doc Narrator'],
            requires_explicit_overwrite: false,
          },
        },
        review_state: 'pending',
        retrieved_at: '2026-11-04T07:00:00Z',
      },
    ],
    review_events: [],
    provenances: [],
    ...overrides,
  };
}

beforeEach(() => {
  startMovieEnrichmentMock.mockReset();
  getMovieEnrichmentJobsMock.mockReset();
  selectEnrichmentCandidateMock.mockReset();
  approveEnrichmentJobMock.mockReset();
  rejectEnrichmentJobMock.mockReset();
});

describe('MetadataEnrichmentPanel', () => {
  it('triggers TMDB enrichment, pre-selects only missing fields, and applies approved fields', async () => {
    const stagedJob = makeStagedJob();
    startMovieEnrichmentMock.mockResolvedValue(stagedJob);
    approveEnrichmentJobMock.mockResolvedValue({
      ...stagedJob,
      status: 'applied',
      application_status: 'applied',
      movie_metadata_version: 2,
    });
    const onApplied = vi.fn();

    render(<MetadataEnrichmentPanel movieId="movie-1" movieMetadataVersion={1} onApplied={onApplied} />);

    fireEvent.click(screen.getByTestId('start-tmdb-enrichment-btn'));

    await waitFor(() => expect(startMovieEnrichmentMock).toHaveBeenCalledWith('movie-1', expect.any(Object)));
    expect(screen.getByTestId('enrichment-candidate-278')).toBeInTheDocument();
    expect(screen.getByTestId('enrichment-candidate-999278')).toBeInTheDocument();

    // Missing fields (cast, keywords) are pre-checked; overwrite fields (title, overview) are unchecked
    const castCheckbox = screen.getByLabelText('Approve cast') as HTMLInputElement;
    const keywordsCheckbox = screen.getByLabelText('Approve keywords') as HTMLInputElement;
    const overviewCheckbox = screen.getByLabelText('Approve overview') as HTMLInputElement;
    expect(castCheckbox.checked).toBe(true);
    expect(keywordsCheckbox.checked).toBe(true);
    expect(overviewCheckbox.checked).toBe(false);

    // Click Approve & Apply for the pre-selected missing fields
    fireEvent.click(screen.getByTestId('approve-apply-enrichment-btn'));

    await waitFor(() =>
      expect(approveEnrichmentJobMock).toHaveBeenCalledWith('job-1', {
        candidate_id: 'cand-1',
        approved_fields: ['cast', 'keywords'],
        allow_overwrite_existing: false,
        expected_metadata_version: 1,
        apply_immediately: true,
      }),
    );
    expect(onApplied).toHaveBeenCalledWith(
      {
        cast: ['Tim Robbins', 'Morgan Freeman'],
        keywords: ['prison', 'hope'],
      },
      2,
    );
    expect(screen.getByTestId('enrichment-success')).toHaveTextContent('Applied 2 field(s) from TMDB #278.');
  });

  it('requires explicit overwrite confirmation when replacing existing values', async () => {
    const stagedJob = makeStagedJob();
    startMovieEnrichmentMock.mockResolvedValue(stagedJob);
    approveEnrichmentJobMock.mockResolvedValue({
      ...stagedJob,
      status: 'applied',
      application_status: 'applied',
      movie_metadata_version: 2,
    });

    render(<MetadataEnrichmentPanel movieId="movie-1" movieMetadataVersion={1} />);
    fireEvent.click(screen.getByTestId('start-tmdb-enrichment-btn'));
    await waitFor(() => expect(screen.getByLabelText('Approve overview')).toBeInTheDocument());

    // Check `overview` which replaces existing value
    fireEvent.click(screen.getByLabelText('Approve overview'));
    expect(screen.getByTestId('confirm-overwrite-checkbox')).toBeInTheDocument();

    // Try approving without checking overwrite confirmation -> shows validation alert
    fireEvent.click(screen.getByTestId('approve-apply-enrichment-btn'));
    expect(screen.getByTestId('enrichment-error')).toHaveTextContent(
      'Please confirm overwriting existing MovSug values before applying.',
    );
    expect(approveEnrichmentJobMock).not.toHaveBeenCalled();

    // Check confirmation checkbox and approve -> succeeds
    fireEvent.click(screen.getByTestId('confirm-overwrite-checkbox'));
    fireEvent.click(screen.getByTestId('approve-apply-enrichment-btn'));

    await waitFor(() =>
      expect(approveEnrichmentJobMock).toHaveBeenCalledWith(
        'job-1',
        expect.objectContaining({
          allow_overwrite_existing: true,
          approved_fields: ['cast', 'keywords', 'overview'],
        }),
      ),
    );
  });

  it('supports candidate switching, rejection, and viewing enrichment history', async () => {
    const stagedJob = makeStagedJob();
    startMovieEnrichmentMock.mockResolvedValue(stagedJob);
    selectEnrichmentCandidateMock.mockResolvedValue({
      ...stagedJob,
      selected_candidate_id: 'cand-2',
    });
    rejectEnrichmentJobMock.mockResolvedValue({
      ...stagedJob,
      status: 'rejected',
      review_state: 'rejected',
    });
    getMovieEnrichmentJobsMock.mockResolvedValue([
      {
        ...stagedJob,
        status: 'rejected',
        reviewing_admin_email: 'admin@movsug.test',
      },
    ]);

    render(<MetadataEnrichmentPanel movieId="movie-1" />);
    fireEvent.click(screen.getByTestId('start-tmdb-enrichment-btn'));
    await waitFor(() => expect(screen.getByTestId('enrichment-candidate-999278')).toBeInTheDocument());

    // Switch to candidate 2
    fireEvent.click(screen.getByTestId('enrichment-candidate-999278'));
    await waitFor(() =>
      expect(selectEnrichmentCandidateMock).toHaveBeenCalledWith('job-1', 'cand-2'),
    );

    // Reject candidate match
    fireEvent.change(screen.getByLabelText('Rejection reason'), {
      target: { value: 'Documentary, not feature film' },
    });
    fireEvent.click(screen.getByTestId('reject-enrichment-btn'));
    await waitFor(() =>
      expect(rejectEnrichmentJobMock).toHaveBeenCalledWith(
        'job-1',
        'Documentary, not feature film',
        'cand-2',
      ),
    );

    // Load history
    fireEvent.click(screen.getByTestId('load-enrichment-history-btn'));
    await waitFor(() => expect(getMovieEnrichmentJobsMock).toHaveBeenCalledWith('movie-1'));
    expect(screen.getByTestId('enrichment-history-list')).toHaveTextContent('admin@movsug.test');
  });
});

