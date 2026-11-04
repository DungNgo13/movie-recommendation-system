"""
Versioned Vector Cache and Staleness Detection for Phase 8B Semantic Embeddings.

Stores precomputed movie embedding matrices and auditable provenance manifests
as versioned filesystem artifacts outside the live relational database
(never storing large float arrays inside SQLite test tables).

Each versioned cache entry consists of:
  1. ``<artifact_id>_vectors.npz`` — float32 matrix of shape ``(N, D)``
  2. ``<artifact_id>_manifest.json`` — provenance metadata including:
     - ``model_name`` and ``model_revision``
     - ``dataset_id``
     - ``metadata_snapshot_checksum``
     - ``embedding_config_checksum``
     - ``movie_id_mapping_checksum``
     - ``vectors_sha256``
     - ``dimensions`` and ``movie_count``
     - per-movie ``metadata_version`` and ``text_sha256`` maps
     - ``generation_duration_seconds``, ``storage_bytes``, ``peak_memory_mb``

Also provides staleness detection when a movie's approved metadata changes
(``metadata_version`` increments) and per-process cache invalidation counters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .embeddings import (
    EmbeddingModelSpec,
    validate_embedding_matrix,
)
from .text_builder import PreparedMovieDocument, extract_normalized_movie_fields

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_CACHE_DIR = (
    Path(__file__).resolve().parents[3] / "reports" / "phase8b_embeddings" / "cache"
)


def compute_movie_id_mapping_checksum(movie_ids: Sequence[str]) -> str:
    """Compute SHA-256 checksum over the ordered ``(index, movie_id)`` mapping."""
    hasher = hashlib.sha256()
    for idx, mid in enumerate(movie_ids):
        hasher.update(f"{idx}:{mid};".encode("utf-8"))
    return hasher.hexdigest()


def compute_vectors_sha256(vectors: np.ndarray) -> str:
    """Compute SHA-256 checksum of contiguous float32 vector bytes."""
    contiguous = np.ascontiguousarray(vectors, dtype=np.float32)
    return hashlib.sha256(contiguous.tobytes()).hexdigest()


@dataclass
class EmbeddingArtifact:
    """Loaded versioned embedding cache artifact."""
    artifact_id: str
    model_key: str
    model_name: str
    model_revision: str
    onnx_filename: str
    is_pretrained_neural: bool
    dataset_id: str
    language_policy: str
    metadata_snapshot_checksum: str
    embedding_config_checksum: str
    movie_id_mapping_checksum: str
    vectors_sha256: str
    dimensions: int
    movie_count: int
    movie_ids: list[str]
    id_to_idx: dict[str, int]
    vectors: np.ndarray
    movie_metadata_versions: dict[str, int] = field(default_factory=dict)
    movie_text_checksums: dict[str, str] = field(default_factory=dict)
    zero_vector_movie_ids: list[str] = field(default_factory=list)
    generation_duration_seconds: float = 0.0
    storage_bytes: int = 0
    peak_memory_mb: float = 0.0
    generated_at_utc: str = ""
    manifest_path: str = ""
    vectors_path: str = ""

    def get_vector(self, movie_id: str) -> np.ndarray | None:
        """Return the 1D embedding vector for ``movie_id``, or ``None`` if absent or zero."""
        idx = self.id_to_idx.get(str(movie_id))
        if idx is None:
            return None
        if str(movie_id) in self.zero_vector_movie_ids:
            return None
        vec = self.vectors[idx]
        if float(np.linalg.norm(vec)) <= 1e-8:
            return None
        return vec

    def to_manifest_dict(self) -> dict[str, Any]:
        """Serialize artifact metadata for JSON manifest storage."""
        return {
            "artifact_id": self.artifact_id,
            "model_key": self.model_key,
            "model_name": self.model_name,
            "model_revision": self.model_revision,
            "onnx_filename": self.onnx_filename,
            "is_pretrained_neural": self.is_pretrained_neural,
            "dataset_id": self.dataset_id,
            "language_policy": self.language_policy,
            "metadata_snapshot_checksum": self.metadata_snapshot_checksum,
            "embedding_config_checksum": self.embedding_config_checksum,
            "movie_id_mapping_checksum": self.movie_id_mapping_checksum,
            "vectors_sha256": self.vectors_sha256,
            "dimensions": self.dimensions,
            "movie_count": self.movie_count,
            "movie_ids": self.movie_ids,
            "movie_metadata_versions": self.movie_metadata_versions,
            "movie_text_checksums": self.movie_text_checksums,
            "zero_vector_movie_ids": self.zero_vector_movie_ids,
            "generation_duration_seconds": round(self.generation_duration_seconds, 4),
            "storage_bytes": self.storage_bytes,
            "peak_memory_mb": round(self.peak_memory_mb, 4),
            "generated_at_utc": self.generated_at_utc,
        }


def save_embedding_artifact(
    cache_dir: Path,
    dataset_id: str,
    spec: EmbeddingModelSpec,
    vectors: np.ndarray,
    documents: Sequence[PreparedMovieDocument],
    metadata_snapshot_checksum: str,
    generation_duration_seconds: float,
    peak_memory_mb: float,
    artifact_id: str | None = None,
) -> EmbeddingArtifact:
    """
    Validate and persist an embedding matrix and its provenance manifest to disk.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    movie_ids = [d.movie_id for d in documents]
    validation = validate_embedding_matrix(
        matrix=vectors,
        expected_rows=len(movie_ids),
        expected_dim=spec.embedding_dim,
        movie_ids=movie_ids,
    )

    config_checksum = spec.compute_config_checksum()
    mapping_checksum = compute_movie_id_mapping_checksum(movie_ids)
    vectors_f32 = np.ascontiguousarray(vectors, dtype=np.float32)
    vec_sha256 = compute_vectors_sha256(vectors_f32)

    resolved_artifact_id = (
        artifact_id
        or f"{dataset_id}__{spec.model_key}__{metadata_snapshot_checksum[:12]}"
    )

    vectors_path = cache_dir / f"{resolved_artifact_id}_vectors.npz"
    manifest_path = cache_dir / f"{resolved_artifact_id}_manifest.json"

    np.savez_compressed(vectors_path, vectors=vectors_f32)
    vec_bytes = vectors_path.stat().st_size if vectors_path.exists() else 0

    version_map = {d.movie_id: int(d.metadata_version) for d in documents}
    text_hash_map = {d.movie_id: d.text_sha256 for d in documents}
    generated_at = datetime.now(timezone.utc).isoformat()

    artifact = EmbeddingArtifact(
        artifact_id=resolved_artifact_id,
        model_key=spec.model_key,
        model_name=spec.model_name,
        model_revision=spec.model_revision,
        onnx_filename=spec.onnx_filename,
        is_pretrained_neural=spec.is_pretrained_neural,
        dataset_id=dataset_id,
        language_policy=spec.language_policy,
        metadata_snapshot_checksum=metadata_snapshot_checksum,
        embedding_config_checksum=config_checksum,
        movie_id_mapping_checksum=mapping_checksum,
        vectors_sha256=vec_sha256,
        dimensions=spec.embedding_dim,
        movie_count=len(movie_ids),
        movie_ids=movie_ids,
        id_to_idx={mid: i for i, mid in enumerate(movie_ids)},
        vectors=vectors_f32,
        movie_metadata_versions=version_map,
        movie_text_checksums=text_hash_map,
        zero_vector_movie_ids=validation["zero_vector_movie_ids"],
        generation_duration_seconds=generation_duration_seconds,
        storage_bytes=vec_bytes,
        peak_memory_mb=peak_memory_mb,
        generated_at_utc=generated_at,
        manifest_path=str(manifest_path),
        vectors_path=str(vectors_path),
    )

    manifest_dict = artifact.to_manifest_dict()
    manifest_path.write_text(json.dumps(manifest_dict, indent=2), encoding="utf-8")

    # Update total storage bytes (vectors.npz + manifest.json)
    total_bytes = vec_bytes + (manifest_path.stat().st_size if manifest_path.exists() else 0)
    artifact.storage_bytes = total_bytes
    manifest_dict["storage_bytes"] = total_bytes
    manifest_path.write_text(json.dumps(manifest_dict, indent=2), encoding="utf-8")

    return artifact


