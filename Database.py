"""Nói chuyện với Supabase. Mọi hàm ở đây là hàm ĐỒNG BỘ (chặn).
Trong code async phải gọi qua `await asyncio.to_thread(supabase.ten_ham, ...)`.

TV chỉ gọi 4 hàm RPC trong schema_v2.sql, không đọc thẳng các bảng, nên RLS của bảng không ảnh hưởng."""
from supabase import Client, create_client, PostgrestAPIError


class SupaBase:
    def __init__(self, url, key):
        self.supabase: Client = create_client(url, key)

    def get_status(self, device_id):
        """'approved' | 'pending' = trạng thái duyệt trên server
        'missing' = server trả lời được nhưng chưa có TV này
        None      = không hỏi được (mất mạng / lỗi Supabase)"""
        try:
            r = self.supabase.rpc("get_device_status", {"p_device_id": device_id}).execute()
            return r.data if r.data else "missing"
        except PostgrestAPIError as e:
            print("Error get_status:", e)
            return None
        except Exception as e:          # lỗi mạng (httpx...) không phải PostgrestAPIError
            print("Error get_status:", e)
            return None

    def register_device(self, device_id):
        """TV mới tự xin phép: tạo dòng ở trạng thái chưa duyệt (có rồi thì không làm gì)."""
        try:
            return self.supabase.rpc("register_device", {"p_device_id": device_id}).execute().data
        except Exception as e:
            print("Error register_device:", e)
            return None

    def get_schedules(self, device_id):
        """TOÀN BỘ lịch của nhóm TV này thuộc về, mỗi lịch kèm danh sách nội dung của playlist.
        Trả về list (có thể rỗng). Lỗi mạng / lỗi Supabase được NÉM RA để scheduler dùng bản lưu."""
        r = self.supabase.rpc("get_device_schedules", {"p_device_id": device_id}).execute()
        return r.data or []

    def heartbeat(self, device_id, ip=None, media_id=None, schedule_id=None,
                  playback_state=None, app_version=None):
        """Báo 'TV còn sống' + đang phát gì. Giờ do SERVER ghi (last_heartbeat = now()).
        Lỗi mạng được ném ra cho vòng heartbeat xử lý."""
        self.supabase.rpc("device_heartbeat", {
            "p_device_id": device_id, "p_ip": ip, "p_media_id": media_id,
            "p_schedule_id": schedule_id, "p_playback_state": playback_state,
            "p_app_version": app_version,
        }).execute()
