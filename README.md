# 🎬 Movie Recommendation & Streaming Web App

## 📌 Giới thiệu

Dự án xây dựng **website xem phim trực tuyến tích hợp hệ thống gợi ý phim thông minh**, trong đó người dùng có thể duyệt phim, xem chi tiết, lưu phim yêu thích, và nhận gợi ý phim tương tự dựa trên nội dung. Hệ thống được phát triển theo mô hình fullstack hiện đại với React + FastAPI.

---

## 🚀 Tính năng chính

| Tính năng | Mô tả |
|-----------|-------|
| 🎞️ **Duyệt phim** | Xem danh sách phim với poster, title, năm phát hành |
| 🔍 **Tìm kiếm & Lọc** | Search theo title, filter theo năm, sort theo A–Z / năm |
| ❤️ **Yêu thích** | Toggle favorite trên mỗi card, lưu localStorage, trang riêng |
| ▶️ **Continue Watching** | Ghi nhận phim xem gần nhất, hiển thị trên trang chủ |
| 🤖 **Gợi ý phim** | Recommendation dựa trên keyword title + năm phát hành |
| 📱 **Responsive** | Giao diện thích ứng desktop, tablet, mobile |

---

## 🧠 Công nghệ sử dụng

### Frontend
- **React 19** + **TypeScript**
- **Vite** — build tool
- **React Router** v7 — client-side routing
- **Vitest** — unit testing
- **localStorage** — client-side persistence (favorites, continue watching)

### Backend
- **FastAPI** — REST API
- **SQLAlchemy** — ORM
- **PostgreSQL** — database (hỗ trợ SQLite cho dev)
- **Pydantic** — schema validation
- **Alembic** — database migration
- **pytest** + **httpx** — API testing

---

## 🏗️ Kiến trúc hệ thống

```
Frontend (React + TypeScript + Vite)
        |
        v
Backend API (FastAPI)
        |
        +---------------------+
        |                     |
        v                     v
Recommendation Engine     Database (PostgreSQL)
(Frontend-based)
```

---

## 📁 Cấu trúc dự án

```
movie-recommendation-system/
├── frontend/
│   └── src/
│       ├── components/          # UI components
│       │   ├── MovieCard.tsx     #   Card phim (poster, title, favorite)
│       │   ├── Navbar.tsx        #   Navigation bar
│       │   ├── LoadingSpinner.tsx #   Loading state
│       │   └── ErrorMessage.tsx  #   Error state
│       ├── pages/               # Route pages
│       │   ├── HomePage.tsx      #   Trang chủ (search, filter, sort, continue watching)
│       │   ├── MovieDetailPage.tsx #  Chi tiết phim + recommendations
│       │   └── FavoritesPage.tsx #   Danh sách phim yêu thích
│       ├── hooks/               # Custom React hooks
│       │   ├── useMovies.ts     #   Fetch danh sách phim
│       │   ├── useFavorites.ts  #   Quản lý favorites state
│       │   ├── useContinueWatching.ts # Continue watching state
│       │   └── useRecommendations.ts  # Tính toán gợi ý
│       ├── services/            # API & localStorage services
│       │   ├── movieService.ts  #   API calls (getMovies, getMovieById)
│       │   ├── favoriteService.ts     # localStorage favorites
│       │   └── continueWatchingService.ts # localStorage continue watching
│       ├── utils/               # Pure utility functions
│       │   ├── recommendation.ts #   Thuật toán scoring gợi ý
│       │   └── movieFilters.ts  #   Search, filter, sort logic
│       ├── models/              # TypeScript interfaces
│       │   └── types.ts         #   Movie, MovieListItem, PaginatedMovies
│       ├── App.tsx              # Root component + routing
│       ├── App.css              # Global styles
│       └── index.css            # Base reset & typography
│
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── database.py          # Database connection & session
│   │   ├── seed.py              # Seed data
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── services/            # Business logic
│   │   └── routers/             # API endpoints
│   │       └── movies.py        #   /api/v1/movies
│   ├── tests/                   # pytest tests
│   └── requirements.txt
│
├── docs/
│   ├── features/                # Feature specs
│   ├── prompts/                 # AI prompt templates
│   └── workflow.md              # Development workflow
│
└── PROJECT_RULES.md             # Coding rules & conventions
```

---

## ⚙️ Cài đặt & Chạy

