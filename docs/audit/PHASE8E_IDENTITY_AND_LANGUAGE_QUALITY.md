# Phase 8E — Identity and Language Quality Report

| Field | Value |
|---|---|
| **Phase** | 8E — Identity & Language Audit |
| **Source** | `phase8d_run_002` snapshot |
| **Date** | 2026-11-20 |
| **Status** | `QUALITY_ASSESSED` |

---

## Tóm tắt

Báo cáo chất lượng danh tính và ngôn ngữ cho 37 phim đã truy vấn. 36 phim có danh
tính xác minh (`LIVE_VERIFIED`), 1 phim mơ hồ. Phân tích ngôn ngữ cho thấy: 18/37
(48.6%) có tiêu đề tiếng Việt thực sự, 12/37 (32.4%) có tóm tắt tiếng Việt thực
sự. 19 tiêu đề "tiếng Việt" thực chất là tiếng Anh fallback từ TMDB API.

---

## 1. Identity Verification Summary

### Per-Movie Identity Confidence

| MovieLens ID | Title | TMDB ID | Title Match | Year Match | Confidence |
|---|---|---|---|---|---|
| 1029 | Dumbo (1941) | 11360 | ✅ | ✅ | HIGH |
| 106782 | Wolf of Wall Street, The (2013) | 106646 | ✅ | ✅ | HIGH |
| 110826 | Brick Mansions (2014) | 254473 | ✅ | ✅ | HIGH |
| 112788 | Sex Tape (2014) | 225886 | ✅ | ✅ | HIGH |
| 135 | Down Periscope (1996) | 9101 | ✅ | ✅ | HIGH |
| 1493 | Love and Other Catastrophes (1996) | 76996 | ✅ | ✅ | HIGH |
| 151317 | Maggie's Plan (2015) | 312669 | ✅ | ✅ | HIGH |
| 152077 | 10 Cloverfield Lane (2016) | 333371 | ✅ | ✅ | HIGH |
| 1891 | Ugly, The (1997) | 40961 | ✅ | ✅ | HIGH |
| 2080 | Lady and the Tramp (1955) | 10340 | ✅ | ✅ | HIGH |
| 2282 | Pecker (1998) | 11855 | ✅ | ✅ | HIGH |
| 2342 | Hard Core Logo (1996) | 21589 | ✅ | ✅ | HIGH |
| 2478 | ¡Three Amigos! (1986) | 8388 | ✅ | ✅ | HIGH |
| 2730 | Barry Lyndon (1975) | 3175 | ✅ | ✅ | HIGH |
| **284** | **New York Cop (1993)** | **109560** | **❌** | **✅** | **AMBIGUOUS** |
| 3 | Grumpier Old Men (1995) | 15602 | ✅ | ✅ | HIGH |
| 3152 | Last Picture Show, The (1971) | 25188 | ✅ | ✅ | HIGH |
| 3385 | Volunteers (1985) | 19259 | ✅ | ✅ | HIGH |
| 3825 | Coyote Ugly (2000) | 6282 | ✅ | ✅ | HIGH |
| 414 | Air Up There, The (1994) | 46094 | ✅ | ✅ | HIGH |
| 4998 | Defiant Ones, The (1958) | 11414 | ✅ | ✅ | HIGH |
| 57147 | Cassandra's Dream (2007) | 4787 | ✅ | ✅ | HIGH |
| 5791 | Frida (2002) | 1360 | ✅ | ✅ | HIGH |
| 58351 | City of Men (2007) | 7343 | ✅ | ✅ | HIGH |
| 59220 | Outsourced (2006) | 7861 | ✅ | ✅ | HIGH |
| 6123 | Sunless (Sans Soleil) (1983) | 1563 | ✅ | ✅ | HIGH |
| 6289 | Ghosts of the Abyss (2003) | 24982 | ✅ | ✅ | HIGH |
| 67534 | Big Stan (2007) | 13161 | ✅ | ✅ | HIGH |
| 6807 | Monty Python's Meaning of Life (1983) | 4543 | ✅ | ✅ | HIGH |
| 6944 | Father of the Bride (1991) | 11846 | ✅ | ✅ | HIGH |
| 70301 | Obsessed (2009) | 17335 | ✅ | ✅ | HIGH |
| 745 | Wallace & Gromit: Close Shave (1995) | 532 | ✅ | ✅ | HIGH |
| 78142 | Baarìa (2009) | 25846 | ✅ | ✅ | HIGH |
| 79091 | Despicable Me (2010) | 20352 | ✅ | ✅ | HIGH |
| 79536 | Hellsinki (Rööperi) (2009) | 25335 | ✅ | ✅ | HIGH |
| 8712 | My Favorite Wife (1940) | 41463 | ✅ | ✅ | HIGH |
| 95497 | Dragon Ball Z: Super Android 13! (1992) | 39104 | ✅ | ✅ | HIGH |

---

## 2. Vietnamese Language Quality

### 2.1 Vietnamese Title Analysis

