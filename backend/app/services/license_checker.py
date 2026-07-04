"""
License checker utilities.

Provides helpers to normalise license strings, determine whether a license is
safe to use, and map licenses to media_rights_status values.
"""

import re
from typing import List

# ── Canonical license map ────────────────────────────────────────────────────
# Keys are lower-cased normalised forms; values are the display name.
_LICENSE_ALIASES: dict[str, str] = {
    "public domain":        "Public Domain",
    "pd":                   "Public Domain",
    "cc0":                  "CC0 1.0",
    "cc0 1.0":              "CC0 1.0",
    "cc-zero":              "CC0 1.0",
    "cc by":                "CC BY 4.0",
    "cc by 4.0":            "CC BY 4.0",
    "cc-by-4.0":            "CC BY 4.0",
    "cc by 3.0":            "CC BY 3.0",
    "cc-by-3.0":            "CC BY 3.0",
    "cc by-sa":             "CC BY-SA 4.0",
    "cc by-sa 4.0":         "CC BY-SA 4.0",
    "cc-by-sa-4.0":         "CC BY-SA 4.0",
    "cc by-sa 3.0":         "CC BY-SA 3.0",
    "cc-by-sa-3.0":         "CC BY-SA 3.0",
    "cc by-nc":             "CC BY-NC 4.0",
    "cc-by-nc-4.0":         "CC BY-NC 4.0",
    "cc by-nc 4.0":         "CC BY-NC 4.0",
    "cc by-nc-sa":          "CC BY-NC-SA 4.0",
    "cc-by-nc-sa-4.0":      "CC BY-NC-SA 4.0",
    "cc by-nd":             "CC BY-ND 4.0",
    "cc-by-nd-4.0":         "CC BY-ND 4.0",
    "pexels license":       "Pexels License",
    "pixabay license":      "Pixabay License",
    "unsplash license":     "Unsplash License",
}

# Licenses that are unambiguously safe for any use (including commercial).
_SAFE_LICENSES = {
    "Public Domain",
    "CC0 1.0",
    "CC BY 4.0",
    "CC BY 3.0",
    "CC BY-SA 4.0",
    "CC BY-SA 3.0",
    "Pexels License",
    "Pixabay License",
    "Unsplash License",
}

# Licenses that are non-commercial only.
_NON_COMMERCIAL_LICENSES = {
    "CC BY-NC 4.0",
    "CC BY-NC-SA 4.0",
}

# Licenses that block redistribution / derivative works.
_BLOCKED_LICENSES = {
    "CC BY-ND 4.0",
    "All Rights Reserved",
}


def normalize_license(raw: str) -> str:
    """
    Convert a raw license string to its canonical display form.

    >>> normalize_license("cc-by-sa-4.0")
    'CC BY-SA 4.0'
    >>> normalize_license("PD")
    'Public Domain'
    >>> normalize_license("some unknown license")
    'some unknown license'
    """
    key = re.sub(r"[\s_]+", " ", raw.strip()).lower()
    return _LICENSE_ALIASES.get(key, raw.strip())


def allow_license(license_type: str) -> bool:
    """
    Return True if the license is safe for use (free, open, or stock-image).

    Rejects NC, ND, all-rights-reserved, and unknown licenses.

    >>> allow_license("CC BY-SA 4.0")
    True
    >>> allow_license("CC BY-NC 4.0")
    False
    >>> allow_license("All Rights Reserved")
    False
    """
    canonical = normalize_license(license_type)
    return canonical in _SAFE_LICENSES


def get_media_rights_status(license_type: str) -> str:
    """
    Map a license string to the appropriate media_rights_status.

    >>> get_media_rights_status("Public Domain")
    'safe_to_use'
    >>> get_media_rights_status("CC BY 4.0")
    'attribution_required'
    >>> get_media_rights_status("CC BY-NC 4.0")
    'non_commercial_only'
    >>> get_media_rights_status("All Rights Reserved")
    'blocked'
    >>> get_media_rights_status("some random thing")
    'unknown'
    """
    canonical = normalize_license(license_type)

    if canonical in {"Public Domain", "CC0 1.0"}:
        return "safe_to_use"

    if canonical in _SAFE_LICENSES:
        # Safe licenses other than PD/CC0 still require attribution
        return "attribution_required"

    if canonical in _NON_COMMERCIAL_LICENSES:
        return "non_commercial_only"

    if canonical in _BLOCKED_LICENSES:
        return "blocked"

    return "unknown"


def block_unknown_or_restricted_media(
    assets: List[dict],
) -> List[dict]:
    """
    Filter a list of asset dicts for public display:
      - Remove assets with media_rights_status == "blocked"
      - Replace assets with media_rights_status == "unknown" with a placeholder marker

    Each dict must have at least a 'media_rights_status' key.

    >>> assets = [
    ...     {"id": 1, "media_rights_status": "safe_to_use"},
    ...     {"id": 2, "media_rights_status": "blocked"},
    ...     {"id": 3, "media_rights_status": "unknown"},
    ... ]
    >>> result = block_unknown_or_restricted_media(assets)
    >>> [a["id"] for a in result]
    [1, 3]
    >>> result[1]["_placeholder"]
    True
    """
    out: List[dict] = []
    for asset in assets:
        status = asset.get("media_rights_status", "unknown")
        if status == "blocked":
            continue
        if status == "unknown":
            asset = {**asset, "_placeholder": True}
        out.append(asset)
    return out
