# 🎬 Mov-Sug — Movie Streaming & Recommendation System

Website xem phim trực tuyến tích hợp **hệ thống gợi ý thông minh**, hỗ trợ **video streaming bằng HLS**, quản trị nội dung phim, theo dõi hành vi người dùng và sinh gợi ý cá nhân hóa dựa trên lịch sử tương tác.

> Đây là đồ án theo hướng **fullstack + AI recommendation + video streaming**, phù hợp để demo học thuật, báo cáo tốt nghiệp và tiếp tục mở rộng thành sản phẩm thực tế.

---

## 📌 Tổng quan

Dự án tập trung giải quyết 3 bài toán chính:

- Xây dựng **web app xem phim** hoàn chỉnh cho người dùng và admin
- Tích hợp **recommendation engine** để đề xuất phim thông minh
- Hỗ trợ **streaming video theo chuẩn HLS** với nhiều mức chất lượng

Hệ thống hiện đã có đầy đủ các nhóm chức năng quan trọng như:

- Đăng ký / đăng nhập bằng JWT
- Quản lý phim, upload video, encode HLS
- Tìm kiếm, lọc phim, xem chi tiết
- Đánh giá phim, lưu yêu thích, lưu tiến độ xem
- Continue Watching / Resume video
- Gợi ý phim tương tự và gợi ý cá nhân hóa
- Dashboard quản trị và theo dõi dữ liệu hệ thống
- Password reset, audit bảo mật, email notification

---

## ✨ Tính năng nổi bật

### 👤 Dành cho người dùng

- Đăng ký / đăng nhập / xác thực JWT
- Xem danh sách phim và chi tiết phim
- Tìm kiếm theo tên, lọc theo thể loại
- Xem video bằng trình phát HLS
- Lưu tiến độ xem và xem tiếp từ vị trí trước đó
- Đánh giá phim theo sao
- Thêm / xóa phim yêu thích
- Nhận gợi ý cá nhân hóa dựa trên hành vi

### 🤖 Recommendation Engine

- Content-based recommendation bằng **TF-IDF + Cosine Similarity**
- Tạo **movie profile** từ tiêu đề, mô tả, thể loại, diễn viên, đạo diễn, keywords
- Tạo **user profile** từ rating, favorites, watch history
- Cold-start fallback cho người dùng mới
- Giải thích lý do gợi ý để dễ demo trong báo cáo đồ án

### 🎥 Streaming Engine

- Upload video phim từ trang admin
- Encode sang **HLS multi-quality** bằng FFmpeg
- Tự chọn các mức chất lượng phù hợp theo độ phân giải nguồn
- Có queue xử lý encode để tránh chạy nhiều FFmpeg cùng lúc
- Có chức năng hủy encode khi cần

### 🛠️ Dành cho quản trị viên

- Quản lý phim: CRUD, upload poster/backdrop/video
- Trigger encode HLS và theo dõi trạng thái xử lý
- Quản lý người dùng và phân quyền admin/user
- Force reset password cho user
- Dashboard thống kê hệ thống
- Audit log cho thao tác quản trị
- Security audit cho tài khoản người dùng

---

## 🧱 Kiến trúc hệ thống

```mermaid
flowchart LR
    A[Frontend - React + TypeScript + Vite] --> B[Backend API - FastAPI]
    B --> C[Recommendation Engine\nTF-IDF + Cosine Similarity]
    B --> D[(Database)]
    B --> E[FFmpeg + HLS Processing]
    E --> F[Nginx / HLS Delivery]
```

### Luồng chính

1. Admin upload video phim lên hệ thống
2. Backend đưa tác vụ encode vào queue
3. FFmpeg xử lý và sinh ra các file `.m3u8` + `.ts`
4. Frontend phát video qua `hls.js` / Plyr
5. Người dùng tương tác với phim (rating, favorite, watch progress)
6. Recommendation engine tổng hợp dữ liệu và trả về danh sách gợi ý

---

## 🧠 Công nghệ sử dụng

### Frontend

- React
- TypeScript
- Vite
- React Router
- Plyr
- hls.js
- CSS

### Backend

- FastAPI
- SQLAlchemy
- Pydantic
- JWT (`python-jose`)
- bcrypt
- Jinja2
- SMTP email service

### Recommendation / ML

- scikit-learn
- TF-IDF Vectorizer
- Cosine Similarity

### Video & Infra

- FFmpeg / FFprobe
- HLS
- Nginx

### Database

- **Development:** SQLite (default, zero-config)
- **Production:** PostgreSQL 14+ (recommended)

---

## 📂 Cấu trúc dự án gợi ý

```text
movie-recommendation-system/
├── backend/
│   ├── app/
│   │   ├── core/
│   │   ├── models/
│   │   ├── routers/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── main.py
│   ├── requirements.txt
│   └── ...
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   ├── hooks/
│   │   └── ...
│   ├── package.json
│   └── ...
├── media/
│   ├── images/
│   └── videos/
└── README.md
```

---

## 🚀 Hướng dẫn chạy project local

### 1) Yêu cầu môi trường

Cần cài sẵn:

- Python 3.10+
- Node.js 18+
- FFmpeg
- Git

---

### 2) Clone repository

```bash
git clone https://github.com/DungNgo13/movie-recommendation-system.git
cd movie-recommendation-system
```

---

### 3) Chạy Backend

```bash
cd backend
python -m venv .venv
```

**Windows**

```bash
.venv\Scripts\activate
```

**macOS / Linux**

```bash
source .venv/bin/activate
```

Cài thư viện:

```bash
pip install -r requirements.txt
```

Chạy server:

```bash
python -m uvicorn app.main:app --reload
```

Backend mặc định chạy tại:

```text
http://localhost:8000
```

---

