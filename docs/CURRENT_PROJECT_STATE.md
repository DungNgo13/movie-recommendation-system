# Báo Cáo Trạng Thái Dự Án
## AI-based Movie Recommendation Website

**Ngày tạo:** 2026-07-06  
**Branch:** main  
**Trạng thái:** Production-ready, đang phát triển thêm tính năng

---

## 1. Tổng Quan Dự Án

| Mục | Chi tiết |
|-----|----------|
| **Tên dự án** | AI-based Movie Recommendation Website (Mov-Sug) |
| **Mục đích** | Website gợi ý phim dựa trên AI sử dụng thuật toán Content-based Filtering |
| **Vai trò người dùng** | User (xem phim, đánh giá, yêu thích) / Admin (quản lý phim, user, giám sát hệ thống) |
| **Vấn đề giải quyết** | Gợi ý phim phù hợp sở thích cá nhân dựa trên lịch sử tương tác |
| **Trạng thái** | Đầy đủ tính năng core, có thể demo |

### Tính năng chính
- Xem danh sách phim, tìm kiếm, lọc theo thể loại
- Đánh giá phim (1–5 sao)
- Yêu thích phim
- Xem lịch sử xem phim
- **Gợi ý phim cá nhân hóa bằng TF-IDF + Cosine Similarity**
- Phát video HLS multi-quality
- Quản trị admin: CRUD phim, quản lý user, audit log
- Đăng ký, đăng nhập, quên mật khẩu, đặt lại mật khẩu
- Upload avatar, poster, backdrop, video
- Admin giám sát thuật toán gợi ý (RecsysMonitor)

---

## 2. Tech Stack

| Layer | Công nghệ |
|-------|-----------|
| **Frontend** | React 18 + TypeScript + Vite |
| **Styling** | Vanilla CSS với OKLCH color system |
| **Backend** | FastAPI (Python) |
| **Database** | PostgreSQL (production) / SQLite (dev) |
| **ORM** | SQLAlchemy |
| **Migration** | Alembic |
| **Auth** | JWT (python-jose) + bcrypt |
| **AI/ML** | scikit-learn (TF-IDF, Cosine Similarity), NumPy, SciPy |
| **Video** | FFmpeg → HLS multi-quality encoding |
| **Email** | smtplib + Jinja2 templates |
| **Deployment** | Ubuntu + Nginx reverse proxy + Uvicorn |

### Thư viện quan trọng (Backend)
- `fastapi`, `uvicorn` — web framework
- `sqlalchemy` — ORM
- `alembic` — migration
- `scikit-learn` — TF-IDF vectorizer
- `numpy`, `scipy` — tính toán vector
- `python-jose` — JWT tokens
- `bcrypt` — hash mật khẩu
- `python-dotenv` — env config
- `jinja2` — email templates

### Thư viện quan trọng (Frontend)
- `react`, `react-dom` — UI framework
- `react-router-dom` — routing
- `hls.js` — HLS video player

---

## 3. Kiến Trúc Backend

### Entry point
- `backend/app/main.py` — Khởi tạo FastAPI app, đăng ký routers, CORS, static files, HLS encoding worker

### Cấu trúc thư mục

