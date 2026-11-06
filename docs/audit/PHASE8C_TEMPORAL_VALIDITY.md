# Phase 8C — Temporal Validity Analysis

## 1. Constraint

MovieLens interactions are **historical** (user ratings timestamped 1996–2018),
while TMDB metadata is **current** (retrieved in 2026). This creates a temporal
mismatch: TMDB fields may have been edited, expanded, or corrected since the
MovieLens interactions occurred.

## 2. Field Classification

### Time-Invariant Fields (Stable)
These fields are unlikely to change after a movie's initial release:

| Field             | Reasoning                                            |
|-------------------|------------------------------------------------------|
| `title`           | Official release title rarely changes                |
| `original_title`  | Original language title is fixed                     |
| `director`        | Director credit is established at release            |
| `cast`            | Principal cast is established at release             |
| `release_date`    | Fixed historical fact                                |
| `original_language` | Fixed property of the production                   |

### Potentially Time-Varying Fields
These fields may have been updated on TMDB after the MovieLens interactions:

| Field         | Risk                                                     |
|---------------|----------------------------------------------------------|
| `overview`    | Plot summaries are community-edited on TMDB              |
| `keywords`    | Users continuously add/remove keywords                   |
| `genres`      | Genre classifications may be refined over time           |
| `title_vi`    | Vietnamese translations may be added long after release  |
| `overview_vi` | Vietnamese overviews may not have existed at interaction time |

## 3. Mitigation

This experiment does **NOT** claim to be a strict historical temporal prediction
benchmark. Results should be interpreted as measuring:

> "The effect of metadata quality (richness, completeness) on recommendation
> model performance using current-best-available metadata."

This is distinct from the causal question:

> "Would richer metadata at the time of user interactions have led to better
> recommendations?"

## 4. Recommendations for Future Work

1. Use Wikidata revision history for time-stamped metadata archives
2. Filter TMDB keywords/overview edits to those existing before the MovieLens
   interaction period (requires TMDB edit history API, not publicly available)
3. Focus analysis on time-invariant fields (cast, director, title) for the
   most defensible causal claims
4. Clearly label all experiments using current TMDB data as "metadata quality
   ablation" rather than "temporal prediction"

## 5. Acknowledgement in Thesis

This limitation must be explicitly acknowledged in the thesis methodology section:

> "Cần lưu ý rằng dữ liệu TMDB được thu thập vào năm 2026, trong khi các
> tương tác MovieLens diễn ra trong giai đoạn 1996–2018. Do đó, một số trường
> metadata (đặc biệt là overview, keywords, genres) có thể đã được chỉnh sửa
> hoặc bổ sung sau thời điểm tương tác. Thí nghiệm này đo lường ảnh hưởng
> của chất lượng metadata đối với hiệu suất mô hình, không phải dự đoán nhân
> quả về quá khứ."

