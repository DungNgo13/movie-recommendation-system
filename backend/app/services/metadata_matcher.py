"""
Deterministic, explainable movie identity matching service (Phase 8A).

Evaluates TMDB candidate records against an existing MovSug `Movie` record using:
  1. Verified external IDs (`tmdb_id`, `imdb_id`, Wikidata QID)
  2. Normalized title (handling MovSug's bilingual `"English YYYY - Vietnamese YYYY"`
     catalog format, punctuation, Unicode diacritics, and special characters)
  3. Original title and alternative titles (`alternative_titles.titles`)
  4. Release year (exact match, ±1 year festival/theatrical offset, or remake gap)
  5. Sequel number consistency (preventing sequel/original cross-contamination)
  6. Director agreement (additional identity evidence from TMDB crew credits)

Scoring Justification & Thresholds (0.0 – 100.0):
  - 100.0 (`verified_id`):
      Exact match on `tmdb_id`, `imdb_id`, or `wikidata_id` with no conflicting
      title or >1-year release discrepancy.
  - 85.0 – 95.0 (`review_required`):
      Exact normalized title (or original/alt title) + exact release year (+ director
      agreement bonus). Never marked `is_verified_id_match=True`; requires manual
      admin approval.
  - 55.0 – 84.0 (`ambiguous`):
      Missing release year, ±1 year offset without director verification, localized
      title match only, or multiple plausible candidates (e.g., remakes).
  - < 55.0 (`conflict`):
      Title mismatch, sequel numeral mismatch, or release year conflict (>1 year gap,
      such as a remake from another decade).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from difflib import SequenceMatcher
import re
import unicodedata
from typing import Any, Optional

# ─── Constants & Regexes ─────────────────────────────────────────────────────

VERIFIED_ID_SCORE = 100.0
HIGH_CONFIDENCE_THRESHOLD = 85.0
AMBIGUOUS_THRESHOLD = 55.0
AMBIGUITY_TIE_WINDOW = 8.0

_YEAR_SUFFIX_RE = re.compile(r"(?:\(\s*(18\d\d|19\d\d|20\d\d)\s*\)|\b(18\d\d|19\d\d|20\d\d)\s*)$")
_WIKIDATA_RE = re.compile(r"\b(Q\d{2,15})\b")
_IMDB_RE = re.compile(r"\b(tt\d{5,12})\b")

_ROMAN_TO_INT = {
    "ii": "2",
    "iii": "3",
    "iv": "4",
    "v": "5",
    "vi": "6",
    "vii": "7",
    "viii": "8",
    "ix": "9",
    "x": "10",
}

_SEQUEL_TOKEN_RE = re.compile(
    r"\b(?:part\s+|chapter\s+|episode\s+|vol(?:ume)?\s*)?(ii|iii|iv|vi|vii|viii|ix|\d{1,2})\b",
    re.IGNORECASE,
)


@dataclass
class ParsedMovSugIdentity:
    """Extracted identity components from an existing MovSug Movie record."""

    raw_title: str
    primary_title: str
    secondary_title: Optional[str]
    title_vi: Optional[str]
    release_year: Optional[int]
    director: Optional[str]
    tmdb_id: Optional[int]
    imdb_id: Optional[str]
    wikidata_id: Optional[str]
    search_queries: list[str]


@dataclass
class CandidateMatchResult:
    """Deterministic, explainable matching result for a single TMDB candidate."""

    tmdb_id: int
    title: str
    original_title: Optional[str]
    release_date: Optional[str]
    release_year: Optional[int]
    original_language: Optional[str]
    director: Optional[str]
    match_score: float
    match_status: str  # verified_id | review_required | ambiguous | conflict
    is_verified_id_match: bool
    match_evidence: dict[str, Any] = field(default_factory=dict)
    conflicts: list[str] = field(default_factory=list)
    reason_for_review: str = "manual_review_required_by_policy"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─── Normalization Helpers ───────────────────────────────────────────────────

def fold_diacritics(text: str) -> str:
    """Strip Unicode accents/diacritics (including Vietnamese Đ/đ) for comparison."""
    if not text:
        return ""
    replaced = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", replaced)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _strip_trailing_year(segment: str) -> tuple[str, Optional[int]]:
    """Strip a trailing `YYYY` or `(YYYY)` from a title segment if present."""
    s = segment.strip()
    m = _YEAR_SUFFIX_RE.search(s)
    if not m:
        return s, None
    year_str = m.group(1) or m.group(2)
    prefix = s[: m.start()].strip(" -–—:()")
    # Do not strip the year if the movie title IS the year/number (e.g. "1917", "2046", "2037")
    if not prefix:
        return s, None
    return prefix, int(year_str)


def normalize_title_for_match(title: Optional[str]) -> str:
    """
    Normalize a movie title into a canonical ASCII token string for deterministic comparison.

    Handles:
      - Special punctuation (`WALL·E` -> `wall e`, `Spider-Man` -> `spider man`)
      - Diacritics (`Georges Méliès` -> `georges melies`)
      - Leading articles (`The `, `A `, `An ` preserved in full form, also compared without)
      - Case & whitespace collapsing
    """
    if not title or not isinstance(title, str):
        return ""
    folded = fold_diacritics(title).lower()
    # Replace middle dots, hyphens, slashes, colons with space
    cleaned = re.sub(r"[\u00b7\u2022\u2027\-–—/:.,!?'\"()\[\]{}&+]+", " ", folded)
    tokens = [t for t in cleaned.split() if t]
    return " ".join(tokens)


def normalize_title_without_leading_article(title: Optional[str]) -> str:
    """Return normalized title with leading English article ('the', 'a', 'an') removed."""
    norm = normalize_title_for_match(title)
    for article in ("the ", "a ", "an "):
        if norm.startswith(article) and len(norm) > len(article):
            return norm[len(article) :].strip()
    return norm


def extract_sequel_markers(title: Optional[str]) -> set[str]:
    """
    Extract explicit sequel numbers/numerals from a title.
    Ignores 4-digit years (1880..2099) and standalone number titles like '2037'.
    """
    if not title:
        return set()
    stripped, _ = _strip_trailing_year(title)
    norm = fold_diacritics(stripped).lower()
    tokens = norm.split()
    if len(tokens) <= 1:
        return set()
    markers: set[str] = set()
    # Check tokens after the first word so titles starting with a number aren't misread
    tail = " ".join(tokens[1:])
    for match in _SEQUEL_TOKEN_RE.finditer(tail):
        raw_num = match.group(1).lower()
        canonical = _ROMAN_TO_INT.get(raw_num, raw_num)
        if canonical.isdigit():
            val = int(canonical)
            if 2 <= val <= 50:
                markers.add(str(val))
    return markers


def parse_movsug_movie_identity(movie: Any) -> ParsedMovSugIdentity:
    """
    Extract structured identity cues from an existing MovSug `Movie` instance.

    Handles MovSug's bilingual title convention (`"English YYYY - Vietnamese YYYY"`)
    as well as Wikidata/IMDb references in `keywords` or `source_url`.
    """
    raw_title = (getattr(movie, "title", "") or "").strip()
    title_vi = (getattr(movie, "title_vi", None) or "").strip() or None

    primary_part = raw_title
    secondary_part: Optional[str] = None
    extracted_year: Optional[int] = None

    if " - " in raw_title:
        parts = [p.strip() for p in raw_title.split(" - ", 1) if p.strip()]
        if len(parts) == 2:
            left_clean, left_year = _strip_trailing_year(parts[0])
            right_clean, right_year = _strip_trailing_year(parts[1])
            primary_part = left_clean
            secondary_part = right_clean
            extracted_year = left_year or right_year
            # If the left side has Vietnamese diacritics and the right side is ASCII
            # (e.g., "Điều Ước Cuối Cùng Của Tù Nhân 2037 - My Girl 2037 (2022)"),
            # include both as candidate primary/secondary titles.
            if fold_diacritics(left_clean) != left_clean and fold_diacritics(right_clean) == right_clean:
                primary_part = right_clean
                secondary_part = left_clean
    else:
        primary_part, extracted_year = _strip_trailing_year(raw_title)

    release_date: Optional[date] = getattr(movie, "release_date", None)
    release_year = release_date.year if isinstance(release_date, date) else extracted_year

    tmdb_id = getattr(movie, "tmdb_id", None)
    imdb_id = getattr(movie, "imdb_id", None)
    wikidata_id: Optional[str] = None

    # Check keywords and source_url for verified external IDs (e.g., "wikidata:Q47703")
    keywords = getattr(movie, "keywords", None) or []
    if isinstance(keywords, list):
        for kw in keywords:
            if isinstance(kw, str):
                if kw.lower().startswith("wikidata:"):
                    q_match = _WIKIDATA_RE.search(kw)
                    if q_match:
                        wikidata_id = q_match.group(1)
                elif not imdb_id:
                    tt_match = _IMDB_RE.search(kw)
                    if tt_match:
                        imdb_id = tt_match.group(1)

    source_url = getattr(movie, "source_url", None) or ""
    if isinstance(source_url, str) and source_url:
        if not wikidata_id and "wikidata.org" in source_url:
            q_match = _WIKIDATA_RE.search(source_url)
            if q_match:
                wikidata_id = q_match.group(1)
        if not imdb_id and "imdb.com/title/" in source_url:
            tt_match = _IMDB_RE.search(source_url)
            if tt_match:
                imdb_id = tt_match.group(1)

    # Build deduplicated search queries in priority order
    queries: list[str] = []
    for candidate_q in (
        primary_part,
        getattr(movie, "original_title", None),
        secondary_part,
        title_vi,
        raw_title,
    ):
        if candidate_q and isinstance(candidate_q, str):
            q_clean = candidate_q.strip()
            if q_clean and q_clean not in queries:
                queries.append(q_clean)

    return ParsedMovSugIdentity(
        raw_title=raw_title,
        primary_title=primary_part or raw_title,
        secondary_title=secondary_part,
        title_vi=title_vi,
        release_year=release_year,
        director=(getattr(movie, "director", None) or "").strip() or None,
        tmdb_id=tmdb_id if isinstance(tmdb_id, int) and tmdb_id > 0 else None,
        imdb_id=imdb_id.strip() if isinstance(imdb_id, str) and imdb_id.strip() else None,
        wikidata_id=wikidata_id,
        search_queries=queries,
    )


def _extract_candidate_year(cand: dict[str, Any]) -> Optional[int]:
    rd = cand.get("release_date")
    if isinstance(rd, str) and len(rd) >= 4 and rd[:4].isdigit():
        return int(rd[:4])
    if isinstance(rd, date):
        return rd.year
    return None


def _extract_candidate_directors(cand: dict[str, Any]) -> list[str]:
    """Extract director names from TMDB `credits.crew` or top-level `director`."""
    directors: list[str] = []
    credits = cand.get("credits")
    if isinstance(credits, dict):
        crew = credits.get("crew", [])
        if isinstance(crew, list):
            for member in crew:
                if isinstance(member, dict) and member.get("job") == "Director":
                    name = (member.get("name") or "").strip()
                    if name and name not in directors:
                        directors.append(name)
    top_dir = cand.get("director")
    if isinstance(top_dir, str) and top_dir.strip() and not directors:
        directors.extend([d.strip() for d in top_dir.split(",") if d.strip()])
    return directors


def _extract_candidate_alt_titles(cand: dict[str, Any]) -> list[str]:
    """Extract alternative titles from TMDB `alternative_titles.titles`."""
    alt_titles: list[str] = []
    alt_block = cand.get("alternative_titles")
    if isinstance(alt_block, dict):
        items = alt_block.get("titles", [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    t = (item.get("title") or "").strip()
                    if t and t not in alt_titles:
                        alt_titles.append(t)
    return alt_titles


def _directors_agree(movsug_director: Optional[str], cand_directors: list[str]) -> Optional[bool]:
    """
    Compare MovSug director string (which may list multiple names) against TMDB directors.
    Returns True on match, False on mismatch, or None if either side is missing.
    """
    if not movsug_director or not cand_directors:
        return None
    ms_names = [
        normalize_title_for_match(part)
        for part in re.split(r"[,/&]| and ", movsug_director)
        if normalize_title_for_match(part)
    ]
    cand_norms = [normalize_title_for_match(d) for d in cand_directors if normalize_title_for_match(d)]
    if not ms_names or not cand_norms:
        return None

    for ms in ms_names:
        for cn in cand_norms:
            if ms == cn or ms in cn or cn in ms:
                return True
    return False


# ─── Core Candidate Scoring & Ranking ────────────────────────────────────────

def score_candidate(
    identity: ParsedMovSugIdentity,
    candidate: dict[str, Any],
    matched_via_external_id: Optional[str] = None,
) -> CandidateMatchResult:
    """
    Compute a deterministic, explainable match score and conflict analysis for one TMDB candidate.
    """
    tmdb_id = int(candidate.get("id", 0))
    cand_title = (candidate.get("title") or "").strip()
    cand_orig_title = (candidate.get("original_title") or "").strip() or None
    cand_release_date = (candidate.get("release_date") or "").strip() or None
    cand_year = _extract_candidate_year(candidate)
    cand_lang = (candidate.get("original_language") or "").strip() or None
    cand_directors = _extract_candidate_directors(candidate)
    cand_alt_titles = _extract_candidate_alt_titles(candidate)

    evidence: dict[str, Any] = {
        "matched_via_external_id": matched_via_external_id,
        "movsug_primary_title": identity.primary_title,
        "movsug_secondary_title": identity.secondary_title,
        "movsug_release_year": identity.release_year,
        "candidate_title": cand_title,
        "candidate_original_title": cand_orig_title,
        "candidate_release_year": cand_year,
        "candidate_directors": cand_directors,
    }
    conflicts: list[str] = []

    # ── 1. Title Comparison ──────────────────────────────────────────────────
    movsug_primary_norm = normalize_title_for_match(identity.primary_title)
    movsug_primary_no_art = normalize_title_without_leading_article(identity.primary_title)
    movsug_secondary_norms = [
        normalize_title_for_match(t)
        for t in (identity.secondary_title, identity.title_vi)
        if t and normalize_title_for_match(t)
    ]

    cand_primary_norm = normalize_title_for_match(cand_title)
    cand_primary_no_art = normalize_title_without_leading_article(cand_title)
    cand_orig_norm = normalize_title_for_match(cand_orig_title) if cand_orig_title else ""
    cand_alt_norms = [normalize_title_for_match(t) for t in cand_alt_titles if normalize_title_for_match(t)]

    exact_primary_title = bool(
        movsug_primary_norm
        and (
            movsug_primary_norm == cand_primary_norm
            or movsug_primary_no_art == cand_primary_no_art
        )
    )
    exact_original_title = bool(
        movsug_primary_norm and cand_orig_norm and movsug_primary_norm == cand_orig_norm
    )
    exact_alt_title = bool(
        movsug_primary_norm and movsug_primary_norm in cand_alt_norms
    )
    localized_title_match = bool(
        movsug_secondary_norms
        and any(
            sec in (cand_primary_norm, cand_orig_norm) or sec in cand_alt_norms
            for sec in movsug_secondary_norms
        )
    )
    # Also check if MovSug's primary title is itself a localized title matching original/alt
    if not exact_primary_title and not exact_original_title and not exact_alt_title:
        if movsug_primary_norm and any(
            movsug_primary_norm == alt or alt in movsug_primary_norm
            for alt in cand_alt_norms
            if len(alt) >= 4
        ):
            localized_title_match = True

    # Best character-level similarity across candidate title representations
    all_cand_norms = [n for n in [cand_primary_norm, cand_orig_norm, *cand_alt_norms] if n]
    all_movsug_norms = [n for n in [movsug_primary_norm, *movsug_secondary_norms] if n]
    best_similarity = 0.0
    for m_norm in all_movsug_norms:
        for c_norm in all_cand_norms:
            sim = SequenceMatcher(None, m_norm, c_norm).ratio()
            if sim > best_similarity:
                best_similarity = sim

    evidence["title_match_type"] = (
        "exact_primary"
        if exact_primary_title
        else "exact_original"
        if exact_original_title
        else "exact_alternative"
        if exact_alt_title
        else "localized_match"
        if localized_title_match
        else "fuzzy"
        if best_similarity >= 0.75
        else "mismatch"
    )
    evidence["title_similarity"] = round(best_similarity, 4)

    # ── 2. Sequel Consistency Check ──────────────────────────────────────────
    ms_sequels = extract_sequel_markers(identity.primary_title)
    # Note: In MovSug, "Ma trận 1" has "1" which is not in 2..50, whereas "Conan 28" has "28"
    cand_sequels = extract_sequel_markers(cand_title) | extract_sequel_markers(cand_orig_title)
    sequel_conflict = False
    if ms_sequels != cand_sequels:
        # Conflict if candidate is a numbered sequel (e.g. "2") while MovSug is the original (empty),
        # or if they have different sequel numbers.
        if (cand_sequels and not ms_sequels) or (ms_sequels and cand_sequels and not (ms_sequels & cand_sequels)):
            sequel_conflict = True
            conflicts.append(
                f"Sequel mismatch: MovSug sequel markers={sorted(ms_sequels)} vs TMDB={sorted(cand_sequels)}"
            )
    evidence["sequel_conflict"] = sequel_conflict

    # ── 3. Release Year Comparison ───────────────────────────────────────────
    year_diff: Optional[int] = None
    if identity.release_year is not None and cand_year is not None:
        year_diff = abs(identity.release_year - cand_year)
        evidence["year_difference"] = year_diff
        if year_diff == 1:
            conflicts.append(
                f"Adjacent release year difference (±1 year): MovSug={identity.release_year} vs TMDB={cand_year}"
            )
        elif year_diff > 1:
            conflicts.append(
                f"Release year conflict ({year_diff} years apart): MovSug={identity.release_year} vs TMDB={cand_year}"
            )
    else:
        evidence["year_difference"] = None
        if identity.release_year is None:
            conflicts.append("MovSug movie has no release year for verification.")
        if cand_year is None:
            conflicts.append("TMDB candidate has no release year.")

    # ── 4. Director Agreement Check ──────────────────────────────────────────
    director_agreement = _directors_agree(identity.director, cand_directors)
    evidence["director_agreement"] = director_agreement
    if director_agreement is False:
        conflicts.append(
            f"Director mismatch: MovSug='{identity.director}' vs TMDB='{', '.join(cand_directors)}'"
        )

    # ── 5. Score Computation & Status Classification ─────────────────────────
    # Case A: Matched via verified external ID (`tmdb_id`, `imdb_id`, `wikidata_id`)
    if matched_via_external_id:
        title_ok = exact_primary_title or exact_original_title or exact_alt_title or localized_title_match or best_similarity >= 0.70
        year_ok = year_diff is None or year_diff <= 1
        if not title_ok:
            conflicts.append(
                f"External ID ({matched_via_external_id}) matched TMDB #{tmdb_id} ('{cand_title}'), "
                f"but title differs from MovSug '{identity.primary_title}'."
            )
        if title_ok and year_ok and director_agreement is not False and not sequel_conflict:
            return CandidateMatchResult(
                tmdb_id=tmdb_id,
                title=cand_title,
                original_title=cand_orig_title,
                release_date=cand_release_date,
                release_year=cand_year,
                original_language=cand_lang,
                director=", ".join(cand_directors) if cand_directors else None,
                match_score=VERIFIED_ID_SCORE,
                match_status="verified_id",
                is_verified_id_match=True,
                match_evidence=evidence,
                conflicts=conflicts,
                reason_for_review="verified_external_id_awaiting_admin_confirmation",
            )
        # External ID had a metadata discrepancy -> downgrade to conflict/ambiguous for review
        return CandidateMatchResult(
            tmdb_id=tmdb_id,
            title=cand_title,
            original_title=cand_orig_title,
            release_date=cand_release_date,
            release_year=cand_year,
            original_language=cand_lang,
            director=", ".join(cand_directors) if cand_directors else None,
            match_score=65.0,
            match_status="conflict",
            is_verified_id_match=False,
            match_evidence=evidence,
            conflicts=conflicts,
            reason_for_review="external_id_metadata_conflict_requires_manual_review",
        )

    # Case B: Title / Year / Director heuristic scoring (never `is_verified_id_match=True`)
    score = 0.0
    if exact_primary_title:
        score += 55.0
    elif exact_original_title or exact_alt_title:
        score += 52.0
    elif localized_title_match:
        score += 48.0
    elif best_similarity >= 0.85:
        score += 38.0
    elif best_similarity >= 0.70:
        score += 25.0
    else:
        score += round(best_similarity * 20.0, 1)
        conflicts.append(
            f"Low title similarity ({best_similarity:.2f}) between '{identity.primary_title}' and '{cand_title}'."
        )

    # Year contribution
    if year_diff == 0:
        score += 30.0
    elif year_diff == 1:
        score += 15.0
    elif year_diff is not None and year_diff > 1:
        # Remake or wrong release decade penalty
        penalty = min(35.0, 15.0 + float(year_diff) * 2.0)
        score -= penalty

    # Director contribution
    if director_agreement is True:
        score += 10.0
    elif director_agreement is False:
        score -= 20.0

    # Sequel mismatch penalty
    if sequel_conflict:
        score -= 25.0

    score = max(0.0, min(95.0, round(score, 1)))

    # Determine status & review reason
    if sequel_conflict or (year_diff is not None and year_diff > 1) or director_agreement is False:
        status = "conflict" if score < AMBIGUOUS_THRESHOLD else "ambiguous"
        reason = "conflicting_year_director_or_sequel_requires_manual_review"
    elif identity.release_year is None or cand_year is None:
        # Missing year can never be high-confidence
        score = min(score, 75.0)
        status = "ambiguous"
        reason = "missing_release_year_requires_manual_review"
    elif localized_title_match and not (exact_primary_title or exact_original_title):
        status = "ambiguous" if score < HIGH_CONFIDENCE_THRESHOLD else "review_required"
        reason = "localized_title_match_requires_manual_review"
    elif score >= HIGH_CONFIDENCE_THRESHOLD:
        status = "review_required"
        reason = "title_and_year_match_requires_manual_approval"
    elif score >= AMBIGUOUS_THRESHOLD:
        status = "ambiguous"
        reason = "fuzzy_or_partial_match_requires_manual_review"
    else:
        status = "conflict"
        reason = "low_confidence_or_conflicting_candidate"

    return CandidateMatchResult(
        tmdb_id=tmdb_id,
        title=cand_title,
        original_title=cand_orig_title,
        release_date=cand_release_date,
        release_year=cand_year,
        original_language=cand_lang,
        director=", ".join(cand_directors) if cand_directors else None,
        match_score=score,
        match_status=status,
        is_verified_id_match=False,
        match_evidence=evidence,
        conflicts=conflicts,
        reason_for_review=reason,
    )


def evaluate_and_rank_candidates(
    movie: Any,
    candidates: list[dict[str, Any]],
    external_id_matches: Optional[dict[int, str]] = None,
) -> list[CandidateMatchResult]:
    """
    Score, deduplicate, and rank all TMDB candidates for a MovSug movie.

    Detects multi-candidate ambiguity (e.g., remakes with identical titles or
    multiple plausible candidates scoring within `AMBIGUITY_TIE_WINDOW` points)
    and marks them as `ambiguous` with explicit review reasons.
    """
    identity = parse_movsug_movie_identity(movie)
    external_map = external_id_matches or {}

    seen_ids: set[int] = set()
    scored: list[CandidateMatchResult] = []

    for cand in candidates:
        if not isinstance(cand, dict) or not cand.get("id"):
            continue
        cid = int(cand["id"])
        if cid in seen_ids:
            continue
        seen_ids.add(cid)

        ext_source = external_map.get(cid)
        result = score_candidate(identity, cand, matched_via_external_id=ext_source)
        scored.append(result)

    # Sort deterministically: highest score first, then smallest year difference, then TMDB ID
    def _sort_key(item: CandidateMatchResult) -> tuple[float, int, int]:
        yd = item.match_evidence.get("year_difference")
        yd_rank = int(yd) if isinstance(yd, int) else 9999
        return (-item.match_score, yd_rank, item.tmdb_id)

    scored.sort(key=_sort_key)

    # Detect remake / multi-candidate ambiguity among non-verified top candidates
    if len(scored) >= 2 and not scored[0].is_verified_id_match:
        top_score = scored[0].match_score
        close_plausible = [
            c
            for c in scored
            if c.match_score >= AMBIGUOUS_THRESHOLD
            and (top_score - c.match_score) <= AMBIGUITY_TIE_WINDOW
        ]
        # Also detect identical normalized titles across multiple candidates (remakes)
        top_norm = normalize_title_for_match(scored[0].title)
        same_title_candidates = [
            c for c in scored if normalize_title_for_match(c.title) == top_norm and top_norm
        ]

        if len(close_plausible) >= 2:
            years = [str(c.release_year or "unknown") for c in close_plausible]
            msg = (
                f"Multiple plausible candidates ({len(close_plausible)}) with close match scores "
                f"(years: {', '.join(years)})."
            )
            for c in close_plausible:
                if msg not in c.conflicts:
                    c.conflicts.append(msg)
                c.match_status = "ambiguous"
                c.reason_for_review = "multiple_plausible_candidates_or_remakes"
        elif len(same_title_candidates) >= 2:
            years = [str(c.release_year or "unknown") for c in same_title_candidates]
            remake_note = (
                f"Multiple releases/remakes share the title '{scored[0].title}' "
                f"(years: {', '.join(years)})."
            )
            for c in same_title_candidates:
                if remake_note not in c.conflicts:
                    c.conflicts.append(remake_note)
                if c is not scored[0] or identity.release_year is None:
                    c.match_status = "ambiguous"
                    c.reason_for_review = "ambiguous_remake_or_multiple_releases"

    return scored

