import flet as ft


def main(page: ft.Page):
    page.title = "Flet路由示例应用"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0

    def route_change(e):
        page.views.clear()

        # 主页视图
        if page.route == "/":
            page.views.append(
                ft.View(
                    route="/",
                    controls=[
                        ft.AppBar(title=ft.Text("主页"), bgcolor=ft.Colors.BLUE_700),
                        ft.Container(
                            content=ft.Column([
                                ft.Text("欢迎使用Flet路由示例", size=24, weight=ft.FontWeight.BOLD),
                                ft.Text("这是一个展示Flet路由功能的示例应用", size=16),
                                ft.Divider(),
                                ft.ElevatedButton(
                                    "前往用户页面",
                                    on_click=lambda _: page.go("/users"),
                                    icon=ft.Icons.PEOPLE
                                ),
                                ft.ElevatedButton(
                                    "前往设置页面",
                                    on_click=lambda _: page.go("/settings"),
                                    icon=ft.Icons.SETTINGS
                                ),
                                ft.ElevatedButton(
                                    "查看产品详情",
                                    on_click=lambda _: page.go("/products/123"),
                                    icon=ft.Icons.SHOPPING_BAG
                                )
                            ]),
                            padding=20,
                            alignment=ft.alignment.center
                        )
                    ]
                )
            )
            page.update()

        # 用户页面
        elif page.route == "/users":
            page.views.append(
                ft.View(
                    route="/users",
                    controls=[
                        ft.AppBar(title=ft.Text("用户管理"), bgcolor=ft.Colors.GREEN_700),
                        ft.Container(
                            content=ft.Column([
                                ft.Text("用户列表", size=20, weight=ft.FontWeight.BOLD),
                                ft.ListView([
                                    ft.ListTile(
                                        leading=ft.Icon(ft.Icons.PERSON),
                                        title=ft.Text("张三"),
                                        subtitle=ft.Text("zhangsan@example.com"),
                                        on_click=lambda _: page.go("/user/1")
                                    ),
                                    ft.ListTile(
                                        leading=ft.Icon(ft.Icons.PERSON),
                                        title=ft.Text("李四"),
                                        subtitle=ft.Text("lisi@example.com"),
                                        on_click=lambda _: page.go("/user/2")
                                    ),
                                    ft.ListTile(
                                        leading=ft.Icon(ft.Icons.PERSON),
                                        title=ft.Text("王五"),
                                        subtitle=ft.Text("wangwu@example.com"),
                                        on_click=lambda _: page.go("/user/3")
                                    )
                                ], height=300),
                                ft.ElevatedButton(
                                    "返回主页",
                                    on_click=lambda _: page.go("/"),
                                    icon=ft.Icons.ARROW_BACK
                                )
                            ]),
                            padding=20
                        )
                    ]
                )
            )
            page.update()

        # 用户详情页面
        elif page.route.startswith("/user/"):
            user_id = page.route.split("/")[-1]
            user_data = {
                "1": {"name": "张三", "email": "zhangsan@example.com", "role": "管理员"},
                "2": {"name": "李四", "email": "lisi@example.com", "role": "用户"},
                "3": {"name": "王五", "email": "wangwu@example.com", "role": "编辑"}
            }

            user = user_data.get(user_id, {"name": "未知用户", "email": "", "role": ""})

            page.views.append(
                ft.View(
                    route=f"/user/{user_id}",
                    controls=[
                        ft.AppBar(title=ft.Text(f"用户详情 - {user['name']}"), bgcolor=ft.Colors.PURPLE_700),
                        ft.Container(
                            content=ft.Column([
                                ft.Card(
                                    content=ft.Container(
                                        content=ft.Column([
                                            ft.ListTile(
                                                leading=ft.Icon(ft.Icons.PERSON, color=ft.Colors.BLUE),
                                                title=ft.Text(user["name"], size=18, weight=ft.FontWeight.BOLD),
                                                subtitle=ft.Text(f"ID: {user_id}")
                                            ),
                                            ft.Divider(),
                                            ft.ListTile(
                                                leading=ft.Icon(ft.Icons.EMAIL, color=ft.Colors.GREEN),
                                                title=ft.Text("邮箱"),
                                                subtitle=ft.Text(user["email"])
                                            ),
                                            ft.ListTile(
                                                leading=ft.Icon(ft.Icons.WORK, color=ft.Colors.ORANGE),
                                                title=ft.Text("角色"),
                                                subtitle=ft.Text(user["role"])
                                            )
                                        ]),
                                        padding=20
                                    ),
                                    margin=10
                                ),
                                ft.Row([
                                    ft.ElevatedButton(
                                        "返回用户列表",
                                        on_click=lambda _: page.go("/users"),
                                        icon=ft.Icons.ARROW_BACK
                                    ),
                                    ft.ElevatedButton(
                                        "编辑用户",
                                        icon=ft.Icons.EDIT,
                                        on_click=lambda _: page.open(
                                            ft.SnackBar(content=ft.Text("编辑功能开发中...")))),
                                ])
                            ]),
                            padding=20
                        )
                    ]
                )
            )
            page.update()

        # 产品详情页面
        elif page.route.startswith("/products/"):
            product_id = page.route.split("/")[-1]
            page.views.append(
                ft.View(
                    route=f"/products/{product_id}",
                    controls=[
                        ft.AppBar(title=ft.Text(f"产品 #{product_id}"), bgcolor=ft.Colors.ORANGE_700),
                        ft.Container(
                            content=ft.Column([
                                ft.Card(
                                    content=ft.Container(
                                        content=ft.Column([
                                            ft.Text(f"产品详情", size=20, weight=ft.FontWeight.BOLD),
                                            ft.Text(f"产品ID: {product_id}", size=16),
                                            ft.Text("这是一个示例产品页面，展示了如何通过URL参数传递数据", size=14),
                                        ]),
                                        padding=20
                                    ),
                                    margin=10
                                ),
                                ft.ElevatedButton(
                                    "返回主页",
                                    on_click=lambda _: page.go("/"),
                                    icon=ft.Icons.ARROW_BACK
                                )
                            ]),
                            padding=20,
                            alignment=ft.alignment.center
                        )
                    ]
                )
            )
            page.update()

        # 设置页面
        elif page.route == "/settings":
            page.views.append(
                ft.View(
                    route="/settings",
                    controls=[
                        ft.AppBar(title=ft.Text("系统设置"), bgcolor=ft.Colors.INDIGO_700),
                        ft.Container(
                            content=ft.Column([
                                ft.Text("应用设置", size=20, weight=ft.FontWeight.BOLD),
                                ft.Card(
                                    content=ft.Container(
                                        content=ft.Column([
                                            ft.Switch(label="深色模式", value=False),
                                            ft.Switch(label="消息通知", value=True),
                                            ft.Slider(label="字体大小", min=12, max=24, divisions=12, value=16),
                                        ]),
                                        padding=20
                                    ),
                                    margin=10
                                ),
                                ft.ElevatedButton(
                                    "保存设置",
                                    icon=ft.Icons.SAVE,
                                    on_click=lambda _: page.open(ft.SnackBar(content=ft.Text("设置已保存!")))),
                                ft.ElevatedButton(
                                    "返回主页",
                                    on_click=lambda _: page.go("/"),
                                    icon=ft.Icons.ARROW_BACK
                                )
                            ]),
                            padding=20
                        )
                    ]
                )
            )
            page.update()

        # 404页面 - 未找到的路由
        else:
            page.views.append(
                ft.View(
                    route=page.route,
                    controls=[
                        ft.AppBar(title=ft.Text("页面未找到"), bgcolor=ft.Colors.RED_700),
                        ft.Container(
                            content=ft.Column([
                                ft.Icon(ft.Icons.ERROR_OUTLINE, size=64, color=ft.Colors.RED),
                                ft.Text("404 - 页面未找到", size=24, weight=ft.FontWeight.BOLD),
                                ft.Text(f"路由 '{page.route}' 不存在", size=16),
                                ft.ElevatedButton(
                                    "返回主页",
                                    on_click=lambda _: page.go("/"),
                                    icon=ft.Icons.HOME
                                )
                            ]),
                            padding=40,
                            alignment=ft.alignment.center
                        )
                    ]

                )

            )
            page.update()

    page.update()

    def view_pop(e):
        if len(page.views) > 1:
            page.views.pop()
            top_view = page.views[-1]
            page.go(top_view.route)
        else:
            page.window.close()

    page.on_route_change = route_change
    page.on_view_pop = view_pop

    # 初始化路由
    page.go(page.route)


if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.WEB_BROWSER)