### 3.5) Chuyển sang PostgreSQL (Production)

Dự án hỗ trợ cả SQLite (development) và PostgreSQL (production). Để chuyển sang PostgreSQL:

#### a) Cài đặt PostgreSQL

```sql
-- Trên PostgreSQL server:
CREATE DATABASE laetus_db;
CREATE USER laetus_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE laetus_db TO laetus_user;
```

#### b) Cập nhật `.env`

```env
DATABASE_URL=postgresql://laetus_user:your_secure_password@localhost:5432/laetus_db
```

#### c) Tạo schema bằng Alembic

```bash
cd backend
python -m alembic upgrade head
```

#### d) Migrate dữ liệu từ SQLite (nếu có)

```bash
# Đảm bảo DATABASE_URL trỏ tới PostgreSQL và SQLITE_SOURCE trỏ tới file SQLite
set SQLITE_SOURCE=sqlite:///./test.db
python scripts/migrate_sqlite_to_pg.py
```

Script sẽ:
- Copy toàn bộ users, movies, ratings, favorites, watch history, audit logs
- Giữ nguyên tất cả ID (UUID), timestamps
- An toàn để chạy lại (idempotent — dùng ON CONFLICT DO NOTHING)
- In bảng so sánh row count trước và sau migration

#### e) Rollback (nếu cần)

Đổi `DATABASE_URL` trong `.env` về `sqlite:///./test.db` và restart server. Dữ liệu SQLite không bị thay đổi.

---

### 4) Chạy Frontend

Mở terminal mới:

```bash
cd frontend
npm install
npm run dev
```

Frontend mặc định chạy tại:

```text
http://localhost:5173
```

---

## 🧪 Testing

### Frontend

```bash
npm run test:run
```

### Backend

```bash
pytest
```

> Nguyên tắc của project: feature mới nên đi kèm test, router chỉ xử lý request/response, business logic nằm ở service, hạn chế sửa lan rộng gây ảnh hưởng code cũ.

---

## 🔐 Một số điểm kỹ thuật đáng chú ý

- JWT authentication với thời hạn token cấu hình được
- Theo dõi IP đăng nhập gần nhất
- Cảnh báo brute-force khi đăng nhập sai nhiều lần
- Password reset cho user và admin-led reset
- Queue encode HLS giúp hệ thống ổn định hơn
- Fallback quality nếu encode multi-quality thất bại
- Guest watch history có thể merge vào tài khoản sau khi đăng nhập
- Guest favorites có thể merge vào tài khoản sau khi đăng nhập
- Dashboard hỗ trợ demo tốt cho phần báo cáo đồ án

---

## 📈 Trạng thái hiện tại của dự án

Dự án đã đạt mức **feature-complete cho demo đồ án**, bao gồm:

- Hệ thống user và admin hoạt động
- Streaming HLS hoạt động
- Recommendation engine hoạt động
- Các route frontend/backend khớp nhau
- Có kiểm soát watch history, favorites, ratings
- Có dashboard, audit log và security audit

### Một số điểm nên cải thiện thêm nếu muốn nâng cấp production

- ~~Chuyển database từ SQLite sang PostgreSQL~~ ✅ Đã hỗ trợ
- ~~Đưa API base URL sang biến môi trường~~ ✅ Đã có `VITE_API_BASE_URL`
- Bổ sung pagination cho một số màn hình admin
- ~~Chuẩn hóa migration bằng Alembic~~ ✅ Đã có
- ~~Mở rộng cấu hình CORS cho môi trường deploy thực tế~~ ✅ Đã có `CORS_ORIGINS`

---

## 🎓 Giá trị nổi bật cho đồ án tốt nghiệp

Dự án có lợi thế vì kết hợp được nhiều mảng trong cùng một hệ thống:

- **Fullstack Web Development**
- **Machine Learning / Recommendation System**
- **Multimedia Streaming**
- **Authentication & Security**
- **Admin Dashboard & Data Monitoring**

Điều này giúp đồ án có cả chiều sâu kỹ thuật lẫn khả năng trình diễn trực quan khi bảo vệ.

---

## 📋 Change Log

### 2026-07-14 — Fix Continue Watching / Resume Playback Regression

Restored the complete Continue Watching flow for both authenticated users and guests.

**Root cause**: `MovieDetailPage.tsx` called `recordWatch(data.id, 0)` on every page load (line 177–179). This fired `POST /api/v1/history/{movieId}` with `playback_position_seconds: 0`, which upserted the watch history record and **reset the saved playback position to zero**. The resume prompt would show the correct position (fetched on lines 158–163), but the database record was immediately overwritten to 0 by the `recordWatch` call that followed. On the next page load, the position was always 0 — too small to trigger the resume prompt.

**Fix**:
1. **Removed `recordWatch(data.id, 0)` call** — the watch history record is already created/updated by `saveWatchProgress()` during actual playback, so the initial zero-position write was unnecessary and destructive.
2. **Added `visibilitychange` handler** — saves progress when the tab becomes hidden (user switches tabs).
3. **Added `beforeunload` handler** — saves progress when the page/tab is closed.
4. **Added validation guards** — `Number.isFinite(currentTime)`, `Number.isFinite(duration)`, `duration > 0` checks in all save callbacks to prevent saving NaN/invalid values.
5. **Cleaned orphaned code** in `config.ts` (`configuredApiBaseUrl` variable and stale expression).

**Save behavior**:
| Trigger | Authenticated | Guest |
|---------|--------------|-------|
| Every 15s during playback | `POST /api/v1/watch-progress` | `localStorage` |
| On pause | ✅ immediate save | ✅ localStorage |
| On ended (100%) | ✅ marks completed | ✅ localStorage |
| On tab hidden | ✅ | ✅ |
| On page close | ✅ | ✅ |
| On route change (unmount) | ✅ | ✅ |