```
backend/
├── app/
│   ├── main.py                 # FastAPI app + lifespan
│   ├── database.py             # SQLAlchemy engine + session
│   ├── seed.py                 # Dữ liệu mẫu (20 phim)
│   ├── core/
│   │   ├── security.py         # JWT, bcrypt, token creation
│   │   └── password_validator.py  # Kiểm tra độ mạnh mật khẩu
│   ├── models/                 # SQLAlchemy models
│   │   ├── user.py
│   │   ├── movie.py
│   │   ├── rating.py
│   │   ├── user_favorite.py
│   │   ├── watch_history.py
│   │   ├── admin_audit_log.py
│   │   └── movie_asset.py
│   ├── schemas/                # Pydantic schemas
│   │   ├── user.py
│   │   ├── movie.py
│   │   ├── rating.py
│   │   ├── favorite.py
│   │   ├── history.py
│   │   ├── recommendation.py
│   │   ├── watch_progress.py
│   │   ├── movie_asset.py
│   │   └── admin.py
│   ├── routers/                # API endpoints
│   │   ├── auth.py             # Đăng ký, đăng nhập, quên/đặt lại MK
│   │   ├── movies.py           # CRUD phim + upload
│   │   ├── ratings.py          # Đánh giá phim
│   │   ├── favorites.py        # Yêu thích
│   │   ├── history.py          # Lịch sử xem
│   │   ├── watch_progress.py   # Tiến trình xem video
│   │   ├── recommendations.py  # API gợi ý
│   │   ├── users.py            # Profile user
│   │   ├── admin_users.py      # Quản lý user (admin)
│   │   ├── admin_dashboard.py  # Dashboard thống kê
│   │   ├── admin_logs.py       # Audit logs
│   │   ├── admin_recommendations.py  # Giải thích gợi ý (admin)
│   │   └── movie_assets.py     # Assets (license)
│   ├── services/
│   │   ├── auth_service.py     # Logic đăng ký, đăng nhập, reset MK
│   │   ├── movie_service.py    # Logic CRUD phim
│   │   ├── rating_service.py   # Logic đánh giá
│   │   ├── favorite_service.py # Logic yêu thích
│   │   ├── history_service.py  # Logic lịch sử xem
│   │   ├── mail_service.py     # Gửi email SMTP
│   │   ├── hls_service.py      # FFmpeg HLS encoding
│   │   ├── avatar_service.py   # Upload avatar
│   │   ├── file_storage_service.py  # Lưu file media
│   │   ├── admin_service.py    # Audit logging
│   │   ├── asset_license_service.py  # CRUD MovieAsset
│   │   ├── license_checker.py  # Kiểm tra license
│   │   └── recommendation/     # ★ LÕI AI/ML
│   │       ├── engine.py       # Orchestrator chính
│   │       ├── movie_profile.py  # Xây dựng text profile
│   │       ├── user_profile.py   # Xây dựng user vector
│   │       ├── vectorizer.py     # TF-IDF vectorizer
│   │       ├── explainer.py      # Giải thích ngắn
│   │       └── explainer_admin.py  # Giải thích chi tiết (admin)
│   └── templates/              # Jinja2 email templates
├── alembic/                    # Database migrations
├── scripts/
│   ├── importers/              # Data importers
│   └── public_domain_movies.json
├── tests/                      # Pytest test suite
└── uploads/ + media/           # Uploaded files
```

### Routers (API Endpoints)

| Router | Prefix | Chức năng |
|--------|--------|-----------|
| `auth.py` | `/api/v1/auth` | Đăng ký, đăng nhập, refresh, quên MK, đặt lại MK |
| `movies.py` | `/api/v1/movies` | CRUD phim, upload poster/backdrop/video, xử lý HLS |
| `ratings.py` | `/api/v1/ratings` | Đánh giá phim 1–5 sao |
| `favorites.py` | `/api/v1/favorites` | Toggle yêu thích |
| `history.py` | `/api/v1/history` | Lịch sử xem phim |
| `watch_progress.py` | `/api/v1/watch-progress` | Lưu/load vị trí xem video |
| `recommendations.py` | `/api/v1/recommendations` | Gợi ý phim cá nhân hóa |
| `users.py` | `/api/v1/users` | Profile + avatar upload |
| `admin_users.py` | `/api/v1/admin/users` | Quản lý user (admin only) |
| `admin_dashboard.py` | `/api/v1/admin/dashboard` | Thống kê tổng quan |
| `admin_logs.py` | `/api/v1/admin/logs` | Audit logs |
| `admin_recommendations.py` | `/api/v1/admin/recommendations` | Giải thích thuật toán (admin) |
| `movie_assets.py` | `/api/v1/movies/{id}/assets` | Per-asset license tracking |

