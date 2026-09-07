"""资源采集服务模块的菜单与权限定义，注册进平台统一权限同步机制。"""

from common.permission.model import MenuConfig
from common.permission.registry import register_menu


def _menu(
    key: str,
    name: str,
    menu_type: str,
    parent_key: str | None = None,
    *,
    perm: str = "",
    path: str = "",
    component: str = "",
    query: str = "",
    icon: str = "#",
    order: int = 1,
    is_frame: int = 1,
    is_cache: int = 0,
    visible: str = "0",
    status: str = "0",
    remark: str = "",
) -> MenuConfig:
    return MenuConfig(
        key=key,
        name=name,
        menu_type=menu_type,
        parent_key=parent_key,
        perm=perm,
        path=path,
        component=component,
        query=query,
        icon=icon,
        order=order,
        is_frame=is_frame,
        is_cache=is_cache,
        visible=visible,
        status=status,
        remark=remark,
    )


MENU_DEFS: tuple[MenuConfig, ...] = (
    _menu(
        "admin.monitor.metrics_collector",
        "资源采集服务",
        "C",
        "admin.monitor",
        perm="monitor:metrics_collector:list",
        path="metricsCollector",
        component="monitor/metrics/index",
        icon="chart",
        order=3,
        remark="资源指标采集服务的可视化配置与启停管理",
    ),
    _menu("admin.monitor.metrics_collector.query", "采集服务查询", "F", "admin.monitor.metrics_collector", perm="monitor:metrics_collector:query", order=1),
    _menu("admin.monitor.metrics_collector.add", "采集服务新增", "F", "admin.monitor.metrics_collector", perm="monitor:metrics_collector:add", order=2),
    _menu("admin.monitor.metrics_collector.edit", "采集服务修改", "F", "admin.monitor.metrics_collector", perm="monitor:metrics_collector:edit", order=3),
    _menu("admin.monitor.metrics_collector.remove", "采集服务删除", "F", "admin.monitor.metrics_collector", perm="monitor:metrics_collector:remove", order=4),
)


def register() -> None:
    """把本模块的菜单与权限注册进全局注册表。"""
    for menu in MENU_DEFS:
        register_menu(menu)