**Resume behavior**:
- Authenticated: `GET /api/v1/watch-progress/{movieId}` → show resume prompt if position ≥ 30s and not completed
- Guest: read `localStorage` `guest_watch_history` → show resume prompt if position ≥ 30s and progress < 95%
- User clicks "Resume" → `initialTime` set → HlsPlayer seeks to saved position
- User clicks "Start over" → `initialTime` set to 0

**Completion threshold**: ≥ 95% (backend `COMPLETION_THRESHOLD`). Completed movies return `current_time_seconds: 0` so replay starts from the beginning.

**Files changed**:
- `frontend/src/pages/MovieDetailPage.tsx` — Removed `recordWatch(data.id, 0)`, added `visibilitychange`/`beforeunload` handlers, added `Number.isFinite` guards
- `frontend/src/pages/MovieDetailPage.test.tsx` — Removed `recordWatch` mock
- `frontend/src/config.ts` — Removed orphaned `configuredApiBaseUrl` variable

**Verification steps**:
1. Play a movie for 30+ seconds → confirm progress save in Network tab
2. Pause → confirm immediate save request
3. Refresh → resume prompt appears with correct position
4. Click Resume → playback jumps to saved position
5. Switch tabs and return → progress preserved
6. Navigate away and return → resume prompt appears
7. Watch past 95% → movie disappears from Continue Watching
8. Guest: repeat steps 1–6 → localStorage updated, no API calls
9. Guest login → guest progress merged into authenticated data

```bash
cd frontend
npm run lint      # ✅ 0 errors
npm run build     # ✅ Passes
npm run test:run  # ✅ 104 tests passed
```

### 2026-07-14 — Movie Detail Banner Height Fix

Fixed the `.movie-banner__bg` element rendering at 2095px instead of the intended 650px on a 1920×1080 viewport.

**Root cause**: The `.movie-banner` CSS lacked `max-height`, `min-height`, and `isolation` constraints. While `height: 650px` was set and `overflow: hidden` clipped the visual overflow, the absolutely-positioned `.movie-banner__bg` (with `inset: 0`) could report an inflated `clientHeight` in certain layout conditions. The `__bg` also lacked explicit `width: 100%; height: 100%` alongside `inset: 0`, and had no `pointer-events: none`.

**Fix**: Hardened `.movie-banner` and `.movie-banner__bg` CSS:
- Added `max-height: 70vh`, `min-height: 420px`, `isolation: isolate` to `.movie-banner`
- Added explicit `width: 100%; height: 100%; pointer-events: none; background-repeat: no-repeat` to `__bg`
- Added responsive banner breakpoints at 1024px, 768px, and 480px

**DOM structure verified**: `.movie-player-container` is a sibling of `.movie-banner`, NOT a descendant. Rating, metadata, and recommendations are also outside the banner.

**Final desktop banner dimensions (1920×1080)**:
```
bannerHeight:           650
backgroundHeight:       650
backgroundParent:       movie-banner
playerInsideBanner:     false
```

**Responsive banner heights**:
| Viewport | Banner height | Min height |
|----------|--------------|------------|
| ≥1025px (desktop) | 650px | 420px |
| 769–1024px (tablet) | 480px | 380px |
| 481–768px (mobile) | 360px | 300px |
| ≤480px (small mobile) | 320px | 280px |

**Files changed**:
- `frontend/src/App.css` — Hardened `.movie-banner` and `__bg`, added responsive breakpoints
- `frontend/src/pages/MovieDetailPage.test.tsx` — **[NEW]** 12 DOM structure tests

**Verification**:
```javascript
// Run in DevTools at 1920×1080
const banner = document.querySelector(".movie-banner");
const bg = document.querySelector(".movie-banner__bg");
console.table({
  bannerHeight: banner?.clientHeight,      // 650
  backgroundHeight: bg?.clientHeight,      // 650
  backgroundParent: bg?.parentElement?.className,  // movie-banner
});
```

```bash
cd frontend
npm run lint      # ✅ 0 errors
npm run build     # ✅ Passes
npm run test:run  # ✅ 104 tests passed (12 new)
```

### 2026-07-14 — Responsive Video Player Sizing

Fixed oversized Plyr/HLS video player on the Movie Detail page. On a 1920×1080 desktop screen, the player previously expanded to the full page width (~1440px). It's now constrained to a centered 16:9 container capped at 1280×720px.

**Root cause**: The `<HlsPlayer>` component had an inline `style={{ width: '100%' }}` with no max-width constraint, and `.movie-detail-page` allowed up to 1600px width. Nothing bounded the player to a reasonable size.

**Fix**: Wrapped the HlsPlayer in a `.movie-player-container` div with:
- `width: min(100%, 1280px, calc((100vh - 160px) * 16 / 9))` — caps width at 1280px and shrinks on short viewports
- `aspect-ratio: 16 / 9` — maintains correct proportions
- `margin: 0 auto` — centered horizontally
- `border-radius: 12px` — rounded corners
- Viewport height protection — player won't exceed visible area on shorter screens

**Poster handling**:
- `.movie-player-container--backdrop` → `background-size: cover` (landscape backdrop fills the 16:9 area)
- `.movie-player-container--portrait-poster` → `background-size: contain` (portrait poster letterboxed with black bars, no distortion)

**Responsive breakpoints**:
| Viewport | Player width | Behavior |
|----------|-------------|----------|
| ≥1440px (large desktop) | 1280px max | Centered, 16:9 |
| 768–1439px (laptop/tablet) | 100% of content | Maintains 16:9 |
| <768px (mobile) | 100% | Reduced border-radius, 16:9 maintained |