---

## 4. Kiến Trúc Frontend

### Entry point
- `frontend/src/main.tsx` → `App.tsx`

### Routing (React Router)

| Path | Page | Quyền |
|------|------|-------|
| `/` | HomePage | Public |
| `/movie/:id` | MovieDetailPage | Public |
| `/favorites` | FavoritesPage | Login |
| `/login` | LoginPage | Public |
| `/register` | RegisterPage | Public |
| `/forgot-password` | ForgotPasswordPage | Public |
| `/reset-password` | ResetPasswordPage | Public |
| `/profile` | ProfilePage | Login |
| `/confirm-password-change` | ConfirmPasswordChangePage | Login |
| `/admin` | AdminDashboardPage | Admin |
| `/admin/movies` | AdminMoviesPage | Admin |
| `/admin/users` | AdminUsersPage | Admin |
| `/admin/logs` | AdminAuditLogsPage | Admin |
| `/admin/recsys` | RecsysMonitorPage | Admin |
| `/admin/security` | AdminSecurityAuditPage | Admin |

### Components quan trọng

| Component | Chức năng |
|-----------|-----------|
| `Navbar.tsx` | Thanh điều hướng trên cùng |
| `MovieCard.tsx` | Card hiển thị phim (poster, tiêu đề) |
| `RecommendationCard.tsx` | Card phim gợi ý (có score/reason) |
| `StarRating.tsx` | UI đánh giá sao |
| `HlsPlayer.tsx` | Video player HLS multi-quality |
| `SourceAttribution.tsx` | Hiển thị thông tin nguồn/license |
| `ProtectedAdminRoute.tsx` | Guard route admin |
| `admin/MovieForm.tsx` | Form thêm/sửa phim (admin) |
| `admin/MovieTable.tsx` | Bảng danh sách phim (admin) |

### Services (API clients)

| Service | Gọi API |
|---------|---------|
| `authService.ts` | Đăng ký, đăng nhập, refresh token, JWT storage |
| `movieService.ts` | CRUD phim, upload, xử lý video |
| `recommendationService.ts` | Lấy gợi ý cá nhân hóa |
| `ratingService.ts` | Đánh giá phim |
| `favoriteService.ts` | Toggle yêu thích |
| `continueWatchingService.ts` | Lưu/load tiến trình xem |
| `adminService.ts` | Admin CRUD users |
| `recsysService.ts` | Admin: giải thích thuật toán gợi ý |

---

## 5. Database Schema

### Bảng `users`

| Column | Type | Ghi chú |
|--------|------|---------|
| id | UUID | PK |
| email | String(255) | UNIQUE, INDEX |
| password_hash | String(255) | bcrypt hash |
| role | String(50) | "user" / "admin" |
| status | String(20) | "active" / "banned" |
| created_at | DateTime | |
| last_login_ip | String(45) | IPv4/IPv6 |
| last_login_at | DateTime | |
| last_password_change | DateTime | |
| last_email_change | DateTime | |
| failed_login_attempts | Integer | Brute-force detection |
| password_reset_token | String(64) | INDEX |
| password_reset_expires | DateTime | |
| avatar_path | String(255) | |

### Bảng `movies`

| Column | Type | Ghi chú |
|--------|------|---------|
| id | UUID | PK |
| title | String(255) | INDEX, NOT NULL |
| overview | Text | |
| release_date | Date | |
| genres | JSON | `["Action", "Drama"]` — **dùng cho TF-IDF** |
| cast | JSON | `["Tom Hanks"]` — **dùng cho TF-IDF** |
| keywords | JSON | `["heist", "space"]` — **dùng cho TF-IDF** |
| director | String(100) | **dùng cho TF-IDF** |
| poster_path | String(255) | |
| backdrop_path | String(255) | |
| video_source_path | String(255) | |
| processing_status | String(50) | no_video/uploaded/processing/ready/failed |
| processing_progress | Integer | 0–100 |
| processing_step | String(100) | |
| hls_playlist_path | String(255) | |
| processing_error | Text | |
| available_qualities | String(100) | "360p,720p,1080p" |
| source_name | String(100) | Optional — nguồn dữ liệu |
| source_url | String(500) | Optional |
| license_type | String(100) | Optional |
| license_url | String(500) | Optional |
| attribution | Text | Optional |
| is_public_domain | Boolean | Default false |
| media_rights_status | String(30) | Default "unknown" |

