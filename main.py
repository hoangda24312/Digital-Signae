import asyncio
import time
import traceback
import flet as ft
import httpx

import config
import network
import player
import playlist
import screens
import storage
import Database as db
from access import check_access
from schedule_logic import pick_schedule
from state import PlayerState

# kết nối tới Supabase
try:
    supabase = db.SupaBase(config.SUPABASE_URL, config.SUPABASE_KEY)
except Exception as init_error:
    print("Không khởi tạo được Supabase:", init_error)
    supabase = None


async def main(page: ft.Page):
    page.title = "Video Sieu Khung"
    page.padding = 0
    page.spacing = 0
    page.bgcolor = ft.Colors.BLACK
    page.window.full_screen = True
    page.window.orientation = "landscape"

    wifi_icon = screens.wifi_off_icon()
    layer = ft.Container(content=screens.connecting_view(), alignment=ft.Alignment.CENTER, expand=True)
    page.add(ft.Stack([layer, wifi_icon], expand=True))
    page.update()

    state = PlayerState()

    # ---------------------------------------------------------------- màn hình
    def set_view(control):
        layer.content = control
        page.update()

    def show_connecting():
        state.reset_playback()
        set_view(screens.connecting_view())

    def show_locked():
        state.reset_playback()
        set_view(screens.locked_view())

    def show_idle(msg):
        state.reset_playback()
        set_view(screens.idle_view(msg))

    def show_waiting(msg=None):          # không có gì để phát và không lấy được: chờ có mạng
        set_view(screens.waiting_view(msg))

    def show_media(control, item):
        state.current_media_id = item.media_id
        state.showing_media = True
        state.playback_state = "loading" if item.media_type == "video" else "playing"
        set_view(control)

    # ---------------------------------------------------------------- sự kiện của video
    async def on_video_complete(e):
        state.item_done = True

    def on_video_error(e):
        print("Video báo lỗi:", getattr(e, "data", e))
        state.playback_state = "error"
        state.need_reload = True

    def on_video_load(e):
        state.playback_state = "playing"

    # ---------------------------------------------------------------- vòng PHÁT: chạy lần lượt các phần tử của playlist
    def ready_count():
        a = state.active
        return sum(1 for i in a.items if i.ready) if a else 0

    def item_limit(item):
        if item.media_type == "video":
            return item.duration_sec * 1.2 + 5 if item.duration_sec else config.VIDEO_MAX_WAIT_SEC
        if item.media_type == "youtube":                  # hết video thì trang báo "#ended"; đây chỉ là mức chặn an toàn
            return item.duration_sec or config.VIDEO_MAX_WAIT_SEC
        return item.duration_sec or config.DEFAULT_IMAGE_SEC

    
    def on_youtube_error(e, single):
        print("YouTube lỗi (thường do video cấm nhúng):", getattr(e, "url", e))
        if single:
            state.need_reload = True      # chỉ có mỗi nó: thử lại sau 15 giây
        else:
            state.item_done = True        # còn item khác: bỏ qua, sang item kế

    async def play_item(item, single, v0, n_ready) -> bool:
        """Phát một phần tử rồi trả về khi đến lúc qua phần tử kế (hoặc playlist đổi)."""
        token = None
        started = 0.0

        def make():
            nonlocal token, started
            token = object()
            my = token
            started = time.monotonic()

            async def on_done(e):
                # chỉ nhận sự kiện của control đang hiển thị, và không nhận trong 2 giây đầu
                if token is not my or time.monotonic() - started < 2.0:
                    print("Bỏ qua on_complete muộn/trùng:", item.title or item.url)
                    return
                state.item_done = True

            on_err = (lambda e: on_youtube_error(e, single)) if item.media_type == "youtube" else on_video_error
            return player.make_control(item, loop=single, on_complete=on_done,
                                        on_error=on_err, on_load=on_video_load)

        ctrl = make()
        if ctrl is None:
            return False
        state.item_done = False
        state.need_reload = False
        show_media(ctrl, item)
        elapsed, limit = 0.0, item_limit(item)
        while True:
            await asyncio.sleep(config.SLICE)
            elapsed += config.SLICE
            if state.version != v0 or ready_count() != n_ready:
                print("Rời item vì playlist đổi")
                return True
            if not single and (state.item_done or elapsed >= limit):
                print("Qua item kế:", "item_done" if state.item_done else "hết giờ", f"({elapsed:.1f}s)")
                return True
            if (state.need_reload and not state.net_down and (item.stream or item.media_type == "youtube")
                    and time.monotonic() - state.last_reload > config.RELOAD_BACKOFF_SEC):
                print("Mạng đã có lại, nạp lại nội dung:", item.title or item.url)
                state.last_reload = time.monotonic()
                state.need_reload = False
                state.item_done = False
                ctrl = make()
                if ctrl is not None:
                    show_media(ctrl, item)
                    elapsed = 0.0

    async def runner():
        while True:
            active = state.active
            if active is None:
                await asyncio.sleep(config.SLICE)
                continue
            v0 = state.version
            ready = [i for i in active.items if i.ready]
            played = False
            for item in ready:
                if state.version != v0:
                    break
                played = await play_item(item, single=len(ready) == 1, v0=v0, n_ready=len(ready)) or played
            if not played:
                await asyncio.sleep(config.SLICE)             # chưa có gì sẵn sàng: chờ tải xong

    # ---------------------------------------------------------------- các vòng lặp nền khác
    async def check_internet():
        fails = 0
        async with httpx.AsyncClient(timeout=3) as client:
            while True:
                fails = 0 if await network.ping_internet(client) else fails + 1
                show = fails >= 2
                if wifi_icon.visible != show:
                    wifi_icon.visible = show
                    page.update()
                if show:
                    state.net_down = True
                    state.need_reload = True
                await asyncio.sleep(config.INTERNET_CHECK_INTERVAL)

    async def heartbeat_loop():
        """Mỗi HEARTBEAT_INTERVAL giây báo cho server: TV còn sống + đang phát gì."""
        while True:
            try:
                if supabase is not None:
                    if state.ip is None:
                        state.ip = await network.get_ip()
                    await asyncio.to_thread(
                        supabase.heartbeat, config.DEVICE_ID, state.ip,
                        state.current_media_id if state.showing_media else None,
                        state.current_schedule_id if state.showing_media else None,
                        state.playback_state, config.APP_VERSION,
                    )
            except Exception as e:
                print("Heartbeat lỗi:", e)
            await asyncio.sleep(config.HEARTBEAT_INTERVAL)

    async def scheduler():
        """Định kỳ lấy lịch của nhóm, chọn lịch đang áp dụng, chuẩn bị nội dung rồi đưa cho vòng phát.
        - Lấy lịch lỗi (mất mạng) -> dùng bản lịch lưu lần cuối, nội dung đã tải vẫn phát được.
        - Playlist không đổi      -> không đụng tới người đang xem (không giật hình)."""
        gate_shown = None
        while True:
            last_error = None

            access = await check_access(supabase, config.DEVICE_ID)
            if access != "allow":
                if gate_shown != access:
                    show_locked() if access == "denied" else show_connecting()
                    gate_shown = access
                await asyncio.sleep(config.GATE_CHECK_INTERVAL)
                continue
            gate_shown = None

            try:
                schedules, from_server = None, False
                try:
                    if supabase is None:
                        raise Exception("Supabase chưa sẵn sàng")
                    schedules = await asyncio.to_thread(supabase.get_schedules, config.DEVICE_ID)
                    from_server = True
                    state.net_down = False                  # lấy được lịch = mạng đã ổn
                    storage.save_schedule_cache(schedules)
                except Exception as ex:
                    last_error = f"{type(ex).__name__}: {ex}"
                    print("Không lấy được lịch:", last_error)
                    state.net_down = True
                    state.need_reload = True
                    schedules = storage.load_schedule_cache()     # dùng bản lưu lần cuối
                    if schedules is None:
                        raise

                if not schedules:
                    if from_server:
                        show_idle("Nhóm thiết bị này chưa có lịch phát.")
                else:
                    sched = pick_schedule(schedules)
                    if sched is None:
                        if from_server or state.active is not None:
                            show_idle("Hiện không có lịch phát vào khung giờ này.")
                    else:
                        new = playlist.active_from_schedule(sched)
                        cur = state.active
                        if cur is not None and cur.signature == new.signature:
                            cur.schedule_id = sched["schedule_id"]          # cùng nội dung: không đụng player
                            state.current_schedule_id = sched["schedule_id"]
                            await playlist.resolve_all(cur, state.mb_cache) # thử lại phần tử tải hỏng
                        else:
                            if cur is None:
                                show_connecting()                           # chưa phát gì: cho vòng xoay + mã
                                state.active = new                          # vòng phát bắt đầu ngay khi có nội dung đầu
                                state.version += 1
                                state.current_schedule_id = sched["schedule_id"]
                                await playlist.resolve_all(new, state.mb_cache)
                            else:
                                await playlist.resolve_all(new, state.mb_cache)   # nội dung cũ vẫn phát trong lúc tải
                                state.active = new
                                state.version += 1
                                state.current_schedule_id = sched["schedule_id"]
                        storage.cleanup_media(playlist.all_media_paths(schedules))

            except Exception as ex:
                last_error = f"{type(ex).__name__}: {ex}"
                print("Không thể cập nhật:", last_error)
                traceback.print_exc()

            if not state.showing_media and (state.active is None or ready_count() == 0):
                if last_error or state.active is not None:
                    show_waiting(last_error or "Chưa tải được nội dung")

            await asyncio.sleep(config.CHECK_INTERVAL)

    page.run_task(check_internet)
    page.run_task(heartbeat_loop)
    page.run_task(scheduler)
    page.run_task(runner)


ft.run(main)
