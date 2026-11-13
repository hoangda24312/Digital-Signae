THỨ TỰ ÁP DỤNG
1. Supabase > SQL Editor: chạy trọn schema_v2.sql (một lần, tự hoàn tác nếu lỗi).
2. Chép các file .py (config, Database, access, network, player, playlist, schedule_logic,
   screens, state, storage, main) vào thư mục app, cùng chỗ với .env; xóa main.py / Database.py cũ.
3. Muốn phát YouTube: thêm "flet-webview" vào dependencies trong pyproject.toml (cùng chỗ flet-video).
4. flet build apk -v
Bảng video cũ đã đổi tên thành media; schedule không còn video_id mà trỏ tới playlist.
Ví dụ tạo công ty / nhóm / media / playlist / lịch nằm cuối schema_v2.sql.
