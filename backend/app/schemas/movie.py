from pydantic import BaseModel, Field, ConfigDict, computed_field, field_validator, model_validator
from typing import Any, Dict, List, Optional, Union
from uuid import UUID
from datetime import date

# Allowed values for Movie.media_rights_status
ALLOWED_MEDIA_RIGHTS = {"safe_to_use", "attribution_required", "non_commercial_only", "unknown", "blocked"}

# ── Vietnamese field validation helpers ──────────────────────────────────────

_MAX_TITLE_VI_LEN = 255
_MAX_OVERVIEW_VI_LEN = 5000
_MAX_KW_LABEL_KEY_LEN = 200
_MAX_KW_LABEL_VAL_LEN = 200


def _trim_or_none(v: Any) -> str | None:
    """Trim whitespace; return None for empty/non-string values."""
    if v is None:
        return None
    if not isinstance(v, str):
        return None
    trimmed = v.strip()
    return trimmed if trimmed else None


def _validate_title_vi(v: Any) -> str | None:
    result = _trim_or_none(v)
    if result and len(result) > _MAX_TITLE_VI_LEN:
        raise ValueError(f"title_vi must be at most {_MAX_TITLE_VI_LEN} characters")
    return result


def _validate_overview_vi(v: Any) -> str | None:
    result = _trim_or_none(v)
    if result and len(result) > _MAX_OVERVIEW_VI_LEN:
        raise ValueError(f"overview_vi must be at most {_MAX_OVERVIEW_VI_LEN} characters")
    return result


def _validate_keyword_labels_vi(v: Any) -> Dict[str, str] | None:
    """Validate keyword_labels_vi as a flat {string: string} mapping."""
    if v is None:
        return None
    if not isinstance(v, dict):
        raise ValueError("keyword_labels_vi must be a JSON object (dict)")

    result: Dict[str, str] = {}
    for key, value in v.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("keyword_labels_vi keys and values must be strings")
        k = key.strip()
        val = value.strip()
        if not k or not val:
            continue  # skip empty entries
        if len(k) > _MAX_KW_LABEL_KEY_LEN:
            raise ValueError(f"keyword_labels_vi key too long (max {_MAX_KW_LABEL_KEY_LEN})")
        if len(val) > _MAX_KW_LABEL_VAL_LEN:
            raise ValueError(f"keyword_labels_vi value too long (max {_MAX_KW_LABEL_VAL_LEN})")
        result[k] = val

    return result if result else None


def normalize_url(path: Optional[str]) -> Optional[str]:
    """Normalize a stored media path to a root-relative URL.

    Returns a root-relative path (e.g. ``/media/videos/hls/…``) so the
    browser fetches it from the same origin as the frontend.  This avoids
    hard-coding a backend host/port that may differ between dev and prod,
    and eliminates Mixed Content errors on HTTPS deployments.

    Handles:
    - None / empty          → None
    - Relative:   media/…   → /media/…
    - Absolute:   /media/…  → /media/… (unchanged)
    - Stale HTTP: http://old-ip/media/… → /media/…
    - Valid HTTPS external:  https://cdn.example.com/poster.jpg → preserved
    """
    if not path:
        return None

    # Legitimate external HTTPS URL — preserve as-is.
    if path.startswith("https://"):
        return path

    # Stale internal HTTP URL (e.g. http://172.35.53.158/media/...).
    # Extract the /media/… portion and discard the scheme + host.
    if path.startswith("http://"):
        media_idx = path.find("/media/")
        if media_idx >= 0:
            return path[media_idx:]
        # Non-media HTTP URL with no /media/ segment — not safe to use.
        return None

    # Local relative or absolute path — ensure leading slash.
    clean = path.lstrip("/\\")
    return f"/{clean}"


def compute_quality_score(
    title: Optional[str],
    overview: Optional[str],
    genres: Optional[list],
    cast: Optional[list],
    director: Optional[str],
    poster_path: Optional[str],
    backdrop_path: Optional[str],
) -> int:
    """
    Compute a 0–100 data-completeness score for a movie's AI-recommendation
    metadata.  Higher score → the TF-IDF engine has more signals to work with.

    Scoring breakdown (max = 100):
      +30  genres present          — strongest content signal
      +20  cast present            — actor-based similarity
      +20  overview > 50 chars     — rich text for TF-IDF
      +15  director present        — director affinity signal
      +10  both poster & backdrop  — visual completeness (UX quality)
      + 5  title present           — always required; sanity check
    """
    score = 0
    if genres:                              score += 30
    if cast:                                score += 20
    if overview and len(overview) > 50:     score += 20
    if director:                            score += 15
    if poster_path and backdrop_path:       score += 10
    if title:                               score +=  5
    return score

