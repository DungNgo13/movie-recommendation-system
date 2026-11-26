"""Conservative field-level TMDB Vietnamese localization checks.

A vi-VN response is a requested locale, not proof of a Vietnamese translation.
When an English comparison is available, unchanged text is treated as fallback.
Different text is only a translation *candidate*, not a linguistic guarantee.
"""

from __future__ import annotations

import unicodedata
from typing import Literal

VietnameseFieldStatus = Literal[
    "missing", "english_fallback", "localized_candidate", "original_vi", "unverified"
]

VI_FIELD_STATUSES = frozenset({"localized_candidate", "original_vi"})


def _normalize_locale_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def classify_tmdb_vi_text(
    english_text: object,
    localized_text: object,
    original_language: object = None,
) -> VietnameseFieldStatus:
    """Classify each vi-VN field without assuming the response was translated.

    For non-Vietnamese originals, same-as-English is conservatively excluded.
    Differing text is a localization candidate (not language-ID proof).
    If English comparison is absent, leave the field unverified.
    """
    vi_value = _normalize_locale_text(localized_text)
    if not vi_value:
        return "missing"
    if original_language == "vi":
        return "original_vi"
    en_value = _normalize_locale_text(english_text)
    if not en_value:
        return "unverified"
    if vi_value == en_value:
        return "english_fallback"
    return "localized_candidate"