**Fullscreen**: Normal-page max-width does NOT restrict fullscreen. When Plyr enters fullscreen, the container constraints are removed via `:has(.plyr--fullscreen-active)`.

**Files changed**:
- `frontend/src/pages/MovieDetailPage.tsx` — Wrapped HlsPlayer in `.movie-player-container` with backdrop/portrait modifier
- `frontend/src/components/HlsPlayer.tsx` — Replaced inline `style={}` with `.hls-player-inner` class
- `frontend/src/App.css` — Added `.movie-player-container` rules, poster variants, fullscreen override, mobile breakpoint

**Verification steps**:
1. Open a movie detail page at 1920×1080 → player is ~1280×720, centered
2. Resize to 1366×768 → player fills available width, maintains 16:9
3. Resize to mobile (390×844) → player is full-width, no horizontal scroll
4. Enter fullscreen → player fills entire screen
5. Exit fullscreen → player returns to 1280px max
6. Landscape backdrop fills the player area
7. Portrait-only poster is contained with black bars, not cropped
8. Quality switching, resume, progress bar all work normally

```bash
cd frontend
npm run lint      # ✅ 0 errors
npm run build     # ✅ Passes
npm run test:run  # ✅ 92 tests passed
```

### 2026-07-14 — Fix Production Media URLs (Mixed Content) & Star Rating UI

Two focused production fixes:

#### Issue A — Media URLs / Mixed Content

**Root cause**: The backend `normalize_url()` function in `movie.py` prepended the `BACKEND_URL` env var (e.g. `http://172.35.53.158`) to every relative media path, producing absolute HTTP URLs. When the frontend loaded on HTTPS (`https://tltn.laetus.io.vn`), Chrome blocked these insecure media requests as Mixed Content.

**Fix**: Rewrote `normalize_url()` to return **root-relative paths** (`/media/...`) instead of absolute URLs. This matches the existing avatar URL pattern (`_normalize_avatar_url` in `user.py`) and is scheme-agnostic — no Mixed Content possible. Stale HTTP URLs stored in the database are stripped to their `/media/...` path. Valid external HTTPS URLs are preserved.

Additionally, added a frontend `resolveMediaUrl()` safety function in `config.ts` that provides a second layer of defense against stale HTTP URLs reaching the browser.

**Production configuration**: No `BACKEND_URL` change needed. Media URLs are now root-relative and served via the existing Nginx `/media/` proxy rule. The `BACKEND_URL` env var is retained for backwards compatibility but is no longer used for media URL generation.

**Files changed**:
- `backend/app/schemas/movie.py` — Rewrote `normalize_url()` to root-relative paths, removed `_BACKEND_URL` and `import os`
- `backend/.env.example` — Updated `BACKEND_URL` documentation
- `backend/tests/test_normalize_url.py` — **[NEW]** 19 tests (unit + schema integration)
- `frontend/src/config.ts` — Added `resolveMediaUrl()` safety function
- `frontend/src/pages/MovieDetailPage.tsx` — Applied `resolveMediaUrl()` to HLS and image URLs
- `frontend/src/services/mediaUrl.test.ts` — **[NEW]** 14 tests for frontend resolver

#### Issue B — Star Rating Shows Numbers Instead of Icons

**Root cause**: `StarRating.tsx` rendered `{star}` (the loop variable 1–5) as button content instead of a star icon. No CSS existed to replace the number with a visual star.

**Fix**: Replaced `{star}` with an inline SVG 5-pointed star icon:
- **Filled** (gold `#f5c518`) when the star is ≤ current rating or hover position
- **Outlined** (gray stroke) when unselected
- 28px size, 4px gap between stars
- Hover preview across all 5 stars; restores saved rating on mouse leave
- `aria-label="Rate N out of 5"` and `aria-pressed` for screen readers
- Keyboard accessible: Tab, Enter, Space
- `disabled` prop disables all interactions

**Files changed**:
- `frontend/src/components/StarRating.tsx` — Full rewrite with inline SVG stars
- `frontend/src/App.css` — Added `.star-rating`, `.star-btn`, `.star-btn--filled` styles
- `frontend/src/components/StarRating.test.tsx` — **[NEW]** 18 tests

**Verification steps**:
1. Open a movie detail page → rating section shows 5 star icons (not numbers)
2. Hover across stars → preview fills stars up to hover position
3. Click star 4 → first 4 stars filled gold, rating saved
4. Refresh page → rating 4 persists
5. Open DevTools Network → no `http://` media requests (no Mixed Content)
6. Poster, backdrop, and HLS playlist load over same-origin `/media/...`
7. HLS video plays without errors

```bash
# Backend
cd backend
python -m pytest tests/test_normalize_url.py -v  # ✅ 19 passed

# Frontend
cd frontend
npm run lint      # ✅ 0 errors
npm run build     # ✅ Passes
npm run test:run  # ✅ 92 tests passed (32 new + 60 existing)
```

### 2026-07-14 — Guest Favorites (localStorage + Login Merge)

Guest users can now mark/unmark movies as favorites before logging in. Guest favorites are stored in `localStorage` and merged into the authenticated user's server-side favorites on login.

**Guest favorite behavior**:
- Clicking the heart icon on a movie card as a guest saves the movie ID to `localStorage` key `guest_favorite_ids`
- The heart icon turns red/gray immediately, same visual behavior as authenticated users
- Guest favorites persist across page refreshes (stored in `localStorage`)
- The Favorites page shows "You have N favorites saved locally" with a login/register prompt for guests

**Guest-to-user favorite migration flow**:
1. User logs in via Login page
2. Frontend reads `guest_favorite_ids` from `localStorage`
3. If any exist, frontend POSTs them to `POST /api/v1/favorites/me/merge`
4. Backend adds each movie ID to the user's favorites (skips duplicates and invalid IDs)
5. On success, frontend clears `localStorage` key `guest_favorite_ids`
6. On failure, `localStorage` data is preserved — will retry on next login

