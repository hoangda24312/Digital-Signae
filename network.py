"""Các lời gọi mạng thuần: không đụng giao diện, không đụng Supabase."""
import httpx


async def get_ip():
    """IP public của TV, hoặc None nếu không lấy được."""
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get("https://api.ipify.org?format=json")
            r.raise_for_status()
            return r.json()["ip"]
    except Exception as e:
        print("Không lấy được IP:", e)
        return None


async def check_mb(url: str):
    """Dung lượng file (MB) bằng request HEAD, không tải video.
    Trả về None nếu không biết (mất mạng, server không trả Content-Length...)."""
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.head(url, follow_redirects=True)
            response.raise_for_status()
            content_length = response.headers.get("Content-Length")
        if content_length:
            return int(content_length) / (1024 * 1024)   # byte -> MB
        return None
    except Exception:
        return None


async def ping_internet(client: httpx.AsyncClient) -> bool:
    """Có internet không? (client do người gọi tạo sẵn để dùng lại)"""
    try:
        r = await client.get("https://www.gstatic.com/generate_204")
        return r.status_code in (200, 204)
    except Exception:
        return False
