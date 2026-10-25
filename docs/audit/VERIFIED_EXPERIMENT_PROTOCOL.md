# Verified Offline Recommendation Experiment Protocol

**Status:** Canonical & Audited  
**Applicability:** Phase 4 (Baseline), Phase 5 (TF-IDF v1.1 Ablation), and Phase 6+ (MMR, Hybrid, Embeddings)  
**Standard Checksums:**
- Raw ZIP: `696d65a3dfceac7c45750ad32df2c259311949efec81f0f144fdfb91ebc9e436`
- Combined Extracted CSVs: `d830d1e560efffd547d0360da5042a5d97884e5cd99dfd145ec9ecc0efbbaa86`
- Chronological Split: `48cc8f10cce949d0add60ad6320bf75668370d1753e5456d6fbd69479f931d67`

---

## 1. Dataset Specification

The evaluation harness uses **MovieLens `ml-latest-small`** (GroupLens Research, University of Minnesota).
- **Source URL:** `https://files.grouplens.org/datasets/movielens/ml-latest-small.zip`
- **Catalog Size:** 9,742 movies
- **Interaction Size:** 100,836 ratings, 3,683 user-applied tags
- **User Population:** 610 users
- **Database Isolation:** Strictly offline; never imported into application databases (`data/` is Git-ignored).

### Cryptographic Manifest

| File | Size (Bytes) | SHA-256 Checksum |
| :--- | :--- | :--- |
| `ml-latest-small.zip` | 978,202 | `696d65a3dfceac7c45750ad32df2c259311949efec81f0f144fdfb91ebc9e436` |
| `movies.csv` | 494,431 | `5a5f32dd9bb3797b8e728a1b98958789d2b13f294a69fdfbc5727f8a9611aa07` |
| `ratings.csv` | 2,483,723 | `aa289ca83157595d0df6aea1be6a4ded676ddc4385472e8313a8ed9805352646` |
| `tags.csv` | 118,660 | `92a9f8bb7916dceef6151209845788c3643f794dfa79d1feaec7121b5960399d` |
| `links.csv` | 197,979 | `97ad18e4e56a09363c65676b6cb3482ce3e2cea2372a24620c1599c843325f31` |
| `README.txt` | 8,342 | `63d22ac138e80fae37021797ed8e1b9424b5239dc576a137422adf783ae3f404` |

---

## 2. Chronological Split & Leakage Prevention Protocol

To faithfully simulate production recommendations, all user interactions are split chronologically per user:

1. **User Interaction Sorting:**
   - Primary Sort Key: Interaction `timestamp` ascending.
   - Secondary Sort Key (deterministic tie-breaker): `movie_id` ascending.
2. **Partition Ratios:**
   - **Training Set:** First 70% of user interactions ($N_{\text{train}} = \max(1, \lfloor 0.70 \times N_{\text{total}} \rfloor)$).
   - **Validation Set:** Next 15% of user interactions ($N_{\text{val}} = \lfloor 0.15 \times N_{\text{total}} \rfloor$).
   - **Test Set:** Final 15% of user interactions ($N_{\text{test}} = N_{\text{total}} - N_{\text{train}} - N_{\text{val}}$).
3. **Temporal Non-Leakage Enforcement:**
   $$\max(T_{\text{train}}) \le \min(T_{\text{val}}) \le \max(T_{\text{val}}) \le \min(T_{\text{test}})$$
   Asserted strictly for every individual user in `dataset.py`.
4. **Tag Leakage Prevention:**
   - User tags in MovieLens serve as keywords. To prevent future test interactions from leaking into movie content representations, the global training timestamp horizon is computed:
     $$T_{\text{train}}^{\max} = \max_{u \in \text{Users}} \left( \max_{r \in \text{Train}(u)} r.\text{timestamp} \right)$$
   - Only tags created at or before $T_{\text{train}}^{\max}$ are included in movie text profiles.

---

## 3. Metadata Adaptation Protocol

The production MovSug recommender builds item text from six fields:
$$\text{text} = \text{title} \times 2 + \text{overview} \times 1 + \text{genres} \times 1 + \text{cast} \times 1 + \text{keywords} \times 2 + \text{director} \times 1$$

MovieLens provides `title`, `genres`, and `tags` (keywords), but lacks `overview`, `cast`, and `director`. Following strict research integrity guidelines:
- Missing fields are **never fabricated**.
- Item representations use:
  $$\text{text} = \text{title} \times 2 + \text{genres} \times 1 + \text{tags} \times 2$$