### Bảng `ratings`

| Column | Type | Ghi chú |
|--------|------|---------|
| id | UUID | PK |
| user_id | UUID | FK → users, CASCADE |
| movie_id | UUID | FK → movies, CASCADE |
| rating | Integer | CHECK 1–5 |
| created_at | DateTime | |
| updated_at | DateTime | |
| | | UNIQUE(user_id, movie_id) |

### Bảng `user_favorites`

| Column | Type | Ghi chú |
|--------|------|---------|
| id | UUID | PK |
| user_id | UUID | FK → users, CASCADE |
| movie_id | UUID | FK → movies, CASCADE |
| created_at | DateTime | |
| | | UNIQUE(user_id, movie_id) |

### Bảng `watch_history`

| Column | Type | Ghi chú |
|--------|------|---------|
| id | UUID | PK |
| user_id | UUID | FK → users, CASCADE |
| movie_id | UUID | FK → movies, CASCADE |
| watched_at | DateTime | |
| progress_percent | Integer | 0–100 |
| playback_position_seconds | Integer | |
| duration_seconds | Integer | |
| is_completed | Boolean | |
| | | UNIQUE(user_id, movie_id) |

### Bảng `admin_audit_logs`

| Column | Type | Ghi chú |
|--------|------|---------|
| id | UUID | PK |
| admin_user_email | String(255) | INDEX |
| action_type | String(50) | INDEX |
| target_type | String(50) | |
| target_id | String(255) | |
| description | Text | |
| created_at | DateTime | INDEX |

### Bảng `movie_assets`

| Column | Type | Ghi chú |
|--------|------|---------|
| id | UUID | PK |
| movie_id | UUID | FK → movies, CASCADE |
| asset_type | String(30) | poster/backdrop/banner/trailer/... |
| url | String(500) | |
| local_path | String(500) | |
| source_name | String(100) | |
| source_url | String(500) | |
| license_type | String(100) | |
| license_url | String(500) | |
| attribution | Text | |
| is_public_domain | Boolean | |
| media_rights_status | String(30) | |
| created_at | DateTime | |

---

## 6. ★ Logic AI / Recommendation (PHẦN QUAN TRỌNG NHẤT)

### Thuật toán: Content-Based Filtering sử dụng TF-IDF + Cosine Similarity

**Đây là thuật toán thực tế được cài đặt trong code, không phải giả định.**

> **Quan trọng:** Hệ thống AI chỉ gợi ý phim có trong catalog của website — tức phim đã được admin upload lên hệ thống. AI không tự lấy hoặc gợi ý phim từ nguồn bên ngoài. Các công cụ nhập dữ liệu (MovieLens, Wikidata) chỉ là tiện ích seed/enrich metadata tùy chọn.

### Candidate Pool (Tập phim ứng viên)

Biến `RECOMMEND_ONLY_UPLOADED_MOVIES` (mặc định `true`) kiểm soát:
- **true:** Chỉ gợi ý phim có `video_source_path` hoặc `hls_playlist_path` hoặc `processing_status = "ready"`
- **false:** Tất cả phim trong bảng `movies`

### Pipeline hoàn chỉnh

