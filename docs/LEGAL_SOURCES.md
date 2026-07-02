# Legal Sources Guide

This document defines which data and media sources are allowed, restricted, or blocked for the Laetus movie recommendation system.

---

## Media Rights Status

Every movie record has a `media_rights_status` field that classifies its copyright standing.

| Status | Meaning | Action |
|--------|---------|--------|
| `safe_to_use` | Fully cleared for use — public domain, CC0, or explicit permission granted | Display normally |
| `attribution_required` | Licensed content that requires visible attribution | Display with attribution shown on movie detail page |
| `non_commercial_only` | Licensed only for non-commercial / educational use | Display with license notice; review before any commercial deployment |
| `unknown` | License status has not been verified | Admin warning in import logs; investigate before production use |
| `blocked` | Known copyrighted content without license | Admin-only indicator; flag for removal or replacement |

---

## Allowed Sources

### MovieLens (University of Minnesota)

- **Use**: Recommendation and rating data only (user-item interaction matrices).
- **License**: Research use permitted. See [GroupLens](https://grouplens.org/datasets/movielens/).
- **Media**: MovieLens does **not** provide poster images, trailers, or video content. Do not scrape linked external media.
- **Status**: `safe_to_use`

### Library of Congress — National Film Registry

- **Use**: Public domain films (pre-1929 US works, or explicitly released by rights holders).
- **URL**: [https://www.loc.gov/film-and-videos/](https://www.loc.gov/film-and-videos/)
- **License**: Public Domain (no copyright restrictions for pre-1929 works).
- **Status**: `safe_to_use` with `is_public_domain = true`

### Wikimedia Commons

- **Use**: Film stills, posters, and video clips for public domain or CC-licensed works.
- **URL**: [https://commons.wikimedia.org/](https://commons.wikimedia.org/)
- **License**: Varies per file — always check the file's license page. Common licenses:
  - CC BY-SA 4.0
  - CC BY 4.0
  - Public Domain
- **Status**: `attribution_required` (unless Public Domain)

### Pexels / Pixabay / Unsplash

- **Use**: Placeholder images and background artwork **only**. Not for pretending these are actual movie posters.
- **License**:
  - Pexels: Free to use, no attribution required
  - Pixabay: Pixabay License (free for commercial use)
  - Unsplash: Unsplash License (free for commercial use)
- **Status**: `safe_to_use` for placeholders

### Internet Archive

- **Use**: Public domain films, documentaries, and historical media.
- **URL**: [https://archive.org/details/movies](https://archive.org/details/movies)
- **License**: Varies — verify each item. Many are public domain.
- **Status**: `safe_to_use` or `attribution_required` depending on the specific item

---

## Restricted Sources

### TMDB (The Movie Database)

- **Use**: Movie metadata (title, overview, genres, cast, crew, release date) via their API.
- **URL**: [https://www.themoviedb.org/](https://www.themoviedb.org/)
- **License**: Free API with required attribution.
- **Required attribution**: Display the following on any page using TMDB data:

  > This product uses the TMDB API but is not endorsed or certified by TMDB.

- **Restrictions**:
  - You **must not** cache TMDB images permanently — use their CDN URLs.
  - You **must not** use TMDB data to build a competing database.
  - You **must** attribute TMDB in your UI.
- **Status**: `attribution_required` with `source_name = "TMDB"`

---

## Blocked Sources

The following sources **must never** be used for data import or media assets:

| Source | Reason |
|--------|--------|
| IMDb (scraping) | Terms of Service prohibit scraping; data is copyrighted by Amazon/IMDb |
| Google Images | No license verification; most results are copyrighted |
| Netflix / Disney+ / HBO | All content is copyrighted and DRM-protected |
| YouTube (ripping) | Violates YouTube ToS; content is typically copyrighted |
| Pinterest | Aggregator of copyrighted images |
| Getty Images / Shutterstock | Paid stock; unauthorized use is copyright infringement |

If any movie record uses one of these sources, set `media_rights_status = "blocked"` and replace the media with a legitimate alternative.

---

## Example Attribution Format

For movies sourced from Wikimedia Commons with CC BY-SA 4.0:

```json
{
  "source_name": "Wikimedia Commons",
  "source_url": "https://commons.wikimedia.org/wiki/File:Nosferatu_poster.jpg",
  "license_type": "CC BY-SA 4.0",
  "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
  "attribution": "Poster image from Wikimedia Commons, licensed under CC BY-SA 4.0.",
  "is_public_domain": false,
  "media_rights_status": "attribution_required"
}
```

For public domain films:

```json
{
  "source_name": "Library of Congress",
  "source_url": "https://www.loc.gov/item/2019600299/",
  "license_type": "Public Domain",
  "license_url": null,
  "attribution": null,
  "is_public_domain": true,
  "media_rights_status": "safe_to_use"
}
```

---

## Import Workflow

1. **Identify source** — determine where the movie data and media come from.
2. **Verify license** — check the source's license page for each individual asset.
3. **Set fields** — populate `source_name`, `license_type`, `media_rights_status`, and `attribution` accordingly.
4. **Review unknowns** — any record with `media_rights_status = "unknown"` should be investigated before production deployment.
5. **Replace blocked** — if a record is marked `blocked`, replace its media assets with legitimate alternatives (Wikimedia, Pexels, or Library of Congress).

---

## Database Fields Reference

| Column | Type | Purpose |
|--------|------|---------|
| `source_name` | `String(100)` | Name of the data/media provider |
| `source_url` | `String(500)` | Link to the original source page |
| `license_type` | `String(100)` | License identifier (e.g., "CC BY 4.0", "Public Domain") |
| `license_url` | `String(500)` | Link to the full license text |
| `attribution` | `Text` | Required attribution text to display |
| `is_public_domain` | `Boolean` | Whether the work is in the public domain |
| `media_rights_status` | `String(30)` | One of: `safe_to_use`, `attribution_required`, `non_commercial_only`, `unknown`, `blocked` |
