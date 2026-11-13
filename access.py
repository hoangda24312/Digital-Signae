"""Cổng duyệt: TV có được phép phát không."""
import asyncio
from config import APPROVED_FLAG

_registered = set()      # chỉ xin phép một lần mỗi lần chạy app, không gọi lại mỗi 10 giây


async def check_access(supabase, device_id):
    """
    'allow'   - được phép phát
    'denied'  - server nói rõ: chưa được duyệt
    'waiting' - chưa hỏi được server VÀ thiết bị chưa từng được duyệt
    """
    status = None
    try:
        if supabase is not None:
            status = await asyncio.to_thread(supabase.get_status, device_id)
    except Exception as e:
        print("check_access:", e)
        status = None

    if status == "approved":
        APPROVED_FLAG.touch()                 # có cờ này thì mất mạng vẫn phát video đã lưu
        return "allow"

    if status == "missing":                   # server chưa biết TV này -> tự xin phép
        if device_id not in _registered:
            try:
                await asyncio.to_thread(supabase.register_device, device_id)
                _registered.add(device_id)
            except Exception as e:
                print("register_device:", e)
        status = "pending"

    if status == "pending":
        APPROVED_FLAG.unlink(missing_ok=True)
        return "denied"

    return "allow" if APPROVED_FLAG.exists() else "waiting"     # status is None: không hỏi được