**localStorage key**: `guest_favorite_ids` — stores a JSON array of movie ID strings.

**API endpoint added**: `POST /api/v1/favorites/me/merge`
- Body: `{ "movie_ids": ["uuid-1", "uuid-2", ...] }` (max 100 IDs)
- Response: `{ "merged": <count> }` — number of newly added favorites
- Auth required (JWT)
- Invalid UUIDs and already-favorited movies are silently skipped

**Files changed**:
- `backend/app/schemas/favorite.py` — Added `GuestFavoriteMergeSchema`
- `backend/app/services/favorite_service.py` — Added `merge_guest_favorites()`
- `backend/app/routers/favorites.py` — Added `POST /me/merge` endpoint
- `backend/tests/test_favorites.py` — **[NEW]** 10 tests (service + endpoint)
- `frontend/src/services/favoriteService.ts` — Added guest localStorage functions + `mergeGuestFavorites()` API call
- `frontend/src/hooks/useFavorites.ts` — Guest mode: loads from localStorage when no user, toggles via localStorage
- `frontend/src/pages/LoginPage.tsx` — Merges guest favorites after login
- `frontend/src/pages/FavoritesPage.tsx` — Shows guest favorites count + login prompt
- `frontend/src/services/guestFavorites.test.ts` — **[NEW]** 12 tests for localStorage functions

**Verification steps**:
1. Open app in incognito (guest) → click heart on a movie → heart turns red
2. Refresh page → guest favorite persists (localStorage)
3. Click red heart → turns gray (unfavorited locally)
4. Open Favorites page as guest → shows "You have N favorites saved locally"
5. Mark 3 movies as favorites as guest
6. Register a new account → redirected to login
7. Log in → guest favorites merge into server-side favorites
8. Open Favorites page → all 3 movies appear
9. Confirm `localStorage.getItem('guest_favorite_ids')` returns `null` after login
10. Log out → hearts are gray on Home page (localStorage was cleared)

```bash
# Backend
cd backend
python -m pytest tests/test_favorites.py -v  # ✅ 10 passed

# Frontend
cd frontend
npm run lint      # ✅ 0 errors
npm run build     # ✅ Passes
npm run test:run  # ✅ 60 tests passed (12 new + 48 existing)
```

### 2026-07-14 — Movie Card Favorite Heart Icon UI

Replaced the clipped text-based "Favorite" button on movie cards with a compact SVG heart icon button.

**Root cause**: The previous `.favorite-btn` rendered the text "Favorite" / "Favorited" inside a 34×34px circular button. The text overflowed the button and was clipped by `.movie-card { overflow: hidden }`, producing a visually broken control.

**Fix**: Replaced the text content with a small inline SVG heart icon (`HeartIcon` component). The heart renders as an outlined gray icon when not favorited and a solid red icon when favorited. The button is now positioned inside the poster container (not on the card root) so it cannot be clipped by the card boundary.

**Files changed**:
- `frontend/src/components/HeartIcon.tsx` — **[NEW]** Inline SVG heart icon component (filled / outlined)
- `frontend/src/components/MovieCard.tsx` — Replaced text button with `HeartIcon`; added `favoriteLoading` prop; improved `aria-label` with movie title
- `frontend/src/components/RecommendationCard.tsx` — Same heart icon treatment; added poster wrapper div for correct positioning
- `frontend/src/App.css` — Replaced `.favorite-btn` styles with BEM-named `.movie-card__favorite-button` styles (38px, blurred backdrop, focus-visible ring, disabled state, responsive sizing)
- `frontend/src/components/FavoriteHeart.test.tsx` — **[NEW]** 18 component tests covering visual states, click behavior, navigation prevention, disabled state, accessible labels, rollback, and both card types
- `frontend/src/test/setup.ts` — **[NEW]** Vitest setup for `@testing-library/jest-dom`
- `frontend/vite.config.ts` — Added Vitest `test` config with `jsdom` environment

**How favorite state is loaded and synchronized**:
1. `useFavorites` hook fetches all favorite IDs once via `GET /api/v1/favorites/me/ids`
2. Pages pass `isFavorite(id)` and `toggleFavorite` to each card
3. `toggleFavorite` uses optimistic updating — UI updates immediately, rolls back on API failure
4. Both `MovieCard` and `RecommendationCard` share the same state via the hook

**How navigation is prevented when clicking the heart**:
The `handleFavoriteClick` handler calls both `e.preventDefault()` and `e.stopPropagation()` to prevent the click from propagating to the wrapping `<Link>` element.

**Verification steps**:
1. Open Home page → standard movie cards show gray/red heart icons (not text)
2. Open Recommended for You → same heart icon treatment
3. Click gray heart → turns red (favorited)
4. Refresh page → favorite state persists
5. Click red heart → turns gray (unfavorited)
6. Click heart → does not open movie detail page
7. Open Favorites page → click red heart → movie removed without page refresh
8. Cards with missing posters → heart correctly positioned on placeholder

```bash
cd frontend
npm run lint      # ✅ 0 errors
npm run build     # ✅ Passes
npm run test:run  # ✅ 48 tests passed (18 new + 30 existing)
```

### 2026-07-12 — HLS 4K Support & Quality Switching Fix (v2)

Two HLS/video playback fixes (backend quality ladder + frontend player).

#### 1. HLS Converter — 4K/1440p Quality Ladder

**Root cause**: The quality ladder in `hls_service.py` only defined tiers up to 1080p. A 4K source (3840×2160) would only produce 1080p/720p/480p/360p output.

**Fix**: Extracted a testable `select_hls_qualities(source_height)` helper function and added two new tiers:

