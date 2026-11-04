"""
Deterministic Movie Text Preparation Pipeline for Phase 8B Semantic Embeddings
and Metadata Quality Ablation Experiments.

Supports explicit language and representation policies without mutating or
replacing the frozen TF-IDF v1.0 / v1.1 text builder in ``movie_profile.py``:
  - ``"en_only"``: Structured natural-language representation using English
    fields only (``title``, ``original_title`` if distinct, ``genres``,
    ``keywords``, ``overview``, ``director``, ``cast``). Prevents feeding
    Vietnamese tokens into English-only encoders.
  - ``"multilingual"``: Structured natural-language representation including
    genuine Vietnamese fields (``title_vi``, ``overview_vi``) alongside
    English/original fields when present.
  - ``"tfidf_original"``: Exact MovSug / MovieLens original TF-IDF token
    repetition representation (Condition A).
  - ``"tfidf_enriched"``: MovSug TF-IDF token repetition representation
    incorporating enriched overview, keywords, genres, cast, and director
    fields (Condition B).

Every prepared movie document records:
  - Deterministic normalized text and its SHA-256 checksum
  - Field availability (present/missing fields and completeness ratio over 9 fields)
  - Character length and whitespace token count
  - Metadata provenance (source, version, enrichment status, language policy)
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re
from typing import Any, Literal, Mapping
import unicodedata

LanguagePolicy = Literal["en_only", "multilingual", "tfidf_original", "tfidf_enriched"]

EVALUATED_METADATA_FIELDS: tuple[str, ...] = (
    "original_title",
    "title",
    "title_vi",
    "genres",
    "keywords",
    "overview",
    "overview_vi",
    "cast",
    "director",
)

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text_value(value: str | None) -> str:
    """Normalize a string with Unicode NFC and collapsed whitespace."""
    if not value or not isinstance(value, str):
        return ""
    nfc = unicodedata.normalize("NFC", value)
    return _WHITESPACE_RE.sub(" ", nfc).strip()


def deduplicate_phrases(items: list[str] | tuple[str, ...] | None) -> list[str]:
    """
    Normalize and deduplicate a sequence of phrases case-insensitively
    while preserving deterministic first-seen order.
    """
    if not items:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for raw in items:
        cleaned = normalize_text_value(str(raw)) if raw is not None else ""
        if not cleaned or cleaned == "(no genres listed)":
            continue
        key = cleaned.casefold()
        if key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


@dataclass(frozen=True)
class PreparedMovieDocument:
    """
    Container for a deterministically prepared movie text document and its
    auditable provenance and completeness metadata.
    """
    movie_id: str
    text: str
    text_sha256: str
    language_policy: LanguagePolicy
    char_length: int
    token_count: int
    fields_present: tuple[str, ...]
    fields_missing: tuple[str, ...]
    completeness_ratio: float
    is_empty: bool
    is_minimal: bool
    metadata_source: str
    metadata_version: int
    enrichment_status: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize document metadata (excluding full text if needed, or full record)."""
        return {
            "movie_id": self.movie_id,
            "text": self.text,
            "text_sha256": self.text_sha256,
            "language_policy": self.language_policy,
            "char_length": self.char_length,
            "token_count": self.token_count,
            "fields_present": list(self.fields_present),
            "fields_missing": list(self.fields_missing),
            "completeness_ratio": round(self.completeness_ratio, 6),
            "is_empty": self.is_empty,
            "is_minimal": self.is_minimal,
            "metadata_source": self.metadata_source,
            "metadata_version": self.metadata_version,
            "enrichment_status": self.enrichment_status,
        }


def _extract_attr_or_key(obj: Any, key: str, default: Any = None) -> Any:
    """Extract a field from either a dict/Mapping or an object attribute."""
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def extract_normalized_movie_fields(movie: Any) -> dict[str, Any]:
    """
    Extract and normalize all 9 evaluated metadata fields plus provenance
    attributes from a SQLAlchemy ``Movie`` model, ``MovieMetadata`` dataclass,
    or dictionary.
    """
    raw_id = _extract_attr_or_key(movie, "id")
    if raw_id is None:
        raw_id = _extract_attr_or_key(movie, "movie_id", "")
    movie_id = str(raw_id).strip()

    title = normalize_text_value(_extract_attr_or_key(movie, "title"))
    original_title = normalize_text_value(_extract_attr_or_key(movie, "original_title"))
    title_vi = normalize_text_value(_extract_attr_or_key(movie, "title_vi"))

    raw_genres = _extract_attr_or_key(movie, "genres") or []
    genres = deduplicate_phrases(raw_genres)

    # Support both `keywords` (Movie model) and `tags` (MovieLens MovieMetadata)
    raw_keywords = _extract_attr_or_key(movie, "keywords")
    if not raw_keywords:
        raw_keywords = _extract_attr_or_key(movie, "tags") or []
    keywords = deduplicate_phrases(raw_keywords)

    overview = normalize_text_value(_extract_attr_or_key(movie, "overview"))
    overview_vi = normalize_text_value(_extract_attr_or_key(movie, "overview_vi"))

    raw_cast = _extract_attr_or_key(movie, "cast") or []
    cast = deduplicate_phrases(raw_cast)

    director = normalize_text_value(_extract_attr_or_key(movie, "director"))

    metadata_source = normalize_text_value(
        _extract_attr_or_key(movie, "metadata_source")
    ) or "movielens_original"
    raw_version = _extract_attr_or_key(movie, "metadata_version")
    metadata_version = int(raw_version) if raw_version is not None else 1
    enrichment_status = normalize_text_value(
        _extract_attr_or_key(movie, "metadata_enrichment_status")
    ) or "not_requested"

    return {
        "movie_id": movie_id,
        "original_title": original_title,
        "title": title,
        "title_vi": title_vi,
        "genres": genres,
        "keywords": keywords,
        "overview": overview,
        "overview_vi": overview_vi,
        "cast": cast,
        "director": director,
        "metadata_source": metadata_source,
        "metadata_version": metadata_version,
        "enrichment_status": enrichment_status,
    }


