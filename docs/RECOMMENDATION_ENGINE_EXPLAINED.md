# Recommendation Engine — Giải Thích Chi Tiết
## AI-based Movie Recommendation Website

---

## 1. Tổng Quan Thuật Toán

| Mục | Chi tiết |
|-----|----------|
| **Loại thuật toán** | Content-Based Filtering |
| **Kỹ thuật NLP** | TF-IDF (Term Frequency–Inverse Document Frequency) |
| **Đo lường tương đồng** | Cosine Similarity |
| **Thư viện** | scikit-learn (`TfidfVectorizer`, `cosine_similarity`), NumPy, SciPy |
| **Cold-start** | Fallback về phim mới nhất |
| **Collaborative filtering** | Không có |
| **Deep learning** | Không có |

**Thuật toán này là Content-Based Filtering thuần — nó gợi ý phim dựa trên nội dung metadata của phim (thể loại, diễn viên, từ khóa, đạo diễn, mô tả) kết hợp với lịch sử tương tác của user.**

---

## 2. Kiến Trúc Code

```
backend/app/services/recommendation/
├── engine.py          ← Orchestrator chính
├── movie_profile.py   ← Xây corpus text từ metadata phim
├── user_profile.py    ← Xây user preference vector
├── vectorizer.py      ← TF-IDF + cache
├── explainer.py       ← Giải thích ngắn cho user
└── explainer_admin.py ← Giải thích đầy đủ cho admin
```

---

## 3. Pipeline Chi Tiết

### Bước 1: Movie Text Profile (`movie_profile.py`)

Mỗi phim được chuyển thành **một chuỗi text duy nhất** bằng cách nối các trường metadata:

```
"Inception Inception A thief who steals corporate secrets... Action Science Fiction Thriller 
 actor leonardo dicaprio actor tom hardy heist dream lucid dream heist dream lucid dream 
 director Christopher Nolan"
```

**Trọng số text (weight by repetition):**

| Trường | Số lần lặp | Lý do |
|--------|-----------|-------|
| Title | ×2 | Token nhận dạng chính — nếu user thích "Inception", những phim có từ tương tự sẽ score cao hơn |
| Keywords | ×2 | Tín hiệu chủ đề ngắn gọn, signal-to-noise ratio cao |
| Overview | ×1 | Nhiều ngữ cảnh nhưng cũng nhiều noise |
| Genres | ×1 | Tín hiệu phân loại rõ ràng |
| Cast | ×1 | Mỗi tên được prefix "actor" để phân biệt với từ thông thường |
| Director | ×1 | Prefix "director" để phân biệt |

**Tại sao prefix "actor" và "director"?**
Nếu không prefix, tên "Tom" trong "Tom Hanks" sẽ match với từ "Tom" bất kỳ trong overview. Prefix tạo ra token đặc biệt: `"actor tom hanks"` → TF-IDF sẽ tạo bigram `"actor_tom"` chỉ match với diễn viên.

### Bước 2: TF-IDF Vectorization (`vectorizer.py`)

```python
vectorizer = TfidfVectorizer(
    max_features=5000,      # Giới hạn vocabulary 5000 terms
    stop_words="english",   # Loại "the", "is", "and"...
    ngram_range=(1, 2),     # Unigrams ("action") + bigrams ("actor tom")
    min_df=1,               # Giữ từ xuất hiện ít nhất 1 lần
    max_df=0.95,            # Bỏ từ xuất hiện >95% tài liệu
)
matrix = vectorizer.fit_transform(corpus)
# → sparse matrix kích thước (n_movies × 5000)
```

**TF-IDF là gì?**
- TF (Term Frequency): tần suất từ trong tài liệu → từ xuất hiện nhiều = quan trọng hơn cho tài liệu đó
- IDF (Inverse Document Frequency): nghịch đảo tần suất trên toàn bộ corpus → từ xuất hiện ở ít phim hơn = đặc trưng hơn
- TF-IDF = TF × IDF → từ vừa phổ biến trong phim này, vừa hiếm ở phim khác = score cao nhất

**Ví dụ:**
- "heist" xuất hiện trong 2/100 phim → IDF cao → phim có "heist" rất đặc trưng
- "movie" xuất hiện trong 90/100 phim → IDF thấp → không giúp phân biệt