```
Admin upload phim + metadata (genres, cast, keywords, video)
    ↓
User tương tác (rating/favorite/watch)
    ↓
Dữ liệu lưu vào DB (ratings, user_favorites, watch_history)
    ↓
build_user_profile() — xây dựng user preference vector
    ↓
get_movie_vectors() — TF-IDF vectorize phim trong catalog (chỉ phim đã upload)
    ↓
cosine_similarity() — so sánh user vector vs movie vectors
    ↓
Xếp hạng theo score giảm dần, loại trừ phim đã tương tác
    ↓
generate_reason() — giải thích tại sao gợi ý
    ↓
API trả về top-N phim gợi ý
    ↓
Frontend hiển thị trong MovieDetailPage
```

### Files cài đặt

| File | Vai trò |
|------|---------|
| `recommendation/engine.py` | Orchestrator — gọi các module khác, trả kết quả |
| `recommendation/movie_profile.py` | Xây dựng text corpus từ metadata phim |
| `recommendation/user_profile.py` | Xây dựng user preference vector từ interactions |
| `recommendation/vectorizer.py` | TF-IDF vectorizer + in-memory cache |
| `recommendation/explainer.py` | Giải thích ngắn cho user |
| `recommendation/explainer_admin.py` | Giải thích chi tiết cho admin (thesis defense) |

### Bước 1: Movie Profile (movie_profile.py)

Mỗi phim được chuyển thành 1 chuỗi text kết hợp:

```python
text = "{title} {title}"               # ×2 weight
     + " {overview}"                     # ×1
     + " {genres}"                       # ×1
     + " actor {name} actor {name}"      # ×1, prefix "actor" để phân biệt
     + " {keywords} {keywords}"          # ×2 weight
     + " director {name}"               # ×1, prefix "director"
```

**Trọng số bằng lặp lại text:**
- Title ×2 — token nhận dạng chính
- Keywords ×2 — tín hiệu chủ đề mạnh
- Overview ×1 — ngữ cảnh phong phú nhưng nhiều noise
- Genres ×1 — tín hiệu thể loại
- Cast ×1 — prefix "actor" để TF-IDF nhận dạng
- Director ×1 — prefix "director"

### Bước 2: TF-IDF Vectorization (vectorizer.py)

```python
TfidfVectorizer(
    max_features=5000,      # Tối đa 5000 features
    stop_words="english",   # Loại bỏ stopwords tiếng Anh
    ngram_range=(1, 2),     # Unigrams + bigrams
    min_df=1,               # Xuất hiện ít nhất 1 lần
    max_df=0.95,            # Bỏ từ xuất hiện >95% documents
)
```

- Cache in-memory — chỉ refit khi số lượng phim thay đổi
- Output: sparse matrix (n_movies × n_features)

### Bước 3: User Profile (user_profile.py)

Xây dựng user vector từ 3 nguồn tín hiệu:

**Tín hiệu tường minh (explicit):**

| Tín hiệu | Trọng số | Lý do |
|-----------|----------|-------|
| Rating 5/5 | 5.0 | Rất thích |
| Rating 4/5 | 3.0 | Thích |
| Rating 3/5 | 1.0 | Trung lập |
| Rating 2/5 | 0.0 | Loại bỏ |
| Rating 1/5 | 0.0 | Loại bỏ |
| Favorite | 3.0 | Tín hiệu mạnh |

**Tín hiệu ngầm (implicit — watch history):**

```
base_weight = 1.0 + (progress% / 100) × 2.0
  → 0%   = 1.0 (mở xem)
  → 50%  = 2.0 (xem nửa)
  → 100% = 3.0 (xem hết)

decay = 1.0 / (1.0 + days_since × 0.05)
  → hôm nay      = 1.00
  → 20 ngày trước = 0.50
  → 40 ngày trước = 0.33

watch_weight = base × decay (cap tại 3.0)
```

**Quy tắc kết hợp:**
- Nếu 1 phim xuất hiện ở nhiều nguồn → lấy MAX weight (không cộng dồn)
- Rating ≤ 2 bị loại bỏ
- User vector = weighted average của movie TF-IDF vectors → L2 normalize