### Yêu cầu

- **Node.js** >= 18
- **Python** >= 3.10
- **PostgreSQL** (hoặc SQLite cho dev)

### 1. Clone project

```bash
git clone https://github.com/DungNgo13/movie-recommendation-system.git
cd movie-recommendation-system
```

### 2. Backend

```bash
cd backend

# Tạo virtual environment
python -m venv venv

# Kích hoạt (Windows)
venv\Scripts\activate

# Cài dependencies
pip install -r requirements.txt

# Chạy server
python -m uvicorn app.main:app --reload
```

Backend chạy tại: **http://localhost:8000**

API docs (Swagger): **http://localhost:8000/docs**

### 3. Frontend

```bash
cd frontend

# Cài dependencies
npm install

# Chạy dev server
npm run dev
```

Frontend chạy tại: **http://localhost:5173**

### 4. Chạy tests

```bash
# Frontend tests
cd frontend
npm run test:run

# Backend tests
cd backend
pytest
```

---

## 📡 API Overview

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `GET` | `/api/v1/movies?page=1&limit=20` | Danh sách phim (phân trang) |
| `GET` | `/api/v1/movies/{id}` | Chi tiết một phim |

**Response mẫu — GET /api/v1/movies:**

```json
{
  "items": [
    {
      "id": "uuid-string",
      "title": "Inception",
      "poster_url": "https://...",
      "release_year": 2010
    }
  ],
  "total": 50,
  "page": 1,
  "limit": 20
}
```

---

## 🎯 Demo Flow

1. **Trang chủ** — Hiển thị danh sách phim với search bar, filter năm, sort dropdown
2. **Tìm kiếm** — Gõ keyword → danh sách lọc real-time
3. **Yêu thích** — Bấm ♡ → phim được lưu, icon đổi thành ♥
4. **Xem chi tiết** — Click poster → trang detail với thông tin + phim gợi ý
5. **Recommendations** — Thuật toán gợi ý 4 phim dựa trên keyword title + năm
6. **Continue Watching** — Quay về trang chủ → section hiện phim vừa xem
7. **Favorites** — Vào trang /favorites → xem & quản lý tất cả phim yêu thích
8. **Persistent** — Reload trang → favorites + continue watching vẫn giữ

---

## 🤖 Thuật toán Recommendation

Hệ thống sử dụng **content-based filtering đơn giản** chạy ở frontend:

| Tiêu chí | Điểm |
|----------|------|
| Mỗi keyword trùng trong title | +3 |
| Cùng năm phát hành | +2 |
| Chênh lệch 1–2 năm | +1 |

- Loại bỏ stop words (the, a, of, ...) khi so sánh title
- Loại bỏ phim hiện tại khỏi kết quả
- Sắp xếp giảm dần theo score, lấy top 4

> ✅ **Ưu điểm**: Đơn giản, dễ giải thích, dễ demo, không cần model training
>
> 🔮 **Hướng phát triển**: Có thể nâng cấp sang content-based filtering thực thụ dùng TF-IDF hoặc word embeddings trên overview/genres

---

## 📊 Test Coverage

| Module | Tests | Mô tả |
|--------|-------|-------|
| `favoriteService` | 12 | localStorage CRUD, edge cases |
| `continueWatchingService` | 10 | localStorage persistence, validation |
| `recommendation` | 18 | Keyword extraction, scoring, ranking |
| `movieFilters` | 19 | Search, filter, sort, composed filters |
| **Tổng** | **59** | |

---

## 🔮 Hướng phát triển

- [ ] 🔐 Đăng ký / Đăng nhập (Authentication)
- [ ] ⭐ Đánh giá phim (Rating system)
- [ ] 🧠 Content-based filtering nâng cao (TF-IDF, cosine similarity)
- [ ] 👤 Collaborative filtering dựa trên user behavior
- [ ] 📺 Video streaming (HLS + Nginx + FFmpeg)
- [ ] 📊 Dashboard thống kê cho admin
- [ ] 🔔 Notification khi có phim mới
- [ ] 🌙 Dark mode toggle
- [ ] ♿ Accessibility improvements (ARIA, keyboard navigation)

---

## 👨‍💻 Tác giả

**Ngô Đăng Dũng** — Sinh viên CNTT

---

## 📝 License

Dự án phục vụ mục đích học tập và đồ án tốt nghiệp.