def _compute_field_availability(fields: dict[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...], float]:
    """Return (fields_present, fields_missing, completeness_ratio) across the 9 evaluated fields."""
    present: list[str] = []
    missing: list[str] = []
    for fname in EVALUATED_METADATA_FIELDS:
        val = fields.get(fname)
        has_val = bool(val) if isinstance(val, (str, list, tuple)) else val is not None
        if has_val:
            present.append(fname)
        else:
            missing.append(fname)
    ratio = len(present) / float(len(EVALUATED_METADATA_FIELDS))
    return tuple(present), tuple(missing), ratio


def build_structured_embedding_text(
    fields: dict[str, Any],
    language_policy: Literal["en_only", "multilingual"] = "en_only",
) -> str:
    """
    Build a deterministic, structured natural-language passage suitable for
    pretrained sentence-transformer encoders.

    Field ordering is strictly deterministic:
      1. Title (plus Original Title if distinct; plus Vietnamese Title only under ``multilingual``)
      2. Genres
      3. Keywords
      4. Director
      5. Cast (top 8 actors to avoid token truncation on long credits)
      6. Overview (English)
      7. Overview (Vietnamese, only under ``multilingual`` when genuinely available and distinct)
    """
    segments: list[str] = []

    title = fields["title"]
    original_title = fields["original_title"]
    title_vi = fields["title_vi"]

    # 1. Title block with deduplication across title variants
    seen_titles: set[str] = set()
    if title:
        segments.append(f"Title: {title}.")
        seen_titles.add(title.casefold())

    if original_title and original_title.casefold() not in seen_titles:
        segments.append(f"Original title: {original_title}.")
        seen_titles.add(original_title.casefold())

    if language_policy == "multilingual" and title_vi and title_vi.casefold() not in seen_titles:
        segments.append(f"Vietnamese title: {title_vi}.")
        seen_titles.add(title_vi.casefold())

    # 2. Genres
    genres: list[str] = fields["genres"]
    if genres:
        segments.append(f"Genres: {', '.join(genres)}.")

    # 3. Keywords
    keywords: list[str] = fields["keywords"]
    if keywords:
        segments.append(f"Keywords: {', '.join(keywords[:25])}.")

    # 4. Director
    director: str = fields["director"]
    if director:
        segments.append(f"Director: {director}.")

    # 5. Cast
    cast: list[str] = fields["cast"]
    if cast:
        segments.append(f"Cast: {', '.join(cast[:8])}.")

    # 6. Overview (English)
    overview: str = fields["overview"]
    if overview:
        ending = "" if overview.endswith((".", "!", "?")) else "."
        segments.append(f"Overview: {overview}{ending}")

    # 7. Overview (Vietnamese - only under multilingual policy)
    overview_vi: str = fields["overview_vi"]
    if (
        language_policy == "multilingual"
        and overview_vi
        and overview_vi.casefold() != overview.casefold()
    ):
        ending_vi = "" if overview_vi.endswith((".", "!", "?")) else "."
        segments.append(f"Vietnamese overview: {overview_vi}{ending_vi}")

    return " ".join(segments).strip()