def load_embedding_artifact(
    cache_dir: Path,
    artifact_id: str,
    verify_checksums: bool = True,
) -> EmbeddingArtifact:
    """
    Load a versioned embedding artifact from ``cache_dir`` and validate its
    dimensions, finite values, and cryptographic checksums.
    """
    cache_dir = Path(cache_dir)
    manifest_path = cache_dir / f"{artifact_id}_manifest.json"
    vectors_path = cache_dir / f"{artifact_id}_vectors.npz"

    if not manifest_path.is_file():
        raise FileNotFoundError(f"Embedding manifest not found: {manifest_path}")
    if not vectors_path.is_file():
        raise FileNotFoundError(f"Embedding vectors file not found: {vectors_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    with np.load(vectors_path) as data:
        if "vectors" not in data:
            raise ValueError(f"Missing 'vectors' array in {vectors_path}")
        vectors = np.ascontiguousarray(data["vectors"], dtype=np.float32)

    movie_ids = [str(m) for m in manifest["movie_ids"]]
    dimensions = int(manifest["dimensions"])
    movie_count = int(manifest["movie_count"])

    validate_embedding_matrix(
        matrix=vectors,
        expected_rows=movie_count,
        expected_dim=dimensions,
        movie_ids=movie_ids,
    )

    if verify_checksums:
        actual_mapping_checksum = compute_movie_id_mapping_checksum(movie_ids)
        if actual_mapping_checksum != manifest.get("movie_id_mapping_checksum"):
            raise ValueError(
                f"Movie ID mapping checksum mismatch in {artifact_id}: "
                f"expected {manifest.get('movie_id_mapping_checksum')}, got {actual_mapping_checksum}"
            )
        actual_vec_sha256 = compute_vectors_sha256(vectors)
        if actual_vec_sha256 != manifest.get("vectors_sha256"):
            raise ValueError(
                f"Vectors SHA-256 mismatch in {artifact_id}: "
                f"expected {manifest.get('vectors_sha256')}, got {actual_vec_sha256}"
            )

    return EmbeddingArtifact(
        artifact_id=str(manifest["artifact_id"]),
        model_key=str(manifest["model_key"]),
        model_name=str(manifest["model_name"]),
        model_revision=str(manifest["model_revision"]),
        onnx_filename=str(manifest.get("onnx_filename", "")),
        is_pretrained_neural=bool(manifest.get("is_pretrained_neural", False)),
        dataset_id=str(manifest["dataset_id"]),
        language_policy=str(manifest["language_policy"]),
        metadata_snapshot_checksum=str(manifest["metadata_snapshot_checksum"]),
        embedding_config_checksum=str(manifest["embedding_config_checksum"]),
        movie_id_mapping_checksum=str(manifest["movie_id_mapping_checksum"]),
        vectors_sha256=str(manifest["vectors_sha256"]),
        dimensions=dimensions,
        movie_count=movie_count,
        movie_ids=movie_ids,
        id_to_idx={mid: i for i, mid in enumerate(movie_ids)},
        vectors=vectors,
        movie_metadata_versions={
            str(k): int(v) for k, v in manifest.get("movie_metadata_versions", {}).items()
        },
        movie_text_checksums={
            str(k): str(v) for k, v in manifest.get("movie_text_checksums", {}).items()
        },
        zero_vector_movie_ids=[str(m) for m in manifest.get("zero_vector_movie_ids", [])],
        generation_duration_seconds=float(manifest.get("generation_duration_seconds", 0.0)),
        storage_bytes=int(manifest.get("storage_bytes", 0)),
        peak_memory_mb=float(manifest.get("peak_memory_mb", 0.0)),
        generated_at_utc=str(manifest.get("generated_at_utc", "")),
        manifest_path=str(manifest_path),
        vectors_path=str(vectors_path),
    )


def find_latest_artifact(
    cache_dir: Path,
    model_key: str,
    dataset_id: str | None = None,
) -> EmbeddingArtifact | None:
    """
    Locate and load the most recent valid ``EmbeddingArtifact`` matching
    ``model_key`` (and optional ``dataset_id``) in ``cache_dir``.
    """
    cache_dir = Path(cache_dir)
    if not cache_dir.is_dir():
        return None

    candidates: list[tuple[str, str]] = []
    for mf in sorted(cache_dir.glob("*_manifest.json")):
        try:
            data = json.loads(mf.read_text(encoding="utf-8"))
            if data.get("model_key") != model_key:
                continue
            if dataset_id is not None and data.get("dataset_id") != dataset_id:
                continue
            candidates.append((str(data.get("generated_at_utc", "")), str(data["artifact_id"])))
        except Exception:
            continue

    if not candidates:
        return None

    candidates.sort(reverse=True)
    for _, art_id in candidates:
        try:
            return load_embedding_artifact(cache_dir, art_id, verify_checksums=True)
        except Exception as exc:
            logger.warning("Skipping invalid embedding artifact %s: %s", art_id, exc)
            continue

    return None


def check_cache_staleness(
    movies: Sequence[Any] | Mapping[str, Any],
    artifact: EmbeddingArtifact,
) -> dict[str, Any]:
    """
    Check whether an ``EmbeddingArtifact`` is stale relative to the current
    movie catalog.

    Detects:
      - ``stale_movie_ids``: movies whose current ``metadata_version`` exceeds
        the cached ``metadata_version`` in the artifact manifest.
      - ``missing_movie_ids``: movies in the current catalog that have no entry
        in the artifact or whose vector is a zero vector.
    """
    if isinstance(movies, Mapping):
        movie_list = list(movies.values())
    else:
        movie_list = list(movies)

    stale_movie_ids: list[str] = []
    missing_movie_ids: list[str] = []
    zero_set = set(artifact.zero_vector_movie_ids)

    for m in movie_list:
        fields = extract_normalized_movie_fields(m)
        mid = fields["movie_id"]
        current_version = fields["metadata_version"]

        if mid not in artifact.id_to_idx or mid in zero_set:
            missing_movie_ids.append(mid)
            continue

        cached_version = artifact.movie_metadata_versions.get(mid, 1)
        if current_version > cached_version:
            stale_movie_ids.append(mid)

    total = len(movie_list)
    unusable_count = len(stale_movie_ids) + len(missing_movie_ids)
    missing_or_stale_rate = round(unusable_count / float(total), 6) if total > 0 else 0.0

    return {
        "is_stale": len(stale_movie_ids) > 0 or len(missing_movie_ids) > 0,
        "has_version_mismatch": len(stale_movie_ids) > 0,
        "stale_movie_ids": stale_movie_ids,
        "missing_movie_ids": missing_movie_ids,
        "stale_count": len(stale_movie_ids),
        "missing_count": len(missing_movie_ids),
        "total_catalog_movies": total,
        "missing_or_stale_rate": missing_or_stale_rate,
    }


# ── In-Process Runtime Cache (Single-Process Scope) ───────────────────────────

_in_process_artifacts: dict[str, EmbeddingArtifact] = {}
_in_process_generation: int = 0
_in_process_invalidation_count: int = 0
_fallback_counter: int = 0


def get_configured_cache_dir() -> Path:
    """Return the configured embedding cache directory from env or default."""
    env_dir = os.getenv("EMBEDDING_CACHE_DIR", "").strip()
    if env_dir:
        return Path(env_dir)
    return DEFAULT_EMBEDDING_CACHE_DIR


def register_in_process_artifact(artifact: EmbeddingArtifact) -> None:
    """Register a loaded ``EmbeddingArtifact`` in the per-process memory cache."""
    global _in_process_generation
    _in_process_artifacts[artifact.model_key] = artifact
    _in_process_generation += 1


def get_in_process_artifact(
    model_key: str,
    cache_dir: Path | None = None,
    dataset_id: str | None = None,
) -> EmbeddingArtifact | None:
    """
    Retrieve an ``EmbeddingArtifact`` from the in-process memory cache, or
    attempt to load the latest matching precomputed artifact from disk.
    Never downloads model weights or runs neural inference during a request.
    """
    global _in_process_generation
    if model_key in _in_process_artifacts:
        return _in_process_artifacts[model_key]

    resolved_dir = cache_dir or get_configured_cache_dir()
    loaded = find_latest_artifact(resolved_dir, model_key=model_key, dataset_id=dataset_id)
    if loaded is not None:
        _in_process_artifacts[model_key] = loaded
        _in_process_generation += 1
    return loaded


def invalidate_embedding_cache() -> None:
    """
    Clear all in-process cached embedding artifacts.
    Called automatically when ``vectorizer.invalidate_cache()`` runs after
    approved metadata updates.
    """
    global _in_process_invalidation_count
    _in_process_artifacts.clear()
    _in_process_invalidation_count += 1


def record_semantic_fallback() -> None:
    """Increment the semantic-to-TFIDF fallback counter."""
    global _fallback_counter
    _fallback_counter += 1


def get_embedding_cache_stats() -> dict[str, Any]:
    """Return diagnostic statistics for the in-process semantic embedding cache."""
    return {
        "loaded_model_keys": sorted(_in_process_artifacts.keys()),
        "cache_generation": _in_process_generation,
        "invalidation_count": _in_process_invalidation_count,
        "fallback_count": _fallback_counter,
        "cache_scope": "single_process_in_memory",
    }
