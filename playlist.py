"""Playlist đang phát: danh sách nội dung (video / ảnh / youtube) và việc chuẩn bị chúng."""
from dataclasses import dataclass, field
from pathlib import Path
import config
import network
import player
import storage


@dataclass
class Item:
    item_id: int
    media_id: int
    media_type: str
    url: str
    title: str = ""
    duration_sec: object = None
    size_bytes: object = None
    position: int = 0
    path: object = None        # file trong máy (video nhỏ / ảnh), None nếu stream / youtube
    stream: bool = False       # video lớn: phát thẳng từ URL
    ready: bool = False        # đã sẵn sàng để phát

    def key(self):
        return (self.media_id, self.media_type, self.url, self.duration_sec, self.position)


@dataclass
class Active:
    schedule_id: int
    playlist_id: int
    items: list = field(default_factory=list)

    @property
    def signature(self):
        return (self.playlist_id, tuple(i.key() for i in self.items))


def active_from_schedule(row) -> Active:
    rows = sorted(row.get("items") or [], key=lambda i: (i.get("position") or 0, i.get("item_id") or 0))
    items = [Item(item_id=i.get("item_id"), media_id=i["media_id"], media_type=i["media_type"],
                  url=i["url"], title=i.get("title") or "", duration_sec=i.get("duration_sec"),
                  size_bytes=i.get("size_bytes"), position=i.get("position") or 0)
             for i in rows]
    return Active(schedule_id=row["schedule_id"], playlist_id=row["playlist_id"], items=items)


def all_media_paths(schedules) -> set:
    """Mọi file nằm trong bất kỳ lịch nào (để không xóa nhầm file của lịch giờ khác)."""
    keep = set()
    for s in schedules or []:
        for i in s.get("items") or []:
            if i.get("media_type") in ("video", "image") and i.get("url"):
                keep.add(storage.media_path_for(i["url"], i["media_type"]))
    return keep


async def resolve_item(item: Item, mb_cache: dict):
    """Chuẩn bị một phần tử: tải về hoặc quyết định stream. Gán item.ready."""
    if item.ready:
        return
    if item.media_type == "youtube":
        item.ready = player.youtube_supported(item.url)
        return
    if item.media_type not in ("video", "image"):
        return

    dest = storage.media_path_for(item.url, item.media_type)
    item.path = dest
    if dest.exists() and dest.stat().st_size > 0:      # đã có file: dùng luôn, không hỏi mạng
        item.ready = True
        return

    if item.media_type == "video":
        mb = mb_cache.get(item.url)
        if mb is None and item.size_bytes:
            mb = item.size_bytes / (1024 * 1024)
        if mb is None:
            mb = await network.check_mb(item.url)       # HEAD: biết dung lượng mà không tải
        if mb is not None:
            mb_cache[item.url] = mb
        if mb is not None and mb >= config.STREAM_THRESHOLD_MB:
            item.stream = True                          # video lớn: không tải, phát thẳng từ URL
            item.ready = True
            return

    item.ready = await storage.download(item.url, dest)


async def resolve_all(active: Active, mb_cache: dict):
    for item in active.items:
        await resolve_item(item, mb_cache)
