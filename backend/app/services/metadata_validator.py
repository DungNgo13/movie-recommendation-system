"""
Field-level metadata validation, sanitization, and conflict detection service (Phase 8A).

Treats all external provider responses (TMDB) as untrusted input:
  - Strips HTML/script markup, control characters, and embedded instruction patterns.
  - Applies Unicode NFC normalization and strict length/type bounds.
  - Maps provider genres to MovSug's canonical `STANDARD_GENRES` vocabulary.
  - Deduplicates cast and keywords while preserving billing/relevance order.
  - Enforces strict separation between English recommendation fields (`title`,
    `overview`, `keywords`) and Vietnamese display fields (`title_vi`, `overview_vi`).
  - Computes field-level diffs and conflict classifications against existing
    MovSug `Movie` records so verified existing data is never silently overwritten.
"""

from __future__ import annotations

from datetime import date
import html
import re
from typing import Any, Optional
import unicodedata

from .tmdb_client import build_tmdb_image_url

# ─── Canonical MovSug Genre Vocabulary (matches MovieForm.tsx) ───────────────

STANDARD_GENRES: tuple[str, ...] = (
    "Action",
    "Adventure",
    "Animation",
    "Comedy",
    "Crime",
    "Documentary",
    "Drama",
    "Family",
    "Fantasy",
    "History",
    "Horror",
    "Music",
    "Mystery",
    "Romance",
    "Sci-Fi",
    "Thriller",
    "War",
    "Western",
)

GENRE_SYNONYM_MAP: dict[str, str] = {
    "action": "Action",
    "adventure": "Adventure",
    "animation": "Animation",
    "comedy": "Comedy",
    "crime": "Crime",
    "documentary": "Documentary",
    "drama": "Drama",
    "family": "Family",
    "fantasy": "Fantasy",
    "history": "History",
    "horror": "Horror",
    "music": "Music",
    "musical": "Music",
    "mystery": "Mystery",
    "romance": "Romance",
    "romantic": "Romance",
    "sci-fi": "Sci-Fi",
    "scifi": "Sci-Fi",
    "science fiction": "Sci-Fi",
    "thriller": "Thriller",
    "war": "War",
    "western": "Western",
}

# Enrichable fields supported by the staging/application pipeline
ENRICHABLE_FIELDS: tuple[str, ...] = (
    "title",
    "original_title",
    "overview",
    "release_date",
    "genres",
    "cast",
    "keywords",
    "director",
    "original_language",
    "tmdb_id",
    "imdb_id",
    "poster_path",
    "backdrop_path",
    "title_vi",
    "overview_vi",
    "source_name",
    "source_url",
    "attribution",
)

# Fields that are strictly forbidden from ever being touched by enrichment
PROTECTED_MOVIE_FIELDS: frozenset[str] = frozenset({
    "id",
    "video_source_path",
    "video_original_filename",
    "processing_status",
    "processing_progress",
    "processing_step",
    "hls_playlist_path",
    "processing_error",
    "available_qualities",
    "source_storage",
    "source_object_key",
})

# ─── Limits & Sanitization Regexes ───────────────────────────────────────────

MAX_TITLE_LEN = 255
MAX_OVERVIEW_LEN = 5000
MAX_DIRECTOR_LEN = 100
MAX_ACTOR_NAME_LEN = 100
MAX_CAST_ITEMS = 15
MAX_KEYWORD_LEN = 100
MAX_KEYWORDS_ITEMS = 25

_HTML_TAG_RE = re.compile(r"<[^>]*>")
_SCRIPT_BLOCK_RE = re.compile(r"<(script|style|iframe|object|embed)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_PROMPT_INJECTION_RE = re.compile(
    r"(ignore\s+(all\s+)?(previous|prior)\s+instructions|system\s*prompt\s*:|<\|im_start\|>|javascript\s*:)",
    re.IGNORECASE,
)
_VIETNAMESE_DIACRITIC_RE = re.compile(
    r"[ăâđêôơưĂÂĐÊÔƠƯáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]"
)
_ISO_LANGUAGE_RE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")
_IMDB_ID_RE = re.compile(r"^tt\d{5,12}$")