| Quality | Bitrate | Condition |
|---------|---------|-----------|
| 2160p | 14 000 kbps | source ≥ 2160px |
| 1440p | 9 000 kbps | source ≥ 1440px |
| 1080p | 5 000 kbps | source ≥ 1080px *(was 4000k)* |
| 720p | 2 800 kbps | source ≥ 720px *(was 2000k)* |
| 480p | 1 200 kbps | source ≥ 480px |
| 360p | 800 kbps | always included |

No upscaling ever occurs — only tiers ≤ source height are generated.

**Files changed**:
- `backend/app/services/hls_service.py` — new `select_hls_qualities()` + updated `_build_multi_quality_cmd()`
- `backend/tests/test_movies.py` — 5 quality ladder unit tests

**How to verify 4K output**:
```bash
# After re-processing a 4K movie, inspect master playlist:
grep "RESOLUTION" media/videos/hls/movie_<id>/master.m3u8
# Expected: RESOLUTION=3840x2160, 2560x1440, 1920x1080, 1280x720, 854x480, 640x360
```

> **Important**: Movies processed before this fix must be re-processed (click "Process HLS" again in admin) to generate the new 4K variants. The old master playlist only contains up to 1080p.

#### 2. HLS Player — Quality Switching & 4K Menu Fix

Three root causes were found and fixed in `HlsPlayer.tsx`:

**Root cause 1 — Circular LEVEL_SWITCHED → onChange loop**:
When hls.js completed a level switch, the `LEVEL_SWITCHED` handler updated `player.quality` to sync the Plyr badge. But setting `player.quality` triggers Plyr's `set quality()` setter, which calls our `onChange` callback **again**, which sets `hls.currentLevel` **again** — creating a circular loop that caused the video to freeze while the progress bar kept moving.

**Fix**: Added a `levelSwitchInProgress` guard flag. The `LEVEL_SWITCHED` handler sets it before touching `player.quality`, and `onChange` checks it to bail out immediately if the change was triggered by the level-switch sync, not by the user.

**Root cause 2 — Harmful `startLoad()` call**:
The previous fix called `hls.startLoad(pos)` after setting `currentLevel`. This interfered with hls.js's internal level-switch state machine, which already handles segment loading when `currentLevel` changes. The double-load caused buffer confusion and stalls.

**Fix**: Removed the `startLoad()` call from `onChange`. hls.js handles segment loading internally. Used `requestAnimationFrame` before `video.play()` to give the browser one frame to process the level change.

**Root cause 3 — Stale cached .m3u8 hiding 4K qualities**:
After re-processing a movie with 4K support, the browser could serve the old cached master playlist that only contained 1080p variants. This made the Plyr quality menu not show 1440p/2160p even though the backend generated them.

**Fix**: Added cache-busting timestamp query parameter to the HLS playlist URL (`?v=<timestamp>`), ensuring the browser always fetches the latest master playlist.

**Additional improvements**:
- Development-only diagnostic logs for MANIFEST_PARSED, LEVEL_SWITCHED, and ERROR events
- Improved error recovery: NETWORK_ERROR passes current position to `startLoad()`, MEDIA_ERROR resumes playback after recovery

**How to verify quality switching**:
1. Hard refresh browser (Ctrl+Shift+R)
2. Open a movie with multiple HLS qualities
3. Open DevTools Console (development mode shows `[HLS]` level logs)
4. Start playback
5. Confirm quality menu shows Auto, 2160p, 1440p, 1080p, 720p, 480p, 360p (for 4K source)
6. Switch quality: 2160p → 1080p → 720p → 2160p
7. Confirm: video image continues, audio continues, progress bar continues, no manual pause/play needed

#### Verification

```bash
# Backend
cd backend
python -m pytest tests/test_movies.py::TestSelectHlsQualities -v  # 5 passed
python -m pytest tests/ -v                                         # 120 passed, 1 pre-existing failure

# Frontend
cd frontend
npm run lint      # ✅ 0 errors
npm run build     # ✅ Passes
npm run test:run  # ✅ 30 tests passed
```

> **Note**: 4K encoding is CPU-intensive (may take 10–30+ minutes depending on source length and server). Disk usage for 4K HLS output can be substantial. For demo purposes, shorter clips (30s–2min) are recommended.

---

## 🔄 Continue Watching — Data Flow & Architecture

### Canonical save/load data flow

```
┌─────────────────────────────────────────────────────────────────┐
│  HlsPlayer.tsx                                                  │
│  <video> dispatches: timeupdate, pause, ended                   │
│  Handlers read: video.currentTime, video.duration               │
└────────────────────┬────────────────────────────────────────────┘
                     │ callbacks (onTimeUpdate, onPause, onEnded)
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  MovieDetailPage.tsx                                             │
│  handleTimeUpdate: throttled every 15s of position change       │
│  handlePause: saves immediately on pause                        │
│  handleEnded: saves at 100% progress                            │
│  saveProgressFromRefs: saves on unmount / visibilitychange /     │
│    beforeunload (uses keepalive fetch for page-exit reliability) │
└────────────────────┬────────────────────────────────────────────┘
                     │ saveWatchProgress(movieId, currentTime, duration)
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  continueWatchingService.ts                                      │
│  POST ${API_BASE_URL}/watch-progress                             │
│  Body: { movie_id, current_time_seconds, duration_seconds,       │
│          progress_percent }                                      │
│  Headers: Authorization: Bearer <token>                          │
└────────────────────┬────────────────────────────────────────────┘
                     │ HTTP POST
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Backend: watch_progress.py → history_service.save_watch_progress│
│  Upsert into watch_history table (unique: user_id + movie_id)   │
│  Sets is_completed = true when progress_percent >= 95           │
└─────────────────────────────────────────────────────────────────┘
```

