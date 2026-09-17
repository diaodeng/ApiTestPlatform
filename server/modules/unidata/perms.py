"""大数据查询模块的菜单与权限定义，注册进平台统一权限同步机制。"""

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
        "unidata.query",
        "大数据查询",
        "C",
        None,
        perm="unidata:query:list",
        path="unidata",
        component="unidata/index",
        icon="chart",
        order=9,
        remark="大数据（Unidata）只读查询：数据源切换、权限库表浏览与 SQL 执行",
    ),
)


def register() -> None:
    """把本模块的菜单与权限注册进全局注册表。"""
    for menu in MENU_DEFS:
        register_menu(menu)
