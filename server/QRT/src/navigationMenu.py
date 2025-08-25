import flet
from contents import Contents

class NavigationMenu:
    def __init__(self, ft: flet, page, log, **kwargs):
        self.ft = ft
        self.page = page
        self.log = log
        # 当前选中索引
        self.selected_index = ft.Ref[int]()
        self.selected_index.current = 0
        # 内容对象
        self.contents = Contents(ft, log, page, **kwargs)
        # 内容区域
        self.content_area = ft.Container(
            content=self.contents.get_content(0),
            expand=True
        )


    # 导航栏点击处理
    def on_nav_change(self, e):
        self.selected_index.current = e.control.selected_index
        self.content_area.content = self.contents.get_content(self.selected_index.current)

        # 添加页面有效性检查
        if self.page:
            try:
                self.page.update()
            except Exception as ex:
                self.log.error(f"页面更新失败:{ex}")
        else:
            self.log.warning(f"尝试更新已关闭的页面")


    def nav_rail_menu(self):
        # 构建导航栏
        nav_rail = self.ft.NavigationRail(
            selected_index=0,
            label_type=self.ft.NavigationRailLabelType.ALL,
            min_width=100,
            min_extended_width=200,

            # group_alignment=-0.9,  # 控制上边距
            destinations=[
                self.ft.NavigationRailDestination(
                    icon=self.ft.Icons.HOME_OUTLINED,
                    selected_icon=self.ft.Icons.HOME,
                    label="首页"
                ),
                self.ft.NavigationRailDestination(
                    icon=self.ft.Icons.DASHBOARD_OUTLINED,
                    selected_icon=self.ft.Icons.DASHBOARD,
                    label="快捷"
                ),
                self.ft.NavigationRailDestination(
                    icon=self.ft.Icons.SETTINGS_OUTLINED,
                    selected_icon=self.ft.Icons.SETTINGS,
                    label="设置"
                ),
                self.ft.NavigationRailDestination(
                    icon=self.ft.Icons.WAREHOUSE_OUTLINED,
                    selected_icon=self.ft.Icons.WAREHOUSE,
                    label="商品"
                ),
                self.ft.NavigationRailDestination(
                    icon=self.ft.Icons.SEARCH_OUTLINED,
                    selected_icon=self.ft.Icons.SEARCH,
                    label="文件搜索"
                ),
                self.ft.NavigationRailDestination(
                    icon=self.ft.Icons.AIRPLAY,
                    selected_icon=self.ft.Icons.AIRPLAY,
                    label="mitmproxy"
                ),
                self.ft.NavigationRailDestination(
                    icon=self.ft.Icons.ROUNDABOUT_LEFT_OUTLINED,
                    selected_icon=self.ft.Icons.ROUNDABOUT_LEFT,
                    label="关于"
                )
            ],
            on_change=self.on_nav_change,
        )
        return nav_rail

    def ref_content_area(self):
        """初始化内容区域"""
        return self.content_area
