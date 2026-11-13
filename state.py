"""Trạng thái dùng chung giữa các vòng lặp nền, gom vào một đối tượng (không cần `nonlocal`)."""
from dataclasses import dataclass, field


@dataclass
class PlayerState:
    active: object = None             # playlist đang phát (playlist.Active) hoặc None
    version: int = 0                  # tăng mỗi khi đổi playlist -> vòng phát biết để bắt đầu lại
    showing_media: bool = False       # đang hiện nội dung (không phải màn hình chờ / khóa)
    playback_state: str = "idle"      # 'idle' | 'loading' | 'playing' | 'error'
    current_media_id: object = None   # gửi lên server trong heartbeat
    current_schedule_id: object = None
    ip: object = None
    item_done: bool = False           # video báo đã phát hết
    need_reload: bool = False         # nội dung stream/youtube có thể đã chết -> nạp lại khi có mạng
    net_down: bool = False            # vừa mất mạng; scheduler lấy được lịch trở lại thì xóa cờ
    last_reload: float = 0.0
    mb_cache: dict = field(default_factory=dict)    # url -> dung lượng MB (hỏi một lần)

    def reset_playback(self):
        """Không còn phát gì (đang chờ duyệt / bị khóa / không có lịch)."""
        self.active = None
        self.version += 1
        self.showing_media = False
        self.playback_state = "idle"
        self.current_media_id = self.current_schedule_id = None
        self.need_reload = False
