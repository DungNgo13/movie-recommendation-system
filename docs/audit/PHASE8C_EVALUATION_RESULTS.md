# Phase 8C — Evaluation Results

## 1. Evaluation Matrix (A–F)

Phase 8C implements a 6-cell evaluation matrix comparing 3 recommendation models
× 2 metadata conditions:

| Cell | Model                          | Metadata  | Status         |
|------|--------------------------------|-----------|----------------|
| A    | TF-IDF v1.1                    | Original  | ✅ Implemented |
| B    | TF-IDF v1.1                    | Enriched  | ✅ Implemented |
| C    | Semantic-EN (all-MiniLM-L6-v2) | Original  | ✅ Implemented |
| D    | Semantic-EN (all-MiniLM-L6-v2) | Enriched  | ✅ Implemented |
| E    | Semantic-Multi (multilingual)  | Original  | ✅ Implemented |
| F    | Semantic-Multi (multilingual)  | Enriched  | ✅ Implemented |

## 2. Experimental Protocol

- **Dataset**: MovieLens ml-latest-small (9,742 movies, 610 users)
- **Split**: 70/15/15 per-user chronological, min 5 interactions
- **Relevance threshold**: ≥ 4.0 stars
- **Exclusion policy**: Train-set exclusion (no already-seen movies)
- **Metrics**: NDCG@K, P@K, R@K, HR@K, MAP@K, Coverage@K, ILD@K, Novelty@K
- **K values**: 5, 10, 20
- **Statistical tests**: Paired t-test, Wilcoxon signed-rank, Bootstrap CI (1000 resamples)

## 3. Enrichment Conditions

### Default (Mock Dry-Run)
- **Source**: Phase 8A mock TMDB catalog (16 movies)
- **Pilot**: Stratified sample of 200 movies (seed=8042)
- **Actually enriched with TMDB data**: 11–13 movies (from mock catalog)
- **Simulated enrichment**: Remaining pilot movies (TMDB ID assigned only)

### Live Pilot (Not Yet Authorized)
- Requires explicit user authorization
- Would use real TMDB API via Phase 8A `TMDBClient`
- Bounded by configurable record count
- Rate-limited (default 4 RPS with backoff)

## 4. Statistical Comparisons

Nine paired comparisons are computed:

1. **RQ1a**: TF-IDF enriched vs original
2. **RQ1b**: Semantic-EN enriched vs original
3. **RQ1c**: Semantic-Multi enriched vs original
4. **RQ2a**: TF-IDF vs Semantic-EN (original)
5. **RQ2b**: TF-IDF vs Semantic-EN (enriched)
6. **RQ2c**: TF-IDF vs Semantic-Multi (original)
7. **RQ2d**: TF-IDF vs Semantic-Multi (enriched)
8. **RQ2e**: Semantic-EN vs Semantic-Multi (original)
9. **RQ2f**: Semantic-EN vs Semantic-Multi (enriched)

## 5. Coverage Sensitivity

**Status**: `INSUFFICIENT EVIDENCE`

The mock catalog contains only 16 movies. Meaningful coverage sensitivity
analysis at granular levels (1%, 5%, 10%, 25%, 50%, 80%, 100%) requires
live TMDB API access.

## 6. Reproduction Commands

```powershell
# Run Phase 8C evaluation (mock dry-run, no model download needed for TF-IDF only)
cd d:\TLTN\movie-recommendation-system\backend
.\.venv\Scripts\python.exe -m app.recommendation_evaluation.cli --phase8c --phase8c-pilot-size 200

# With semantic models (requires model files)
.\.venv\Scripts\python.exe -m app.recommendation_evaluation.cli --phase8c --allow-model-download

# Run Phase 8C tests
.\.venv\Scripts\python.exe -m pytest tests/test_phase8c_identity_mapping.py -v

# Run TEC collector tests
cd d:\TLTN\movie-recommendation-system
.\.venv\Scripts\python.exe -m pytest test_center/tests/test_phase8c_collector.py -v
```

## 7. Output Artifacts

All artifacts are saved to `backend/reports/phase8c_research/`:

| File                              | Content                               |
|-----------------------------------|---------------------------------------|
| `phase8c_evaluation_summary.json` | Complete evaluation summary           |
| `phase8c_identity_coverage.json`  | MovieLens-TMDB mapping audit          |
| `phase8c_field_coverage.json`     | Field-level metadata coverage         |
| `phase8c_field_coverage.csv`      | Coverage table (CSV)                  |
| `phase8c_6cell_comparison.csv`    | 6-cell comparison table               |
| `phase8c_per_user_metrics.csv`    | Per-user metrics for paired analysis  |
| `phase8c_statistical_comparisons.json` | Statistical test results         |
| `snapshots/snapshot_*.json`       | Immutable research metadata snapshots |
| `snapshots/manifest_*.json`       | Compact snapshot manifests            |
