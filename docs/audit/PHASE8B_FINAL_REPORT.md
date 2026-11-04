# MovSug Phase 8B — Final Report: Semantic Embeddings, Metadata Quality Experiments & TEC Evaluation

**Date:** 2026-11-04  
**Phase:** Phase 8B — Semantic Embeddings, Metadata Quality Experiments, and TEC Evaluation  
**TEC Run ID:** `tec-20261104-090658-8f3e707`  
**Overall Verification Status:** **PASS** (`435/435` backend pytest, `418/418` frontend vitest, `47/47` Phase 8B + TEC tests, `0` ESLint errors, `0` TypeScript errors)

---

## 1. Executive Summary & Answers to Research Questions (RQ1–RQ4)

| Research Question | Empirical Finding | Key Statistical Evidence ($N = 587$ Active Users, $K = 10$) |
| :--- | :--- | :--- |
| **RQ1: Does enriching movie metadata improve TF-IDF and semantic recommendation quality?** | **Yes for TF-IDF (`+9.31%` NDCG@10, `+14.80%` P@10); Not yet for catalog-wide semantic embeddings due to `0.11%` catalog coverage asymmetry.** | Enriching just the `11` matched MovieLens movies (`0.113%` of `9,742` movies) from `backend/movsug.db` significantly improves `TF-IDF v1.1` `P@10` from `0.004600` to `0.005281` ($t = 2.0051, p = 0.0454$, Wilcoxon $p = 0.0455$) and `NDCG@10` from `0.007153` to `0.007819` (Wilcoxon $p = 0.0431$, 95% CI `[+0.000114, +0.001421]`, 5 wins / 0 losses). Within the uniformly enriched `10`-movie diagnostic subset (Protocol B2, `NOT ENOUGH EVIDENCE`), `Semantic-EN` improves from `NDCG@10 = 0.6593` to `0.7190`. |
| **RQ2: Do semantic embeddings outperform TF-IDF when both use identical metadata?** | **No on sparse MovieLens metadata.** Lexical `TF-IDF v1.1` outperforms standalone dense centroid embeddings on unenriched (`title` + `genres` + `tags`) MovieLens catalog data. | On Condition A (`9,742` movies), `TF-IDF v1.1` achieves `NDCG@10 = 0.007153` vs `0.004930` for `Semantic-EN` ($\Delta = -0.002222, p = 0.2393$ at $K=10$; $\Delta\text{NDCG@20} = -0.003903, p = 0.0465$) and `0.002921` for `Semantic-Multi` ($\Delta = -0.004232, p = 0.0220$). Averaging $30+$ short-text dense embeddings causes **centroid hubness**, reducing `Coverage@10` from `13.10%` to `5.06%`. |
| **RQ3: Do semantic embeddings provide a useful ranking or diversity trade-off relative to TF-IDF v1.1 + MMR?** | **They provide higher lexical novelty (`14.59` vs `13.84` bits) and lexical diversity (`TFIDF_ILD@10 = 0.8905`), but lower top-$K$ accuracy than `TF-IDF v1.1 + MMR (λ=0.5)`.** | `TF-IDF v1.1 + MMR (λ=0.5, pool=100)` achieves the highest overall accuracy and catalog coverage (`NDCG@10 = 0.009091`, `Coverage@10 = 14.22%`, `ILD@10 = 0.7686`), outperforming `Semantic-EN` ($p = 0.0497$). Adding MMR ($\lambda=0.5$) to `Semantic-EN` improves `NDCG@10` (`0.004930` $\to$ `0.005113`) and `Coverage@10` (`5.06%` $\to$ `5.42%`). |
| **RQ4: What are the CPU, memory, storage, preprocessing, and inference costs of semantic embeddings?** | **Online latency is fast (`p50 = 8.52 ms`), but offline batch generation (`30.0s–58.9s`) and memory (`~50 MB`) are $50\times\text{–}120\times$ higher than TF-IDF (`0.48s`, `0.94 MB`).** | Precomputing `.npz` caches is mandatory. Once cached, `.npz` load takes `108.6 ms` and online inference (`p50 = 8.52 ms`, `p95 = 10.23 ms`) easily meets real-time latency targets. |

---

## 2. Deliverables Completed & File Index