def build_tfidf_compatible_text(
    fields: dict[str, Any],
    include_enriched_fields: bool = True,
    title_weight: int = 2,
    keywords_weight: int = 2,
    genres_weight: int = 1,
    overview_weight: int = 1,
    cast_weight: int = 1,
    director_weight: int = 1,
) -> str:
    """
    Build a TF-IDF bag-of-words text document following the exact MovSug
    field repetition rules:
      - When ``include_enriched_fields=False`` (``tfidf_original``): uses only
        ``title * 2``, ``genres * 1``, and ``keywords * 2`` (matching MovieLens
        Condition A).
      - When ``include_enriched_fields=True`` (``tfidf_enriched``): uses
        ``title * 2``, ``overview * 1``, ``genres * 1``, ``actor <name> * 1``,
        ``keywords * 2``, and ``director <name> * 1`` (matching ``movie_profile.py``).
    """
    parts: list[str] = []
    title: str = fields["title"]
    genres: list[str] = fields["genres"]
    keywords: list[str] = [k.lower() for k in fields["keywords"]]
    overview: str = fields["overview"]
    cast: list[str] = fields["cast"]
    director: str = fields["director"]

    if title:
        for _ in range(title_weight):
            parts.append(title)

    if include_enriched_fields and overview:
        for _ in range(overview_weight):
            parts.append(overview)

    if genres:
        genre_str = " ".join(genres)
        for _ in range(genres_weight):
            parts.append(genre_str)

    if include_enriched_fields and cast:
        cast_str = " ".join(f"actor {actor}" for actor in cast)
        for _ in range(cast_weight):
            parts.append(cast_str)

    if keywords:
        kw_str = " ".join(keywords)
        for _ in range(keywords_weight):
            parts.append(kw_str)

    if include_enriched_fields and director:
        dir_str = f"director {director}"
        for _ in range(director_weight):
            parts.append(dir_str)

    return " ".join(parts).strip()


def prepare_movie_document(
    movie: Any,
    language_policy: LanguagePolicy = "en_only",
) -> PreparedMovieDocument:
    """
    Prepare a single movie into a ``PreparedMovieDocument`` under the specified
    ``language_policy``.

    Handles empty descriptions safely without throwing errors.
    """
    fields = extract_normalized_movie_fields(movie)
    present, missing, ratio = _compute_field_availability(fields)

    if language_policy in ("en_only", "multilingual"):
        text = build_structured_embedding_text(fields, language_policy=language_policy)
    elif language_policy == "tfidf_original":
        text = build_tfidf_compatible_text(fields, include_enriched_fields=False)
    elif language_policy == "tfidf_enriched":
        text = build_tfidf_compatible_text(fields, include_enriched_fields=True)
    else:
        raise ValueError(f"Unsupported language_policy: {language_policy}")

    is_empty = len(text) == 0
    tokens = text.split() if text else []
    token_count = len(tokens)
    is_minimal = token_count < 5

    text_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()

    return PreparedMovieDocument(
        movie_id=fields["movie_id"],
        text=text,
        text_sha256=text_sha256,
        language_policy=language_policy,
        char_length=len(text),
        token_count=token_count,
        fields_present=present,
        fields_missing=missing,
        completeness_ratio=ratio,
        is_empty=is_empty,
        is_minimal=is_minimal,
        metadata_source=fields["metadata_source"],
        metadata_version=fields["metadata_version"],
        enrichment_status=fields["enrichment_status"],
    )


def prepare_catalog_documents(
    movies: list[Any] | Mapping[str, Any],
    language_policy: LanguagePolicy = "en_only",
) -> tuple[list[PreparedMovieDocument], dict[str, Any]]:
    """
    Prepare a full catalog of movies deterministically (sorted by movie_id) and
    return ``(documents, snapshot_summary)``.

    The ``snapshot_summary`` includes ``metadata_snapshot_checksum`` (SHA-256
    over all ``(movie_id, metadata_version, text_sha256)`` tuples) for cache
    validation and reproducibility auditing.
    """
    if isinstance(movies, Mapping):
        movie_list = list(movies.values())
    else:
        movie_list = list(movies)

    docs = [prepare_movie_document(m, language_policy=language_policy) for m in movie_list]
    docs.sort(key=lambda d: (0, int(d.movie_id)) if d.movie_id.isdigit() else (1, d.movie_id))

    snapshot_hasher = hashlib.sha256()
    field_counts: dict[str, int] = {f: 0 for f in EVALUATED_METADATA_FIELDS}
    empty_count = 0
    minimal_count = 0
    total_chars = 0
    total_tokens = 0

    for doc in docs:
        snapshot_hasher.update(
            f"{doc.movie_id}:v{doc.metadata_version}:{doc.text_sha256};".encode("utf-8")
        )
        for f in doc.fields_present:
            field_counts[f] = field_counts.get(f, 0) + 1
        if doc.is_empty:
            empty_count += 1
        if doc.is_minimal:
            minimal_count += 1
        total_chars += doc.char_length
        total_tokens += doc.token_count

    n_docs = len(docs)
    field_coverage = {
        f: round(count / float(n_docs), 6) if n_docs > 0 else 0.0
        for f, count in field_counts.items()
    }

    summary = {
        "language_policy": language_policy,
        "total_movies": n_docs,
        "metadata_snapshot_checksum": snapshot_hasher.hexdigest(),
        "empty_documents_count": empty_count,
        "minimal_documents_count": minimal_count,
        "mean_char_length": round(total_chars / float(n_docs), 2) if n_docs > 0 else 0.0,
        "mean_token_count": round(total_tokens / float(n_docs), 2) if n_docs > 0 else 0.0,
        "field_coverage": field_coverage,
    }
    return docs, summary