### API endpoints

| Purpose | Method | Endpoint | Used by |
|---------|--------|----------|---------|
| Save progress | POST | `/api/v1/watch-progress` | `saveWatchProgress()` |
| Get resume position | GET | `/api/v1/watch-progress/{movie_id}` | `getWatchProgress()` |
| Continue Watching list | GET | `/api/v1/history/me?limit=N` | `getWatchHistory()` |
| Legacy record watch | POST | `/api/v1/history/{movie_id}` | `recordWatch()` (unused in normal flow) |

Both `/watch-progress` and `/history` endpoints read/write the **same `watch_history` table**.

### Database verification

```sql
-- Check a user's watch progress
SELECT user_id, movie_id, playback_position_seconds, duration_seconds,
       progress_percent, is_completed, watched_at
FROM watch_history
WHERE user_id = '<user-uuid>'
ORDER BY watched_at DESC;
```

### Deployment verification

```bash
# Verify frontend build matches deployed files
grep -oE 'assets/[^"]+\.js' frontend/dist/index.html
# Compare with production
curl -s https://tltn.laetus.io.vn | grep -oE 'assets/[^"]+\.js'

# Verify CORS allows the frontend origin
# In backend .env on the production server:
# CORS_ORIGINS must include the frontend domain (e.g. https://tltn.laetus.io.vn)
```

### Verified root cause (2025-07-15)

The Continue Watching feature was not working in production due to **four compounding issues**:

1. **Silent error swallowing**: `saveWatchProgress()` had no `try/catch` and no response status checking. Failed saves (401, CORS errors, network failures) were invisible.

2. **Unreliable page-exit saves**: `beforeunload` and `visibilitychange` handlers used regular async `fetch()` which browsers cancel during page close. Saves on tab-close or navigation were lost.

3. **Stale Continue Watching list**: The HomePage `useEffect` for fetching watch history only depended on `user` — navigating Home→Movie→Home did not trigger a refetch, so newly saved progress never appeared.

4. **Production CORS configuration**: The backend `CORS_ORIGINS` env var must include the actual frontend domain. If missing, all cross-origin `POST /watch-progress` requests are silently blocked by the browser.

**Backend was correct** — upsert semantics, shared `watch_history` table, proper schema. No backend changes were needed.

---

## 📋 Change Log

### 2025-07-15 — Fix Continue Watching save/load/display

**Files changed:**
- `frontend/src/services/continueWatchingService.ts` — Added error handling, response logging, `keepalive` fetch option, new `saveWatchProgressBeacon()` for page-exit saves
- `frontend/src/pages/MovieDetailPage.tsx` — Uses beacon save for `beforeunload`/`visibilitychange`, added dev diagnostics
- `frontend/src/pages/HomePage.tsx` — Added `location.key` dependency so Continue Watching list refetches on navigation
- `frontend/src/components/HlsPlayer.tsx` — Added dev-only video event diagnostics
- `frontend/src/services/continueWatchingService.test.ts` — New: 20 tests for service HTTP calls, error handling, and guest localStorage
- `frontend/src/pages/MovieDetailPage.test.tsx` — Updated mock to include `saveWatchProgressBeacon`

**Test results:**
- Frontend: 124 tests passed, 0 failed
- Backend: 15 watch-progress tests passed, 0 failed
- Build: clean (`tsc -b && vite build`)

### 2025-07-15 — Fix Guest Continue Watching (complete read/render/resume flow)

**Root cause:** Guest watch progress was written to localStorage but never consumed.
- `HomePage.tsx` returned early with `if (!user) return;` — guest CW was never loaded
- `MovieDetailPage.tsx` used `MIN_RESUME_SECONDS = 30` — a 31-second movie at 92% (position ≈ 28s) could never trigger resume
- `GuestWatchEntry` schema was missing `is_completed`, `updated_at`, and used `current_time_seconds` instead of `playback_position_seconds`

**Guest localStorage Schema (`guest_watch_history`):**
```typescript
interface GuestWatchEntry {
  movie_id: string;                // UUID of the movie
  playback_position_seconds: number; // current position in seconds (integer)
  duration_seconds: number;        // total duration in seconds (integer)
  progress_percent: number;        // 0–100 (clamped, 2 decimals)
  is_completed: boolean;           // true when progress_percent >= 95
  updated_at: string;              // ISO 8601 timestamp of last save
}
```

**Completion threshold:**
- `isWatchCompleted(progressPercent) → progressPercent >= 95` (shared function)
- Same 95% rule for both guest and authenticated users
- Backend uses identical threshold in `history_service.py`
- A 31-second movie at 92.17% is **not completed** and appears in Continue Watching

**Guest Continue Watching on HomePage:**
- When `user === null`, reads `guest_watch_history` from localStorage
- Resolves movie metadata by matching `movie_id` against already-loaded catalog (no extra API calls)
- Filters: `!is_completed && progress_percent > 0 && playback_position_seconds > 0`
- Sorted by `updated_at` descending (most recently watched first)
- Shows poster, title, progress bar, percentage, and resume time badge
- Refreshes on: mount, navigation (location.key), `guest-watch-history-updated` custom event, `storage` event (cross-tab)

**Guest Resume on MovieDetailPage:**
- `MIN_RESUME_SECONDS` lowered to 3 (was 30) for both guest and authenticated
- When `playback_position_seconds >= 3 && !isWatchCompleted(progress_percent)`, shows resume prompt
- Resume prompt: "Continue from **00:28**?" with Resume / Start Over buttons
- Resume seeks to saved position; Start Over begins at 0