### Bước 4: Cosine Similarity (engine.py)

```python
scores = cosine_similarity(user_vector.reshape(1, -1), movie_matrix).flatten()
```

- So sánh user vector (1 × n_features) với tất cả movie vectors (n_movies × n_features)
- Output: 1 score (0–1) cho mỗi phim
- Loại trừ phim user đã favorite
- Sắp xếp giảm dần, lấy top-N

### Bước 5: Cold-Start Handling

Khi user chưa có tương tác nào → `build_user_profile()` trả về `None` → fallback:
- Trả về phim mới nhất (ORDER BY release_date DESC)
- Score = 0.0
- Reason = "Popular movie — rate or favorite some movies for personalized picks!"

### Guest users (chưa đăng nhập)
- Frontend: `recommendationService.ts` kiểm tra `getToken()`, nếu null → trả về `[]`
- Không gọi API → không hiển thị gợi ý

### Dữ liệu cần thiết cho chất lượng gợi ý

| Dữ liệu | Ảnh hưởng |
|----------|-----------|
| Genres | ★★★★★ Tín hiệu mạnh nhất |
| Keywords | ★★★★ Tín hiệu chủ đề mạnh |
| Cast | ★★★ Gợi ý dựa trên diễn viên |
| Director | ★★ Gợi ý dựa trên đạo diễn |
| Overview | ★★ Ngữ cảnh bổ sung |
| Title | ★ Nhận dạng |

### Limitations
1. **Content-based only** — không có collaborative filtering
2. **Không học online** — cần restart để refit vectorizer khi thêm phim mới
3. **Cold-start cho phim mới** — phim vừa thêm chưa có interaction nào
4. **Phụ thuộc metadata** — phim thiếu genres/cast/keywords sẽ gợi ý kém
5. **Tiếng Anh only** — stopwords chỉ hỗ trợ English
6. **Cache đơn giản** — invalidate khi movie count thay đổi, không theo thời gian

---

## 7. Data Sources & Importers

> **Lưu ý:** Tất cả dữ liệu phim trong hệ thống đều do admin nhập/upload. Các importer script dưới đây chỉ là tiện ích tùy chọn để seed hoặc enrich metadata — KHÔNG phải nguồn gợi ý của AI. Hệ thống AI chỉ gợi ý phim có trong catalog website.

### Seed data
- `backend/app/seed.py` — 20 phim mẫu (Inception, Shawshank Redemption, etc.)
- Dùng poster URL từ TMDB (cho mục đích demo)

### Importer scripts (công cụ seed/enrich tùy chọn, KHÔNG phải nguồn gợi ý)

| Script | Nguồn | Import gì |
|--------|-------|-----------|
| `import_movielens.py` | MovieLens | Metadata + ratings only, KHÔNG có media |
| `import_wikidata.py` | Wikidata | Metadata (title, year, cast, director) |
| `import_wikimedia_commons.py` | Wikimedia | Images (chỉ license hợp lệ) |
| `import_loc_public_domain.py` | Library of Congress | Public domain films |
| `import_stock_assets.py` | Pexels/Pixabay/Unsplash | Backdrop/banner placeholders |

### `public_domain_movies.json`
- ~10 phim public domain với metadata đầy đủ
- Dùng cho import_loc_public_domain.py

---

## 8. Admin Movie Management

### Form hiện tại (sau khi đơn giản hóa)

**Các trường hiển thị:**
1. Title * (bắt buộc)
2. Overview
3. Release Year
4. Director
5. Genres — checkbox grid (18 thể loại chuẩn)
6. Cast / Actors — tag input
7. Keywords / Tags — tag input
8. Poster URL + upload file
9. Backdrop URL + upload file
10. Source Video — upload + HLS encoding

**Trường ẩn (collapsible):**
- "Advanced Source Information (Optional)" — source_name, source_url, license_type

