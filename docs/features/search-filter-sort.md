# Feature Spec: Search / Filter / Sort

## Mục tiêu

Cho phép user search, filter theo year, và sort danh sách phim trên HomePage. Tất cả xử lý ở frontend.

## User Story

- Là user, tôi muốn gõ keyword để tìm phim theo title
- Tôi muốn filter theo năm phát hành
- Tôi muốn sort theo title hoặc năm
- Tôi có thể kết hợp cả 3 cùng lúc

## Acceptance Criteria

1. Ô search lọc theo title, case-insensitive
2. Dropdown year filter với "All Years" + các năm có trong data
3. Dropdown sort: Title A-Z, Title Z-A, Newest First, Oldest First
4. Hiển thị "No movies found." nếu không có kết quả
5. Không đổi API backend
6. Continue Watching section không bị ảnh hưởng

## Test Cases

1. Search "dark" → chỉ hiện phim có "dark" trong title
2. Filter year 2008 → chỉ phim năm 2008
3. Sort Title A-Z → đúng thứ tự alphabetical
4. Kết hợp search + filter → đúng kết quả
5. Xóa search → hiện lại tất cả
6. Không kết quả → hiện "No movies found."