- TF-IDF parameters remain fixed to production settings:
  - `max_features = 5000`
  - `ngram_range = (1, 2)`
  - `stop_words = "english"`
  - `norm = "l2"`, `use_idf = True`, `smooth_idf = True`, `sublinear_tf = False`

---

## 4. Candidate Pool & Seen-Item Exclusion Policy

- **Candidate Catalog:** All $9,742$ catalog movies are scored for every user.
- **Seen-Item Policies Tested:**
  - `exclude_seen = "none"`: Preserves Defect R1. Movies rated by the user in the training set are retained in the candidate pool.
  - `exclude_seen = "train"`: Implements Correctness Fix R1. All movies present in the user's chronological training set are strictly removed from candidate consideration.
  - *Integrity Rule:* Movies in the validation or test sets are never excluded based on future knowledge.

---

## 5. Evaluation Cohort & Ground Truth Relevance

- **Relevance Threshold:** A test interaction is considered positive/relevant if and only if:
  $$\text{rating} \ge 4.0$$
- **Cohort Breakdown:**
  - **Total Users Evaluated:** 610 users.
  - **Active Test Users ($N=587$):** Users with at least one test item rated $\ge 4.0$. Ranking metrics (Precision, Recall, NDCG, MAP, HitRate) are macro-averaged over these $587$ users.
  - **Zero-Positive Users ($N=23$):** Users whose test set contains no items rated $\ge 4.0$. (Their metrics are tracked in the all-users denominator in `metrics.json` to prevent denominator distortion).

---

## 6. Mathematical Metric Definitions

For user $u$ with Top-$K$ recommendations $\text{TopK}(u)$ and relevant test items $\text{Rel}(u) = \{ m \in \text{Test}(u) \mid \text{rating} \ge 4.0 \}$:

1. **Precision@K:**
   $$\text{Precision}@K(u) = \frac{|\text{TopK}(u) \cap \text{Rel}(u)|}{K}$$

2. **Recall@K:**
   $$\text{Recall}@K(u) = \frac{|\text{TopK}(u) \cap \text{Rel}(u)|}{|\text{Rel}(u)|}$$

3. **NDCG@K:**
   $$\text{DCG}@K(u) = \sum_{i=1}^K \frac{\mathbb{I}(\text{TopK}(u)[i] \in \text{Rel}(u))}{\log_2(i + 1)}, \quad \text{NDCG}@K(u) = \frac{\text{DCG}@K(u)}{\text{IDCG}@K(u)}$$

4. **HitRate@K:**
   $$\text{HitRate}@K(u) = \mathbb{I}(|\text{TopK}(u) \cap \text{Rel}(u)| > 0)$$

5. **Mean Average Precision (MAP@K):**
   $$\text{AP}@K(u) = \frac{1}{\min(K, |\text{Rel}(u)|)} \sum_{i=1}^K \mathbb{I}(\text{TopK}(u)[i] \in \text{Rel}(u)) \cdot \text{Precision}@i(u)$$

6. **Catalog Coverage@K:**
   $$\text{Coverage}@K = \frac{|\bigcup_{u \in \text{Cohort}} \text{TopK}(u)|}{|\text{Catalog}|} \quad (\text{Catalog} = 9742)$$

7. **Intra-List Diversity (ILD@K):**
   $$\text{ILD}@K(u) = \frac{2}{K(K-1)} \sum_{1 \le i < j \le K} (1 - \cos(\vec{m}_i, \vec{m}_j))$$

8. **Novelty@K (bits):**
   $$\text{Novelty}@K(u) = \frac{1}{K} \sum_{m \in \text{TopK}(u)} -\log_2(P(m)), \quad P(m) = \frac{\text{count}_{\text{train}}(m)}{N_{\text{total\_train}}}$$

---

## 7. Statistical Testing & Determinism

- **Paired Hypothesis Tests:** Evaluated on paired per-user metric vectors ($\Delta_u = M_{v1.1}(u) - M_{v1.0}(u)$).
  - Paired Student's t-test (`scipy.stats.ttest_rel`)
  - Wilcoxon signed-rank test (`scipy.stats.wilcoxon`)
- **Bootstrap Confidence Interval:**
  - $B = 1,000$ iterations with fixed seed (`seed = 42`).
  - Empirical percentile method at $\alpha = 0.05$ (95% CI).
- **Test-Set Non-Contamination:** No model hyperparameters were adjusted or tuned on the test set.
