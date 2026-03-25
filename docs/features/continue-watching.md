# Feature Spec: Continue Watching

## Mục tiêu

Hiển thị section "Continue Watching" trên HomePage với bộ phim gần nhất user đã xem chi tiết. Dữ liệu lưu localStorage, không cần backend.

## User Story

- Là user, khi tôi mở chi tiết một phim, hệ thống ghi nhận phim đó
- Khi quay về HomePage, tôi thấy section "Continue Watching" hiển thị phim vừa xem
- Reload trang vẫn giữ
- Mở phim khác thì cập nhật thành phim mới nhất

## Acceptance Criteria

1. Vào MovieDetailPage → phim được lưu vào localStorage
2. HomePage hiển thị section "Continue Watching" nếu có dữ liệu
3. Section ẩn nếu chưa xem phim nào
4. Reload → vẫn hiển thị đúng
5. Mở phim mới → cập nhật section
6. Không đổi API backend

## Test Cases

1. Xem detail phim A → về home → thấy phim A trong Continue Watching
2. Xem detail phim B → về home → Continue Watching cập nhật thành phim B
3. Reload → vẫn còn
4. localStorage bị corrupt → section ẩn, không crash
5. Movie thiếu poster_url → vẫn render được với placeholder
