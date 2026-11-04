# MovSug Phase 8B — Operational Cost, Latency & Memory Benchmark Report (RQ4)

**Date:** 2026-11-04  
**Phase:** Phase 8B — Semantic Embeddings, Metadata Quality Experiments, and TEC Evaluation  
**Source Artifacts:**
- [phase8b_performance_benchmark.json](file:///d:/TLTN/movie-recommendation-system/backend/reports/phase8b_embeddings/phase8b_performance_benchmark.json)
- [embedding_cache.py](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/embedding_cache.py)
- [semantic_engine.py](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/semantic_engine.py)

---

## 1. Test Hardware & Runtime Environment

- **OS / Platform:** Windows 11 (`Windows-11-10.0.26200-SP0`, `AMD64`)
- **Processor:** Intel64 Family 6 Model 186 Stepping 2 (`CPUExecutionProvider` only; no GPU acceleration required)
- **Python Runtime:** Python `3.14.3` (`MSC v.1944 64 bit`)
- **Inference Engine:** `onnxruntime==1.31.1`, `tokenizers==0.23.3`, `numpy==2.5.1`, `scikit-learn==1.9.0`
- **Catalog Size:** `9,742` MovieLens movies (`ml-latest-small`), `587` active test users (`610` total users)

---

## 2. End-to-End Resource & Latency Comparison (RQ4)

| Algorithm / Model | Vector Representation | Dim | Batch Fit / Generation Time (s) | Cache Load Time (ms) | Storage Footprint (MB) | Peak Memory Footprint (MB) | Online p50 Latency (ms) | Online p95 Latency (ms) | Online Mean Latency (ms) | Cold-Start Latency (ms) | Missing Vector Rate | Fallback Rate |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `TF-IDF v1.1 (no MMR)` | Sparse CSR (`float64`) | `5,000` | **`0.4839 s`** (`1.0×`) | `483.89 ms` | **`0.94 MB`** (`1.0×`) | **`0.94 MB`** (`1.0×`) | **`5.74 ms`** | **`8.93 ms`** | **`6.22 ms`** | `0.004 ms` | `0.0%` | `0.0%` |
| `TF-IDF v1.1 + MMR (λ=0.5, pool=100)` | Sparse CSR (`float64`) | `5,000` | `0.4792 s` (`1.0×`) | `479.24 ms` | `0.94 MB` (`1.0×`) | `0.94 MB` (`1.0×`) | `34.07 ms` | `37.60 ms` | `34.60 ms` | `0.006 ms` | `0.0%` | `0.0%` |
| `Semantic-EN (all-MiniLM-L6-v2)` | Dense `float32` (`.npz`) | `384` | `29.9943 s` (`62.0×`) | **`108.62 ms`** | `14.26 MB` (`15.2×`) | `49.73 MB` (`53.1×`) | `8.52 ms` | `10.23 ms` | `8.69 ms` | `0.006 ms` | `0.0%` | `0.0%` |
| `Semantic-Multi (L12-v2)` | Dense `float32` (`.npz`) | `384` | `58.8596 s` (`121.6×`) | `134.71 ms` | `14.25 MB` (`15.2×`) | `52.05 MB` (`55.6×`) | `8.91 ms` | `10.71 ms` | `9.06 ms` | `0.007 ms` | `0.0%` | `0.0%` |
| `Semantic-EN + MMR (λ=0.5, pool=100)` | Dense `float32` (`.npz`) | `384` | `29.9943 s` (`62.0×`) | `108.62 ms` | `14.26 MB` (`15.2×`) | `49.73 MB` (`53.1×`) | `26.57 ms` | `28.53 ms` | `26.72 ms` | `0.006 ms` | `0.0%` | `0.0%` |

---

## 3. Systems Engineering Observations

1. **Offline Batch Precomputation Is Mandatory for Neural Embeddings:**
   - Encoding `9,742` movies on CPU takes `29.99 s` for 6-layer `all-MiniLM-L6-v2` and `58.86 s` for 12-layer `paraphrase-multilingual-MiniLM-L12-v2` (`62×` to `121.6×` slower than `TfidfVectorizer.fit_transform` at `0.48 s`).
   - Consequently, neural embeddings **must never be computed synchronously inside an HTTP request path**. Instead, MovSug precomputes and persists versioned `.npz` + `_manifest.json` artifacts via [`save_embedding_artifact`](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/embedding_cache.py#L96-L157).
2. **Fast Disk Cache Loading (`~109 ms`) and Sub-11ms Online Scoring:**
   - Once persisted to `.npz`, loading and SHA-256-verifying the `9,742 × 384` `float32` matrix takes only `108.62 ms` (faster than fitting TF-IDF from scratch at `483.89 ms`).
   - Online recommendation latency for `Semantic-EN` (`p50 = 8.52 ms`, `p95 = 10.23 ms`) is well within interactive SLA budgets (`<50 ms`), and `Semantic-EN + MMR (λ=0.5, pool=100)` (`p50 = 26.57 ms`) is actually **faster** than `TF-IDF + MMR (λ=0.5, pool=100)` (`p50 = 34.07 ms`) because pairwise cosine similarity over a `100 × 384` dense `float32` submatrix is more cache-friendly than over a `100 × 5,000` sparse CSR matrix.
3. **Cache Scope & Production Fallback Safety:**
   - Both the TF-IDF cache ([vectorizer.py](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/vectorizer.py)) and the semantic embedding runtime cache ([embedding_cache.py](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/embedding_cache.py)) are **single-process in-memory caches** synchronized via [`invalidate_cache()`](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/vectorizer.py#L140-L149).
   - If `RECOMMENDATION_STRATEGY` is set to `semantic_en` or `semantic_multi` and the `.npz` artifact is missing, corrupted, or stale (`metadata_version` mismatch), [`get_recommendations`](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/engine.py#L118-L210) automatically falls back to `tfidf_v1_1`, increments the observable fallback counter (`get_embedding_cache_stats()`), and logs a warning without raising an HTTP 500 error.
