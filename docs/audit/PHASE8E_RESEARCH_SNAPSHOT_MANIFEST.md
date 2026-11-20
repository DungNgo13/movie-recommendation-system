# Phase 8E — Research Snapshot Manifest

| Field | Value |
|---|---|
| **Phase** | 8E — Research-Ready Snapshot |
| **Source** | `phase8d_run_002` |
| **Date** | 2026-11-20 |
| **Status** | `SNAPSHOT_VALIDATED` |

---

## Tóm tắt

Manifest cho snapshot nghiên cứu được rút trích từ dữ liệu pilot run_002.
Chỉ bao gồm 36 bản ghi `LIVE_VERIFIED` — loại trừ 1 phim danh tính mơ hồ
(ML#284) và 3 phim không có TMDB ID. Snapshot gốc run_002 được bảo toàn nguyên
vẹn. Snapshot nghiên cứu là dạng dẫn xuất (derived), immutable.

---

## 1. Source Snapshot Reference

| Property | Value |
|---|---|
| Source file | `backend/reports/phase8d_pilot_run_002/snapshots/phase8d_pilot_snapshot.json` |
| Source SHA-256 | `a92f40184550596322aeca21677f79c4c69a0cd07027be2d441c33354934c153` |
| Source records | 37 movies |
| Source timestamp | `2026-11-20T04:27:58.604887+00:00` |
| Manifest checksum | `d23fc802aefe509088127ede5d03009bc22354165d1b1adbc8f4906567d8800c` |

> [!CAUTION]
> The source snapshot manifest (`phase8d_snapshot_manifest.json`) contains a path
> reference bug — it points to `backend/reports/phase8d_pilot/` (run_001) instead
> of `backend/reports/phase8d_pilot_run_002/`. Use the SHA-256 hash above for
> verification, not the manifest paths.

---

## 2. Research Snapshot Inclusion Criteria

| Criterion | Filter |
|---|---|
| Verification status | `LIVE_VERIFIED` only |
| Title match | ✅ True |
| Year match | ✅ True |
| Identity confidence | HIGH |
| Excludes | ML#284 (ambiguous), ML#2851/#32600/#791 (no TMDB ID) |

---

## 3. Research Snapshot Contents (36 movies)

### MovieLens ID Mapping

| # | ML ID | TMDB ID | IMDb ID | Title | Year |
|---|---|---|---|---|---|
| 1 | 1029 | 11360 | tt0033563 | Dumbo | 1941 |
| 2 | 106782 | 106646 | tt0993846 | The Wolf of Wall Street | 2013 |
| 3 | 110826 | 254473 | tt1430612 | Brick Mansions | 2014 |
| 4 | 112788 | 225886 | tt1956620 | Sex Tape | 2014 |
| 5 | 135 | 9101 | tt0116130 | Down Periscope | 1996 |
| 6 | 1493 | 76996 | tt0116931 | Love and Other Catastrophes | 1996 |
| 7 | 151317 | 312669 | tt3471098 | Maggie's Plan | 2015 |
| 8 | 152077 | 333371 | tt1179933 | 10 Cloverfield Lane | 2016 |
| 9 | 1891 | 40961 | tt0120401 | The Ugly | 1997 |
| 10 | 2080 | 10340 | tt0048280 | Lady and the Tramp | 1955 |
| 11 | 2282 | 11855 | tt0126604 | Pecker | 1998 |
| 12 | 2342 | 21589 | tt0116488 | Hard Core Logo | 1996 |
| 13 | 2478 | 8388 | tt0092086 | ¡Three Amigos! | 1986 |
| 14 | 2730 | 3175 | tt0072684 | Barry Lyndon | 1975 |
| 15 | 3 | 15602 | tt0113228 | Grumpier Old Men | 1995 |
| 16 | 3152 | 25188 | tt0067328 | The Last Picture Show | 1971 |
| 17 | 3385 | 19259 | tt0090274 | Volunteers | 1985 |
| 18 | 3825 | 6282 | tt0200550 | Coyote Ugly | 2000 |
| 19 | 414 | 46094 | tt0109067 | The Air Up There | 1994 |
| 20 | 4998 | 11414 | tt0051525 | The Defiant Ones | 1958 |
| 21 | 57147 | 4787 | tt0795493 | Cassandra's Dream | 2007 |
| 22 | 5791 | 1360 | tt0120679 | Frida | 2002 |
| 23 | 58351 | 7343 | tt0870090 | City of Men | 2007 |
| 24 | 59220 | 7861 | tt0425326 | Outsourced | 2006 |
| 25 | 6123 | 1563 | tt0084628 | Sans Soleil | 1983 |
| 26 | 6289 | 24982 | tt0297144 | Ghosts of the Abyss | 2003 |
| 27 | 67534 | 13161 | tt0490086 | Big Stan | 2007 |
| 28 | 6807 | 4543 | tt0085959 | Monty Python's Meaning of Life | 1983 |
| 29 | 6944 | 11846 | tt0101862 | Father of the Bride | 1991 |
| 30 | 70301 | 17335 | tt1198138 | Obsessed | 2009 |
| 31 | 745 | 532 | tt0112691 | A Close Shave | 1995 |
| 32 | 78142 | 25846 | tt1081935 | Baarìa | 2009 |
| 33 | 79091 | 20352 | tt1323594 | Despicable Me | 2010 |
| 34 | 79536 | 25335 | tt1227536 | Hellsinki | 2009 |
| 35 | 8712 | 41463 | tt0029284 | My Favorite Wife | 1940 |
| 36 | 95497 | 39104 | tt0142241 | Dragon Ball Z: Super Android 13! | 1992 |

---

## 4. Field-Level Coverage (36 LIVE_VERIFIED)

| Field | Language | Populated | Coverage | Provenance |
|---|---|---|---|---|
| title | en-US | 36 | 100% | TMDB `/movie/{id}` |
| original_title | en-US | 36 | 100% | TMDB `/movie/{id}` |
| overview | en-US | 36 | 100% | TMDB `/movie/{id}` |
| genres | en-US | 36 | 100% | TMDB `/movie/{id}` |
| keywords | en-US | 35 | 97.2% | TMDB `/movie/{id}?append=keywords` |
| cast (top 10) | en-US | 36 | 100% | TMDB `/movie/{id}?append=credits` |
| director | en-US | 36 | 100% | TMDB `/movie/{id}?append=credits` |
| release_date | en-US | 36 | 100% | TMDB `/movie/{id}` |
| title_vi (authentic) | vi-VN | 18 | 50.0% | TMDB `/movie/{id}?language=vi-VN` |
| title_vi (any) | vi-VN/fallback | 36 | 100% | TMDB (may be EN fallback) |
| overview_vi | vi-VN | 12 | 33.3% | TMDB `/movie/{id}?language=vi-VN` |

---

## 5. Excluded Records

| ML ID | Reason | Disposition |
|---|---|---|
| 284 | Ambiguous identity (title mismatch) | Excluded until manual review |
| 2851 | No TMDB ID in links.csv | Excluded — no data available |
| 32600 | No TMDB ID in links.csv | Excluded — no data available |
| 791 | No TMDB ID in links.csv | Excluded — no data available |

---

## 6. Immutability

| Artifact | Status |
|---|---|
| Source run_002 snapshot | **IMMUTABLE** — not modified |
| Source run_002 checkpoint | **IMMUTABLE** — 74/100 |
| Source run_001 checkpoint | **IMMUTABLE** — 74/74 |
| Research snapshot | **DERIVED** — created from source, read-only |
| Production database | **UNMODIFIED** |
