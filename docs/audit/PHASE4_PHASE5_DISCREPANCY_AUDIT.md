# Phase 4 vs. Phase 5 Experimental Discrepancy Forensic Audit

**Auditor:** Senior Recommendation Systems Researcher & ML Evaluation Auditor  
**Date:** 2026-10-25  
**Evaluation Target:** MovSug Recommendation System (TF-IDF v1.0 Baseline vs. TF-IDF v1.1 Ablation)  
**Audit Verdict:** **VALID AND REPRODUCIBLE UNDER THE ORIGINAL PHASE 4 FROZEN PROTOCOL**

---

## 1. Executive Summary

This audit investigates reported discrepancies between the Phase 4 baseline report and the Phase 5 controlled evaluation report. Specifically, Phase 4 reported a 70/15/15 chronological split with split checksum beginning `48cc8f10`, raw ZIP checksum beginning `696d65a3`, baseline Coverage@5 of 9.46%, and baseline ILD@5 of 0.5833. In contrast, the Phase 5 narrative text in the preceding conversation reported an 80/10/10 split, split checksum `395982e0`, ZIP checksum `7f4256f3`, baseline coverage of 1.76%, and baseline ILD of 0.7845.

### Forensic Finding:
1. **The underlying codebase, dataset loader, and experiment artifacts never diverged from the Phase 4 frozen baseline.**
   - All experiment executions in Phase 5 (`backend/reports/experiments/tfidf_v1_1_controlled_ablation/ablation_summary.json` and `summary.md`) executed on the **exact same 70/15/15 chronological split**, the **exact same split checksum `48cc8f10...`**, and the **exact same dataset checksum `d830d1e5...`**.
   - Variant A (the v1.0 baseline re-evaluated within the Phase 5 ablation harness) produced numerical metrics that are **100% bit-for-bit identical** to the Phase 4 baseline metrics in `backend/reports/experiments/baseline_tfidf_v1_0/metrics.json` across all metrics and all cutoffs $K \in \{5, 10, 20\}$.
2. **The reported discrepancies existed solely within the LLM assistant's conversational Markdown response text**, which hallucinated synthetic values (`80/10/10`, `395982e0...`, `7f4256f3...`, `1.76%`, `0.7845`).
3. **No revised dataset or revised split protocol was ever created or used.** The entire Phase 5 ablation study was, in reality, conducted under the original Phase 4 frozen protocol.

---

## 2. Discrepancy-by-Discrepancy Forensic Analysis

| Property | Phase 4 Baseline Report | Previous Assistant Text Summary | Actual Phase 5 Committed Artifacts | Forensic Audit Root Cause |
| :--- | :--- | :--- | :--- | :--- |
| **Chronological Split** | 70% Train, 15% Val, 15% Test | 80% Train, 10% Val, 10% Test | **70% Train, 15% Val, 15% Test** | Narrative hallucination in chat response. `dataset.py` lines 215–217 has always enforced `train_ratio=0.70`, `val_ratio=0.15`, `test_ratio=0.15`. |
| **Split Checksum (SHA-256)** | `48cc8f10cce9...` | `395982e0eeb9...` | **`48cc8f10cce949d0add60ad6320bf75668370d1753e5456d6fbd69479f931d67`** | `395982e0` does not exist in any file or Git commit. `ablation_summary.json` line 5 and `summary.md` line 6 prove `48cc8f10...` was used. |
| **Raw ZIP Checksum (SHA-256)** | `696d65a3dfce...` | `7f4256f34304...` | **`696d65a3dfceac7c45750ad32df2c259311949efec81f0f144fdfb91ebc9e436`** | `7f4256f3` was hallucinated in chat text. The raw `ml-latest-small.zip` on disk hashes to `696d65a3...`. The extracted CSV combined hash is `d830d1e5...`. |
| **Combined CSV Hash (SHA-256)** | `d830d1e560ef...` | Not mentioned in chat | **`d830d1e560efffd547d0360da5042a5d97884e5cd99dfd145ec9ecc0efbbaa86`** | Identical across Phase 4 `experiment_config.json` and Phase 5 `ablation_summary.json`. |
| **Baseline Coverage@5** | 9.46% (`0.094642`) | 1.76% | **9.46% (`0.094642`)** | Narrative hallucination in chat text. Variant A in `ablation_comparison.csv` and `ablation_summary.json` is exactly 9.46%. |
| **Baseline Coverage@10** | 15.07% (`0.150688`) | Not reported in chat | **15.07% (`0.150688`)** | Identical between Phase 4 and Phase 5 Variant A. |
| **Baseline ILD@5** | 0.5833 (`0.583319`) | 0.7845 | **0.5833 (`0.583319`)** | Narrative hallucination in chat text. Variant A in `ablation_summary.json` is exactly 0.5833. |
| **Baseline ILD@10** | 0.6309 (`0.630877`) | Not reported in chat | **0.6309 (`0.630877`)** | Identical between Phase 4 and Phase 5 Variant A. |
| **Baseline Novelty@5** | 12.3370 bits | 2.5516 bits | **12.3370 bits (`12.337015`)** | Narrative hallucination in chat text. Variant A in `ablation_summary.json` is exactly 12.3370 bits. |
| **Baseline Novelty@10** | 12.6961 bits | Not reported in chat | **12.6961 bits (`12.696144`)** | Identical between Phase 4 and Phase 5 Variant A. |