class MetadataValidationError(ValueError):
    """Raised when a proposed metadata field fails validation."""

    def __init__(self, field_name: str, message: str) -> None:
        super().__init__(f"{field_name}: {message}")
        self.field_name = field_name
        self.message = message


# ─── Sanitization & Type Validation Helpers ──────────────────────────────────

def sanitize_untrusted_text(raw: Any, max_length: int, allow_newlines: bool = False) -> Optional[str]:
    """
    Sanitize untrusted external text:
      1. Reject non-strings or empty strings.
      2. Strip <script>/<style> blocks and all HTML tags.
      3. Unescape HTML entities, then re-strip any residual angle brackets.
      4. Strip control characters and neutralized prompt-injection markers.
      5. Normalize Unicode to NFC and enforce `max_length`.
    """
    if raw is None or not isinstance(raw, str):
        return None
    text = unicodedata.normalize("NFC", raw)
    text = _SCRIPT_BLOCK_RE.sub(" ", text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = text.replace("<", "").replace(">", "")
    text = _CONTROL_CHARS_RE.sub("", text)
    text = _PROMPT_INJECTION_RE.sub("[filtered]", text)

    if allow_newlines:
        lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
        cleaned = "\n".join(ln for ln in lines if ln)
    else:
        cleaned = re.sub(r"\s+", " ", text).strip()

    if not cleaned:
        return None
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip()
    return cleaned or None


def looks_like_vietnamese(text: Optional[str]) -> bool:
    """Detect whether a text string contains characteristic Vietnamese diacritics."""
    if not text:
        return False
    matches = _VIETNAMESE_DIACRITIC_RE.findall(text)
    return len(matches) >= 3


def validate_release_date(raw: Any) -> Optional[str]:
    """Validate release date and return ISO string `YYYY-MM-DD` or None."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, date):
        d = raw
    elif isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            d = date.fromisoformat(s[:10])
        except ValueError as exc:
            raise MetadataValidationError("release_date", f"Invalid ISO date: {raw!r}") from exc
    else:
        raise MetadataValidationError("release_date", f"Unsupported date type: {type(raw).__name__}")

    if d.year < 1870 or d.year > 2100:
        raise MetadataValidationError("release_date", f"Release year {d.year} out of valid range 1870..2100")
    return d.isoformat()


def normalize_and_validate_genres(raw_genres: Any) -> list[str]:
    """
    Map TMDB genre objects (`[{"id": 28, "name": "Action"}, ...]`) or strings
    into MovSug's deduplicated canonical `STANDARD_GENRES` list.
    """
    if not raw_genres or not isinstance(raw_genres, list):
        return []
    mapped: list[str] = []
    seen: set[str] = set()
    for item in raw_genres:
        name: Optional[str] = None
        if isinstance(item, dict):
            name = item.get("name")
        elif isinstance(item, str):
            name = item
        if not name or not isinstance(name, str):
            continue
        clean_key = re.sub(r"\s+", " ", name.strip()).lower()
        canonical = GENRE_SYNONYM_MAP.get(clean_key)
        if canonical and canonical not in seen:
            seen.add(canonical)
            mapped.append(canonical)
    return mapped


def normalize_and_validate_keywords(raw_keywords: Any) -> list[str]:
    """
    Extract and deduplicate English thematic keywords from TMDB response.
    Rejects empty strings, overly long strings, HTML, and Vietnamese-diacritic
    strings so the English TF-IDF keyword list stays language-clean.
    """
    items: list[Any] = []
    if isinstance(raw_keywords, dict):
        items = raw_keywords.get("keywords") or raw_keywords.get("results") or []
    elif isinstance(raw_keywords, list):
        items = raw_keywords

    if not isinstance(items, list):
        return []

    deduped: list[str] = []
    seen: set[str] = set()
    for entry in items:
        raw_name = entry.get("name") if isinstance(entry, dict) else entry
        cleaned = sanitize_untrusted_text(raw_name, max_length=MAX_KEYWORD_LEN)
        if not cleaned:
            continue
        low = cleaned.lower()
        # Keep English keywords separate from Vietnamese display phrases
        if looks_like_vietnamese(low):
            continue
        if low not in seen:
            seen.add(low)
            deduped.append(low)
        if len(deduped) >= MAX_KEYWORDS_ITEMS:
            break
    return deduped


def normalize_and_validate_cast(raw_credits_or_cast: Any) -> list[str]:
    """
    Extract top-billed cast members from TMDB `credits.cast` or a list of actor names.
    Orders by TMDB `order` ascending when available and deduplicates case-insensitively.
    """
    cast_items: list[Any] = []
    if isinstance(raw_credits_or_cast, dict):
        cast_items = raw_credits_or_cast.get("cast", [])
    elif isinstance(raw_credits_or_cast, list):
        cast_items = raw_credits_or_cast

    if not isinstance(cast_items, list):
        return []

    # Sort dict items by billing order if present
    dict_items = [c for c in cast_items if isinstance(c, dict)]
    if dict_items and any("order" in c for c in dict_items):
        cast_items = sorted(
            dict_items,
            key=lambda c: int(c.get("order", 9999)) if isinstance(c.get("order"), int) else 9999,
        )

    actors: list[str] = []
    seen: set[str] = set()
    for item in cast_items:
        if isinstance(item, dict):
            # If character or known_for_department is explicitly non-acting crew, skip
            dept = item.get("known_for_department")
            if dept and isinstance(dept, str) and dept.lower() not in ("acting", "actors", ""):
                # Still allow if they have a cast character credit in the movie
                if not item.get("character") and "order" not in item:
                    continue
            raw_name = item.get("name")
        else:
            raw_name = item

        cleaned = sanitize_untrusted_text(raw_name, max_length=MAX_ACTOR_NAME_LEN)
        if not cleaned:
            continue
        norm_key = cleaned.lower()
        if norm_key not in seen:
            seen.add(norm_key)
            actors.append(cleaned)
        if len(actors) >= MAX_CAST_ITEMS:
            break
    return actors


def normalize_and_validate_director(raw_credits_or_director: Any) -> Optional[str]:
    """
    Extract director name(s) strictly from crew members with `job == 'Director'`
    or a validated director string, bounded to `MAX_DIRECTOR_LEN` (100 chars).
    """
    if isinstance(raw_credits_or_director, str):
        return sanitize_untrusted_text(raw_credits_or_director, max_length=MAX_DIRECTOR_LEN)

    crew_items: list[Any] = []
    if isinstance(raw_credits_or_director, dict):
        crew_items = raw_credits_or_director.get("crew", [])
    elif isinstance(raw_credits_or_director, list):
        crew_items = raw_credits_or_director

    directors: list[str] = []
    seen: set[str] = set()
    for member in crew_items:
        if not isinstance(member, dict):
            continue
        if member.get("job") != "Director":
            continue
        name = sanitize_untrusted_text(member.get("name"), max_length=MAX_ACTOR_NAME_LEN)
        if name and name.lower() not in seen:
            seen.add(name.lower())
            directors.append(name)

    if not directors:
        return None

    joined = ", ".join(directors)
    if len(joined) <= MAX_DIRECTOR_LEN:
        return joined
    # Fit as many full director names as possible within 100 chars
    fitted: list[str] = []
    for d in directors:
        candidate = ", ".join([*fitted, d])
        if len(candidate) <= MAX_DIRECTOR_LEN:
            fitted.append(d)
        else:
            break
    return ", ".join(fitted) if fitted else directors[0][:MAX_DIRECTOR_LEN]


def extract_and_validate_tmdb_fields(
    tmdb_details: dict[str, Any],
    localized_vi: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Transform a raw TMDB movie detail response (and optional `vi-VN` translation)
    into a clean, validated dictionary of proposed MovSug fields.

    Language separation guarantee:
      - `title` and `overview` are populated from `en-US` details ONLY if they
        do not appear to be untranslated Vietnamese text.
      - `title_vi` and `overview_vi` are populated strictly in their `_vi` fields.
    """
    proposed: dict[str, Any] = {}

    tmdb_id = tmdb_details.get("id")
    if isinstance(tmdb_id, int) and not isinstance(tmdb_id, bool) and tmdb_id > 0:
        proposed["tmdb_id"] = tmdb_id

    # External IDs (IMDb)
    imdb_id = tmdb_details.get("imdb_id")
    if not imdb_id and isinstance(tmdb_details.get("external_ids"), dict):
        imdb_id = tmdb_details["external_ids"].get("imdb_id")
    if isinstance(imdb_id, str) and _IMDB_ID_RE.match(imdb_id.strip()):
        proposed["imdb_id"] = imdb_id.strip()

    # Primary English Title & Original Title
    en_title = sanitize_untrusted_text(tmdb_details.get("title"), max_length=MAX_TITLE_LEN)
    if en_title:
        proposed["title"] = en_title

    orig_title = sanitize_untrusted_text(tmdb_details.get("original_title"), max_length=MAX_TITLE_LEN)
    if orig_title:
        proposed["original_title"] = orig_title

    # Original Language
    orig_lang = sanitize_untrusted_text(tmdb_details.get("original_language"), max_length=16)
    if orig_lang and _ISO_LANGUAGE_RE.match(orig_lang):
        proposed["original_language"] = orig_lang

    # Primary English Overview (guard against accidental Vietnamese translation overwrite)
    en_overview = sanitize_untrusted_text(
        tmdb_details.get("overview"), max_length=MAX_OVERVIEW_LEN, allow_newlines=False
    )
    if en_overview:
        if looks_like_vietnamese(en_overview) and orig_lang != "vi":
            # Do not put Vietnamese text into the English AI overview field
            proposed["overview_vi"] = en_overview
        else:
            proposed["overview"] = en_overview

    # Release Date
    try:
        valid_date = validate_release_date(tmdb_details.get("release_date"))
        if valid_date:
            proposed["release_date"] = valid_date
    except MetadataValidationError:
        pass

    # Genres
    genres = normalize_and_validate_genres(tmdb_details.get("genres"))
    if genres:
        proposed["genres"] = genres

    # Keywords
    keywords = normalize_and_validate_keywords(tmdb_details.get("keywords"))
    if keywords:
        proposed["keywords"] = keywords

    # Cast & Director
    credits = tmdb_details.get("credits")
    cast = normalize_and_validate_cast(credits if isinstance(credits, dict) else tmdb_details.get("cast"))
    if cast:
        proposed["cast"] = cast

    director = normalize_and_validate_director(
        credits if isinstance(credits, dict) else tmdb_details.get("director")
    )
    if director:
        proposed["director"] = director

    # Poster & Backdrop URLs (allowlisted TMDB image CDN only)
    poster_url = build_tmdb_image_url(tmdb_details.get("poster_path"), size="w500")
    if poster_url:
        proposed["poster_path"] = poster_url

    backdrop_url = build_tmdb_image_url(tmdb_details.get("backdrop_path"), size="w1280")
    if backdrop_url:
        proposed["backdrop_path"] = backdrop_url

    # Localized Vietnamese Display Fields (kept strictly separate)
    if isinstance(localized_vi, dict):
        vi_title = sanitize_untrusted_text(localized_vi.get("title"), max_length=MAX_TITLE_LEN)
        # Only set title_vi if it is non-empty and not just an identical copy of English title
        # (unless original language is Vietnamese)
        if vi_title and (vi_title != en_title or orig_lang == "vi"):
            proposed["title_vi"] = vi_title

        vi_overview = sanitize_untrusted_text(
            localized_vi.get("overview"), max_length=MAX_OVERVIEW_LEN, allow_newlines=False
        )
        if vi_overview and vi_overview != en_overview:
            proposed["overview_vi"] = vi_overview

    # Standard TMDB Attribution & Provenance Metadata
    if "tmdb_id" in proposed:
        proposed["source_name"] = "TMDB"
        proposed["source_url"] = f"https://www.themoviedb.org/movie/{proposed['tmdb_id']}"
        proposed["attribution"] = (
            "Metadata provided by The Movie Database (TMDB). "
            "This product uses the TMDB API but is not endorsed or certified by TMDB."
        )

    return proposed


def validate_proposed_field_value(field_name: str, value: Any) -> Any:
    """
    Validate an individual proposed field value prior to database application.
    Raises `MetadataValidationError` if invalid or if `field_name` is protected/unsupported.
    """
    if field_name in PROTECTED_MOVIE_FIELDS:
        raise MetadataValidationError(field_name, "Field is protected and cannot be modified by enrichment.")
    if field_name not in ENRICHABLE_FIELDS:
        raise MetadataValidationError(field_name, f"Field '{field_name}' is not an enrichable metadata field.")
    if value is None:
        raise MetadataValidationError(field_name, "Cannot apply null/empty metadata value.")

    if field_name in ("title", "original_title", "title_vi"):
        cleaned = sanitize_untrusted_text(value, max_length=MAX_TITLE_LEN)
        if not cleaned:
            raise MetadataValidationError(field_name, "Title must be a non-empty string.")
        return cleaned

    if field_name == "overview":
        cleaned = sanitize_untrusted_text(value, max_length=MAX_OVERVIEW_LEN)
        if not cleaned:
            raise MetadataValidationError(field_name, "Overview must be a non-empty string.")
        if looks_like_vietnamese(cleaned):
            raise MetadataValidationError(
                field_name,
                "Translated Vietnamese text cannot be written into the primary English overview field.",
            )
        return cleaned

    if field_name == "overview_vi":
        cleaned = sanitize_untrusted_text(value, max_length=MAX_OVERVIEW_LEN)
        if not cleaned:
            raise MetadataValidationError(field_name, "Vietnamese overview must be a non-empty string.")
        return cleaned

    if field_name == "release_date":
        iso_str = validate_release_date(value)
        if not iso_str:
            raise MetadataValidationError(field_name, "Invalid release_date.")
        return date.fromisoformat(iso_str)

    if field_name == "genres":
        genres = normalize_and_validate_genres(value)
        if not genres:
            raise MetadataValidationError(field_name, "Genres must contain at least one valid canonical genre.")
        return genres

    if field_name == "cast":
        cast = normalize_and_validate_cast(value)
        if not cast:
            raise MetadataValidationError(field_name, "Cast must contain at least one valid actor name.")
        return cast

    if field_name == "keywords":
        keywords = normalize_and_validate_keywords(value)
        if not keywords:
            raise MetadataValidationError(field_name, "Keywords must contain at least one valid English tag.")
        return keywords

    if field_name == "director":
        director = normalize_and_validate_director(value)
        if not director:
            raise MetadataValidationError(field_name, "Director must be a non-empty string.")
        return director

    if field_name == "original_language":
        cleaned = sanitize_untrusted_text(value, max_length=16)
        if not cleaned or not _ISO_LANGUAGE_RE.match(cleaned):
            raise MetadataValidationError(field_name, f"Invalid ISO language code: {value!r}")
        return cleaned

    if field_name == "tmdb_id":
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise MetadataValidationError(field_name, f"Invalid tmdb_id: {value!r}")
        return value

    if field_name == "imdb_id":
        if not isinstance(value, str) or not _IMDB_ID_RE.match(value.strip()):
            raise MetadataValidationError(field_name, f"Invalid imdb_id: {value!r}")
        return value.strip()

    if field_name in ("poster_path", "backdrop_path"):
        if not isinstance(value, str) or not value.strip():
            raise MetadataValidationError(field_name, "Image path must be a non-empty string.")
        s = value.strip()
        if s.startswith("https://image.tmdb.org/t/p/"):
            return s
        size = "w500" if field_name == "poster_path" else "w1280"
        built = build_tmdb_image_url(s, size=size)
        if not built:
            raise MetadataValidationError(field_name, f"Disallowed or malformed TMDB image URL: {value!r}")
        return built

    if field_name in ("source_name", "source_url", "attribution"):
        max_len = 100 if field_name == "source_name" else (500 if field_name == "source_url" else 2000)
        cleaned = sanitize_untrusted_text(value, max_length=max_len)
        if not cleaned:
            raise MetadataValidationError(field_name, f"{field_name} must be non-empty.")
        if field_name == "source_url" and not cleaned.startswith("https://"):
            raise MetadataValidationError(field_name, "source_url must use HTTPS.")
        return cleaned

    raise MetadataValidationError(field_name, "Unsupported field.")


def snapshot_existing_movie_fields(movie: Any) -> dict[str, Any]:
    """Capture current metadata values on a MovSug `Movie` for staging comparison and provenance."""
    rd = getattr(movie, "release_date", None)
    return {
        "title": getattr(movie, "title", None),
        "original_title": getattr(movie, "original_title", None),
        "overview": getattr(movie, "overview", None),
        "release_date": rd.isoformat() if isinstance(rd, date) else rd,
        "genres": list(getattr(movie, "genres", None) or []) or None,
        "cast": list(getattr(movie, "cast", None) or []) or None,
        "keywords": list(getattr(movie, "keywords", None) or []) or None,
        "director": getattr(movie, "director", None),
        "original_language": getattr(movie, "original_language", None),
        "tmdb_id": getattr(movie, "tmdb_id", None),
        "imdb_id": getattr(movie, "imdb_id", None),
        "poster_path": getattr(movie, "poster_path", None),
        "backdrop_path": getattr(movie, "backdrop_path", None),
        "title_vi": getattr(movie, "title_vi", None),
        "overview_vi": getattr(movie, "overview_vi", None),
        "source_name": getattr(movie, "source_name", None),
        "source_url": getattr(movie, "source_url", None),
        "attribution": getattr(movie, "attribution", None),
    }


def compare_existing_and_proposed(
    existing_values: dict[str, Any],
    proposed_fields: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """
    Compare existing MovSug movie values against proposed TMDB values per field.

    Returns a dictionary keyed by field_name:
      {
        field_name: {
          "status": "missing_in_movsug" | "identical" | "conflict",
          "existing": ...,
          "proposed": ...,
          "requires_explicit_overwrite": bool,
          "reason": str,
        }
      }
    """
    diffs: dict[str, dict[str, Any]] = {}
    for field_name, proposed_val in proposed_fields.items():
        if proposed_val is None or proposed_val == [] or proposed_val == "":
            continue
        existing_val = existing_values.get(field_name)
        is_empty = existing_val is None or existing_val == "" or existing_val == []

        if is_empty:
            diffs[field_name] = {
                "status": "missing_in_movsug",
                "existing": None,
                "proposed": proposed_val,
                "requires_explicit_overwrite": False,
                "reason": f"Field '{field_name}' is currently empty in MovSug.",
            }
            continue

        if existing_val == proposed_val:
            diffs[field_name] = {
                "status": "identical",
                "existing": existing_val,
                "proposed": proposed_val,
                "requires_explicit_overwrite": False,
                "reason": "Existing value already matches TMDB.",
            }
            continue

        # Detect special MovSug patterns (e.g. Jan 1 synthetic date or bilingual title)
        reason = f"Existing value differs from proposed TMDB value for '{field_name}'."
        if field_name == "release_date" and isinstance(existing_val, str) and existing_val.endswith("-01-01"):
            if isinstance(proposed_val, str) and proposed_val[:4] == existing_val[:4]:
                reason = (
                    f"Existing date '{existing_val}' is a year-only placeholder; "
                    f"TMDB provides exact release date '{proposed_val}'."
                )
        elif field_name == "title" and isinstance(existing_val, str) and " - " in existing_val:
            reason = (
                f"Existing title '{existing_val}' contains bilingual concatenation; "
                f"TMDB provides canonical title '{proposed_val}'."
            )

        diffs[field_name] = {
            "status": "conflict",
            "existing": existing_val,
            "proposed": proposed_val,
            "requires_explicit_overwrite": True,
            "reason": reason,
        }

    return diffs
