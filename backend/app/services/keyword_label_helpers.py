"""
Helpers for normalizing Vietnamese keyword display labels.

Canonical English keywords are the source of truth.  Vietnamese labels
are optional display-only mappings that must reference existing keywords.
"""

import re


def _normalize_ws(s: str) -> str:
    """Trim and collapse internal whitespace."""
    return re.sub(r"\s+", " ", s.strip())


def normalize_keyword_labels(
    keywords: list[str] | None,
    labels: dict[str, str] | None,
) -> dict[str, str] | None:
    """Keep only labels whose key matches a canonical keyword (case-insensitive).

    * Keys are stored using exact canonical keyword casing.
    * Values are trimmed; empty values are dropped.
    * Returns ``None`` when no valid labels remain.
    """
    if not labels or not keywords:
        return None

    # Build a lowercase → canonical mapping
    canonical_map: dict[str, str] = {}
    for kw in keywords:
        norm = _normalize_ws(kw).lower()
        if norm:
            canonical_map[norm] = _normalize_ws(kw)

    result: dict[str, str] = {}
    for key, value in labels.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        norm_key = _normalize_ws(key).lower()
        norm_val = _normalize_ws(value)
        if norm_key in canonical_map and norm_val:
            result[canonical_map[norm_key]] = norm_val

    return result if result else None
