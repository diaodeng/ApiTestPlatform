"""配置任务资源模块权限定义。"""

from common.permission.model import PermDef
from common.permission.registry import register_perm

PERM_DEFS: tuple[PermDef, ...] = (
    PermDef("configuration_task:resource:list", "配置任务资源列表"),
    PermDef("configuration_task:resource:query", "配置任务资源详情"),
    PermDef("configuration_task:resource:add", "配置任务资源登记"),
    PermDef("configuration_task:resource:edit", "配置任务资源就绪确认"),
)


def register() -> None:
    """注册资源模块权限码，供路由权限扫描和菜单同步使用。"""
    for permission in PERM_DEFS:
        register_perm(permission)