**Old localStorage Migration:**
- Old entries `{ movie_id, duration_seconds, progress_percent }` auto-migrate on read
- Derives `playback_position_seconds = floor(duration * percent / 100)`
- Old `current_time_seconds` field mapped to `playback_position_seconds`
- Missing `is_completed` computed from 95% rule
- Missing `updated_at` set to epoch (sorts last)

**Guest-to-Account Merge:**
- On login, `getGuestWatchHistory()` reads + migrates entries
- Maps `playback_position_seconds` → `current_time_seconds` for backend payload
- Sends via `guest_history` field in login request
- localStorage cleared only after successful login
- Failed login preserves guest history

**Verification steps:**
1. Log out. Clear `guest_watch_history` in DevTools
2. Open a 31-second movie, watch to ~50%, pause
3. Verify `guest_watch_history` in localStorage has `playback_position_seconds ≈ 15`, `is_completed: false`
4. Navigate to Home → "Continue Watching" section visible
5. Open movie → "Continue from 00:15?" prompt visible
6. Click Resume → playback starts near 15s
7. Watch to 92% → still shows in Continue Watching (below 95%)
8. Finish the movie → disappears from Continue Watching (`is_completed: true`)
9. Log in → guest progress merges to server, localStorage cleared

**Files changed:**
- `frontend/src/services/continueWatchingService.ts` — Canonical `GuestWatchEntry` with `is_completed`/`updated_at`/`playback_position_seconds`, shared `isWatchCompleted(95%)`, `formatPlaybackTime()`, old entry migration, `GUEST_HISTORY_EVENT` custom event
- `frontend/src/pages/HomePage.tsx` — Guest Continue Watching section reading localStorage, resolving movie metadata from catalog, custom event + storage event listeners
- `frontend/src/pages/MovieDetailPage.tsx` — `MIN_RESUME_SECONDS` lowered to 3, uses `isWatchCompleted()` and `formatPlaybackTime()`
- `frontend/src/pages/LoginPage.tsx` — Maps canonical `playback_position_seconds` → `current_time_seconds` for backend merge payload
- `frontend/src/services/continueWatchingService.test.ts` — 48 tests covering completion threshold, formatPlaybackTime, guest schema, old migration, short videos, custom event
- `frontend/src/pages/MovieDetailPage.test.tsx` — Updated mock with new exports

**Test results:**
- Frontend: 152 tests passed, 0 failed
- Backend: 15 watch-progress tests passed, 0 failed
- Build: clean (`tsc -b && vite build`)

### 2025-07-15 — Redesign Continue Watching card presentation

**Root cause:** The previous CW card used inline styles to overlay a 4px progress bar directly on the movie poster edge, with metadata (`▶ 00:29 · 91%`) rendered outside the card in a disconnected badge. There was no proper footer, no title spacing from the progress bar, and no accessible markup.

**New design — `ContinueWatchingCard` component:**
```
┌──────────────────────────┐
│         Poster           │
│      (2:3 aspect)        │
│                   ❤      │
├──────────────────────────┤
│  Movie Title             │
│  ▬▬▬▬▬▬▬▬▬▬▬▬░░░░ 6px   │  ← progress bar with rounded ends
│  ▶ 02:00           42%  │  ← playback time + percentage
└──────────────────────────┘
```

**Progress bar styling:**
- Height: 6px desktop, 5px mobile
- Fully rounded ends (`border-radius: 9999px`)
- Track: `oklch(0.49 0.028 255 / 0.18)` (muted, blends with design system)
- Fill: gradient from `--destructive` to `oklch(0.66 0.18 18)` (warm accent gradient)
- Smooth 240ms width transition
- All values clamped 0–100 and NaN/Infinity → 0

**Accessibility:**
- `role="progressbar"` with `aria-valuemin`, `aria-valuemax`, `aria-valuenow`
- `aria-label="Watched N% of Movie Title"`
- Play icon marked `aria-hidden="true"`
- Percentage text remains visible alongside the bar

**Responsive behavior:**
- Desktop: 200px card width, 16px content padding, 6px progress bar
- Mobile (≤640px): 160px card width, 13px padding, 5px progress bar, 0.8125rem meta text

**Verification steps:**
1. Open a movie as guest, watch to ~42%, pause
2. Navigate Home → CW card shows poster + title + 42% bar + "▶ 01:08 42%"
3. All metadata is inside the card footer — nothing floats outside
4. Progress bar has rounded ends and accent gradient fill
5. Favorite heart button remains clickable on the poster
6. Clicking the card navigates to `/movie/{id}`
7. Test with 2%, 23%, 50%, 91%, 94% — bar fill matches each value accurately
8. On mobile viewport, card and text remain readable without horizontal overflow

**Files changed:**
- `frontend/src/components/ContinueWatchingCard.tsx` — **New**: dedicated card component with clamped progress, accessible progressbar, formatted time, poster + footer layout
- `frontend/src/components/ContinueWatchingCard.test.tsx` — **New**: 23 tests for progress rendering, clamping, accessibility, card navigation, favorites
- `frontend/src/pages/HomePage.tsx` — Both auth and guest CW sections now use `ContinueWatchingCard` instead of inline styles
- `frontend/src/App.css` — New `.cw-card` ruleset with design-system OKLCH tokens, responsive breakpoint

**Test results:**
- Frontend: 175 tests passed, 0 failed
- Build: clean (`tsc -b && vite build`)

---

## 🔗 Repository

```text
https://github.com/DungNgo13/movie-recommendation-system
```

---

## 👨‍💻 Tác giả

Phát triển cho mục tiêu học tập, nghiên cứu và báo cáo đồ án tốt nghiệp.

Nếu dùng README này để public repo, có thể bổ sung thêm:

- ảnh chụp giao diện hệ thống
- link demo video
- sơ đồ database
- tài liệu báo cáo / slide bảo vệ

