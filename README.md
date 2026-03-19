# 🎬 Movie Recommendation & Streaming Web App

## 📌 Giới thiệu

Đây là dự án xây dựng **website xem phim trực tuyến tích hợp hệ thống gợi ý thông minh** dựa trên hành vi người dùng.

---

## 🎯 Mục tiêu

- Xây dựng hệ thống web fullstack hoàn chỉnh
- Tích hợp thuật toán gợi ý
- Hỗ trợ streaming video

---

## 🚀 Tính năng chính

### 👤 User
- Đăng ký / Đăng nhập
- Tìm kiếm và lọc phim
- Xem chi tiết phim
- Xem trailer/phim mẫu
- Đánh giá phim
- Lưu yêu thích
- Resume phim
- Continue watching

---

### 🤖 Recommendation
- Gợi ý phim tương tự
- Gợi ý cá nhân hóa
- Hiển thị lý do gợi ý

---

### 📊 Hệ thống
- Top phim phổ biến
- Thống kê người dùng

---

## 🧠 Công nghệ

- React
- FastAPI
- PostgreSQL
- scikit-learn
- FFmpeg + HLS
- Nginx

---

## 🏗️ Kiến trúc hệ thống

```text
Frontend (React)
        |
        v
Backend API (FastAPI)
        |
        +---------------------+
        |                     |
        v                     v
Recommendation Engine     Database (PostgreSQL)
        |
        v
Video Streaming (HLS + Nginx + FFmpeg)
