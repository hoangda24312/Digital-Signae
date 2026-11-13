"""Chọn lịch nào đang áp dụng lúc này. Thuần logic: không gọi mạng, dễ test."""
from datetime import datetime, time, date


def parse_time(time_str: str) -> time:
    parts = str(time_str).split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    s = int(float(parts[2])) if len(parts) > 2 else 0
    return time(h, m, s)


def pick_schedule(danh_sach, now=None, today=None):
    """Trả về DÒNG lịch (dict) đầu tiên có khung giờ chứa thời điểm hiện tại, hoặc None.
    Lịch có start_date/end_date là ngày đặc biệt: nằm trong khoảng ngày đó thì xét,
    ngoài khoảng thì bỏ qua. Lịch không có ngày (null) áp dụng mọi ngày.
    Thứ tự trong danh_sach quyết định lịch nào thắng khi trùng (xem get_device_schedule)."""
    now = now or datetime.now().time()
    now_day = today or date.today().isoformat()
    for schedule in danh_sach:
        start_date = schedule["start_date"]
        end_date = schedule["end_date"]
        start = parse_time(schedule["start_time"])
        end = parse_time(schedule["end_time"])

        if start_date is not None and end_date is not None:      # ngày đặc biệt
            if start_date <= now_day <= end_date:
                if start < end:
                    if start <= now < end:
                        return schedule
                elif start > end:                                # khung giờ qua nửa đêm
                    if now >= start or now < end:
                        return schedule
            continue

        if start < end:
            if start <= now < end:
                return schedule
        elif start > end:                                        # khung giờ qua nửa đêm
            if now >= start or now < end:
                return schedule
    return None
