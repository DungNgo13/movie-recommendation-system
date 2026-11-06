# Phase 8C — Identity Mapping Audit

## 1. Overview

The identity mapping layer reads `links.csv` from the MovieLens ml-latest-small dataset
and creates a deterministic mapping between MovieLens movie IDs, IMDb IDs, and TMDB IDs.

## 2. Module

- **File**: `backend/app/recommendation_evaluation/identity_mapping.py`
- **Functions**: `load_identity_mapping()`, `get_tmdb_id_for_movie()`, `get_imdb_id_for_movie()`, `build_tmdb_to_movielens_index()`, `generate_identity_coverage_report()`
- **Data classes**: `ExternalIdRecord`, `IdentityMappingResult`

## 3. links.csv Structure

| Field     | Type     | Example      | Notes                                |
|-----------|----------|-------------|--------------------------------------|
| movieId   | integer  | 1           | MovieLens movie identifier           |
| imdbId    | string   | 0114709     | Zero-padded, no `tt` prefix          |
| tmdbId    | integer  | 862         | May be empty for some movies         |

## 4. Expected Coverage (ml-latest-small)

- **Total catalog**: 9,742 movies in `movies.csv`
- **links.csv rows**: 9,743 (1 extra row for movieId not in catalog, or header)
- **TMDB ID coverage**: ~99.9% (only a few movies lack TMDB IDs)
- **IMDb ID coverage**: ~100%

## 5. Validation Checks

1. ✅ Non-null TMDB IDs parsed as positive integers
2. ✅ IMDb IDs preserved as zero-padded strings
3. ✅ Duplicate TMDB IDs detected and reported
4. ✅ Cross-reference between `movies.csv` and `links.csv`
5. ✅ Title/year extraction for later TMDB verification
6. ✅ SHA-256 checksum of `links.csv`

## 6. Production Isolation

The identity mapping module:
- Does NOT import SQLAlchemy
- Does NOT access `app.models`
- Does NOT modify any database
- Reads only CSV files from the dataset directory
- Outputs only in-memory data structures and JSON files

## 7. Test Coverage

30 tests in `backend/tests/test_phase8c_identity_mapping.py`:
- Valid mapping loading
- Coverage percentage computation
- Missing TMDB ID detection
- Forward and reverse lookups
- Duplicate detection
- Coverage report generation
- Error handling (missing files)
- Production isolation verification

