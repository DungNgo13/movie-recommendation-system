# PROJECT RULES

## Stack
- Frontend: React + TypeScript + Vite
- Backend: FastAPI + SQLAlchemy
- Database: PostgreSQL
- Testing:
  - Frontend: Vitest
  - Backend: pytest

## Coding Rules
- Mọi feature mới phải đi kèm test
- Không viết function quá dài nếu có thể tách nhỏ
- Router chỉ xử lý request/response, business logic nằm ở service
- Schema tách riêng khỏi model
- Code phải dễ đọc, đặt tên rõ nghĩa
- Không hard-code secrets
- Ưu tiên sửa ít, đúng chỗ, tránh phá code cũ

## Frontend Rules
- Component có logic thì cần test
- Tách API call khỏi UI component
- Dùng TypeScript rõ type, tránh any
- Có loading state và error state

## Backend Rules
- API mới phải có schema request/response
- API mới phải có pytest
- Service nên dễ test độc lập
- Validate input rõ ràng
- Trả lỗi HTTP hợp lý

## Recommendation Rules
- Ưu tiên giải pháp đơn giản, dễ demo, dễ giải thích
- Mọi hàm recommendation phải xử lý thiếu dữ liệu
- Không gợi ý phim user đã xem nếu logic yêu cầu loại bỏ

## Commit Rules
- Mỗi commit chỉ nên tập trung một feature nhỏ
- Commit message:
  - feat:
  - fix:
  - refactor:
  - test:
  - docs:

## AI Collaboration Rules
- Khi tạo code mới, luôn yêu cầu kèm test
- Khi refactor, phải giữ nguyên behavior cũ nếu không có yêu cầu khác
- Khi bug xuất hiện, phân tích root cause trước rồi mới sửa