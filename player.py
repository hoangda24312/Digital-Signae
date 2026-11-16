"""Dựng control cho từng loại nội dung: video, ảnh, youtube."""
import re
import flet as ft
import flet_video as fvt

try:                                    # YouTube cần gói flet-webview (thêm vào pyproject.toml)
    import flet_webview as fwv
except Exception:
    fwv = None

_YT = re.compile(r"(?:youtu\.be/|youtube\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/))([A-Za-z0-9_-]{11})")


def youtube_id(url: str):
    m = _YT.search(url or "")
    return m.group(1) if m else None


def youtube_supported(url: str) -> bool:
    return fwv is not None and youtube_id(url) is not None


YT_PAGE = "https://hoangda24312.github.io/Digital-Signae/"   # đổi thành địa chỉ trang bạn vừa host

def youtube_embed_url(url: str, loop: bool = False) -> str:
    vid = youtube_id(url)
    return f"{YT_PAGE}?v={vid}" + ("&loop=1" if loop else "")

def build_video(source: str, loop: bool, on_complete=None, on_error=None, on_load=None):
    kwargs = dict(playlist=[fvt.VideoMedia(source)], autoplay=True, expand=True,
                  fit=ft.BoxFit.FILL, muted=True)
    if on_error is not None:
        kwargs["on_error"] = on_error
    if on_load is not None:
        kwargs["on_load"] = on_load
    if on_complete is not None:
        kwargs["on_complete"] = on_complete
    mode_cls = getattr(fvt, "PlaylistMode", None) or getattr(ft, "PlaylistMode", None)
    if loop and mode_cls is not None:
        kwargs["playlist_mode"] = mode_cls.LOOP         # chỉ có 1 nội dung: tự lặp
    return fvt.Video(**kwargs, controls=None)


def build_image(item):
    src = item.url
    if item.path is not None and item.path.exists():
        try:
            src = item.path.read_bytes()                # ảnh đã tải: đọc từ máy
        except OSError:
            pass
    return ft.Image(src=src, fit=ft.BoxFit.COVER, expand=True)


def build_youtube(item, loop: bool = False, on_complete=None, on_error=None):
    if not youtube_supported(item.url):
        return None

    async def on_url_change(e):
        # trang index.html đổi #hash: "#ended-..." = video hết, "#error-..." = lỗi
        url = getattr(e, "url", None) or str(getattr(e, "data", "") or "")
        if "#ended" in url and on_complete is not None:
            await on_complete(e)
        elif "#error" in url and on_error is not None:
            on_error(e)

    return fwv.WebView(url=youtube_embed_url(item.url, loop), expand=True, bgcolor=ft.Colors.BLACK,
                       on_url_change=on_url_change)



def make_control(item, loop: bool, on_complete=None, on_error=None, on_load=None):
    """Control tương ứng loại nội dung, hoặc None nếu không dựng được."""
    if item.media_type == "video":
        source = item.url if item.stream else str(item.path)
        return build_video(source, loop, on_complete, on_error, on_load)
    if item.media_type == "image":
        return build_image(item)
    if item.media_type == "youtube":
        return build_youtube(item, loop, on_complete, on_error)
    return None
