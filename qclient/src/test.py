import os

import flet as ft
import sys


def main(page: ft.Page):
    page.title = "Flet 关闭确认应用"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.window_width = 600
    page.window_height = 500

    # 创建确认对话框
    confirm_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("确认关闭"),
        content=ft.Text("您确定要关闭应用吗？所有未保存的数据将会丢失。"),
        actions=[
            ft.TextButton("取消", on_click=lambda e: close_dialog(e)),
            ft.TextButton("确定关闭",
                          style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ft.Colors.RED_400),
                          on_click=lambda e: confirm_close(e))
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def show_confirm_dialog():
        """显示确认对话框"""
        print("2222222222222222222")
        page.open(confirm_dialog)
        confirm_dialog.open = True
        print("33333333333333")
        page.update()
        print("44444444444444444")

    def close_dialog(e):
        """关闭对话框"""
        confirm_dialog.open = False
        page.update()

    def confirm_close(e):
        """确认关闭应用"""
        print("正在关闭应用...")
        cleanup()
        confirm_dialog.open = False
        page.update()
        # page.window.destroy()
        os._exit(0)
        # sys.exit()
        # 延迟关闭以确保UI更新完成
        # import threading
        # threading.Timer(0.1, lambda: [page.window.destroy(), sys.exit(0)]).start()

    def window_event(e):
        """处理窗口事件 - 关键修复部分"""
        print(f"窗口事件: {e.data}")
        if e.data == "close":
            # 阻止默认关闭行为，显示确认弹窗
            e.control.prevent_default = True
            show_confirm_dialog()

    def cleanup():
        """清理资源"""
        print("正在保存数据并清理资源...")
        # 这里可以添加保存用户数据、关闭连接等操作

    def safe_close_click(e):
        print("111111111111111111")
        """安全关闭按钮点击事件"""
        show_confirm_dialog()

    # 关键：正确绑定窗口事件处理器
    page.on_window_event = window_event

    # 创建主界面内容
    header = ft.Container(
        content=ft.Column([
            ft.Icon(ft.Icons.SECURITY, size=60, color=ft.Colors.BLUE_700),
            ft.Text("安全关闭确认",
                    size=28,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.BLUE_900),
            ft.Text("点击右上角关闭按钮或下方按钮测试关闭确认功能",
                    size=16,
                    color=ft.Colors.GREY_700),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        padding=20,
        margin=ft.margin.only(bottom=30)
    )

    # 功能说明卡片
    feature_card = ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN),
                    title=ft.Text("安全关闭确认", weight=ft.FontWeight.BOLD),
                    subtitle=ft.Text("防止意外关闭导致数据丢失"),
                ),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.SAVE, color=ft.Colors.BLUE),
                    title=ft.Text("数据保护", weight=ft.FontWeight.BOLD),
                    subtitle=ft.Text("关闭前提供保存数据的机会"),
                ),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.WARNING, color=ft.Colors.ORANGE),
                    title=ft.Text("用户友好", weight=ft.FontWeight.BOLD),
                    subtitle=ft.Text("清晰的确认提示和操作选项"),
                ),
            ]),
            padding=15,
        ),
        elevation=5,
        margin=ft.margin.only(bottom=20)
    )

    # 关闭按钮
    close_button = ft.ElevatedButton(
        content=ft.Row([
            ft.Icon(ft.Icons.EXIT_TO_APP, color=ft.Colors.WHITE),
            ft.Text("安全关闭应用", color=ft.Colors.WHITE),
        ], alignment=ft.MainAxisAlignment.CENTER),
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.RED_500,
            padding=20,
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
        on_click=safe_close_click,
        width=200
    )

    # 测试按钮 - 验证事件处理
    test_button = ft.ElevatedButton(
        "测试事件",
        on_click=lambda e: print("按钮点击正常")
    )

    # 添加到页面
    page.add(
        ft.Column([
            header,
            feature_card,
            ft.Container(
                content=ft.Column([
                    close_button,
                    ft.Container(height=10),
                    test_button
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                alignment=ft.alignment.center,
                margin=ft.margin.only(top=20)
            )
        ],
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True
        )
    )

    # 打印初始化完成信息
    print("应用初始化完成，等待关闭事件...")

if __name__ == "__main__":
    ft.app(target=main)