# Schema for an item in the movie list
class MovieListItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    title_vi: Optional[str] = None

    # Exclude raw DB columns — exposed only through computed_field properties below
    poster_path: Optional[str] = Field(None, exclude=True)
    backdrop_path: Optional[str] = Field(None, exclude=True)
    processing_status: Optional[str] = Field("no_video", exclude=True)
    processing_progress: Optional[int] = Field(0, exclude=True)
    processing_step: Optional[str] = Field(None, exclude=True)
    hls_playlist_path: Optional[str] = Field(None, exclude=True)
    release_date: Optional[date] = Field(None, exclude=True)
    # Needed only for quality_score calculation — not exposed in list output
    overview: Optional[str] = Field(None, exclude=True)
    director: Optional[str] = Field(None, exclude=True)
    cast: Optional[List[str]] = Field(None, exclude=True)

    genres: Optional[List[str]] = []
    available_qualities: Optional[str] = None

    @computed_field
    @property
    def poster_url(self) -> Optional[str]:
        return normalize_url(self.poster_path)

    @computed_field
    @property
    def backdrop_url(self) -> Optional[str]:
        return normalize_url(self.backdrop_path)

    @computed_field
    @property
    def video_status(self) -> Optional[str]:
        return self.processing_status

    @computed_field
    @property
    def video_progress(self) -> int:
        return self.processing_progress or 0

    @computed_field
    @property
    def video_step(self) -> Optional[str]:
        return self.processing_step

    @computed_field
    @property
    def hls_playlist_url(self) -> Optional[str]:
        return normalize_url(self.hls_playlist_path)

    @computed_field
    @property
    def release_year(self) -> Optional[int]:
        if self.release_date:
            return self.release_date.year
        return None

    @computed_field
    @property
    def quality_score(self) -> int:
        """0–100 data-completeness score for the AI recommendation engine."""
        return compute_quality_score(
            title=self.title,
            overview=self.overview,
            genres=self.genres,
            cast=self.cast,
            director=self.director,
            poster_path=self.poster_path,
            backdrop_path=self.backdrop_path,
        )

# Schema for the detailed movie view
class MovieDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    title_vi: Optional[str] = None
    overview: Optional[str] = None
    overview_vi: Optional[str] = None
    release_date: Optional[date] = None
    genres: Optional[List[str]] = []
    cast: Optional[List[str]] = []
    keywords: Optional[List[str]] = []
    keyword_labels_vi: Optional[Dict[str, str]] = None
    director: Optional[str] = None

    video_original_filename: Optional[str] = None
    processing_error: Optional[str] = None
    available_qualities: Optional[str] = None

    # Source & license — public-facing fields
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    license_type: Optional[str] = None
    license_url: Optional[str] = None
    attribution: Optional[str] = None
    is_public_domain: bool = False
    media_rights_status: Optional[str] = "unknown"

    # Excluded Physical Native Paths
    poster_path: Optional[str] = Field(None, exclude=True)
    backdrop_path: Optional[str] = Field(None, exclude=True)
    video_source_path: Optional[str] = Field(None, exclude=True)
    processing_status: Optional[str] = Field("no_video", exclude=True)
    processing_progress: Optional[int] = Field(0, exclude=True)
    processing_step: Optional[str] = Field(None, exclude=True)
    hls_playlist_path: Optional[str] = Field(None, exclude=True)

    @computed_field
    @property
    def poster_url(self) -> Optional[str]:
        return normalize_url(self.poster_path)

    @computed_field
    @property
    def backdrop_url(self) -> Optional[str]:
        return normalize_url(self.backdrop_path)

    @computed_field
    @property
    def video_url(self) -> Optional[str]:
        return normalize_url(self.video_source_path)

    @computed_field
    @property
    def video_status(self) -> Optional[str]:
        return self.processing_status

    @computed_field
    @property
    def video_progress(self) -> int:
        return self.processing_progress or 0

    @computed_field
    @property
    def video_step(self) -> Optional[str]:
        return self.processing_step

    @computed_field
    @property
    def hls_playlist_url(self) -> Optional[str]:
        return normalize_url(self.hls_playlist_path)

    @computed_field
    @property
    def quality_score(self) -> int:
        """0–100 data-completeness score for the AI recommendation engine."""
        return compute_quality_score(
            title=self.title,
            overview=self.overview,
            genres=self.genres,
            cast=self.cast,
            director=self.director,
            poster_path=self.poster_path,
            backdrop_path=self.backdrop_path,
        )