**Trường ảnh hưởng AI:**
- Genres, Cast, Keywords — trực tiếp ảnh hưởng TF-IDF vector
- Overview, Title, Director — ảnh hưởng gián tiếp

---

## 9. Source / License / MovieAsset System

### Trạng thái: Đã cài đặt, ẩn khỏi UI mặc định

- **Movie-level:** 7 trường source/license trên bảng `movies` — chỉ 3 trường hiện trong Advanced section
- **MovieAsset:** Bảng riêng cho per-asset license — không hiện trong admin UI
- **Backend APIs:** Đầy đủ CRUD tại `/api/v1/movies/{id}/assets`
- **Frontend rendering:** SourceAttribution component hiển thị trên movie detail
- **Đánh giá:** Hệ thống này KHÔNG cần thiết cho phạm vi học thuật, là tính năng production nâng cao

---

## 10. Tests

| File | Số test | Lĩnh vực |
|------|---------|----------|
| `test_auth.py` | 20 | Đăng nhập, JWT, IP tracking, password reset |
| `test_movie_assets.py` | 9 | MovieAsset CRUD, license checker |
| `test_movies.py` | ~15 | CRUD phim, upload |
| `test_password_validator.py` | ~8 | Password strength |
| `test_user_profile.py` | ~10 | User profile builder, weighting |
| `test_watch_progress.py` | ~12 | Watch progress save/load |

**Framework:** pytest  
**Tổng:** ~74 tests  
**Lĩnh vực chưa test:** Recommendation engine end-to-end, email sending, HLS encoding

---

## 11. Deployment

| Mục | Chi tiết |
|-----|----------|
| **Server** | Ubuntu + Nginx reverse proxy |
| **Backend** | Uvicorn trên localhost:8010 |
| **Frontend** | Nginx phục vụ static build |
| **Database** | PostgreSQL |
| **Migrations** | `python -m alembic upgrade head` |
| **Build** | `npm run build` trong frontend/ |
| **Service** | systemd (laetus-backend) |

---

## 12. Đánh Giá Phạm Vi Học Thuật

### Tính năng TRỌNG TÂM cho luận văn
1. ★ **Thuật toán TF-IDF + Cosine Similarity** — cốt lõi
2. ★ **User profile building** (rating + favorite + watch history weighting)
3. ★ **Cold-start handling**
4. ★ **Admin RecsysMonitor** — giải thích thuật toán
5. ★ **Đánh giá phim + yêu thích** — tín hiệu cho AI

### Tính năng HỖ TRỢ
- CRUD phim, user auth, admin dashboard
- HLS video streaming
- Upload avatar, poster, backdrop

### Tính năng OVER-ENGINEERED cho học thuật
- Source/License/MovieAsset system — nên document là "future production enhancement"
- 5 data importers — chỉ cần cho production
- Security audit page
- IP login tracking chi tiết

### Khuyến nghị
- **Giữ** source/license như trường ẩn — không xóa backend code
- **Tập trung trình bày:** thuật toán AI, user profile weighting, RecsysMonitor
- **Demo:** tạo 2–3 user với profile khác nhau, so sánh gợi ý

---

## 13. Rủi Ro & Bước Tiếp Theo

### Rủi ro
1. **Dữ liệu mẫu ít** — 20 phim seed data hạn chế chất lượng gợi ý
2. **Thiếu collaborative filtering** — chỉ content-based
3. **Cache đơn giản** — vectorizer invalidate khi movie count thay đổi
4. **TMDB poster URLs** — seed data dùng URL từ TMDB (copyright concern)

### 5 bước tiếp theo thực tế
1. Import thêm phim từ MovieLens (ít nhất 100+ phim với metadata đầy đủ)
2. Tạo 5–10 test users với profiles khác nhau để demo
3. Viết unit tests cho recommendation engine end-to-end
4. Chuẩn bị demo RecsysMonitor cho thesis defense
5. Thay TMDB poster URLs bằng public domain images