**Cache:**
- Vectorizer được cache in-memory
- Chỉ refit khi `db.query(Movie).count()` thay đổi
- `invalidate_cache()` có thể gọi thủ công

### Bước 3: User Preference Vector (`user_profile.py`)

**3 nguồn tín hiệu:**

#### 3a. Star Ratings (Tín hiệu tường minh mạnh nhất)

| Rating | Weight | Ý nghĩa |
|--------|--------|---------|
| 5★ | 5.0 | User rất thích → ảnh hưởng mạnh nhất |
| 4★ | 3.0 | User thích |
| 3★ | 1.0 | Trung lập, vẫn tính |
| 2★ | 0.0 | **Loại bỏ** — tránh kéo profile về phía nội dung không thích |
| 1★ | 0.0 | **Loại bỏ** |

#### 3b. Favorites (Tín hiệu tường minh)

| Hành động | Weight |
|-----------|--------|
| Favorite một phim | 3.0 (= ngang 4★) |

#### 3c. Watch History (Tín hiệu ngầm — implicit)

Công thức 2 yếu tố:

**Yếu tố 1 — Progress (tuyến tính):**
```
base = 1.0 + (progress_percent / 100) × 2.0
```
| Progress | Base weight |
|----------|-------------|
| 0% (mở xem) | 1.0 |
| 25% | 1.5 |
| 50% | 2.0 |
| 75% | 2.5 |
| 100% (xem hết) | 3.0 |

**Yếu tố 2 — Time Decay (suy giảm theo thời gian):**
```
decay = 1.0 / (1.0 + days_since × 0.05)
```
| Thời gian | Decay |
|-----------|-------|
| Hôm nay | 1.00 |
| 10 ngày trước | 0.67 |
| 20 ngày trước | 0.50 |
| 40 ngày trước | 0.33 |
| 100 ngày trước | 0.17 |

**Kết hợp:**
```
watch_weight = min(base × decay, 3.0)   # cap tại 3.0
```

#### Quy tắc kết hợp nhiều tín hiệu

Nếu 1 phim xuất hiện ở **nhiều nguồn** (ví dụ: user vừa rate 5★ VÀ favorite VÀ xem 80%):
- **Lấy MAX**, không cộng dồn
- Ví dụ: max(5.0, 3.0, 2.6) = 5.0

**Lý do:** Cộng dồn sẽ khiến 1 phim dominate toàn bộ profile nếu user tương tác nhiều cách.

#### Xây dựng vector cuối cùng

```python
user_vector = Σ (weight_i × movie_vector_i) / Σ weight_i
user_vector = L2_normalize(user_vector)
```

- Weighted average → vector "trung bình" của tất cả phim user thích
- L2 normalize → đảm bảo cosine similarity hoạt động đúng

### Bước 4: Cosine Similarity (`engine.py`)

```python
scores = cosine_similarity(
    user_vector.reshape(1, -1),   # 1 × n_features
    movie_matrix                   # n_movies × n_features
).flatten()
# → 1 score (0.0 – 1.0) cho mỗi phim
```

**Cosine Similarity:**
- Đo góc giữa 2 vector trong không gian n chiều
- 1.0 = hoàn toàn giống nhau
- 0.0 = không liên quan
- Không phụ thuộc vào độ dài vector (nhờ L2 normalize)

**Post-processing:**
1. Loại bỏ phim user đã favorite
2. Sắp xếp giảm dần theo score
3. Lấy top-N (mặc định 10)

### Bước 5: Giải Thích (`explainer.py`)

```python
if score >= 0.5:  → "Strong match"
elif score >= 0.2: → "Good match"  
else:              → "You might like this"

# Kết hợp với nguồn tín hiệu chính:
"Based on your ratings · Strong match"
"Based on your favorites · Good match"
"Similar to movies you watched · You might like this"
```

### Bước 6: Cold-Start Handling

Khi `build_user_profile()` trả về `None` (user chưa rate/favorite/xem gì):
- Trả về phim mới nhất (`ORDER BY release_date DESC`)
- Score = 0.0
- Reason = "Popular movie — rate or favorite some movies for personalized picks!"

---

## 4. API Flow

