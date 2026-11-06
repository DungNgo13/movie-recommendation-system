"""
Phase 8D: Controlled Live TMDB Pilot Pipeline.

Extends the Phase 8C mock retrieval pipeline with a carefully gated live
TMDB API retrieval capability. Default mode is ALWAYS offline.

Authorization Gate:
  - Default command remains offline (dry-run)
  - Live requests require: --phase8d-live flag AND PHASE8D_LIVE_AUTHORIZED=true env var
  - TMDB_ENABLE_LIVE_REQUESTS alone is NOT sufficient
  - Request budget is hard-capped (default: 120 for 40-movie pilot)
  - Checkpointing after each movie for safe resume
  - Cancellation support via checkpoint inspection

Security:
  - TMDB host allowlist (inherited from TMDBClient)
  - Rate limiting (inherited, default 4 RPS)
  - Bounded retries (inherited, default 3)
  - Secret-safe logging (inherited)
  - No production database writes
"""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ..services.recommendation.text_builder import deduplicate_phrases, prepare_movie_document
from ..services.tmdb_client import TMDBClient, TMDBClientError, TMDBConfig
from .dataset import EvaluationDataset, MovieMetadata
from .identity_mapping import (
    IdentityMappingResult,
    get_imdb_id_for_movie,
    get_tmdb_id_for_movie,
    load_identity_mapping,
)
from .tmdb_research_retrieval import (
    RetrievalRecord,
    RetrievalSummary,
    _apply_tmdb_payload_to_movie,
    _identify_missing_fields,
    _identify_retrieved_fields,
)

logger = logging.getLogger("phase8d_live_pilot")

# Phase 8D constants
PHASE8D_DEFAULT_PILOT_SIZE = 40
PHASE8D_DEFAULT_SEED = 8042
PHASE8D_DEFAULT_REQUEST_BUDGET = 120  # 40 movies × 3 requests max each (en + vi + retry)
PHASE8D_AUTHORIZATION_ENV = "PHASE8D_LIVE_AUTHORIZED"

_YEAR_RE = re.compile(r"\((\d{4})\)\s*$")


class Phase8DAuthorizationError(Exception):
    """Raised when live TMDB requests are attempted without proper authorization."""
    pass


@dataclass
class Phase8DPilotConfig:
    """Configuration for the Phase 8D controlled live pilot."""

    pilot_size: int = PHASE8D_DEFAULT_PILOT_SIZE
    seed: int = PHASE8D_DEFAULT_SEED
    request_budget: int = PHASE8D_DEFAULT_REQUEST_BUDGET
    live_authorized: bool = False
    dry_run: bool = True
    checkpoint_dir: Path | None = None
    output_dir: Path | None = None

    @classmethod
    def from_args(
        cls,
        pilot_size: int = PHASE8D_DEFAULT_PILOT_SIZE,
        seed: int = PHASE8D_DEFAULT_SEED,
        request_budget: int = PHASE8D_DEFAULT_REQUEST_BUDGET,
        live: bool = False,
    ) -> Phase8DPilotConfig:
        """Build config from CLI args with authorization gate check."""
        env_authorized = os.getenv(PHASE8D_AUTHORIZATION_ENV, "").strip().lower() in (
            "true", "1", "yes",
        )
        is_live = live and env_authorized
        return cls(
            pilot_size=pilot_size,
            seed=seed,
            request_budget=max(1, min(500, request_budget)),
            live_authorized=is_live,
            dry_run=not is_live,
        )


@dataclass
class LiveRetrievalRecord:
    """Extended retrieval record for Phase 8D live pilot."""

    movielens_id: str
    tmdb_id: int
    imdb_id: str
    movielens_title: str
    movielens_year: int | None
    tmdb_title: str
    tmdb_original_title: str
    tmdb_release_date: str
    status: str  # "success", "not_found", "api_error", "identity_conflict", "skipped"
    verification_status: str  # "LIVE_VERIFIED", "MOCK_VERIFIED", "NOT_RUN", "FAILED"
    title_match: bool
    year_match: bool
    fields_retrieved: list[str]
    fields_missing: list[str]
    request_count: int
    latency_ms: float
    error_message: str = ""
    has_overview: bool = False
    has_keywords: bool = False
    has_cast: bool = False
    has_director: bool = False
    has_vi_title: bool = False
    has_vi_overview: bool = False