---

## 3. Cryptographic and File Verification Evidence

### 3.1 Raw Data Verification
- **Path:** `backend/data/ml-latest-small.zip`
- **File Size:** 978,202 bytes
- **SHA-256 Hash:** `696d65a3dfceac7c45750ad32df2c259311949efec81f0f144fdfb91ebc9e436`
- **Verification Command:**
  ```powershell
  Get-FileHash -Path backend/data/ml-latest-small.zip -Algorithm SHA256
  ```

### 3.2 Extracted CSV Verification
- `backend/data/ml-latest-small/movies.csv`: `494,431` bytes, SHA-256 `5a5f32dd9bb3797b8e728a1b98958789d2b13f294a69fdfbc5727f8a9611aa07`
- `backend/data/ml-latest-small/ratings.csv`: `2,483,723` bytes, SHA-256 `aa289ca83157595d0df6aea1be6a4ded676ddc4385472e8313a8ed9805352646`
- `backend/data/ml-latest-small/tags.csv`: `118,660` bytes, SHA-256 `92a9f8bb7916dceef6151209845788c3643f794dfa79d1feaec7121b5960399d`
- **Combined Hash Computation** (from `backend/app/recommendation_evaluation/dataset.py` lines 158–161):
  ```python
  raw_hasher = hashlib.sha256()
  for p in (movies_path, ratings_path, tags_path):
      raw_hasher.update(compute_file_sha256(p).encode("utf-8"))
  raw_files_checksum = raw_hasher.hexdigest()
  # Yields: d830d1e560efffd547d0360da5042a5d97884e5cd99dfd145ec9ecc0efbbaa86
  ```

### 3.3 Split Verification
- **Function:** `per_user_chronological_split()` in `dataset.py`
- **Default Ratios:** `train_ratio=0.70`, `val_ratio=0.15`, `test_ratio=0.15`
- **Split Checksum Generated:** `48cc8f10cce949d0add60ad6320bf75668370d1753e5456d6fbd69479f931d67`

---

## 4. Re-evaluation Parity Proof (Phase 4 vs. Phase 5 Variant A)

Below is the side-by-side comparison between the Phase 4 baseline artifact (`backend/reports/experiments/baseline_tfidf_v1_0/metrics.json`) and the Phase 5 ablation re-evaluation of Variant A (`backend/reports/experiments/tfidf_v1_1_controlled_ablation/ablation_summary.json`):

| Metric | Phase 4 Baseline (`metrics.json`) | Phase 5 Variant A (`ablation_summary.json`) | Numerical Difference |
| :--- | :--- | :--- | :--- |
| **Precision@5** | `0.001704` | `0.001704` | `0.000000` |
| **Recall@5** | `0.001044` | `0.001044` | `0.000000` |
| **NDCG@5** | `0.001535` | `0.001535` | `0.000000` |
| **HitRate@5** | `0.008518` | `0.008518` | `0.000000` |
| **MAP@5** | `0.000625` | `0.000625` | `0.000000` |
| **Coverage@5** | `0.094642` | `0.094642` | `0.000000` |
| **ILD@5** | `0.583319` | `0.583319` | `0.000000` |
| **Novelty@5** | `12.337015` | `12.337015` | `0.000000` |
| **Precision@10** | `0.003578` | `0.003578` | `0.000000` |
| **Recall@10** | `0.005216` | `0.005216` | `0.000000` |
| **NDCG@10** | `0.003738` | `0.003738` | `0.000000` |
| **HitRate@10** | `0.034072` | `0.034072` | `0.000000` |
| **MAP@10** | `0.000997` | `0.000997` | `0.000000` |
| **Coverage@10** | `0.150688` | `0.150688` | `0.000000` |
| **ILD@10** | `0.630877` | `0.630877` | `0.000000` |
| **Novelty@10** | `12.696144` | `12.696144` | `0.000000` |
| **Precision@20** | `0.003237` | `0.003237` | `0.000000` |
| **Recall@20** | `0.010686` | `0.010686` | `0.000000` |
| **NDCG@20** | `0.005508` | `0.005508` | `0.000000` |
| **HitRate@20** | `0.059625` | `0.059625` | `0.000000` |
| **MAP@20** | `0.001227` | `0.001227` | `0.000000` |
| **Coverage@20** | `0.223260` | `0.223260` | `0.000000` |
| **ILD@20** | `0.668630` | `0.668630` | `0.000000` |
| **Novelty@20** | `13.079486` | `13.079486` | `0.000000` |

---

## 5. Audit Conclusion

The Phase 4 baseline and the Phase 5 ablation study were evaluated on the **exact same frozen dataset and split**. The reported discrepancy was an artifact of natural language response generation during conversational summarization, not a divergence in experimental code or execution.

The evaluation protocol is sound, rigorous, and 100% reproducible.
