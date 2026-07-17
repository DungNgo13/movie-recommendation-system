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
- **Metadata Discovery**: bấm vào đạo diễn, diễn viên hoặc keyword trên trang chi tiết phim để khám phá các phim liên quan ngay trong mục "Recommended for You" mà không rời trang

### 🤖 Recommendation Engine

- Content-based recommendation bằng **TF-IDF + Cosine Similarity**
- Tạo **movie profile** từ tiêu đề, mô tả, thể loại, diễn viên, đạo diễn, keywords
- Tạo **user profile** từ rating, favorites, watch history
- Cold-start fallback cho người dùng mới
- Giải thích lý do gợi ý để dễ demo trong báo cáo đồ án
- **Metadata Discovery Mode**: in-place khám phá phim theo đạo diễn, diễn viên, keyword ngay trên trang chi tiết phim — sử dụng `GET /api/v1/movies` với filter `director`, `cast`, `keyword`, `exclude` (tất cả là public, không yêu cầu auth)

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

