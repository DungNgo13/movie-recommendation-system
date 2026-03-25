# Feature Spec: Simple Recommendation

## Mục tiêu

Hiển thị section "Recommended Movies" trên MovieDetailPage. Gợi ý 4 phim tương tự dựa trên title keyword matching + release year proximity. Logic tính toán hoàn toàn ở frontend.

## User Story

- Là user, khi tôi xem chi tiết một phim, tôi muốn thấy các phim tương tự được gợi ý
- Tôi có thể bấm vào phim gợi ý để xem chi tiết phim đó

## Acceptance Criteria

1. MovieDetailPage hiển thị section "Recommended Movies" bên dưới thông tin phim
2. Section hiển thị tối đa 4 phim gợi ý
3. Không hiển thị lại chính phim hiện tại
4. Nếu không đủ score thì fallback sang các phim khác
5. Có thể click vào phim gợi ý để sang detail
6. Không đổi API backend

## Thuật toán scoring

- +3 điểm cho mỗi keyword trùng trong title (bỏ qua stop words ngắn)
- +2 điểm nếu cùng release_year
- +1 điểm nếu chênh lệch 1–2 năm
- Bỏ qua phim hiện tại
- Sắp xếp giảm dần theo score, lấy top 4

## Test Cases

1. Phim có title tương tự → xuất hiện trong recommendations
2. Phim cùng năm → score cao hơn phim khác năm
3. Phim hiện tại không xuất hiện trong recommendations
4. Fallback khi không có match tốt
5. Danh sách rỗng → section ẩn
