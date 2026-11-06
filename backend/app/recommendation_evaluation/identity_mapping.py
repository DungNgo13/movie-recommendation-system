"""
MovieLens-to-TMDB Identity Mapping Layer (Phase 8C).

Loads ``links.csv`` from the MovieLens ml-latest-small dataset and creates
a deterministic mapping between MovieLens movie IDs, IMDb IDs, and TMDB IDs.

Provides:
  1. Comprehensive identity mapping from links.csv
  2. Coverage audit: total, mapped, unmapped, duplicates
  3. Cross-reference validation against movies.csv titles/years
  4. ID provenance tracking
  5. JSON identity coverage report generation
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("identity_mapping")

# Year extraction regex: matches "(1995)" or "(2003)" at end of title
_YEAR_RE = re.compile(r"\((\d{4})\)\s*$")


@dataclass
class ExternalIdRecord:
    """A single MovieLens → external ID mapping record."""

    movielens_id: str
    imdb_id: str  # zero-padded 7-digit (no 'tt' prefix)
    tmdb_id: int | None  # None if missing in links.csv
    source: str = "movielens_links_csv"


@dataclass
class IdentityMappingResult:
    """Complete identity mapping audit result."""

    total_movielens_movies: int
    total_links_rows: int
    movies_with_tmdb_id: int
    movies_without_tmdb_id: int
    movies_with_imdb_id: int
    movies_without_imdb_id: int
    tmdb_coverage_pct: float
    imdb_coverage_pct: float
    duplicate_tmdb_ids: list[dict[str, Any]]
    movies_only_in_links: list[str]
    movies_only_in_catalog: list[str]
    links_checksum: str
    records: dict[str, ExternalIdRecord]
    unmapped_movie_ids: list[str]
    title_year_index: dict[str, tuple[str, int | None]]  # mid -> (title, year)


def _extract_year(title: str) -> int | None:
    """Extract year from MovieLens title format: 'Toy Story (1995)'."""
    m = _YEAR_RE.search(title)
    return int(m.group(1)) if m else None


def _extract_clean_title(title: str) -> str:
    """Remove trailing year from MovieLens title."""
    return _YEAR_RE.sub("", title).strip()


def load_identity_mapping(
    dataset_dir: Path,
) -> IdentityMappingResult:
    """
    Load ``links.csv`` and ``movies.csv`` to build a complete identity mapping.

    Validates:
      - Non-null and correctly formatted TMDB IDs (positive integers)
      - IMDb IDs (zero-padded strings)
      - Duplicate TMDB IDs (same tmdbId → multiple movieIds)
      - Movies present in movies.csv but missing from links.csv (and vice versa)

    Returns:
        IdentityMappingResult with all mapping data and audit information.
    """
    links_path = dataset_dir / "links.csv"
    movies_path = dataset_dir / "movies.csv"

    if not links_path.is_file():
        raise FileNotFoundError(f"links.csv not found at {links_path}")
    if not movies_path.is_file():
        raise FileNotFoundError(f"movies.csv not found at {movies_path}")

    # Compute links.csv checksum
    hasher = hashlib.sha256()
    with open(links_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    links_checksum = hasher.hexdigest()

    # 1. Load movies.csv for title/year reference
    title_year_index: dict[str, tuple[str, int | None]] = {}
    catalog_movie_ids: set[str] = set()
    with open(movies_path, mode="r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            mid = row["movieId"].strip()
            title = row["title"].strip()
            year = _extract_year(title)
            title_year_index[mid] = (title, year)
            catalog_movie_ids.add(mid)

    # 2. Load links.csv
    records: dict[str, ExternalIdRecord] = {}
    tmdb_id_to_movie_ids: dict[int, list[str]] = {}
    links_movie_ids: set[str] = set()

    with open(links_path, mode="r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            mid = row.get("movieId", "").strip()
            raw_imdb = row.get("imdbId", "").strip()
            raw_tmdb = row.get("tmdbId", "").strip()

            if not mid:
                continue

            links_movie_ids.add(mid)

            # Parse TMDB ID
            tmdb_id: int | None = None
            if raw_tmdb and raw_tmdb.isdigit():
                parsed = int(raw_tmdb)
                if parsed > 0:
                    tmdb_id = parsed

            # Parse IMDb ID (keep as zero-padded string)
            imdb_id = raw_imdb if raw_imdb else ""

            records[mid] = ExternalIdRecord(
                movielens_id=mid,
                imdb_id=imdb_id,
                tmdb_id=tmdb_id,
            )

            # Track duplicates
            if tmdb_id is not None:
                tmdb_id_to_movie_ids.setdefault(tmdb_id, []).append(mid)

    # 3. Compute coverage statistics
    movies_with_tmdb = sum(1 for r in records.values() if r.tmdb_id is not None)
    movies_without_tmdb = sum(1 for r in records.values() if r.tmdb_id is None)
    movies_with_imdb = sum(1 for r in records.values() if r.imdb_id)
    movies_without_imdb = sum(1 for r in records.values() if not r.imdb_id)

    # 4. Detect duplicate TMDB IDs
    duplicate_tmdb = [
        {"tmdb_id": tid, "movielens_ids": mids}
        for tid, mids in tmdb_id_to_movie_ids.items()
        if len(mids) > 1
    ]

    # 5. Cross-reference check
    only_in_links = sorted(links_movie_ids - catalog_movie_ids)
    only_in_catalog = sorted(catalog_movie_ids - links_movie_ids)

    # 6. Unmapped movie IDs (in catalog but no TMDB ID)
    unmapped_ids = sorted(
        mid
        for mid in catalog_movie_ids
        if mid not in records or records[mid].tmdb_id is None
    )

    total_catalog = len(catalog_movie_ids)
    tmdb_coverage_pct = round(movies_with_tmdb / total_catalog * 100, 4) if total_catalog > 0 else 0.0
    imdb_coverage_pct = round(movies_with_imdb / total_catalog * 100, 4) if total_catalog > 0 else 0.0

    logger.info(
        "Identity mapping loaded: %d catalog movies, %d links rows, "
        "%d with TMDB (%.2f%%), %d with IMDb (%.2f%%), %d duplicates",
        total_catalog,
        len(records),
        movies_with_tmdb,
        tmdb_coverage_pct,
        movies_with_imdb,
        imdb_coverage_pct,
        len(duplicate_tmdb),
    )

    return IdentityMappingResult(
        total_movielens_movies=total_catalog,
        total_links_rows=len(records),
        movies_with_tmdb_id=movies_with_tmdb,
        movies_without_tmdb_id=movies_without_tmdb,
        movies_with_imdb_id=movies_with_imdb,
        movies_without_imdb_id=movies_without_imdb,
        tmdb_coverage_pct=tmdb_coverage_pct,
        imdb_coverage_pct=imdb_coverage_pct,
        duplicate_tmdb_ids=duplicate_tmdb,
        movies_only_in_links=only_in_links,
        movies_only_in_catalog=only_in_catalog,
        links_checksum=links_checksum,
        records=records,
        unmapped_movie_ids=unmapped_ids,
        title_year_index=title_year_index,
    )


def get_tmdb_id_for_movie(mapping: IdentityMappingResult, movie_id: str) -> int | None:
    """Look up the TMDB ID for a given MovieLens movie ID."""
    rec = mapping.records.get(movie_id)
    return rec.tmdb_id if rec else None


def get_imdb_id_for_movie(mapping: IdentityMappingResult, movie_id: str) -> str | None:
    """Look up the IMDb ID for a given MovieLens movie ID (with tt prefix)."""
    rec = mapping.records.get(movie_id)
    if rec and rec.imdb_id:
        return f"tt{rec.imdb_id}"
    return None


def build_tmdb_to_movielens_index(
    mapping: IdentityMappingResult,
) -> dict[int, str]:
    """Build a reverse index: TMDB ID → MovieLens ID (first match only)."""
    index: dict[int, str] = {}
    for mid, rec in mapping.records.items():
        if rec.tmdb_id is not None and rec.tmdb_id not in index:
            index[rec.tmdb_id] = mid
    return index


def generate_identity_coverage_report(
    mapping: IdentityMappingResult,
    output_dir: Path,
) -> Path:
    """
    Generate a JSON identity coverage report.

    Returns:
        Path to the written report file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Sample unmapped movies with titles for review
    sample_unmapped = []
    for mid in mapping.unmapped_movie_ids[:50]:
        title_info = mapping.title_year_index.get(mid)
        sample_unmapped.append({
            "movie_id": mid,
            "title": title_info[0] if title_info else "UNKNOWN",
            "year": title_info[1] if title_info else None,
        })

    report = {
        "report_type": "phase8c_identity_coverage",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "links_csv_checksum": mapping.links_checksum,
        "summary": {
            "total_movielens_catalog": mapping.total_movielens_movies,
            "total_links_rows": mapping.total_links_rows,
            "movies_with_tmdb_id": mapping.movies_with_tmdb_id,
            "movies_without_tmdb_id": mapping.movies_without_tmdb_id,
            "movies_with_imdb_id": mapping.movies_with_imdb_id,
            "movies_without_imdb_id": mapping.movies_without_imdb_id,
            "tmdb_coverage_pct": mapping.tmdb_coverage_pct,
            "imdb_coverage_pct": mapping.imdb_coverage_pct,
        },
        "data_quality": {
            "duplicate_tmdb_ids_count": len(mapping.duplicate_tmdb_ids),
            "duplicate_tmdb_ids": mapping.duplicate_tmdb_ids,
            "movies_only_in_links_count": len(mapping.movies_only_in_links),
            "movies_only_in_links": mapping.movies_only_in_links,
            "movies_only_in_catalog_count": len(mapping.movies_only_in_catalog),
            "movies_only_in_catalog": mapping.movies_only_in_catalog[:50],
        },
        "unmapped_movies_sample": sample_unmapped,
        "provenance": {
            "source": "movielens_links_csv",
            "dataset": "ml-latest-small",
            "id_fields": ["movieId", "imdbId", "tmdbId"],
        },
    }

    report_path = output_dir / "phase8c_identity_coverage.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Identity coverage report written to %s", report_path)
    return report_path

