"""Các màn hình/thành phần giao diện (chỉ dựng control, không có logic mạng)."""
import flet as ft
from config import DEVICE_ID


def wifi_off_icon():
    return ft.Container(
        content=ft.Icon(icon=ft.Icons.WIFI_OFF, color=ft.Colors.RED, size=36),
        right=24, bottom=24, padding=8, visible=False, bgcolor="black54",
    )


def connecting_view():
    # hiện mã ngay từ đầu, kể cả khi chưa kết nối được server, để admin đọc mà thêm thiết bị
    return ft.Column(
        [
            ft.ProgressRing(color=ft.Colors.WHITE),
            ft.Text(f"Mã thiết bị: {DEVICE_ID}", text_align=ft.TextAlign.CENTER,
                    color="white54", size=16),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )


def waiting_view(msg=None):
    return ft.Column(
        [
            ft.Icon(ft.Icons.WIFI_OFF, color=ft.Colors.RED, size=50),
            ft.Text("Chưa có video. Vui lòng kết nối Internet.\nỨng dụng sẽ tự thử lại.",
                    text_align=ft.TextAlign.CENTER, color="white"),
            ft.Text(f"Chi tiết lỗi: {msg}" if msg else "",
                    text_align=ft.TextAlign.CENTER, color="white54", size=12),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )


def locked_view():
    return ft.Column(
        [
            ft.Icon(ft.Icons.LOCK, color=ft.Colors.AMBER, size=50),
            ft.Text("Thiết bị chưa được cấp quyền.\nVui lòng liên hệ quản trị viên để kích hoạt.",
                    text_align=ft.TextAlign.CENTER, color="white"),
            ft.Text(f"Mã thiết bị: {DEVICE_ID}",
                    text_align=ft.TextAlign.CENTER, color="white54", size=16),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )


def idle_view(msg="Hiện không có lịch phát."):
    return ft.Column(
        [
            ft.Text(msg, text_align=ft.TextAlign.CENTER, color="white54", size=18),
            ft.Text(f"Mã thiết bị: {DEVICE_ID}", text_align=ft.TextAlign.CENTER,
                    color="white24", size=12),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