@dataclass
class LivePilotSummary:
    """Extended summary for Phase 8D live pilot."""

    pilot_size: int = 0
    seed: int = PHASE8D_DEFAULT_SEED
    is_live: bool = False
    verification_mode: str = "MOCK_VERIFIED"
    total_attempted: int = 0
    successful: int = 0
    identity_verified: int = 0
    identity_conflicts: int = 0
    not_found: int = 0
    api_errors: int = 0
    skipped: int = 0
    total_requests: int = 0
    request_budget: int = PHASE8D_DEFAULT_REQUEST_BUDGET
    http_429_count: int = 0
    retry_count: int = 0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    field_completeness: dict[str, int] = field(default_factory=dict)
    records: list[LiveRetrievalRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pilot_size": self.pilot_size,
            "seed": self.seed,
            "is_live": self.is_live,
            "verification_mode": self.verification_mode,
            "total_attempted": self.total_attempted,
            "successful": self.successful,
            "identity_verified": self.identity_verified,
            "identity_conflicts": self.identity_conflicts,
            "not_found": self.not_found,
            "api_errors": self.api_errors,
            "skipped": self.skipped,
            "total_requests": self.total_requests,
            "request_budget": self.request_budget,
            "request_budget_remaining": self.request_budget - self.total_requests,
            "http_429_count": self.http_429_count,
            "retry_count": self.retry_count,
            "latency_p50_ms": self.latency_p50_ms,
            "latency_p95_ms": self.latency_p95_ms,
            "success_rate_pct": (
                round(self.successful / self.total_attempted * 100, 2)
                if self.total_attempted > 0 else 0.0
            ),
            "field_completeness": self.field_completeness,
        }


