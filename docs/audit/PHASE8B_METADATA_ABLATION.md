# MovSug Phase 8B — 2×2 Metadata Quality vs. Model Architecture Ablation Report

**Date:** 2026-11-04  
**Phase:** Phase 8B — Semantic Embeddings, Metadata Quality Experiments, and TEC Evaluation  
**Source Artifacts:**
- [phase8b_ablation_2x2.csv](file:///d:/TLTN/movie-recommendation-system/backend/reports/phase8b_embeddings/phase8b_ablation_2x2.csv)
- [phase8b_evaluation_summary.json](file:///d:/TLTN/movie-recommendation-system/backend/reports/phase8b_embeddings/phase8b_evaluation_summary.json)

---

## 1. Purpose of the 2×2 Ablation Study (RQ1 & RQ2)

A core scientific contribution of Phase 8B is separating **data quality** (Original MovieLens metadata vs. Phase 8A TMDB-enriched metadata) from **model architecture** (sparse lexical `TF-IDF v1.1` vs. dense neural `Sentence-Transformers`).

We evaluate a 2×3 factorial grid:
- **Metadata Axis:**
  1. `Original Metadata` (`title`, `genres`, `tags`)
  2. `Enriched Metadata` (Phase 8A approved TMDB fields merged: `original_title`, `title`, `title_vi`, `genres`, `keywords`, `overview`, `overview_vi`, `cast`, `director`)
- **Model Axis:**
  1. `TF-IDF v1.1` (`ngram_range=(1,2)`, `max_features=5000`, `sublinear_tf=True`)
  2. `English Semantic Embeddings` (`sentence-transformers/all-MiniLM-L6-v2`, `en_only`)
  3. `Multilingual Semantic Embeddings` (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, `multilingual` EN+VI)

---

## 2. Protocol B1 — Full Catalog (`9,742` Movies, `587` Active Users) with Partial Phase 8A Enrichment

In Protocol B1, the `10` MovieLens movies that match approved Phase 8A TMDB records in `backend/movsug.db` via `links.csv` (`tmdbId`)—plus `1` exact title/year match (`11 / 9,742 = 0.113%` of the catalog)—receive full TMDB metadata (`overview`, `overview_vi`, `cast`, `director`, `keywords`, `title_vi`), while the remaining `9,731` MovieLens movies retain their original metadata.

### 2.1 Protocol B1 Results ($K = 10$, $N = 587$ Active Users)

| Model Architecture | Metadata Condition | P@10 | R@10 | NDCG@10 | HR@10 | MAP@10 | Coverage@10 | Native ILD@10 | Novelty@10 |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `TF-IDF v1.1` | **Original** | `0.004600` | `0.006896` | `0.007153` | `0.040886` | `0.003061` | `13.10%` | `0.5719` | `14.05` |
| `TF-IDF v1.1` | **Enriched (B1)** | **`0.005281`** | **`0.008131`** | **`0.007819`** | **`0.047700`** | **`0.003209`** | `13.10%` | `0.5733` | `14.05` |
| `Semantic-EN (all-MiniLM-L6-v2)` | **Original** | `0.004089` | `0.005347` | `0.004930` | `0.040886` | `0.001545` | `5.06%` | `0.3117` | `14.59` |
| `Semantic-EN (all-MiniLM-L6-v2)` | **Enriched (B1)** | `0.004089` | `0.005347` | `0.004897` | `0.040886` | `0.001519` | `5.06%` | `0.3122` | `14.58` |
| `Semantic-Multi (L12-v2)` | **Original** | `0.002726` | `0.003193` | `0.002921` | `0.027257` | `0.000835` | `4.27%` | `0.2492` | `14.43` |
| `Semantic-Multi (L12-v2)` | **Enriched (B1)** | `0.002215` | `0.001773` | `0.002390` | `0.022147` | `0.000747` | `4.23%` | `0.2489` | `14.47` |

### 2.2 Paired Statistical Tests for Metadata Enrichment Impact (RQ1 — Protocol B1)

| Comparison | Metric | Original Mean | Enriched Mean | $\Delta$ | Relative $\Delta$ | Paired $t$ | $p$-value ($t$) | Wilcoxon $p$ | 95% Bootstrap CI | Wins / Ties / Losses |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **RQ1a:** `TF-IDF Enriched` vs `Original` | `NDCG@10` | `0.007153` | `0.007819` | **`+0.000666`** | **`+9.31%`** | `+1.9304` | `0.0540` | **`0.0431`** | `[+0.000114, +0.001421]` | `5 / 582 / 0` |
| **RQ1a:** `TF-IDF Enriched` vs `Original` | `P@10` | `0.004600` | `0.005281` | **`+0.000681`** | **`+14.80%`** | `+2.0051` | **`0.0454`** | **`0.0455`** | `[+0.000170, +0.001363]` | `4 / 583 / 0` |
| **RQ1a:** `TF-IDF Enriched` vs `Original` | `R@10` | `0.006896` | `0.008131` | `+0.001235` | `+17.91%` | `+1.7554` | `0.0797` | `0.0679` | `[+0.000114, +0.002797]` | `4 / 583 / 0` |
| **RQ1b:** `Semantic-EN Enriched` vs `Original` | `NDCG@10` | `0.004930` | `0.004897` | `-0.000033` | `-0.67%` | `-1.1228` | `0.2620` | `0.2733` | `[-0.000099, +0.000014]` | `1 / 583 / 3` |
| **RQ1c:** `Semantic-Multi Enriched` vs `Original` | `NDCG@10` | `0.002921` | `0.002390` | `-0.000531` | `-18.18%` | `-1.3326` | `0.1832` | `0.1282` | `[-0.001312, +0.000167]` | `2 / 580 / 5` |

### 2.3 Key Scientific Insight from Protocol B1 (Asymmetric Enrichment Effect)
- **Even `0.11%` catalog enrichment of popular movies produces a statistically significant improvement in `TF-IDF v1.1` `P@10` ($+14.80\%, p = 0.0454$) and non-parametric `NDCG@10` (Wilcoxon $p = 0.0431$, 95% bootstrap CI `[+0.000114, +0.001421]`, 5 wins / 0 losses):** Adding rich TMDB cast, director, keywords, and plot terms to high-interaction movies (*The Dark Knight*, *Inception*, *The Lord of the Rings*, *The Matrix*, *Fight Club*) enriches the user preference profile with shared actor/director/theme n-grams (e.g., `"christopher nolan"`, `"christian bale"`, `"peter jackson"`, `"dystopia"`), allowing `TF-IDF` to match other unenriched movies that carry those tags in MovieLens `tags.csv`.
- **Why partial enrichment (`11 / 9,742` movies) does NOT improve dense embeddings in Protocol B1:** When only `11` movies have `150`-word structured paragraphs while `9,731` movies have `8`-word title+genre strings, neural sentence encoders place long narrative paragraphs and ultra-short title strings into **distinct regions of the embedding manifold** (length/domain shift). This is especially pronounced in `Semantic-Multi` when `11` movies contain bilingual English + Vietnamese text (`title_vi`, `overview_vi`) while `9,731` movies are English-only, shifting the `11` bilingual vectors away from English-only candidates (`NDCG@10` drops from `0.002921` to `0.002390`).

---

## 3. Protocol B2 — Matched Enriched Subset (`10` Movies, `33` Active Users)

To inspect model behavior when **100% of candidate movies** have uniform Phase 8A TMDB enrichment (eliminating the `11` vs `9,731` length/language asymmetry), Protocol B2 restricts the evaluation sub-catalog to the `10` matched MovieLens movies and the `33` test users who have both training and held-out relevant test interactions within that subset.

> [!WARNING]
> **Evidence Status: `NOT ENOUGH EVIDENCE`**  
> Because the matched subset contains only `10` movies (`K=10` spans the entire candidate pool, so `Recall@10 = 1.0` and `HR@10 = 1.0` trivially for all models, and only rank-order metrics `NDCG@10`, `MAP@10`, and `ILD@10` vary across `33` users), Protocol B2 is reported strictly as a diagnostic micro-experiment and **must not** be used to claim catalog-wide superiority.

### 3.1 Protocol B2 Diagnostic Results ($K = 10$, `10` Movies, `33` Users)

| Model Architecture | Metadata Condition | NDCG@10 | MAP@10 | Native ILD@10 | Evidence Status |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `TF-IDF v1.1` | Original | `0.605855` | `0.482071` | `0.9916` | `NOT ENOUGH EVIDENCE` |
| `TF-IDF v1.1` | **Enriched** | `0.607179` | `0.477718` | `0.9928` | `NOT ENOUGH EVIDENCE` |
| `Semantic-EN (all-MiniLM-L6-v2)` | Original | `0.659307` | `0.544637` | `0.6719` | `NOT ENOUGH EVIDENCE` |
| `Semantic-EN (all-MiniLM-L6-v2)` | **Enriched** | **`0.718965`** | **`0.626130`** | `0.7750` | `NOT ENOUGH EVIDENCE` |
| `Semantic-Multi (L12-v2)` | Original | `0.469230` | `0.300986` | `0.5273` | `NOT ENOUGH EVIDENCE` |
| `Semantic-Multi (L12-v2)` | **Enriched** | `0.458035` | `0.284404` | `0.4931` | `NOT ENOUGH EVIDENCE` |

### 3.2 Diagnostic Observation
Within the uniformly enriched `10`-movie subset, enriching metadata increases `Semantic-EN` `NDCG@10` from `0.6593` to `0.7190` (`+9.05%`) and `MAP@10` from `0.5446` to `0.6261` (`+14.96%`), while increasing native embedding diversity (`ILD@10` from `0.6719` to `0.7750`) because rich plot overviews differentiate movies that previously had similar short genre strings. Confirming this effect at scale requires enriching a high percentage ($\ge 80\%$) of the evaluation catalog via batch TMDB ingestion in Phase 9.

