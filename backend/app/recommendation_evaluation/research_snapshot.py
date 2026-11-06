"""
Research Metadata Snapshot Infrastructure (Phase 8C).

Creates and manages immutable research metadata snapshots that are completely
isolated from the production PostgreSQL database. Snapshots store enriched
movie metadata as JSON files for reproducible offline experiments.

Design principles:
  - Each snapshot is immutable once written (new snapshot ID, never overwrite)
  - SHA-256 checksums ensure integrity verification
  - Complete provenance tracking (source, timestamp, coverage, config)
  - Snapshots stored in ``backend/reports/phase8c_research/snapshots/``
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dataset import MovieMetadata

logger = logging.getLogger("research_snapshot")


@dataclass
class FieldCoverage:
    """Field-level coverage statistics for a metadata snapshot."""

    title: int = 0
    original_title: int = 0
    title_vi: int = 0
    genres: int = 0
    overview: int = 0
    overview_vi: int = 0
    keywords: int = 0
    cast: int = 0
    director: int = 0
    original_language: int = 0

    def to_dict(self, total: int) -> dict[str, Any]:
        """Convert to dict with percentages."""
        fields = {
            "title": self.title,
            "original_title": self.original_title,
            "title_vi": self.title_vi,
            "genres": self.genres,
            "overview": self.overview,
            "overview_vi": self.overview_vi,
            "keywords": self.keywords,
            "cast": self.cast,
            "director": self.director,
            "original_language": self.original_language,
        }
        result: dict[str, Any] = {}
        for fname, count in fields.items():
            pct = round(count / total * 100, 4) if total > 0 else 0.0
            result[fname] = {"count": count, "total": total, "coverage_pct": pct}
        return result


@dataclass
class ResearchMetadataSnapshot:
    """An immutable research metadata snapshot for offline experiments."""

    snapshot_id: str
    created_at: str
    movielens_checksum: str
    split_checksum: str
    links_checksum: str
    total_movies: int
    enriched_count: int
    unenriched_count: int
    failed_count: int
    field_coverage: FieldCoverage
    enrichment_source: str  # "mock_tmdb_catalog" or "live_tmdb_api"
    enrichment_config: dict[str, Any]
    movies: dict[str, dict[str, Any]]  # mid -> serialised MovieMetadata
    snapshot_checksum: str = ""

    def compute_checksum(self) -> str:
        """Compute SHA-256 over snapshot content (excluding the checksum itself)."""
        payload = {
            "snapshot_id": self.snapshot_id,
            "movielens_checksum": self.movielens_checksum,
            "split_checksum": self.split_checksum,
            "links_checksum": self.links_checksum,
            "total_movies": self.total_movies,
            "enriched_count": self.enriched_count,
            "movies_keys_sorted": sorted(self.movies.keys()),
        }
        content = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(content).hexdigest()


def serialize_movie_metadata(movie: MovieMetadata) -> dict[str, Any]:
    """Serialize a MovieMetadata into a JSON-safe dictionary."""
    return {
        "movie_id": movie.movie_id,
        "title": movie.title,
        "genres": list(movie.genres),
        "tags": list(movie.tags),
        "text_profile": movie.text_profile,
        "original_title": movie.original_title,
        "title_vi": movie.title_vi,
        "overview": movie.overview,
        "overview_vi": movie.overview_vi,
        "cast": list(movie.cast),
        "director": movie.director,
        "keywords": list(movie.keywords),
        "tmdb_id": movie.tmdb_id,
        "metadata_source": movie.metadata_source,
        "metadata_version": movie.metadata_version,
        "metadata_enrichment_status": movie.metadata_enrichment_status,
    }


def deserialize_movie_metadata(data: dict[str, Any]) -> MovieMetadata:
    """Deserialize a dictionary back into MovieMetadata."""
    return MovieMetadata(
        movie_id=str(data["movie_id"]),
        title=str(data.get("title", "")),
        genres=list(data.get("genres", [])),
        tags=list(data.get("tags", [])),
        text_profile=str(data.get("text_profile", "")),
        original_title=str(data.get("original_title", "")),
        title_vi=str(data.get("title_vi", "")),
        overview=str(data.get("overview", "")),
        overview_vi=str(data.get("overview_vi", "")),
        cast=list(data.get("cast", [])),
        director=str(data.get("director", "")),
        keywords=list(data.get("keywords", [])),
        tmdb_id=data.get("tmdb_id"),
        metadata_source=str(data.get("metadata_source", "movielens_original")),
        metadata_version=int(data.get("metadata_version", 1)),
        metadata_enrichment_status=str(data.get("metadata_enrichment_status", "not_requested")),
    )


def compute_field_coverage(movies: dict[str, MovieMetadata]) -> FieldCoverage:
    """Compute field-level coverage across a movie catalog."""
    cov = FieldCoverage()
    for movie in movies.values():
        if movie.title:
            cov.title += 1
        if movie.original_title:
            cov.original_title += 1
        if movie.title_vi:
            cov.title_vi += 1
        if movie.genres:
            cov.genres += 1
        if movie.overview:
            cov.overview += 1
        if movie.overview_vi:
            cov.overview_vi += 1
        if movie.keywords or movie.tags:
            cov.keywords += 1
        if movie.cast:
            cov.cast += 1
        if movie.director:
            cov.director += 1
    return cov


def create_snapshot(
    snapshot_id: str,
    movies: dict[str, MovieMetadata],
    movielens_checksum: str,
    split_checksum: str,
    links_checksum: str,
    enriched_count: int,
    failed_count: int,
    enrichment_source: str,
    enrichment_config: dict[str, Any] | None = None,
) -> ResearchMetadataSnapshot:
    """
    Create an immutable research metadata snapshot.

    The snapshot captures the current state of movie metadata for
    reproducible evaluation experiments.
    """
    field_cov = compute_field_coverage(movies)
    serialized = {mid: serialize_movie_metadata(m) for mid, m in movies.items()}

    snapshot = ResearchMetadataSnapshot(
        snapshot_id=snapshot_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        movielens_checksum=movielens_checksum,
        split_checksum=split_checksum,
        links_checksum=links_checksum,
        total_movies=len(movies),
        enriched_count=enriched_count,
        unenriched_count=len(movies) - enriched_count - failed_count,
        failed_count=failed_count,
        field_coverage=field_cov,
        enrichment_source=enrichment_source,
        enrichment_config=enrichment_config or {},
        movies=serialized,
    )
    snapshot.snapshot_checksum = snapshot.compute_checksum()
    return snapshot


def save_snapshot(
    snapshot: ResearchMetadataSnapshot,
    output_dir: Path,
) -> Path:
    """
    Save a snapshot as an immutable JSON file.

    File naming: ``snapshot_{snapshot_id}.json``
    Never overwrites existing snapshots.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"snapshot_{snapshot.snapshot_id}.json"
    filepath = output_dir / filename

    if filepath.exists():
        raise FileExistsError(
            f"Snapshot {snapshot.snapshot_id} already exists at {filepath}. "
            "Snapshots are immutable — create a new snapshot ID instead."
        )

    # Build manifest (without full movie data for the manifest file)
    manifest = {
        "snapshot_id": snapshot.snapshot_id,
        "created_at": snapshot.created_at,
        "movielens_checksum": snapshot.movielens_checksum,
        "split_checksum": snapshot.split_checksum,
        "links_checksum": snapshot.links_checksum,
        "total_movies": snapshot.total_movies,
        "enriched_count": snapshot.enriched_count,
        "unenriched_count": snapshot.unenriched_count,
        "failed_count": snapshot.failed_count,
        "field_coverage": snapshot.field_coverage.to_dict(snapshot.total_movies),
        "enrichment_source": snapshot.enrichment_source,
        "enrichment_config": snapshot.enrichment_config,
        "snapshot_checksum": snapshot.snapshot_checksum,
        "movies": snapshot.movies,
    }

    filepath.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info(
        "Snapshot %s saved (%d movies, %d enriched) → %s",
        snapshot.snapshot_id,
        snapshot.total_movies,
        snapshot.enriched_count,
        filepath,
    )

    # Write compact manifest (without movie data) for quick reference
    manifest_only = {k: v for k, v in manifest.items() if k != "movies"}
    manifest_path = output_dir / f"manifest_{snapshot.snapshot_id}.json"
    manifest_path.write_text(json.dumps(manifest_only, indent=2), encoding="utf-8")

    return filepath