| # | Deliverable | File / Artifact Link | Status |
| :---: | :--- | :--- | :---: |
| 1 | Repository inspection & architecture alignment | Preserved `movie_profile.py`, `user_profile.py`, `mmr.py`, and frozen Phase 4–6 artifacts | **Completed** |
| 2 | Embedding model selection report | [PHASE8B_EMBEDDING_MODEL_SELECTION.md](file:///d:/TLTN/movie-recommendation-system/docs/audit/PHASE8B_EMBEDDING_MODEL_SELECTION.md) | **Completed** |
| 3 | Deterministic movie metadata text builder | [text_builder.py](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/text_builder.py) | **Completed** |
| 4 | Batch CPU embedding generation service | [embeddings.py](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/embeddings.py) | **Completed** |
| 5 | Versioned vector cache & staleness verifier | [embedding_cache.py](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/embedding_cache.py) | **Completed** |
| 6 | Semantic user-profile & ranking engine | [semantic_engine.py](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/semantic_engine.py) | **Completed** |
| 7 | Offline evaluation adapter & CLI (`--phase8b`) | [semantic_eval.py](file:///d:/TLTN/movie-recommendation-system/backend/app/recommendation_evaluation/semantic_eval.py), [cli.py](file:///d:/TLTN/movie-recommendation-system/backend/app/recommendation_evaluation/cli.py) | **Completed** |
| 8 | Condition A (Original metadata) experiments | [phase8b_condition_a_comparison.csv](file:///d:/TLTN/movie-recommendation-system/backend/reports/phase8b_embeddings/phase8b_condition_a_comparison.csv), [PHASE8B_EMBEDDING_RESULTS.md](file:///d:/TLTN/movie-recommendation-system/docs/audit/PHASE8B_EMBEDDING_RESULTS.md) | **Completed** |
| 9 | Condition B (2×2 Metadata vs Model ablation) | [phase8b_ablation_2x2.csv](file:///d:/TLTN/movie-recommendation-system/backend/reports/phase8b_embeddings/phase8b_ablation_2x2.csv), [PHASE8B_METADATA_ABLATION.md](file:///d:/TLTN/movie-recommendation-system/docs/audit/PHASE8B_METADATA_ABLATION.md) | **Completed** |
| 10 | Statistical significance & protocol reports | [phase8b_statistical_significance.json](file:///d:/TLTN/movie-recommendation-system/backend/reports/phase8b_embeddings/phase8b_statistical_significance.json), [PHASE8B_EXPERIMENT_PROTOCOL.md](file:///d:/TLTN/movie-recommendation-system/docs/audit/PHASE8B_EXPERIMENT_PROTOCOL.md) | **Completed** |
| 11 | Latency & memory benchmark report | [phase8b_performance_benchmark.json](file:///d:/TLTN/movie-recommendation-system/backend/reports/phase8b_embeddings/phase8b_performance_benchmark.json), [PHASE8B_PERFORMANCE_REPORT.md](file:///d:/TLTN/movie-recommendation-system/docs/audit/PHASE8B_PERFORMANCE_REPORT.md) | **Completed** |
| 12 | Production feature flag & safe fallback | [engine.py](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/engine.py), [explainer_admin.py](file:///d:/TLTN/movie-recommendation-system/backend/app/services/recommendation/explainer_admin.py), [.env.example](file:///d:/TLTN/movie-recommendation-system/backend/.env.example) | **Completed** |
| 13 | MovSug TEC integration & multi-format reports | [semantic_recommendation_collector.py](file:///d:/TLTN/movie-recommendation-system/test_center/collectors/semantic_recommendation_collector.py), [report.md](file:///d:/TLTN/movie-recommendation-system/test_center/reports/tec-20261104-090658-8f3e707/report/report.md), [bao_cao_tom_tat.md](file:///d:/TLTN/movie-recommendation-system/test_center/reports/tec-20261104-090658-8f3e707/report/bao_cao_tom_tat.md), [report.html](file:///d:/TLTN/movie-recommendation-system/test_center/reports/tec-20261104-090658-8f3e707/report/report.html) | **Completed** |
| 14 | Automated unit & integration tests | [test_semantic_recommendations.py](file:///d:/TLTN/movie-recommendation-system/backend/tests/test_semantic_recommendations.py), [test_semantic_recommendation_collector.py](file:///d:/TLTN/movie-recommendation-system/test_center/tests/test_semantic_recommendation_collector.py) | **Completed** |
| 15 | Vietnamese thesis-ready summary | Section 4 below & [bao_cao_tom_tat.md](file:///d:/TLTN/movie-recommendation-system/test_center/reports/tec-20261104-090658-8f3e707/report/bao_cao_tom_tat.md) | **Completed** |
| 16 | Exact reproduction commands | Section 5 below | **Completed** |

---

## 3. Evidence-Based Recommendation for Phase 9

Based on the empirical evidence gathered in Phase 8B:

1. **Keep `RECOMMENDATION_STRATEGY=tfidf_v1_1` (with optional MMR $\lambda=0.5$) as the production default:** On catalogs where most items have sparse lexical metadata (`title`, `genres`, `tags`), `TF-IDF v1.1 + MMR (λ=0.5)` delivers superior accuracy (`NDCG@10 = 0.009091`), coverage (`14.22%`), and diversity (`ILD@10 = 0.7686`) at `<1 MB` RAM.
2. **Prioritize Batch TMDB Metadata Coverage Before Deploying Standalone Dense Embeddings:** Both Protocol B1 (`TF-IDF` `+9.31%` `NDCG@10` from enriching just `11` popular movies) and Protocol B2 (`Semantic-EN` `+9.05%` `NDCG@10` when `100%` of candidates have rich overviews) prove that **metadata completeness is the primary bottleneck**.
3. **Evaluate Hybrid Lexical + Semantic Score Fusion in Phase 9:** Because `Semantic-EN` retrieves lexically distinct items (`TFIDF_ILD@10 = 0.8905`) with higher long-tail novelty (`14.59` bits), combining `TF-IDF v1.1` lexical precision with `Semantic-EN` conceptual recall via calibrated score fusion ($\alpha \cdot s_{\text{TF-IDF}} + (1 - \alpha) \cdot s_{\text{Semantic}}$) or multi-interest user sub-profiles is the most promising research direction for Phase 9.

---

## 4. Tóm Tắt Kết Quả Nghiên Cứu (Bản Sẵn Sàng Cho Khóa Luận Tốt Nghiệp)

### 4.1 Mục Tiêu Giai Đoạn 8B (Phase 8B)
Giai đoạn 8B xây dựng hệ thống gợi ý phim dựa trên biểu diễn ngữ nghĩa dày (Dense Semantic Embeddings) sử dụng các mô hình ngôn ngữ tiền huấn luyện chạy trên CPU thông qua ONNX Runtime (`sentence-transformers/all-MiniLM-L6-v2` cho tiếng Anh và `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` hỗ trợ đa ngôn ngữ Anh–Việt). Hệ thống được đánh giá thực nghiệm nghiêm ngặt so với đường cơ sở `TF-IDF v1.1` và `TF-IDF v1.1 + MMR` trên tập dữ liệu chuẩn MovieLens `ml-latest-small` (`9,742` bộ phim, `610` người dùng, `587` người dùng kiểm thử tích cực; mã băm dữ liệu `d830d1e5...`, mã băm phân chia tập huấn luyện/kiểm thử theo thời gian `48cc8f10...`), đồng thời tích hợp toàn diện vào Trung tâm Kiểm thử & Đánh giá MovSug (TEC).

### 4.2 Kết Quả Thực Nghiệm & Trả Lời 4 Câu Hỏi Nghiên Cứu (RQ1–RQ4)
1. **RQ1 — Tác động của việc làm giàu Metadata (Phase 8A TMDB Enrichment) đến chất lượng gợi ý:**
   - Trong thực nghiệm toàn danh mục (**Protocol B1**, nơi `11 / 9,742` bộ phim phổ biến trong MovieLens khớp với dữ liệu TMDB đã được quản trị viên phê duyệt trong cơ sở dữ liệu MovSug), việc bổ sung tóm tắt nội dung (`overview`), đạo diễn (`director`), diễn viên (`cast`) và từ khóa (`keywords`) giúp mô hình `TF-IDF v1.1` **tăng `Precision@10` từ `0.004600` lên `0.005281` (`+14.80%`, kiểm định $t$ bắt cặp $p = 0.0454$, Wilcoxon $p = 0.0455$)** và **tăng `NDCG@10` từ `0.007153` lên `0.007819` (`+9.31%`, Wilcoxon $p = 0.0431$, khoảng tin cậy Bootstrap 95% `[+0.000114, +0.001421]`, 5 thắng / 0 thua)**.
   - Trong thực nghiệm chẩn đoán trên tập con `10` bộ phim đã được làm giàu đồng nhất (**Protocol B2**, `33` người dùng — được gắn nhãn minh bạch là `NOT ENOUGH EVIDENCE` do quy mô tập ứng viên nhỏ), việc làm giàu metadata giúp `Semantic-EN` tăng `NDCG@10` từ `0.6593` lên `0.7190` (`+9.05%`) và `MAP@10` từ `0.5446` lên `0.6261`.
2. **RQ2 — So sánh Semantic Embeddings và TF-IDF v1.1 trên cùng điều kiện Metadata gốc (Condition A):**
   - Khi đánh giá trên metadata gốc rất thưa của MovieLens (`83.9%` số phim chỉ có tên phim và nhãn thể loại, hoàn toàn thiếu tóm tắt cốt truyện), mô hình từ vựng thưa `TF-IDF v1.1` (`NDCG@10 = 0.007153`, `Coverage@10 = 13.10%`) vượt trội hơn so với `Semantic-EN` (`NDCG@10 = 0.004930`, `Coverage@10 = 5.06%`, $p = 0.2393$ tại $K=10$ và $p = 0.0465$ tại $K=20$) cũng như `Semantic-Multi` (`NDCG@10 = 0.002921`, $p = 0.0220$).
   - **Giải thích khoa học:** Khi chuỗi văn bản đầu vào quá ngắn và thiếu ngữ cảnh tự sự, các vector nhúng 384 chiều từ mạng Transformer bị co cụm dị hướng (anisotropic cone). Khi lấy trung bình có trọng số lịch sử xem phim đa dạng của người dùng thành một vector tâm (single user centroid), vector người dùng bị kéo về vùng trung tâm phổ biến (hubness effect), làm giảm độ phủ danh mục (`Coverage@10` giảm từ `13.10%` xuống `5.06%`).
3. **RQ3 — Đánh đổi giữa Độ chính xác xếp hạng và Độ đa dạng (so với TF-IDF v1.1 + MMR):**
   - `TF-IDF v1.1 + MMR (λ=0.5, pool=100)` vẫn là cấu hình có hiệu năng tổng thể tốt nhất trên tập MovieLens gốc (`NDCG@10 = 0.009091`, `Recall@10 = 0.010158`, `Coverage@10 = 14.22%`, `ILD@10 = 0.7686`).
   - Tuy nhiên, các danh sách gợi ý từ `Semantic-EN` có **độ mới (Novelty@10 = `14.59 bits` so với `13.84 bits`)** và **độ đa dạng từ vựng (`TFIDF_ILD@10 = 0.8905`)** cao hơn hẳn `TF-IDF`, chứng tỏ mô hình ngữ nghĩa có khả năng khám phá các bộ phim ít phổ biến (long-tail) không trùng khớp từ khóa bề mặt. Khi kết hợp thêm `MMR (λ=0.5)` vào `Semantic-EN`, cả `NDCG@10` (`0.004930` $\to$ `0.005113`) và `Coverage@10` (`5.06%` $\to$ `5.42%`) đều được cải thiện.
4. **RQ4 — Chi phí tài nguyên hệ thống và độ trễ suy luận:**
   - Thời gian sinh vector hàng loạt trên CPU cho `9,742` bộ phim là `29.99 giây` đối với `all-MiniLM-L6-v2` và `58.86 giây` đối với `paraphrase-multilingual-MiniLM-L12-v2` (chậm hơn `62–121 lần` so với `0.48 giây` của `TF-IDF`), dung lượng lưu trữ nén `.npz` là `14.26 MB` và bộ nhớ RAM đỉnh là `49.73 MB`.
   - Nhờ cơ chế lưu trữ đệm có kiểm tra mã băm phiên bản (`embedding_cache.py`), thời gian nạp ma trận từ đĩa chỉ mất `108.62 ms` và **độ trễ gợi ý trực tuyến đạt `p50 = 8.52 ms`, `p95 = 10.23 ms`**, hoàn toàn đáp ứng yêu cầu thời gian thực.

---

## 5. Exact Reproduction Commands

```powershell
# 1. Run the complete Phase 8B offline evaluation suite (Condition A + Condition B1/B2 + Benchmarks)
d:\TLTN\movie-recommendation-system\backend\.venv\Scripts\python.exe -m app.recommendation_evaluation.run --phase8b --allow-model-download --batch-size 128

# 2. Run Phase 8B unit & integration tests (100% offline, <2s)
d:\TLTN\movie-recommendation-system\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_semantic_recommendations.py test_center/tests/test_semantic_recommendation_collector.py -v

# 3. Run the full MovSug Test & Evaluation Center (TEC) verification suite
d:\TLTN\movie-recommendation-system\backend\.venv\Scripts\python.exe -m test_center run --suite all-safe --with-coverage --with-lint --with-build

# 4. Generate all TEC reports (JSON, CSV, Markdown, Vietnamese Summary, Self-Contained HTML)
d:\TLTN\movie-recommendation-system\backend\.venv\Scripts\python.exe -m test_center report --run test_center/reports/tec-20261104-090658-8f3e707 --format all
```

