# MovSug Phase 8B — Embedding Model Selection Report

**Date:** 2026-11-04  
**Phase:** Phase 8B — Semantic Embeddings, Metadata Quality Experiments, and TEC Evaluation  
**Implementation Module:** [embeddings.py](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/embeddings.py)

---

## 1. Selection Criteria & Hardware Constraints

MovSug runs locally on developer and evaluation machines without requiring dedicated CUDA GPUs or paid external embedding APIs. Furthermore, the recommendation evaluation harness must be 100% deterministic, offline-capable once model weights are cached, and compatible with Python 3.14 on Windows x64.

Accordingly, candidate sentence-embedding models were evaluated against six engineering and research criteria:

1. **Pretrained Neural Quality:** Strong zero-shot semantic similarity performance on MTEB / STS benchmarks for short-to-medium movie descriptions (`64–256` tokens).
2. **CPU Inference Throughput:** Ability to encode the full `9,742`-movie MovieLens `ml-latest-small` catalog on CPU in under `60` seconds and compute online user-profile cosine rankings in `<15 ms` p95.
3. **Python 3.14 & ONNX Runtime Compatibility:** Native support via `onnxruntime==1.31.1` (`CPUExecutionProvider`) and `tokenizers==0.23.3` without requiring heavy PyTorch CUDA distributions.
4. **Multilingual Coverage (English + Vietnamese):** Because Phase 8A TMDB enrichment populates both English (`title`, `overview`, `keywords`, `cast`, `director`) and Vietnamese (`title_vi`, `overview_vi`) metadata, we must evaluate both an English-specialized model and a multilingual model supporting Vietnamese.
5. **Compact Vector Footprint:** `384`-dimensional `float32` vectors (`~14.25 MB` compressed `.npz` for `9,742` movies) to keep memory overhead below `60 MB`.
6. **Permissive Open-Source License:** Apache-2.0 licensing suitable for academic thesis and production deployment.

---

## 2. Candidate Models Evaluated

| Model Key | HuggingFace Model ID | Pinned Revision (Commit SHA) | ONNX File | Dim | Max Seq Length | Language Policy | License | Status |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `english_minilm` | `sentence-transformers/all-MiniLM-L6-v2` | `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` | `onnx/model.onnx` | `384` | `256` | `en_only` | Apache-2.0 | **Selected (Primary English)** |
| `multilingual_minilm` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | `e8f8c211226b894fcb81acc59f3b34ba3efd5f42` | `onnx/model_quint8_avx2.onnx` | `384` | `128` | `multilingual` | Apache-2.0 | **Selected (Multilingual EN+VI)** |
| `bge_small_en` | `BAAI/bge-small-en-v1.5` | Evaluated | `onnx/model.onnx` | `384` | `512` | `en_only` | MIT | Deferred (slower CPU latency at 512 tokens; similar 384-d capacity) |
| `e5_multilingual_small` | `intfloat/multilingual-e5-small` | Evaluated | `onnx/model.onnx` | `384` | `512` | `multilingual` | MIT | Deferred (requires asymmetric `query:` / `passage:` prefixes; items are symmetric in user-centroid recommendation) |
| `deterministic_test` | `movsug/deterministic-hash-projection-384` | `v1.0.0-offline-test` | Built-in NumPy | `384` | `256` | `multilingual` | MIT | **Selected (Offline Unit Test Fixture Only)** |

---

## 3. Detailed Specification of Selected Models

### 3.1 Primary English Model: `sentence-transformers/all-MiniLM-L6-v2`
- **Pinned Revision:** `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`
- **Architecture:** 6-layer MiniLM distilled from RoBERTa/BERT, trained on over 1 billion sentence pairs with contrastive learning.
- **Pooling & Normalization:** Attention-mask weighted mean pooling over `last_hidden_state` (`[batch, seq_len, 384]`), followed by strict L2 unit-norm normalization ($\|\mathbf{v}\|_2 = 1.0$).
- **Max Sequence Length:** `256` wordpiece tokens (sufficient to cover title, genres, director, top-5 cast, keywords, and full English synopsis).
- **Language Policy:** `en_only` — excludes `title_vi` and `overview_vi` so Vietnamese tokens are not fragmented into out-of-distribution English subwords.
- **Measured CPU Performance on `ml-latest-small` (`9,742` movies):**
  - Batch generation time (`batch_size=128`): `29.99 seconds` (`324.8 movies/sec`)
  - Compressed `.npz` cache size: `14.26 MB`
  - Cache load time: `108.62 ms`
  - Peak memory footprint: `49.73 MB`
  - Online recommendation latency: `p50 = 8.52 ms`, `p95 = 10.23 ms`

### 3.2 Multilingual Model (English + Vietnamese): `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- **Pinned Revision:** `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`
- **Architecture:** 12-layer multilingual MiniLM supporting 50+ languages including English and Vietnamese, using SentencePiece unigram tokenization (`tokenizer.json`) and AVX2 dynamic quantized ONNX weights (`onnx/model_quint8_avx2.onnx`).
- **Pooling & Normalization:** Attention-mask weighted mean pooling over `last_hidden_state`, followed by strict L2 normalization.
- **Max Sequence Length:** `128` tokens.
- **Language Policy:** `multilingual` — encodes both English (`original_title`, `title`, `genres`, `keywords`, `overview`, `cast`, `director`) and Vietnamese (`title_vi`, `overview_vi`) fields into a shared 384-dimensional cross-lingual vector space.
- **Measured CPU Performance on `ml-latest-small` (`9,742` movies):**
  - Batch generation time (`batch_size=128`): `58.86 seconds` (`165.5 movies/sec`)
  - Compressed `.npz` cache size: `14.25 MB`
  - Cache load time: `134.71 ms`
  - Peak memory footprint: `52.05 MB`
  - Online recommendation latency: `p50 = 8.91 ms`, `p95 = 10.71 ms`

### 3.3 Offline Unit-Test Encoder: `movsug/deterministic-hash-projection-384`
- **Purpose:** Used **exclusively** in automated unit and CI tests ([test_semantic_recommendations.py](file:///d:/TLTN/movie-recommendation-system/backend/tests/test_semantic_recommendations.py)) so `pytest` runs 100% offline in `<2 seconds` without network access or neural weight downloads.
- **Strict Separation:** Flagged with `is_pretrained_neural = False` in [`EmbeddingModelSpec`](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/embeddings.py#L44-L57); never used for research evaluation claims in Phase 8B reports.