def load_snapshot(
    snapshot_path: Path,
) -> ResearchMetadataSnapshot:
    """
    Load and verify a snapshot from disk.

    Validates the snapshot checksum for integrity.
    """
    if not snapshot_path.is_file():
        raise FileNotFoundError(f"Snapshot not found: {snapshot_path}")

    data = json.loads(snapshot_path.read_text(encoding="utf-8"))

    # Reconstruct FieldCoverage from stored dict
    fc_data = data.get("field_coverage", {})
    field_cov = FieldCoverage(
        title=fc_data.get("title", {}).get("count", 0),
        original_title=fc_data.get("original_title", {}).get("count", 0),
        title_vi=fc_data.get("title_vi", {}).get("count", 0),
        genres=fc_data.get("genres", {}).get("count", 0),
        overview=fc_data.get("overview", {}).get("count", 0),
        overview_vi=fc_data.get("overview_vi", {}).get("count", 0),
        keywords=fc_data.get("keywords", {}).get("count", 0),
        cast=fc_data.get("cast", {}).get("count", 0),
        director=fc_data.get("director", {}).get("count", 0),
        original_language=fc_data.get("original_language", {}).get("count", 0),
    )

    snapshot = ResearchMetadataSnapshot(
        snapshot_id=data["snapshot_id"],
        created_at=data["created_at"],
        movielens_checksum=data["movielens_checksum"],
        split_checksum=data["split_checksum"],
        links_checksum=data["links_checksum"],
        total_movies=data["total_movies"],
        enriched_count=data["enriched_count"],
        unenriched_count=data.get("unenriched_count", 0),
        failed_count=data.get("failed_count", 0),
        field_coverage=field_cov,
        enrichment_source=data["enrichment_source"],
        enrichment_config=data.get("enrichment_config", {}),
        movies=data.get("movies", {}),
        snapshot_checksum=data.get("snapshot_checksum", ""),
    )

    # Verify integrity
    computed = snapshot.compute_checksum()
    if snapshot.snapshot_checksum and computed != snapshot.snapshot_checksum:
        raise ValueError(
            f"Snapshot checksum mismatch! Expected {snapshot.snapshot_checksum}, "
            f"computed {computed}. Snapshot may be corrupted."
        )

    return snapshot


def load_movies_from_snapshot(
    snapshot: ResearchMetadataSnapshot,
) -> dict[str, MovieMetadata]:
    """Convert snapshot movie data back into MovieMetadata objects."""
    return {
        mid: deserialize_movie_metadata(mdata)
        for mid, mdata in snapshot.movies.items()
    }
