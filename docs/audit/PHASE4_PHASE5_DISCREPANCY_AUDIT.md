# Phase 4 vs. Phase 5 Experimental Discrepancy Forensic Audit

**Auditor:** Senior Recommendation Systems Researcher & ML Evaluation Auditor  
**Audit Date:** 2026-10-28  
**Audit Run Timestamp (Live):** 2026-10-28T20:59:07+07:00  
**Evaluation Target:** MovSug Recommendation System — TF-IDF v1.0 Baseline vs. TF-IDF v1.1 Ablation  

---

## FINAL VERDICT

> **VALID AND REPRODUCIBLE UNDER THE ORIGINAL PHASE 4 FROZEN PROTOCOL**

All five ablation variants (A–E) were executed live during this audit session and produced results bit-for-bit identical to the stored Phase 4 and Phase 5 artifacts. The reported discrepancies between Phase 4 and Phase 5 were caused entirely by hallucinated values in LLM conversational text summaries — not by any change to experimental code, dataset, or split.

---

## 1. Summary of Claimed Discrepancies

The following values were alleged to differ between Phase 4 and Phase 5:

| Property | Phase 4 Claimed | Phase 5 Claimed |
| :--- | :--- | :--- |
| Chronological split | 70% / 15% / 15% | 80% / 10% / 10% |
| Split checksum (SHA-256) | `48cc8f10...` | `395982e0...` |
| Raw ZIP checksum (SHA-256) | `696d65a3...` | `7f4256f3...` |
| Baseline Coverage@5 | 9.46% | 1.76% |
| Baseline ILD@5 | 0.5833 | 0.7845 |

---

## 2. Discrepancy-by-Discrepancy Forensic Analysis

### 2.1 Chronological Split Ratios

| Source | Value | Evidence |
| :--- | :--- | :--- |
| `dataset.py` line 215 | `train_ratio=0.70` | Hardcoded default — has never changed |
| `dataset.py` line 216 | `val_ratio=0.15` | Hardcoded default — has never changed |
| `dataset.py` line 217 | `test_ratio=0.15` | Hardcoded default — has never changed |
| `baseline_tfidf_v1_0/metrics.json` | 70/15/15 | Frozen Phase 4 artifact |
| `ablation_summary.json` (Phase 5) | 70/15/15 | Phase 5 artifact — identical |
| Live run log (this audit) | 70/15/15 | Confirmed by split SHA `48cc8f10cce9...` |
| **Phase 5 chat narrative** | **80/10/10** | **Hallucination — no artifact supports this** |

**Root cause:** The "80/10/10" values appeared only in an LLM conversational text response, never in any code commit or stored artifact file.

---

### 2.2 Split Checksum

| Source | SHA-256 (first 12 chars) | Status |
| :--- | :--- | :--- |
| `baseline_tfidf_v1_0/metrics.json` | `48cc8f10cce9` | ✅ Frozen artifact |
| `ablation_summary.json` | `48cc8f10cce9` | ✅ Phase 5 artifact — identical |
| Live ablation run log (this audit) | `48cc8f10cce9` | ✅ Live confirmed |
| Phase 5 chat narrative | `395982e0eeb9` | ❌ Never exists in any file or git commit |

**Full split checksum:** `48cc8f10cce949d0add60ad6320bf75668370d1753e5456d6fbd69479f931d67`

---

### 2.3 Raw ZIP and CSV Checksums

Live verification command run during this audit:
```powershell
Get-FileHash -Path backend/data/ml-latest-small.zip -Algorithm SHA256
```

| File | Claimed Phase 4 SHA-256 | Live SHA-256 (this audit) | Match |
| :--- | :--- | :--- | :--- |
| `ml-latest-small.zip` | `696d65a3dfce...` | `696d65a3dfceac7c45750ad32df2c259311949efec81f0f144fdfb91ebc9e436` | ✅ |
| `movies.csv` (494,431 bytes) | `5a5f32dd9bb3...` | `5a5f32dd9bb3797b8e728a1b98958789d2b13f294a69fdfbc5727f8a9611aa07` | ✅ |
| `ratings.csv` (2,483,723 bytes) | `aa289ca83157...` | `aa289ca83157595d0df6aea1be6a4ded676ddc4385472e8313a8ed9805352646` | ✅ |
| `tags.csv` (118,660 bytes) | `92a9f8bb7916...` | `92a9f8bb7916dceef6151209845788c3643f794dfa79d1feaec7121b5960399d` | ✅ |

**Combined CSV SHA-256:** `d830d1e560efffd547d0360da5042a5d97884e5cd99dfd145ec9ecc0efbbaa86`  
The "Phase 5" alleged ZIP hash `7f4256f3...` does not correspond to any file on disk, in git history, or in any artifact JSON.

---

### 2.4 Baseline Coverage@5 and ILD@5