# Schema for creating a new movie (Matches Frontend Expected input!)
class MovieCreateSchema(BaseModel):
    title: str
    overview: Optional[str] = None
    release_date: Union[date, str, int, None] = None
    genres: Optional[List[str]] = None
    cast: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    director: Optional[str] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None

    # Vietnamese display metadata (optional)
    title_vi: Optional[str] = None
    overview_vi: Optional[str] = None
    keyword_labels_vi: Optional[Dict[str, str]] = None

    # Source & license — optional on create
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    license_type: Optional[str] = None
    license_url: Optional[str] = None
    attribution: Optional[str] = None
    is_public_domain: Optional[bool] = None
    media_rights_status: Optional[str] = None

    @field_validator('release_date')
    @classmethod
    def parse_release_date(cls, v):
        if v is None:
            return None
        if isinstance(v, date):
            return v
        v_str = str(v).strip()
        if len(v_str) == 4 and v_str.isdigit():
            return date(int(v_str), 1, 1)
        try:
            return date.fromisoformat(v_str)
        except ValueError:
            raise ValueError("Release date must be 'YYYY' or 'YYYY-MM-DD'")

    @field_validator('media_rights_status')
    @classmethod
    def validate_media_rights(cls, v):
        if v is not None and v not in ALLOWED_MEDIA_RIGHTS:
            raise ValueError(
                f"media_rights_status must be one of: {', '.join(sorted(ALLOWED_MEDIA_RIGHTS))}"
            )
        return v

    @field_validator('title_vi')
    @classmethod
    def clean_title_vi(cls, v: Any) -> str | None:
        return _validate_title_vi(v)

    @field_validator('overview_vi')
    @classmethod
    def clean_overview_vi(cls, v: Any) -> str | None:
        return _validate_overview_vi(v)

    @field_validator('keyword_labels_vi')
    @classmethod
    def clean_keyword_labels_vi(cls, v: Any) -> Dict[str, str] | None:
        return _validate_keyword_labels_vi(v)

# Schema for updating an existing movie (All fields optional)
class MovieUpdateSchema(BaseModel):
    title: Optional[str] = None
    overview: Optional[str] = None
    release_date: Union[date, str, int, None] = None
    genres: Optional[List[str]] = None
    cast: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    director: Optional[str] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None

    # Vietnamese display metadata (optional)
    title_vi: Optional[str] = None
    overview_vi: Optional[str] = None
    keyword_labels_vi: Optional[Dict[str, str]] = None

    # Source & license — optional on update
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    license_type: Optional[str] = None
    license_url: Optional[str] = None
    attribution: Optional[str] = None
    is_public_domain: Optional[bool] = None
    media_rights_status: Optional[str] = None

    @field_validator('release_date')
    @classmethod
    def parse_release_date(cls, v):
        if v is None:
            return None
        if isinstance(v, date):
            return v
        v_str = str(v).strip()
        if len(v_str) == 4 and v_str.isdigit():
            return date(int(v_str), 1, 1)
        try:
            return date.fromisoformat(v_str)
        except ValueError:
            raise ValueError("Release date must be 'YYYY' or 'YYYY-MM-DD'")

    @field_validator('media_rights_status')
    @classmethod
    def validate_media_rights(cls, v):
        if v is not None and v not in ALLOWED_MEDIA_RIGHTS:
            raise ValueError(
                f"media_rights_status must be one of: {', '.join(sorted(ALLOWED_MEDIA_RIGHTS))}"
            )
        return v

# Schema for the paginated movie list response
class MovieListResponseSchema(BaseModel):
    items: List[MovieListItemSchema]
    total: int
    page: int
    limit: int