```
Frontend (HomePage/MovieDetailPage)
  │
  ├─ getRecommendations(top_n=10)
  │     │
  │     └─ GET /api/v1/recommendations/me?top_n=10
  │           Authorization: Bearer <JWT>
  │
  ↓
Backend (recommendations.py router)
  │
  ├─ get_current_user() → xác thực JWT → user_id
  │
  └─ get_recommendations(db, user_id, top_n=10)
        │
        ├─ build_user_profile(db, user_id)
        │     ├─ get_user_ratings(db, user_id)
        │     ├─ get_user_favorite_ids(db, user_id)
        │     ├─ _get_watch_records(db, user_id)
        │     └─ weighted average → L2 normalize → user_vector
        │
        ├─ get_movie_vectors(db)
        │     └─ TF-IDF vectorizer (cached) → (matrix, movie_ids)
        │
        ├─ cosine_similarity(user_vector, matrix) → scores
        │
        ├─ exclude favorited movies
        │
        ├─ sort by score DESC → top-N
        │
        └─ generate_reason() → reason string
              │
              ↓
        Response: [{ id, title, poster_url, release_year, score, reason }]
```

---

## 5. Admin Explainer (`explainer_admin.py`)

Endpoint: `GET /api/v1/admin/recommendations/explain/{user_id}`

Trả về payload chi tiết bao gồm:
- `user_context` — từng interaction và weight tính toán
- `weight_summary` — thống kê tổng hợp
- `top_recommendations` — top-N với `contributing_factors`
- `algorithm_summary` — mô tả thuật toán bằng tiếng Anh

**Mục đích:** Dùng cho thesis defense — "mở hộp đen" thuật toán.

---

## 6. Điểm Mạnh

1. **Interpretable** — có thể giải thích chính xác tại sao phim X được gợi ý
2. **Không cần dữ liệu user khác** — chỉ cần data của chính user đó
3. **3 nguồn tín hiệu** — kết hợp explicit (rating, favorite) + implicit (watch)
4. **Time decay** — ưu tiên sở thích gần đây hơn
5. **Cold-start handling** — có fallback rõ ràng
6. **Metadata weighting** — text repetition cho trọng số khác nhau
7. **Admin explainer** — minh bạch hoàn toàn cho academic defense

---

## 7. Điểm Yếu

1. **Không có Collaborative Filtering** — không học từ user tương tự
2. **Filter bubble** — chỉ gợi ý phim giống phim đã thích → thiếu diversity
3. **Phụ thuộc metadata** — phim thiếu genres/cast/keywords = gợi ý kém
4. **English only** — TF-IDF stopwords chỉ hỗ trợ tiếng Anh
5. **Cache đơn giản** — invalidate khi movie count thay đổi, không theo nội dung
6. **Không negative feedback** — rating 1-2★ chỉ bị loại bỏ, không đẩy xa
7. **Scale** — TF-IDF refit trên toàn bộ corpus mỗi khi cache miss

---

## 8. Cải Tiến Gợi Ý (Tương Lai)

| Cải tiến | Mô tả | Độ khó |
|----------|-------|--------|
| Collaborative Filtering hybrid | Kết hợp user-user similarity | Cao |
| Diversity boost | Random sampling từ các cluster khác | Trung bình |
| Negative signals | Dùng rating 1-2★ để đẩy xa phim tương tự | Thấp |
| Genre preference decay | Giảm weight nếu user xem quá nhiều 1 genre | Trung bình |
| Vietnamese stopwords | Thêm stopwords tiếng Việt nếu dữ liệu song ngữ | Thấp |
| Incremental TF-IDF | Online update khi thêm phim mới | Cao |
| A/B testing framework | So sánh hiệu quả các thuật toán | Cao |

---

## 9. Dữ Liệu Cần Thiết Cho Chất Lượng Gợi Ý

| Dữ liệu | Mức ảnh hưởng | Hiện trạng |
|----------|--------------|------------|
| Genres | ★★★★★ | Có — 18 thể loại chuẩn |
| Keywords | ★★★★ | Có — tag input tự do |
| Cast | ★★★ | Có — tag input |
| Director | ★★ | Có — text field |
| Overview | ★★ | Có — textarea |
| User ratings | ★★★★★ | Có — 1-5 sao |
| User favorites | ★★★ | Có — toggle |
| Watch progress | ★★ | Có — 0-100% |
| Số lượng phim | ★★★★ | Thấp (~20) — cần 100+ |
| Số lượng users | ★★★ | Cần tạo demo users |
