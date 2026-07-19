# Content Source and License Guidelines

## 1. Purpose

This document provides guidance for managing content sources and license
metadata within the Laetus movie recommendation system. It describes the
fields available in the application, how to use them, and what limitations
apply.

This is project guidance for contributors, not professional legal advice.

## 2. Academic and Non-Commercial Use

Laetus is an academic project created for research, learning, and educational
demonstration purposes. It is not operated for business or commercial
purposes.

Non-commercial intent does not automatically grant permission to use any
particular media. Source and license requirements still apply regardless of
the project's academic nature.

## 3. Disclaimer Is Not a License

The non-commercial disclaimer displayed on the website states the project's
intent. It does not modify, override, or replace the license terms of any
third-party content. Each piece of content must be evaluated independently
based on its actual license.

## 4. Required Metadata Fields

Each movie in the system has the following source and license fields
(`movies` table):

| Field | Type | Description |
|-------|------|-------------|
| `source_name` | String (nullable) | Name of the content provider (e.g., "Pexels", "Wikimedia Commons") |
| `source_url` | String (nullable) | URL of the original content page at the provider |
| `license_type` | String (nullable) | License identifier (e.g., "CC0", "CC BY 4.0", "Pexels License") |
| `license_url` | String (nullable) | URL of the license text |
| `attribution` | String (nullable) | Required attribution text (e.g., "Video by John Doe") |
| `is_public_domain` | Boolean | Whether the content is in the public domain |
| `media_rights_status` | String | One of: `safe_to_use`, `attribution_required`, `non_commercial_only`, `unknown`, `blocked` |

## 5. Per-Movie Attribution

The `SourceAttribution` component on the Movie Detail page displays the
source and license information for each movie. This is visible to all users
when they view a movie's detail page.

For each movie, fill in:
- `source_name` — the provider name
- `source_url` — the original URL at the provider (not an internal media URL)
- `license_type` — the license name
- `attribution` — any required credit text

## 6. Per-Asset Attribution

Individual assets (poster images, backdrop images, trailer clips) can have
separate source and license metadata via the `movie_assets` table:

| Field | Type | Description |
|-------|------|-------------|
| `asset_type` | String | Type of asset (e.g., "poster", "backdrop", "trailer") |
| `url` | String | URL or path to the asset |
| `source_name` | String (nullable) | Provider name for this specific asset |
| `license_type` | String (nullable) | License for this specific asset |
| `is_public_domain` | Boolean | Whether this specific asset is public domain |
| `media_rights_status` | String | Rights status for this specific asset |

## 7. Public-Domain Content

Content marked `is_public_domain = true` and `media_rights_status = "safe_to_use"`
may generally be used without restrictions. However, verify the specific
terms — some jurisdictions handle public domain differently.

Examples: works explicitly released under CC0, government works in certain
jurisdictions, content whose copyright has expired.

## 8. Attribution-Required Content

Content with `media_rights_status = "attribution_required"` must include
the attribution text from the `attribution` field wherever the content is
displayed.

Examples: Creative Commons BY licenses (CC BY 2.0, CC BY 4.0), some stock
photo licenses.

## 9. Non-Commercial-Only Content

Content with `media_rights_status = "non_commercial_only"` may only be used
in non-commercial contexts. This aligns with the project's academic purpose
but does not extend to derivative works or redistribution.

Examples: Creative Commons NC licenses (CC BY-NC 4.0).

## 10. Unknown or Blocked Rights Status

- `unknown` — The rights status has not been determined. Treat as restricted
  until verified.
- `blocked` — The content has been identified as restricted or infringing.
  Do not use this content.

Content with `unknown` or `blocked` status should not be treated as verified
safe for any use.

## 11. External Source URLs Versus Internal Media URLs

- **Source URLs** (`source_url`) must point to the original content at the
  provider (e.g., `https://www.pexels.com/video/12345/`). These are
  permanent references to the original source.
- **Internal media paths** (e.g., `/media/videos/hls/movie_xxx/master.m3u8`)
  are internal storage paths. They are not source URLs.

Do not use internal media paths as source URLs.

## 12. Content Review Checklist

Before adding content to the system:

- [ ] Identify the original source and provider
- [ ] Determine the license type
- [ ] Record the source URL (original provider page, not internal path)
- [ ] Record any required attribution text
- [ ] Set `media_rights_status` accurately
- [ ] Set `is_public_domain` accurately
- [ ] If the asset is separate from the movie video, create a `movie_assets` entry

## 13. Limitations

- This document is project guidance, not professional legal advice
- Non-commercial intent does not automatically grant permission to reuse
  any specific media
- Third-party rights remain with their respective owners
- The presence of content in this system does not imply any license grant
  from the rights holder to the project
- Content from providers like Pexels, Wikimedia, or MovieLens has its own
  specific terms — do not assume blanket permission for every use
- The `media_rights_status` field reflects the contributor's assessment and
  may not be legally binding
- When in doubt, consult the original license terms at the provider's URL
