"""Cấu hình và đường dẫn. Chỉ sửa số liệu ở file này, các module khác `import config`."""
import os
import secrets
import sys
from pathlib import Path
from dotenv import load_dotenv

# ---- cấu hình ----
APP_VERSION = "0.3.0"
CHECK_INTERVAL = 30          # giây: bao lâu hỏi lịch / nội dung mới một lần
GATE_CHECK_INTERVAL = 10     # giây: bao lâu hỏi lại quyền khi chưa được duyệt
HEARTBEAT_INTERVAL = 60      # giây: bao lâu báo "TV còn sống" một lần
INTERNET_CHECK_INTERVAL = 30 # giây: bao lâu kiểm tra internet một lần
STREAM_THRESHOLD_MB = 50     # video >= số MB này thì phát thẳng từ URL (streaming), không tải về
DEFAULT_IMAGE_SEC = 10       # ảnh / youtube không ghi thời gian thì hiện bấy nhiêu giây
VIDEO_MAX_WAIT_SEC = 1800    # video trong playlist nhiều phần tử không báo "hết" thì sau bấy nhiêu giây qua phần tử kế
RELOAD_BACKOFF_SEC = 15      # nạp lại nội dung stream/youtube bị chết: cách nhau ít nhất bấy nhiêu giây
SLICE = 0.5                  # giây: nhịp kiểm tra của vòng phát

# ---- đường dẫn ----
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

APP_STORAGE = os.getenv("FLET_APP_STORAGE_DATA")
if not APP_STORAGE:
    print("FLET_APP_STORAGE_DATA chưa được thiết lập")
    sys.exit(1)

APP_DIR = Path(APP_STORAGE)
MEDIA_DIR = APP_DIR / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
print("Thư mục lưu nội dung:", MEDIA_DIR)

SCHEDULE_CACHE = APP_DIR / "schedules.json"      # bản lịch cuối cùng lấy được, dùng khi mất mạng
APPROVED_FLAG = APP_DIR / "approved.flag"        # "đã từng được duyệt": mất mạng vẫn được phát
ID_PATH = APP_DIR / "uuid.txt"                   # mã thiết bị (giữ tên file cũ để không đổi mã)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("API_KEY")

# ---- mã thiết bị: sinh ở lần chạy đầu, lưu file, các lần sau đọc lại ----
# Bỏ ký tự dễ nhầm (0/O, 1/I) vì admin đọc mã trên TV rồi gõ lại. Ví dụ "K7QM-4TXA".
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def load_device_id() -> str:
    try:
        code = ID_PATH.read_text(encoding="utf-8").strip()
        if code:
            return code
    except OSError:
        pass
    code = "".join(secrets.choice(_ALPHABET) for _ in range(8))
    code = f"{code[:4]}-{code[4:]}"
    ID_PATH.write_text(code, encoding="utf-8")
    return code


DEVICE_ID = load_device_id()
print("Mã thiết bị:", DEVICE_ID)
