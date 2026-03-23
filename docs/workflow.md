# Development Workflow

## 1. Tạo Feature Spec

* Tạo file trong docs/features/
* Ghi rõ:

  * mục tiêu
  * API
  * database
  * UI
  * test cases

---

## 2. Tạo Branch

* Naming:

  * feat/<feature-name>
  * fix/<bug-name>

---

## 3. Dùng Gemini Code Assist

* Sinh code theo spec
* Luôn yêu cầu:

  * clean code
  * đúng cấu trúc project
  * kèm test

---

## 4. Chạy test local

Frontend:

```
npm run test:run
```

Backend:

```
pytest
```

---

## 5. Debug nếu lỗi

* Copy error + code
* Gửi Gemini hoặc ChatGPT:

  * tìm root cause
  * fix tối thiểu

---

## 6. Review

* Gemini: review nhanh trong IDE
* ChatGPT: review logic + kiến trúc

---

## 7. Commit

* Viết message đúng chuẩn:

  * feat:
  * fix:
  * test:
  * docs:

---

## 8. Push

* GitHub Actions sẽ chạy test

---

## 9. Hoàn thành Feature

* Test pass
* Có thể demo
* Có tài liệu

---

## Nguyên tắc vàng

* Spec → Code → Test → Review → Commit
* Không code khi chưa có spec
