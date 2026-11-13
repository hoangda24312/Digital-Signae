"""Nội dung lưu trong máy (video / ảnh) và bản lưu của lịch."""
import hashlib
import json
import os
from pathlib import Path
import httpx
from config import MEDIA_DIR, SCHEDULE_CACHE

_EXT = {"video": ".mp4", "image": ".img"}


def media_path_for(url: str, media_type: str) -> Path:
    """Mỗi URL -> một tên file riêng, nên nội dung mới không ghi đè file đang phát."""
    name = hashlib.md5(url.encode("utf-8")).hexdigest()[:16]
    return MEDIA_DIR / f"{name}{_EXT.get(media_type, '.bin')}"


async def download(url: str, dest: Path) -> bool:
    temp_path = dest.with_suffix(".tmp")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60)) as client:
            async with client.stream("GET", url) as r:
                r.raise_for_status()
                with open(temp_path, "wb") as f:
                    async for chunk in r.aiter_bytes(chunk_size=1024 * 1024):
                        f.write(chunk)
        os.replace(temp_path, dest)
        print("Đã lưu:", dest)
        return True
    except Exception as e:
        print("Download thất bại:", e)
        temp_path.unlink(missing_ok=True)
        return False


def cleanup_media(keep: set):
    """Xóa file cũ / file tạm, chỉ giữ các file còn nằm trong lịch."""
    for f in list(MEDIA_DIR.glob("*")):
        if f not in keep:
            try:
                f.unlink()
            except Exception:
                pass            # file còn bị khóa thì bỏ qua, lần sau xóa tiếp


def save_schedule_cache(schedules):
    try:
        tmp = SCHEDULE_CACHE.with_suffix(".tmp")
        tmp.write_text(json.dumps(schedules, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, SCHEDULE_CACHE)
    except Exception as e:
        print("Không lưu được lịch:", e)


def load_schedule_cache():
    """Bản lịch lưu lần cuối, hoặc None nếu chưa có / hỏng."""
    try:
        return json.loads(SCHEDULE_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return None
