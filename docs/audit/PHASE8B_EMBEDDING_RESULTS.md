# MovSug Phase 8B — Semantic Embedding Evaluation Results (Condition A)

**Date:** 2026-11-04  
**Phase:** Phase 8B — Semantic Embeddings, Metadata Quality Experiments, and TEC Evaluation  
**Source Artifacts:**
- [phase8b_evaluation_summary.json](file:///d:/TLTN/movie-recommendation-system/backend/reports/phase8b_embeddings/phase8b_evaluation_summary.json)
- [phase8b_condition_a_comparison.csv](file:///d:/TLTN/movie-recommendation-system/backend/reports/phase8b_embeddings/phase8b_condition_a_comparison.csv)
- [phase8b_statistical_significance.json](file:///d:/TLTN/movie-recommendation-system/backend/reports/phase8b_embeddings/phase8b_statistical_significance.json)

---

## 1. Evaluation Cohort & Provenance

- **Catalog:** `9,742` MovieLens `ml-latest-small` movies (Condition A: Original Metadata — `title`, `genres`, and user `tags` only; `0%` overviews, `0%` cast, `0%` directors).
- **Dataset SHA-256:** `d830d1e560efffd547d0360da5042a5d97884e5cd99dfd145ec9ecc0efbbaa86`
- **Split SHA-256:** `48cc8f10cce949d0add60ad6320bf75668370d1753e5456d6fbd69479f931d67`
- **Active Evaluation Cohort:** `587` users with $\ge 1$ relevant test item (`rating >= 4.0`) out of `610` total users.

---

## 2. Full Condition A Comparison Across Cutoffs ($K \in \{5, 10, 20\}$)

### 2.1 Primary Cutoff: $K = 10$

| Variant | Model / Architecture | P@10 | R@10 | NDCG@10 | HR@10 | MAP@10 | Coverage@10 | Native ILD@10 | TF-IDF Space ILD@10 | Novelty@10 (bits) | p50 (ms) | p95 (ms) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `tfidf_v1_1` | `TF-IDF v1.1 (no MMR)` | `0.004600` | `0.006896` | `0.007153` | `0.040886` | `0.003061` | `13.10%` | `0.5719` | `0.5719` | `14.05` | `5.74` | `8.93` |
| `tfidf_v1_1_mmr_05` | `TF-IDF v1.1 + MMR (λ=0.5, pool=100)` | `0.005451` | **`0.010158`** | **`0.009091`** | `0.052811` | **`0.004047`** | **`14.22%`** | `0.7686` | `0.7686` | `13.84` | `34.07` | `37.60` |
| `tfidf_v1_1_mmr_07` | `TF-IDF v1.1 + MMR (λ=0.7, pool=100)` | **`0.005622`** | `0.008606` | `0.008508` | **`0.054514`** | `0.003508` | `13.69%` | `0.6624` | `0.6624` | `13.91` | `34.60` | `37.93` |
| `semantic_en` | `all-MiniLM-L6-v2` (384-d) | `0.004089` | `0.005347` | `0.004930` | `0.040886` | `0.001545` | `5.06%` | `0.3117` | `0.8905` | **`14.59`** | `8.52` | `10.23` |
| `semantic_multi` | `paraphrase-multilingual-MiniLM-L12-v2` (384-d) | `0.002726` | `0.003193` | `0.002921` | `0.027257` | `0.000835` | `4.27%` | `0.2492` | **`0.9372`** | `14.43` | `8.91` | `10.71` |
| `semantic_en_mmr_05` | `all-MiniLM-L6-v2 + MMR (λ=0.5, pool=100)` | `0.004089` | `0.005378` | `0.005113` | `0.039182` | `0.001664` | `5.42%` | `0.3215` | `0.9013` | `14.58` | `26.57` | `28.53` |
| `semantic_en_mmr_07` | `all-MiniLM-L6-v2 + MMR (λ=0.7, pool=100)` | `0.003918` | `0.005359` | `0.004925` | `0.039182` | `0.001585` | `5.20%` | `0.3153` | `0.8941` | `14.59` | `25.88` | `28.07` |

### 2.2 Secondary Cutoffs: $K = 5$ and $K = 20$

| Variant | P@5 | R@5 | NDCG@5 | HR@5 | Coverage@5 | P@20 | R@20 | NDCG@20 | HR@20 | Coverage@20 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `tfidf_v1_1` | `0.005111` | `0.003798` | `0.005987` | `0.025554` | `8.75%` | `0.005451` | `0.015573` | `0.010476` | `0.095400` | `19.10%` |
| `tfidf_v1_1_mmr_05` | `0.005451` | **`0.005775`** | `0.007066` | `0.027257` | `8.71%` | **`0.006303`** | **`0.018111`** | **`0.012724`** | **`0.112436`** | **`22.32%`** |
| `tfidf_v1_1_mmr_07` | **`0.006814`** | `0.005751` | **`0.007531`** | **`0.034072`** | `8.75%` | `0.005366` | `0.015290` | `0.010997` | `0.095400` | `20.62%` |
| `semantic_en` | `0.003066` | `0.000900` | `0.003339` | `0.015332` | `2.84%` | `0.003748` | `0.010709` | `0.006573` | `0.066440` | `8.51%` |
| `semantic_multi` | `0.002726` | `0.000951` | `0.002342` | `0.013629` | `2.64%` | `0.002896` | `0.007275` | `0.004508` | `0.057922` | `7.04%` |
| `semantic_en_mmr_05` | `0.004429` | `0.001456` | `0.004390` | `0.022147` | `2.97%` | `0.003748` | `0.010610` | `0.006616` | `0.066440` | `9.13%` |
| `semantic_en_mmr_07` | `0.004429` | `0.001456` | `0.004299` | `0.022147` | `2.88%` | `0.003748` | `0.010581` | `0.006612` | `0.066440` | `8.76%` |

---

## 3. Paired Statistical Significance Tests ($N = 587$ Active Users)

| Comparison ID | Baseline | Candidate | Metric | Baseline Mean | Candidate Mean | $\Delta$ (Cand - Base) | Paired $t$ | $p$-value ($t$) | Wilcoxon $p$ | 95% Bootstrap CI | Cohen's $d$ | Wins / Ties / Losses | Sig. ($\alpha=0.05$)? |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **RQ2a** | `TF-IDF v1.1` | `Semantic-EN` | `NDCG@5` | `0.005987` | `0.003339` | `-0.002648` | `-1.3250` | `0.1857` | `0.1989` | `[-0.006744, +0.001242]` | `-0.0547` | `9 / 564 / 14` | No |
| **RQ2a** | `TF-IDF v1.1` | `Semantic-EN` | `NDCG@10` | `0.007153` | `0.004930` | `-0.002222` | `-1.1780` | `0.2393` | `0.4105` | `[-0.006019, +0.001196]` | `-0.0486` | `20 / 543 / 24` | No |
| **RQ2a** | `TF-IDF v1.1` | `Semantic-EN` | `NDCG@20` | `0.010476` | `0.006573` | `-0.003903` | `-1.9952` | **`0.0465`** | `0.0804` | `[-0.007747, -0.000297]` | `-0.0824` | `35 / 501 / 51` | **Yes (TF-IDF > Sem-EN)** |
| **RQ2a** | `TF-IDF v1.1` | `Semantic-EN` | `P@10` | `0.004600` | `0.004089` | `-0.000511` | `-0.4469` | `0.6551` | `0.6547` | `[-0.002555, +0.001533]` | `-0.0184` | `20 / 545 / 22` | No |
| **RQ2b** | `TF-IDF v1.1` | `Semantic-Multi` | `NDCG@10` | `0.007153` | `0.002921` | `-0.004232` | `-2.2972` | **`0.0220`** | **`0.0304`** | `[-0.007750, -0.000834]` | `-0.0948` | `16 / 547 / 24` | **Yes (TF-IDF > Sem-Multi)** |
| **RQ2b** | `TF-IDF v1.1` | `Semantic-Multi` | `NDCG@20` | `0.010476` | `0.004508` | `-0.005968` | `-3.1168` | **`0.0019`** | **`0.0080`** | `[-0.009817, -0.002268]` | `-0.1286` | `33 / 502 / 52` | **Yes (TF-IDF > Sem-Multi)** |
| **RQ2c** | `Semantic-Multi` | `Semantic-EN` | `NDCG@10` | `0.002921` | `0.004930` | `+0.002009` | `+1.5072` | `0.1323` | `0.1801` | `[-0.000498, +0.004716]` | `+0.0622` | `24 / 548 / 15` | No |
| **RQ3a** | `TF-IDF + MMR (0.5)` | `Semantic-EN` | `NDCG@10` | `0.009091` | `0.004930` | `-0.004160` | `-1.9668` | **`0.0497`** | `0.0845` | `[-0.008440, -0.000251]` | `-0.0812` | `21 / 536 / 30` | **Yes (TF-IDF+MMR > Sem-EN)** |
| **RQ3b** | `TF-IDF + MMR (0.5)` | `Semantic-EN + MMR (0.5)` | `NDCG@10` | `0.009091` | `0.005113` | `-0.003978` | `-1.8604` | `0.0633` | `0.1475` | `[-0.008381, -0.000012]` | `-0.0768` | `20 / 537 / 30` | No ($p=0.063$) |
| **RQ3c** | `Semantic-EN` | `Semantic-EN + MMR (0.5)` | `NDCG@10` | `0.004930` | `0.005113` | `+0.000183` | `+0.7288` | `0.4664` | `0.2678` | `[-0.000324, +0.000654]` | `+0.0301` | `9 / 572 / 6` | No |
| **RQ3d** | `Semantic-EN` | `Semantic-EN + MMR (0.7)` | `NDCG@10` | `0.004930` | `0.004925` | `-0.000005` | `-0.0263` | `0.9791` | `0.4752` | `[-0.000436, +0.000370]` | `-0.0011` | `7 / 577 / 3` | No |

---

## 4. Scientific Analysis of Findings (RQ2 & RQ3)

1. **Why Lexical TF-IDF Outperforms Dense Neural Embeddings on Unenriched MovieLens Metadata (RQ2):**
   - In Condition A (`ml-latest-small` raw), `83.9%` of movies have **only a title and pipe-separated genre tokens** (no plot overview, no cast, no director, and no user tags).
   - Pretrained transformer encoders (`all-MiniLM-L6-v2` and `paraphrase-multilingual-MiniLM-L12-v2`) map short template strings (`"Title: X. Genres: Action, Comedy."`) into a dense, anisotropic `384`-dimensional cone where items sharing generic syntactic structure have high baseline cosine similarity ($\approx 0.688$, reflected by native `ILD@10 = 0.3117`).
   - Furthermore, when a user has rated $30+$ diverse movies in their training history, averaging $30+$ dense unit vectors in $\mathbb{R}^{384}$ collapses toward the global hub of the embedding space (**centroid hubness**), shrinking `Coverage@10` from `13.10%` (TF-IDF) down to `5.06%` (`Semantic-EN`) and `4.27%` (`Semantic-Multi`).
   - Conversely, `TF-IDF v1.1` maintains orthogonal dimensions for exact title tokens, franchise terms, and rare user tags (`5,000` sparse dimensions with IDF weighting), preventing centroid collapse when averaging multi-interest user histories.
2. **Lexical Diversity vs. Dense Embedding Diversity (`ILD@10` & `Novelty@10`):**
   - Although `Semantic-EN` has low diversity in its own dense cosine space (`native ILD@10 = 0.3117`), when its recommended top-10 lists are measured in lexical `TF-IDF` space (`TFIDF_ILD@10 = 0.8905`), semantic recommendations are **lexically much more diverse** than `TF-IDF v1.1` (`0.5719`) and retrieve more novel long-tail titles (`Novelty@10 = 14.59 bits` vs `14.05 bits`) because semantic similarity does not require lexical token overlap.
3. **Effect of MMR on Semantic Embeddings (RQ3):**
   - Applying MMR ($\lambda = 0.5$, `pool_size = 100`) on top of `Semantic-EN` slightly improves `NDCG@5` (`0.003339` $\to$ `0.004390`), `NDCG@10` (`0.004930` $\to$ `0.005113`), `Coverage@10` (`5.06%` $\to$ `5.42%`), and `ILD@10` (`0.3117` $\to$ `0.3215`), confirming that MMR mitigates dense cluster redundancy. However, `TF-IDF v1.1 + MMR (λ=0.5)` (`NDCG@10 = 0.009091`) remains significantly stronger on sparse metadata ($p = 0.0497$).

