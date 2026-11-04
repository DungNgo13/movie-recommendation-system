"""
Batch Semantic Embedding Generation Service for Phase 8B.

Provides:
  1. Pinned model specifications (`EmbeddingModelSpec`) for:
     - English model: ``sentence-transformers/all-MiniLM-L6-v2``
     - Multilingual model (EN + VI): ``sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2``
     - Deterministic offline test model: ``movsug/deterministic-char-ngram-384``
       (for fast, 100% offline unit tests without neural weight downloads)
  2. CPU-only ONNX Runtime sentence encoder with attention-mask mean pooling
     and L2 normalization.
  3. Strict output validation (finite check, dimensionality check, zero-vector
     detection, L2 unit-norm verification).
  4. Never downloads neural model weights inside a normal recommendation API
     request; weight downloads are only permitted in explicit offline batch
     generation commands when ``allow_download=True``.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
from pathlib import Path
import time
import tracemalloc
from typing import Any, Literal, Protocol, Sequence

import numpy as np

from .text_builder import LanguagePolicy

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmbeddingModelSpec:
    """Pinned specification and provenance for a sentence embedding model."""
    model_key: str
    model_name: str
    model_revision: str
    onnx_filename: str
    embedding_dim: int
    max_seq_length: int
    language_policy: LanguagePolicy
    license: str
    is_pretrained_neural: bool
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_key": self.model_key,
            "model_name": self.model_name,
            "model_revision": self.model_revision,
            "onnx_filename": self.onnx_filename,
            "embedding_dim": self.embedding_dim,
            "max_seq_length": self.max_seq_length,
            "language_policy": self.language_policy,
            "license": self.license,
            "is_pretrained_neural": self.is_pretrained_neural,
            "description": self.description,
        }

    def compute_config_checksum(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ── Pinned Model Registry ─────────────────────────────────────────────────────

ENGLISH_MINILM_SPEC = EmbeddingModelSpec(
    model_key="english_minilm",
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_revision="1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
    onnx_filename="onnx/model.onnx",
    embedding_dim=384,
    max_seq_length=256,
    language_policy="en_only",
    license="Apache-2.0",
    is_pretrained_neural=True,
    description=(
        "6-layer MiniLM sentence-transformer trained on >1B English sentence pairs; "
        "384-dim mean-pooled L2-normalized embeddings via CPU ONNX Runtime."
    ),
)

MULTILINGUAL_MINILM_SPEC = EmbeddingModelSpec(
    model_key="multilingual_minilm",
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    model_revision="e8f8c211226b894fcb81acc59f3b34ba3efd5f42",
    onnx_filename="onnx/model_quint8_avx2.onnx",
    embedding_dim=384,
    max_seq_length=128,
    language_policy="multilingual",
    license="Apache-2.0",
    is_pretrained_neural=True,
    description=(
        "12-layer multilingual MiniLM sentence-transformer supporting 50+ languages "
        "including English and Vietnamese; 384-dim mean-pooled L2-normalized embeddings "
        "via CPU ONNX Runtime (AVX2 quantized INT8 weights for practical CPU batch speed)."
    ),
)

DETERMINISTIC_TEST_SPEC = EmbeddingModelSpec(
    model_key="deterministic_test",
    model_name="movsug/deterministic-hash-projection-384",
    model_revision="v1.0.0-offline-test",
    onnx_filename="none",
    embedding_dim=384,
    max_seq_length=256,
    language_policy="en_only",
    license="MIT",
    is_pretrained_neural=False,
    description=(
        "Deterministic offline token/character n-gram signed random projection encoder "
        "(384-dim). Used strictly for fast unit tests without network or weight downloads."
    ),
)

MODEL_SPECS: dict[str, EmbeddingModelSpec] = {
    ENGLISH_MINILM_SPEC.model_key: ENGLISH_MINILM_SPEC,
    MULTILINGUAL_MINILM_SPEC.model_key: MULTILINGUAL_MINILM_SPEC,
    DETERMINISTIC_TEST_SPEC.model_key: DETERMINISTIC_TEST_SPEC,
    # Aliases for convenience
    "semantic_en": ENGLISH_MINILM_SPEC,
    "semantic_multi": MULTILINGUAL_MINILM_SPEC,
}


def get_model_spec(model_key: str) -> EmbeddingModelSpec:
    """Resolve a model key to its pinned ``EmbeddingModelSpec``."""
    if model_key not in MODEL_SPECS:
        raise ValueError(
            f"Unknown embedding model key '{model_key}'. "
            f"Available keys: {sorted(MODEL_SPECS.keys())}"
        )
    return MODEL_SPECS[model_key]


class SentenceEncoderProtocol(Protocol):
    """Protocol implemented by all sentence encoders."""
    spec: EmbeddingModelSpec

    def encode(
        self,
        texts: Sequence[str],
        batch_size: int = 64,
        normalize: bool = True,
    ) -> np.ndarray:
        ...


# ── Pooling, Normalization, and Validation Helpers ────────────────────────────

def mean_pool_and_normalize(
    token_embeddings: np.ndarray,
    attention_mask: np.ndarray,
    normalize: bool = True,
) -> np.ndarray:
    """
    Perform attention-mask weighted mean pooling over token embeddings
    ``(batch_size, seq_len, hidden_dim)`` and optional L2 normalization.
    """
    mask_expanded = np.expand_dims(attention_mask, axis=-1).astype(np.float32)
    sum_embeddings = np.sum(token_embeddings.astype(np.float32) * mask_expanded, axis=1)
    sum_mask = np.clip(mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
    pooled = sum_embeddings / sum_mask

    if normalize:
        pooled = l2_normalize_rows(pooled)

    return pooled.astype(np.float32)


def l2_normalize_rows(matrix: np.ndarray) -> np.ndarray:
    """
    L2-normalize each row of a 2D array safely. Rows with zero norm remain all zeros.
    """
    if matrix.ndim != 2:
        raise ValueError(f"Expected 2D array for L2 normalization, got {matrix.ndim}D")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    safe_norms = np.where(norms > 1e-12, norms, 1.0)
    normalized = np.where(norms > 1e-12, matrix / safe_norms, 0.0)
    return normalized.astype(np.float32)


def validate_embedding_matrix(
    matrix: np.ndarray,
    expected_rows: int,
    expected_dim: int,
    movie_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """
    Validate an embedding matrix for shape, finite values, and unit L2 norms.

    Raises ``ValueError`` if shape mismatches or NaN/Inf values are present.
    Returns diagnostic metadata including any ``zero_vector_movie_ids``.
    """
    if not isinstance(matrix, np.ndarray) or matrix.ndim != 2:
        raise ValueError("Embedding matrix must be a 2D numpy ndarray.")

    if matrix.shape != (expected_rows, expected_dim):
        raise ValueError(
            f"Embedding matrix shape mismatch: expected ({expected_rows}, {expected_dim}), "
            f"got {matrix.shape}."
        )

    if not np.isfinite(matrix).all():
        n_bad = int(np.sum(~np.isfinite(matrix)))
        raise ValueError(f"Embedding matrix contains {n_bad} NaN or Inf values.")

    norms = np.linalg.norm(matrix, axis=1)
    zero_mask = norms <= 1e-8
    zero_indices = [int(i) for i in np.where(zero_mask)[0]]
    zero_movie_ids = (
        [str(movie_ids[i]) for i in zero_indices]
        if movie_ids is not None
        else [str(i) for i in zero_indices]
    )

    non_zero_norms = norms[~zero_mask]
    if len(non_zero_norms) > 0:
        max_norm_dev = float(np.max(np.abs(non_zero_norms - 1.0)))
    else:
        max_norm_dev = 0.0

    return {
        "rows": expected_rows,
        "dimensions": expected_dim,
        "all_finite": True,
        "zero_vector_count": len(zero_indices),
        "zero_vector_movie_ids": zero_movie_ids,
        "max_unit_norm_deviation": round(max_norm_dev, 8),
    }


# ── Deterministic Offline Test Encoder ────────────────────────────────────────

class DeterministicHashEncoder:
    """
    Fast, 100% offline deterministic encoder using word and character 3-gram
    feature hashing into ``spec.embedding_dim`` dimensions.

    Used strictly for unit tests and offline verification where downloading
    neural weights is forbidden. Preserves lexical/subword similarity between
    related movie texts while remaining completely deterministic across platforms.
    """

    def __init__(self, spec: EmbeddingModelSpec = DETERMINISTIC_TEST_SPEC):
        self.spec = spec

    def encode(
        self,
        texts: Sequence[str],
        batch_size: int = 64,
        normalize: bool = True,
    ) -> np.ndarray:
        dim = self.spec.embedding_dim
        n = len(texts)
        out = np.zeros((n, dim), dtype=np.float32)

        for row_idx, raw_text in enumerate(texts):
            text = (raw_text or "").strip().lower()
            if not text:
                continue

            words = text.split()
            features: list[str] = []
            for w in words:
                features.append(f"w:{w}")
                if len(w) >= 4:
                    for j in range(len(w) - 2):
                        features.append(f"c3:{w[j:j+3]}")

            vec = np.zeros(dim, dtype=np.float32)
            for feat in features:
                digest = hashlib.md5(feat.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:4], "little") % dim
                sign = 1.0 if (digest[4] & 1) == 0 else -1.0
                weight = 2.0 if feat.startswith("w:") else 0.5
                vec[idx] += sign * weight

            out[row_idx] = vec

        if normalize and n > 0:
            out = l2_normalize_rows(out)

        return out


# ── Pretrained ONNX Runtime CPU Sentence Encoder ──────────────────────────────

class OnnxSentenceEncoder:
    """
    CPU-only ONNX Runtime encoder for HuggingFace sentence-transformer models.

    Uses ``huggingface_hub`` + ``tokenizers`` + ``onnxruntime`` (`CPUExecutionProvider`)
    to run exact transformer inference with attention-mask mean pooling and
    L2 normalization.
    """

    def __init__(
        self,
        spec: EmbeddingModelSpec,
        allow_download: bool = False,
        cache_dir: Path | None = None,
    ):
        self.spec = spec
        self.allow_download = allow_download
        self.cache_dir = cache_dir
        self._tokenizer: Any = None
        self._session: Any = None
        self._input_names: list[str] = []

    def _ensure_loaded(self) -> None:
        if self._session is not None and self._tokenizer is not None:
            return

        import onnxruntime as ort
        from tokenizers import Tokenizer
        from huggingface_hub import hf_hub_download

        local_only = not self.allow_download
        cache_str = str(self.cache_dir) if self.cache_dir else None

        try:
            tok_path = hf_hub_download(
                repo_id=self.spec.model_name,
                filename="tokenizer.json",
                revision=self.spec.model_revision,
                local_files_only=local_only,
                cache_dir=cache_str,
            )
            mdl_path = hf_hub_download(
                repo_id=self.spec.model_name,
                filename=self.spec.onnx_filename,
                revision=self.spec.model_revision,
                local_files_only=local_only,
                cache_dir=cache_str,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Model weights for '{self.spec.model_name}' (revision {self.spec.model_revision}) "
                f"are not cached locally and allow_download={self.allow_download}. "
                f"Run the batch embedding generation CLI first. Underlying error: {exc}"
            ) from exc

        tokenizer = Tokenizer.from_file(tok_path)
        tokenizer.enable_truncation(max_length=self.spec.max_seq_length)
        tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")

        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = 0  # Allow ONNX Runtime to use available CPU cores
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        session = ort.InferenceSession(
            mdl_path,
            sess_options=sess_options,
            providers=["CPUExecutionProvider"],
        )
        self._tokenizer = tokenizer
        self._session = session
        self._input_names = [inp.name for inp in session.get_inputs()]

    def encode(
        self,
        texts: Sequence[str],
        batch_size: int = 64,
        normalize: bool = True,
    ) -> np.ndarray:
        n = len(texts)
        dim = self.spec.embedding_dim
        if n == 0:
            return np.zeros((0, dim), dtype=np.float32)

        self._ensure_loaded()

        all_batches: list[np.ndarray] = []
        for start in range(0, n, batch_size):
            batch_texts = [t if (t and t.strip()) else "" for t in texts[start : start + batch_size]]
            non_empty_Flags = np.array([bool(t) for t in batch_texts], dtype=bool)

            # Replace completely empty texts with a single pad token during forward pass,
            # then explicitly zero out their rows afterward so empty movies get 0-vectors.
            safe_texts = [t if t else "[PAD]" for t in batch_texts]
            encodings = self._tokenizer.encode_batch(safe_texts)

            input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
            attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)

            ort_inputs: dict[str, np.ndarray] = {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
            }
            if "token_type_ids" in self._input_names:
                ort_inputs["token_type_ids"] = np.array(
                    [e.type_ids for e in encodings], dtype=np.int64
                )

            outputs = self._session.run(None, ort_inputs)
            # outputs[0] is token_embeddings / last_hidden_state of shape (batch, seq_len, hidden_dim)
            token_embeddings = outputs[0]
            pooled = mean_pool_and_normalize(
                token_embeddings=token_embeddings,
                attention_mask=attention_mask,
                normalize=normalize,
            )

            # Force empty-text rows to exact zero vectors
            if not non_empty_Flags.all():
                pooled[~non_empty_Flags] = 0.0

            all_batches.append(pooled)

        return np.vstack(all_batches).astype(np.float32)


def create_encoder(
    model_key: str,
    allow_download: bool = False,
    cache_dir: Path | None = None,
) -> SentenceEncoderProtocol:
    """
    Factory for creating a ``SentenceEncoderProtocol`` instance from a pinned
    model key.
    """
    spec = get_model_spec(model_key)
    if not spec.is_pretrained_neural:
        return DeterministicHashEncoder(spec=spec)
    return OnnxSentenceEncoder(
        spec=spec,
        allow_download=allow_download,
        cache_dir=cache_dir,
    )


def generate_catalog_embeddings(
    movies: list[Any] | dict[str, Any],
    model_key: str = "english_minilm",
    batch_size: int = 64,
    allow_download: bool = False,
    encoder: SentenceEncoderProtocol | None = None,
) -> dict[str, Any]:
    """
    End-to-end batch embedding generation for a movie catalog:
      1. Prepares deterministic movie texts using the model's ``language_policy``
      2. Encodes all movie texts in batches on CPU
      3. L2-normalizes and validates the output matrix
      4. Measures generation wall-clock time and peak memory allocation

    Returns a dictionary containing ``vectors``, ``documents``, ``spec``,
    ``snapshot_summary``, ``validation``, ``generation_duration_seconds``,
    and ``peak_memory_mb``.
    """
    from .text_builder import prepare_catalog_documents

    spec = encoder.spec if encoder is not None else get_model_spec(model_key)
    active_encoder = encoder or create_encoder(model_key, allow_download=allow_download)

    docs, snapshot_summary = prepare_catalog_documents(
        movies=movies,
        language_policy=spec.language_policy,
    )
    movie_ids = [d.movie_id for d in docs]
    texts = [d.text for d in docs]

    was_tracing = tracemalloc.is_tracing()
    if not was_tracing:
        tracemalloc.start()

    t0 = time.perf_counter()
    vectors = active_encoder.encode(texts, batch_size=batch_size, normalize=True)
    duration_sec = time.perf_counter() - t0

    _, peak_bytes = tracemalloc.get_traced_memory()
    if not was_tracing:
        tracemalloc.stop()

    peak_memory_mb = max(
        float(peak_bytes) / (1024.0 * 1024.0),
        float(vectors.nbytes) / (1024.0 * 1024.0),
    )

    validation = validate_embedding_matrix(
        matrix=vectors,
        expected_rows=len(docs),
        expected_dim=spec.embedding_dim,
        movie_ids=movie_ids,
    )

    return {
        "spec": spec,
        "vectors": vectors,
        "documents": docs,
        "movie_ids": movie_ids,
        "snapshot_summary": snapshot_summary,
        "validation": validation,
        "generation_duration_seconds": round(duration_sec, 4),
        "peak_memory_mb": round(peak_memory_mb, 4),
    }