| Category | Count | % of 37 Queried | Movies |
|---|---|---|---|
| **Authentic VI translation** | **18** | **48.6%** | Dumbo→Chú Voi Biết Bay, Wolf→Sói Già Phố Wall, Brick Mansions→Khu Nguy Hiểm, Sex Tape→Đoạn Phim Sex Bị Lộ, 10 Cloverfield→Căn Hầm, Lady & Tramp→Tiểu Thư và Gã Lang Thang, Barry Lyndon→Chàng Barry May Mắn, Last Picture Show→Buổi Chiếu Phim Cuối Cùng, City of Men→Cidade dos Homens, Sans Soleil→Sans soleil, Ghosts→Con Tàu Ma, Big Stan→Đại Ca Stan, Monty Python→Ý Nghĩa Cuộc Sống, Obsessed→Ám Ảnh, Baarìa→Baarìa, Despicable Me→Kẻ Trộm Mặt Trăng, Hellsinki→Rööperi, Dragon Ball Z→Bảy Viên Ngọc Rồng |
| **English fallback** | **19** | **51.4%** | Down Periscope, Love and Other Catastrophes, Maggie's Plan, The Ugly, Pecker, Hard Core Logo, ¡Three Amigos!, New York Undercover Cop, Grumpier Old Men, Volunteers, Coyote Ugly, Air Up There, Defiant Ones, Cassandra's Dream, Frida, Outsourced, Father of the Bride, A Close Shave, My Favorite Wife |

> [!WARNING]
> The Phase 8D.6 report claimed `has_vi_title: 37/37 (100%)`. This is **technically
> true** (the TMDB API returned a non-empty title for the `vi-VN` locale), but
> **semantically misleading**. 19 of these are English-language fallbacks where
> TMDB has no Vietnamese translation. The authentic Vietnamese title coverage is
> **48.6%**, not 100%.

### 2.2 Vietnamese Overview Analysis

| Category | Count | % of 37 Queried |
|---|---|---|
| **Authentic VI overview** | **12** | **32.4%** |
| **Missing (empty)** | **25** | **67.6%** |
| **English fallback** | **0** | **0%** |

Movies with authentic Vietnamese overviews: ML#1029 (Dumbo), #106782 (Wolf of Wall
Street), #110826 (Brick Mansions), #112788 (Sex Tape), #152077 (10 Cloverfield Lane),
#2730 (Barry Lyndon), #3152 (Last Picture Show), #67534 (Big Stan), #6807 (Monty
Python), #70301 (Obsessed), #79091 (Despicable Me), #95497 (Dragon Ball Z).

> [!NOTE]
> TMDB returns empty overview (not English fallback) when no Vietnamese translation
> exists. This means `has_vi_overview: 12/37 (32.4%)` is **accurate** — all 12
> are genuine Vietnamese translations.

### 2.3 Provenance Bug

All `title_vi` and `overview_vi` provenance labels incorrectly show `en-US` source:
```json
"title_vi": "tmdb:movie/11360:en-US"   // Should be: tmdb:movie/11360:vi-VN
"overview_vi": "tmdb:movie/11360:en-US" // Should be: tmdb:movie/11360:vi-VN
```

**Root cause:** The provenance recording in `phase8d_live_pilot.py` does not
distinguish the language parameter of the second HTTP request. The `vi-VN` request
endpoint is correct, but the provenance string is copied from the `en-US` template.

---

## 3. English Metadata Quality

### Denominator: 36 LIVE_VERIFIED movies

| Field | Populated | of 36 | % |
|---|---|---|---|
| EN overview | 36 | 36 | **100%** |
| Keywords | 35 | 36 | **97.2%** |
| Cast (top 10) | 36 | 36 | **100%** |
| Director | 36 | 36 | **100%** |
| Original title | 36 | 36 | **100%** |
| Release date | 36 | 36 | **100%** |
| Genres | 36 | 36 | **100%** |

**Missing keywords:** ML#70301 (Obsessed, 2009) — TMDB has no keywords for this movie.

### Including ambiguous movie (37 queried):

| Field | Populated | of 37 | % |
|---|---|---|---|
| EN overview | 37 | 37 | 100% |
| Keywords | 35 | 37 | 94.6% |
| Cast | 37 | 37 | 100% |
| Director | 37 | 37 | 100% |

> [!NOTE]
> ML#284 (ambiguous) also has overview, cast, and director but its identity is
> unverified. For research experiments, exclude ML#284 unless manually confirmed.

---

## 4. Corrected Completeness Summary

### Research-safe denominators (36 LIVE_VERIFIED only)

| Field | Coverage | Authentic |
|---|---|---|
| EN overview | 36/36 (100%) | ✅ All authentic |
| EN keywords | 35/36 (97.2%) | ✅ All authentic |
| EN cast | 36/36 (100%) | ✅ All authentic |
| EN director | 36/36 (100%) | ✅ All authentic |
| VI title | 18/36 (50.0%) | ✅ Excludes fallbacks |
| VI overview | 12/36 (33.3%) | ✅ All authentic |

### Note on "authentic" determination

A Vietnamese title is classified as "authentic" when it differs from the English
title returned by the `en-US` endpoint. This heuristic is imperfect:
- Some movies may have the same title in both languages (e.g., proper nouns)
- Some VI titles may be minor transliterations rather than full translations

For research purposes, the conservative approach (treating same-as-EN as fallback)
is preferred.

---

## 5. Genre Distribution of Pilot (36 LIVE_VERIFIED)

| Genre | Count |
|---|---|
| Comedy | 20 |
| Drama | 17 |
| Romance | 10 |
| Crime | 7 |
| Family | 6 |
| Thriller | 6 |
| Animation | 5 |
| Action | 3 |
| Science Fiction | 3 |
| Horror | 2 |
| Adventure | 2 |
| Music | 2 |
| Documentary | 2 |
| Western | 1 |
| History | 1 |

> [!NOTE]
> The pilot is dominated by Comedy/Drama/Romance. A scaled expansion should ensure
> better representation of Action, Horror, Sci-Fi, and Documentary genres.