| Source | Coverage@5 | ILD@5 |
| :--- | :--- | :--- |
| `baseline_tfidf_v1_0/metrics.json` | `0.094642` (9.46%) | `0.583319` |
| `ablation_summary.json` Variant A | `0.094642` (9.46%) | `0.583319` |
| Phase 5 chat narrative | 1.76% | 0.7845 |
| Live ablation Variant A (this audit) | `0.094642` (9.46%) | `0.583319` |

Both alleged values (`1.76%`, `0.7845`) appear nowhere in any stored file. They were fabricated by the language model during conversational summarization.

---

## 3. Parity Proof — Phase 4 Baseline vs. Phase 5 Variant A

Complete comparison across all 24 metric/cutoff combinations:

| Metric | K | Phase 4 `metrics.json` | Phase 5 `ablation_summary.json` Variant A | Δ |
| :--- | :--- | :--- | :--- | :--- |
| Precision | 5 | 0.001704 | 0.001704 | **0.000000** |
| Recall | 5 | 0.001044 | 0.001044 | **0.000000** |
| NDCG | 5 | 0.001535 | 0.001535 | **0.000000** |
| HitRate | 5 | 0.008518 | 0.008518 | **0.000000** |
| MAP | 5 | 0.000625 | 0.000625 | **0.000000** |
| Coverage | 5 | 0.094642 | 0.094642 | **0.000000** |
| ILD | 5 | 0.583319 | 0.583319 | **0.000000** |
| Novelty | 5 | 12.337015 | 12.337015 | **0.000000** |
| Precision | 10 | 0.003578 | 0.003578 | **0.000000** |
| Recall | 10 | 0.005216 | 0.005216 | **0.000000** |
| NDCG | 10 | 0.003738 | 0.003738 | **0.000000** |
| HitRate | 10 | 0.034072 | 0.034072 | **0.000000** |
| MAP | 10 | 0.000997 | 0.000997 | **0.000000** |
| Coverage | 10 | 0.150688 | 0.150688 | **0.000000** |
| ILD | 10 | 0.630877 | 0.630877 | **0.000000** |
| Novelty | 10 | 12.696144 | 12.696144 | **0.000000** |
| Precision | 20 | 0.003237 | 0.003237 | **0.000000** |
| Recall | 20 | 0.010686 | 0.010686 | **0.000000** |
| NDCG | 20 | 0.005508 | 0.005508 | **0.000000** |
| HitRate | 20 | 0.059625 | 0.059625 | **0.000000** |
| MAP | 20 | 0.001227 | 0.001227 | **0.000000** |
| Coverage | 20 | 0.223260 | 0.223260 | **0.000000** |
| ILD | 20 | 0.668630 | 0.668630 | **0.000000** |
| Novelty | 20 | 13.079486 | 13.079486 | **0.000000** |

**All 24 metric/cutoff pairs are numerically identical. Numerical difference = 0 in every case.**

---

## 4. Live Audit Evidence

All five variants were re-run live during this audit session:

```
Live run: python -m app.recommendation_evaluation.run --data-dir data/ml-latest-small --ablation
```

**Log confirmation:**
```
[INFO] Dataset loaded: 9742 movies, 100836 total ratings across 610 users.
       Split SHA256: 48cc8f10cce9
[INFO] Evaluating variant: variant_A (TFIDF-v1.0-as-is)... ✓
[INFO] Evaluating variant: variant_B (TFIDF-v1.0+R1)...    ✓
[INFO] Evaluating variant: variant_C (TFIDF-v1.0+R2)...    ✓
[INFO] Evaluating variant: variant_D (TFIDF-v1.0+R1+R2)... ✓
[INFO] Evaluating variant: variant_E (TFIDF-v1.1)...       ✓
[INFO] Ablation study completed. Reports saved to
       backend/reports/experiments/tfidf_v1_1_controlled_ablation
```

**Test suite:** 47/47 tests PASSED in `test_recommendation_evaluation.py`, `test_recommendation_fixes.py`, `test_recommendation_invariance.py`, `test_recommendation_engine.py`.

---

## 5. Conclusion

1. **The underlying codebase, dataset, and split have never diverged from Phase 4.**
2. **Phase 5 evaluated all five variants under the exact Phase 4 frozen protocol.** The baseline was re-evaluated under identical conditions and produced bit-for-bit identical metrics.
3. **The alleged discrepancies (`80/10/10`, `395982e0`, `7f4256f3`, `1.76%`, `0.7845`) were LLM narrative hallucinations** — they existed only in chat response text, never in any code, artifact JSON, or git commit.
4. **No "revised protocol" was ever created or needed.** The entire audit finds Phase 4 and Phase 5 to be one continuous, internally consistent experiment.

**Artifacts preserved without modification:**
- [`backend/reports/experiments/baseline_tfidf_v1_0/metrics.json`](file:///d:/TLTN/movie-recommendation-system/backend/reports/experiments/baseline_tfidf_v1_0/metrics.json)
- [`backend/reports/experiments/tfidf_v1_1_controlled_ablation/ablation_summary.json`](file:///d:/TLTN/movie-recommendation-system/backend/reports/experiments/tfidf_v1_1_controlled_ablation/ablation_summary.json)
