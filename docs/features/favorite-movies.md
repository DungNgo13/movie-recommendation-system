# Feature Spec: Favorite Movies

## Mục tiêu

Cho phép người dùng yêu thích/bỏ yêu thích phim ngay trên MovieCard. Trạng thái favorite được lưu ở `localStorage`, không cần backend.

## User Story

- Là user, tôi muốn bấm nút ♡ trên movie card để đánh dấu phim yêu thích
- Khi đã favorite, icon đổi thành ♥ (filled heart)
- Khi reload trang, trạng thái favorite vẫn được giữ
- Tôi có thể bấm lại để bỏ favorite

## Acceptance Criteria

1. Mỗi MovieCard hiển thị nút favorite (♡/♥)
2. Bấm nút toggle trạng thái favorite
3. Trạng thái lưu vào `localStorage` key `favoriteMovieIds`
4. Reload trang → trạng thái hiển thị đúng
5. Không thay đổi API backend
6. Không phá vỡ UI hiện tại

## API

Không cần API mới. Chỉ dùng `localStorage`.

## Database

Không thay đổi.

## UI

- Thêm nút heart icon ở góc trên bên phải movie card
- ♡ (outline) = chưa favorite
- ♥ (filled, màu đỏ) = đã favorite
- Nút không che poster, dễ bấm

## Test Cases

1. Toggle favorite → state đổi đúng
2. Reload trang → favorite vẫn giữ
3. Toggle nhiều lần → không lỗi
4. Movie id null/undefined → không crash
5. localStorage bị corrupt → xử lý gracefully