def select_phase8d_pilot(
    dataset: EvaluationDataset,
    mapping: IdentityMappingResult,
    pilot_size: int = PHASE8D_DEFAULT_PILOT_SIZE,
    seed: int = PHASE8D_DEFAULT_SEED,
) -> tuple[list[str], dict[str, Any]]:
    """
    Select a deterministic stratified pilot of exactly ``pilot_size`` movies.

    Includes representation from:
      - High-popularity (top 20%) and long-tail (bottom 40%) movies
      - Multiple genres (Action, Comedy, Drama, Horror, Documentary, etc.)
      - Different decades (pre-1980, 1980s, 1990s, 2000s, 2010s+)
      - English and non-English titles
      - Movies with and without original MovieLens tags
      - Movies with valid TMDB IDs (required for live pilot)
      - Includes 8 movies without TMDB IDs for conflict testing

    Returns:
        Tuple of (sorted movie IDs, selection rationale dict).
    """
    import random
    rng = random.Random(seed)

    # Count ratings per movie
    rating_counts: dict[str, int] = {}
    for splits in [dataset.train_by_user, dataset.val_by_user, dataset.test_by_user]:
        for events in splits.values():
            for ev in events:
                rating_counts[ev.movie_id] = rating_counts.get(ev.movie_id, 0) + 1

    # Classify all movies
    all_ids = list(dataset.movies.keys())
    with_tmdb = [mid for mid in all_ids if get_tmdb_id_for_movie(mapping, mid) is not None]
    without_tmdb = [mid for mid in all_ids if get_tmdb_id_for_movie(mapping, mid) is None]

    # Popularity strata (among TMDB-mapped movies)
    pop_sorted = sorted(with_tmdb, key=lambda m: rating_counts.get(m, 0), reverse=True)
    n = len(pop_sorted)
    popular = pop_sorted[:max(1, n // 5)]
    longtail = pop_sorted[max(1, n * 3 // 5):]

    # Decade strata
    decade_bins: dict[str, list[str]] = {
        "pre_1980": [], "1980s": [], "1990s": [], "2000s": [], "2010s_plus": [],
    }
    for mid in with_tmdb:
        info = mapping.title_year_index.get(mid)
        year = info[1] if info else None
        if year is None:
            continue
        elif year < 1980:
            decade_bins["pre_1980"].append(mid)
        elif year < 1990:
            decade_bins["1980s"].append(mid)
        elif year < 2000:
            decade_bins["1990s"].append(mid)
        elif year < 2010:
            decade_bins["2000s"].append(mid)
        else:
            decade_bins["2010s_plus"].append(mid)

    # Tag strata
    has_tags = [mid for mid in with_tmdb if dataset.movies[mid].tags]
    no_tags = [mid for mid in with_tmdb if not dataset.movies[mid].tags]

    # Non-English detection (heuristic: title contains non-ASCII or foreign-language markers)
    non_english = [
        mid for mid in with_tmdb
        if any(ord(c) > 127 for c in dataset.movies[mid].title)
    ]

    # Build the pilot set with guaranteed representation
    selected: set[str] = set()

    # 1. Pick from each popularity stratum
    if popular:
        selected.update(rng.sample(popular, min(6, len(popular))))
    if longtail:
        selected.update(rng.sample(longtail, min(6, len(longtail))))

    # 2. Pick from each decade
    for _decade, pool in decade_bins.items():
        if pool:
            selected.update(rng.sample(pool, min(3, len(pool))))

    # 3. Ensure tag diversity
    tagged_remaining = [m for m in has_tags if m not in selected]
    untagged_remaining = [m for m in no_tags if m not in selected]
    if tagged_remaining:
        selected.update(rng.sample(tagged_remaining, min(3, len(tagged_remaining))))
    if untagged_remaining:
        selected.update(rng.sample(untagged_remaining, min(3, len(untagged_remaining))))

    # 4. Non-English titles
    ne_remaining = [m for m in non_english if m not in selected]
    if ne_remaining:
        selected.update(rng.sample(ne_remaining, min(2, len(ne_remaining))))

    # 5. Include movies WITHOUT TMDB IDs (for conflict testing)
    no_tmdb_to_include = min(min(3, len(without_tmdb)), pilot_size - len(selected))
    if without_tmdb and no_tmdb_to_include > 0:
        selected.update(rng.sample(without_tmdb, no_tmdb_to_include))

    # 6. Fill remaining from TMDB-mapped pool
    tmdb_remaining = sorted(set(with_tmdb) - selected)
    if len(selected) < pilot_size and tmdb_remaining:
        extra = min(pilot_size - len(selected), len(tmdb_remaining))
        selected.update(rng.sample(tmdb_remaining, extra))

    # Trim to exact pilot_size
    selected_list = sorted(selected)
    if len(selected_list) > pilot_size:
        selected_list = sorted(rng.sample(selected_list, pilot_size))

    # Build rationale
    rationale = {
        "pilot_size": len(selected_list),
        "seed": seed,
        "total_catalog": len(all_ids),
        "eligible_with_tmdb": len(with_tmdb),
        "without_tmdb_included": len(set(selected_list) & set(without_tmdb)),
        "popular_included": len(set(selected_list) & set(popular)),
        "longtail_included": len(set(selected_list) & set(longtail)),
        "has_tags_count": len(set(selected_list) & set(has_tags)),
        "no_tags_count": len(set(selected_list) & set(no_tags)),
        "non_english_count": len(set(selected_list) & set(non_english)),
        "decade_distribution": {
            dec: len(set(selected_list) & set(pool))
            for dec, pool in decade_bins.items()
        },
    }

    return selected_list, rationale


def generate_pilot_manifest(
    pilot_ids: list[str],
    dataset: EvaluationDataset,
    mapping: IdentityMappingResult,
    rationale: dict[str, Any],
    output_dir: Path,
) -> Path:
    """
    Generate the 40-movie pilot manifest for human review.

    The manifest shows each movie's identity, TMDB ID, title, year,
    genres, tag count, and rating count for the project owner to review
    before authorizing live execution.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Count ratings per movie
    rating_counts: dict[str, int] = {}
    for splits in [dataset.train_by_user, dataset.val_by_user, dataset.test_by_user]:
        for events in splits.values():
            for ev in events:
                rating_counts[ev.movie_id] = rating_counts.get(ev.movie_id, 0) + 1

    movies_detail = []
    requests_estimate = 0
    for mid in pilot_ids:
        movie = dataset.movies.get(mid)
        if not movie:
            continue
        tmdb_id = get_tmdb_id_for_movie(mapping, mid)
        imdb_id = get_imdb_id_for_movie(mapping, mid)
        title_info = mapping.title_year_index.get(mid)
        year = title_info[1] if title_info else None

        # Estimate requests: 2 per movie (EN details + VI localization), +1 for potential retry
        if tmdb_id is not None:
            requests_estimate += 2  # get_movie_details + get_movie_localized_details
        else:
            requests_estimate += 0  # No TMDB ID = skip (no API request)

        movies_detail.append({
            "movielens_id": mid,
            "title": movie.title,
            "year": year,
            "tmdb_id": tmdb_id,
            "imdb_id": imdb_id or "",
            "genres": movie.genres,
            "tag_count": len(movie.tags),
            "rating_count": rating_counts.get(mid, 0),
            "has_tmdb_id": tmdb_id is not None,
        })

    manifest = {
        "manifest_type": "phase8d_pilot_manifest",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pilot_size": len(pilot_ids),
        "seed": rationale.get("seed", PHASE8D_DEFAULT_SEED),
        "estimated_api_requests": requests_estimate,
        "estimated_retry_budget": min(requests_estimate // 3, 20),
        "total_request_budget": requests_estimate + min(requests_estimate // 3, 20),
        "operations_contacting_tmdb": [
            "GET /movie/{tmdb_id}?append_to_response=credits,keywords,alternative_titles,external_ids (English details)",
            "GET /movie/{tmdb_id}?language=vi-VN (Vietnamese localization)",
        ],
        "tmdb_host": "api.themoviedb.org",
        "rate_limit": "4 requests/second (configurable via TMDB_RATE_LIMIT_RPS)",
        "provider_terms": (
            "TMDB API usage is governed by the TMDB Terms of Service. "
            "Metadata retrieved is for research and educational purposes only. "
            "Attribution to TMDB is required per their terms."
        ),
        "output_locations": [
            "backend/reports/phase8d_pilot/ (all pilot artifacts)",
            "backend/reports/phase8d_pilot/checkpoint/ (resumable checkpoints)",
            "backend/reports/phase8d_pilot/snapshots/ (immutable research snapshots)",
        ],
        "selection_rationale": rationale,
        "movies": movies_detail,
    }

    manifest_path = output_dir / "phase8d_pilot_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Also generate CSV for easy review
    csv_path = output_dir / "phase8d_pilot_manifest.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "movielens_id", "title", "year", "tmdb_id", "imdb_id",
            "genres", "tag_count", "rating_count", "has_tmdb_id",
        ])
        for m in movies_detail:
            writer.writerow([
                m["movielens_id"], m["title"], m["year"] or "",
                m["tmdb_id"] or "", m["imdb_id"],
                "|".join(m["genres"]), m["tag_count"],
                m["rating_count"], m["has_tmdb_id"],
            ])

    logger.info("Pilot manifest: %d movies, ~%d API requests → %s", len(pilot_ids), requests_estimate, manifest_path)
    return manifest_path


def check_authorization_gate(config: Phase8DPilotConfig) -> dict[str, Any]:
    """
    Check whether the live pilot is authorized.

    Returns a dict describing the authorization status. Never bypasses the gate.
    """
    tmdb_live_enabled = os.getenv("TMDB_ENABLE_LIVE_REQUESTS", "").strip().lower() in ("true", "1", "yes")
    phase8d_authorized = os.getenv(PHASE8D_AUTHORIZATION_ENV, "").strip().lower() in ("true", "1", "yes")
    has_token = bool(os.getenv("TMDB_API_READ_ACCESS_TOKEN", "").strip())

    return {
        "dry_run": config.dry_run,
        "live_flag_passed": not config.dry_run,
        "tmdb_live_requests_enabled": tmdb_live_enabled,
        "phase8d_authorization_env": phase8d_authorized,
        "api_token_present": has_token,
        "authorization_granted": config.live_authorized,
        "gate_status": "AUTHORIZED" if config.live_authorized else "BLOCKED",
        "message": (
            "Live pilot authorized. Proceeding with bounded TMDB requests."
            if config.live_authorized
            else (
                "Live pilot NOT authorized. Running in dry-run mode only. "
                "To authorize, set PHASE8D_LIVE_AUTHORIZED=true AND pass --phase8d-live flag."
            )
        ),
    }


def _save_checkpoint(
    checkpoint_dir: Path,
    movie_id: str,
    record: LiveRetrievalRecord,
    completed_ids: list[str],
) -> None:
    """Save a checkpoint after each movie retrieval for safe resume."""
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = {
        "last_movie_id": movie_id,
        "completed_count": len(completed_ids),
        "completed_ids": completed_ids,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    cp_path = checkpoint_dir / "checkpoint.json"
    cp_path.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")


def _load_checkpoint(checkpoint_dir: Path) -> set[str]:
    """Load previously completed movie IDs from checkpoint."""
    cp_path = checkpoint_dir / "checkpoint.json"
    if not cp_path.is_file():
        return set()
    try:
        data = json.loads(cp_path.read_text(encoding="utf-8"))
        return set(data.get("completed_ids", []))
    except Exception:
        return set()


def _normalize_title(title: str) -> str:
    """Normalize a title for comparison."""
    # Remove year suffix
    clean = _YEAR_RE.sub("", title).strip()
    return clean.lower().strip()


def _check_title_match(ml_title: str, tmdb_title: str, tmdb_original: str) -> bool:
    """Check if MovieLens and TMDB titles are reasonably similar."""
    ml_norm = _normalize_title(ml_title)
    tmdb_norm = tmdb_title.lower().strip() if tmdb_title else ""
    tmdb_orig_norm = tmdb_original.lower().strip() if tmdb_original else ""

    # Exact or substring match
    if ml_norm == tmdb_norm or ml_norm == tmdb_orig_norm:
        return True
    if ml_norm in tmdb_norm or tmdb_norm in ml_norm:
        return True
    if ml_norm in tmdb_orig_norm or tmdb_orig_norm in ml_norm:
        return True

    # Handle "The" prefix differences
    for prefix in ("the ", "a ", "an "):
        ml_stripped = ml_norm.removeprefix(prefix)
        tmdb_stripped = tmdb_norm.removeprefix(prefix)
        if ml_stripped == tmdb_stripped:
            return True

    return False


def _check_year_match(ml_year: int | None, tmdb_release_date: str) -> bool:
    """Check if MovieLens year matches TMDB release date year (±1 year tolerance)."""
    if ml_year is None:
        return True  # Can't verify, don't flag as conflict
    if not tmdb_release_date:
        return True
    try:
        tmdb_year = int(tmdb_release_date[:4])
        return abs(ml_year - tmdb_year) <= 1
    except (ValueError, IndexError):
        return True


def run_live_pilot(
    pilot_ids: list[str],
    dataset: EvaluationDataset,
    mapping: IdentityMappingResult,
    config: Phase8DPilotConfig,
    output_dir: Path,
) -> LivePilotSummary:
    """
    Execute the controlled live TMDB pilot (or dry-run).

    In dry-run mode: produces NOT_RUN records for all movies.
    In live mode (after authorization): retrieves real TMDB data.

    Always:
      - Respects request budget
      - Checkpoints after each movie
      - Never modifies production database
      - Logs with secret redaction
    """
    checkpoint_dir = output_dir / "checkpoint"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    completed_ids = _load_checkpoint(checkpoint_dir)

    summary = LivePilotSummary(
        pilot_size=len(pilot_ids),
        seed=config.seed,
        is_live=config.live_authorized,
        verification_mode="LIVE_VERIFIED" if config.live_authorized else "NOT_RUN",
        request_budget=config.request_budget,
    )

    if not config.live_authorized:
        # Dry-run mode: generate NOT_RUN records
        logger.info("Phase 8D dry-run: generating NOT_RUN records for %d movies", len(pilot_ids))
        for mid in pilot_ids:
            tmdb_id = get_tmdb_id_for_movie(mapping, mid) or 0
            imdb_id = get_imdb_id_for_movie(mapping, mid) or ""
            title_info = mapping.title_year_index.get(mid)
            ml_title = dataset.movies[mid].title if mid in dataset.movies else ""
            ml_year = title_info[1] if title_info else None

            summary.total_attempted += 1
            summary.records.append(LiveRetrievalRecord(
                movielens_id=mid,
                tmdb_id=tmdb_id,
                imdb_id=imdb_id,
                movielens_title=ml_title,
                movielens_year=ml_year,
                tmdb_title="",
                tmdb_original_title="",
                tmdb_release_date="",
                status="not_run",
                verification_status="NOT_RUN",
                title_match=False,
                year_match=False,
                fields_retrieved=[],
                fields_missing=["all"],
                request_count=0,
                latency_ms=0.0,
            ))
        return summary

    # ── Live mode (authorized) ───────────────────────────────────────────
    logger.info("Phase 8D LIVE pilot: retrieving TMDB data for %d movies", len(pilot_ids))

    tmdb_config = TMDBConfig.from_env()
    tmdb_config.enable_live_requests = True  # Already authorized via gate
    client = TMDBClient(config=tmdb_config)
    latencies: list[float] = []

    try:
        for mid in pilot_ids:
            # Check budget
            if summary.total_requests >= config.request_budget:
                logger.warning("Request budget exhausted (%d/%d). Stopping.", summary.total_requests, config.request_budget)
                break

            # Skip already completed (checkpoint resume)
            if mid in completed_ids:
                continue

            summary.total_attempted += 1
            tmdb_id = get_tmdb_id_for_movie(mapping, mid)
            imdb_id = get_imdb_id_for_movie(mapping, mid) or ""
            title_info = mapping.title_year_index.get(mid)
            ml_title = dataset.movies[mid].title if mid in dataset.movies else ""
            ml_year = title_info[1] if title_info else None

            if tmdb_id is None:
                summary.skipped += 1
                record = LiveRetrievalRecord(
                    movielens_id=mid, tmdb_id=0, imdb_id=imdb_id,
                    movielens_title=ml_title, movielens_year=ml_year,
                    tmdb_title="", tmdb_original_title="", tmdb_release_date="",
                    status="skipped", verification_status="FAILED",
                    title_match=False, year_match=False,
                    fields_retrieved=[], fields_missing=["all"],
                    request_count=0, latency_ms=0.0,
                    error_message="No TMDB ID in links.csv",
                )
                summary.records.append(record)
                completed_ids.add(mid)
                _save_checkpoint(checkpoint_dir, mid, record, sorted(completed_ids))
                continue

            # Retrieve English details
            start = time.monotonic()
            req_count = 0
            try:
                en_payload = client.get_movie_details(tmdb_id)
                req_count += 1
                summary.total_requests += 1
            except TMDBClientError as e:
                elapsed = (time.monotonic() - start) * 1000
                latencies.append(elapsed)
                summary.api_errors += 1
                summary.total_requests += 1
                record = LiveRetrievalRecord(
                    movielens_id=mid, tmdb_id=tmdb_id, imdb_id=imdb_id,
                    movielens_title=ml_title, movielens_year=ml_year,
                    tmdb_title="", tmdb_original_title="", tmdb_release_date="",
                    status="api_error", verification_status="FAILED",
                    title_match=False, year_match=False,
                    fields_retrieved=[], fields_missing=["all"],
                    request_count=req_count, latency_ms=elapsed,
                    error_message=str(e),
                )
                summary.records.append(record)
                completed_ids.add(mid)
                _save_checkpoint(checkpoint_dir, mid, record, sorted(completed_ids))
                continue

            # Retrieve Vietnamese localization
            vi_payload: dict[str, Any] = {}
            if summary.total_requests < config.request_budget:
                try:
                    vi_payload = client.get_movie_localized_details(tmdb_id, language="vi-VN")
                    req_count += 1
                    summary.total_requests += 1
                except TMDBClientError:
                    summary.total_requests += 1
                    # Non-fatal: Vietnamese localization is optional

            elapsed = (time.monotonic() - start) * 1000
            latencies.append(elapsed)

            # Identity verification
            tmdb_title = str(en_payload.get("title", ""))
            tmdb_original = str(en_payload.get("original_title", ""))
            tmdb_release = str(en_payload.get("release_date", ""))
            title_ok = _check_title_match(ml_title, tmdb_title, tmdb_original)
            year_ok = _check_year_match(ml_year, tmdb_release)

            if not title_ok or not year_ok:
                summary.identity_conflicts += 1
                status = "identity_conflict"
                v_status = "FAILED"
            else:
                summary.successful += 1
                summary.identity_verified += 1
                status = "success"
                v_status = "LIVE_VERIFIED"

            # Inject vi data into payload for field identification
            en_payload["vi"] = vi_payload
            fields_retrieved = _identify_retrieved_fields(en_payload)
            fields_missing = _identify_missing_fields(en_payload)

            record = LiveRetrievalRecord(
                movielens_id=mid, tmdb_id=tmdb_id, imdb_id=imdb_id,
                movielens_title=ml_title, movielens_year=ml_year,
                tmdb_title=tmdb_title, tmdb_original_title=tmdb_original,
                tmdb_release_date=tmdb_release,
                status=status, verification_status=v_status,
                title_match=title_ok, year_match=year_ok,
                fields_retrieved=fields_retrieved, fields_missing=fields_missing,
                request_count=req_count, latency_ms=elapsed,
                has_overview=bool(en_payload.get("overview")),
                has_keywords=bool(en_payload.get("keywords", {}).get("keywords")),
                has_cast=bool(en_payload.get("credits", {}).get("cast")),
                has_director=any(
                    c.get("job") == "Director"
                    for c in en_payload.get("credits", {}).get("crew", [])
                    if isinstance(c, dict)
                ),
                has_vi_title=bool(vi_payload.get("title")),
                has_vi_overview=bool(vi_payload.get("overview")),
            )
            summary.records.append(record)
            completed_ids.add(mid)
            _save_checkpoint(checkpoint_dir, mid, record, sorted(completed_ids))

    finally:
        # Update stats from client
        summary.http_429_count = client.stats.http_429_count
        summary.retry_count = client.stats.retry_count
        client.close()

    # Compute latency percentiles
    if latencies:
        latencies.sort()
        n = len(latencies)
        summary.latency_p50_ms = round(latencies[n // 2], 2)
        summary.latency_p95_ms = round(latencies[min(n - 1, int(n * 0.95))], 2)

    # Compute field completeness
    for fname in ["has_overview", "has_keywords", "has_cast", "has_director", "has_vi_title", "has_vi_overview"]:
        count = sum(1 for r in summary.records if getattr(r, fname, False))
        summary.field_completeness[fname] = count

    return summary


def generate_pilot_quality_report(
    summary: LivePilotSummary,
    output_dir: Path,
) -> Path:
    """Generate JSON + CSV quality reports for the pilot."""
    output_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "report_type": "phase8d_data_quality",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary.to_dict(),
        "per_movie_records": [
            {
                "movielens_id": r.movielens_id,
                "tmdb_id": r.tmdb_id,
                "imdb_id": r.imdb_id,
                "movielens_title": r.movielens_title,
                "movielens_year": r.movielens_year,
                "tmdb_title": r.tmdb_title,
                "tmdb_original_title": r.tmdb_original_title,
                "tmdb_release_date": r.tmdb_release_date,
                "status": r.status,
                "verification_status": r.verification_status,
                "title_match": r.title_match,
                "year_match": r.year_match,
                "fields_retrieved": r.fields_retrieved,
                "fields_missing": r.fields_missing,
                "request_count": r.request_count,
                "latency_ms": r.latency_ms,
                "error_message": r.error_message,
                "has_overview": r.has_overview,
                "has_keywords": r.has_keywords,
                "has_cast": r.has_cast,
                "has_director": r.has_director,
                "has_vi_title": r.has_vi_title,
                "has_vi_overview": r.has_vi_overview,
            }
            for r in summary.records
        ],
    }

    json_path = output_dir / "phase8d_data_quality.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # CSV per-movie quality records
    csv_path = output_dir / "phase8d_per_movie_quality.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "movielens_id", "tmdb_id", "imdb_id", "movielens_title",
            "movielens_year", "tmdb_title", "status", "verification_status",
            "title_match", "year_match", "request_count", "latency_ms",
            "has_overview", "has_keywords", "has_cast", "has_director",
            "has_vi_title", "has_vi_overview", "error_message",
        ])
        for r in summary.records:
            writer.writerow([
                r.movielens_id, r.tmdb_id, r.imdb_id, r.movielens_title,
                r.movielens_year or "", r.tmdb_title, r.status,
                r.verification_status, r.title_match, r.year_match,
                r.request_count, round(r.latency_ms, 2),
                r.has_overview, r.has_keywords, r.has_cast, r.has_director,
                r.has_vi_title, r.has_vi_overview, r.error_message,
            ])

    logger.info("Quality report → %s", json_path)
    return json_path


def estimate_full_catalog_enrichment(
    mapping: IdentityMappingResult,
    rate_limit_rps: float = 4.0,
) -> dict[str, Any]:
    """
    Estimate resources for full-catalog TMDB enrichment.

    Does NOT execute any requests — pure planning calculation.
    """
    total = mapping.total_movielens_movies
    with_tmdb = mapping.movies_with_tmdb_id
    without_tmdb = mapping.movies_without_tmdb_id

    # 2 requests per movie (EN details + VI localization)
    base_requests = with_tmdb * 2
    # ~5% retry overhead estimate
    estimated_retries = int(base_requests * 0.05)
    total_requests = base_requests + estimated_retries

    # Duration at configured rate limit
    seconds = total_requests / rate_limit_rps
    minutes = seconds / 60
    hours = minutes / 60

    # Storage estimate: ~5KB per movie JSON payload
    storage_bytes = with_tmdb * 5 * 1024
    storage_mb = storage_bytes / (1024 * 1024)

    return {
        "report_type": "phase8d_full_catalog_estimate",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "catalog": {
            "total_movies": total,
            "with_valid_tmdb_id": with_tmdb,
            "without_tmdb_id": without_tmdb,
            "tmdb_coverage_pct": mapping.tmdb_coverage_pct,
        },
        "request_estimate": {
            "base_requests": base_requests,
            "estimated_retries": estimated_retries,
            "total_estimated_requests": total_requests,
            "requests_per_movie": 2,
        },
        "duration_estimate": {
            "rate_limit_rps": rate_limit_rps,
            "estimated_seconds": round(seconds, 1),
            "estimated_minutes": round(minutes, 1),
            "estimated_hours": round(hours, 2),
        },
        "storage_estimate": {
            "per_movie_bytes": 5120,
            "total_bytes": storage_bytes,
            "total_mb": round(storage_mb, 2),
        },
        "recommended_checkpoint_size": 100,
        "recovery_strategy": (
            "Checkpoint after each movie. On interruption, resume from "
            "last checkpoint. Already-retrieved movies are skipped."
        ),
        "compliance_notes": (
            "TMDB API rate limit: 40 requests per 10 seconds (~4 RPS). "
            "Attribution required per TMDB Terms of Service. "
            "Data used for academic research only."
        ),
        "minimum_useful_coverage": {
            "recommendation_experiment": "≥500 movies (5% catalog) for exploratory analysis",
            "confirmatory_study": "≥2000 movies (20% catalog) with stratified sampling",
            "full_catalog": f"{with_tmdb} movies (all mapped)",
            "note": "These are engineering estimates, not guaranteed accuracy thresholds.",
        },
        "approval_required": True,
        "approval_note": (
            "A large-scale live retrieval requires separate approval after "
            "the 40-movie pilot results are reviewed."
        ),
    }

