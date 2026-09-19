"""配置任务资源模块权限定义。"""

from common.permission.model import PermDef
from common.permission.registry import register_perm

PERM_DEFS: tuple[PermDef, ...] = (
    PermDef("configuration_task:resource:list", "配置任务资源列表"),
    PermDef("configuration_task:resource:query", "配置任务资源详情"),
    PermDef("configuration_task:resource:add", "配置任务资源登记"),
    PermDef("configuration_task:resource:edit", "配置任务资源就绪确认"),
    PermDef("configuration_task:resource:transfer", "配置任务资源传输"),
    PermDef("configuration_task:task:list", "配置任务列表"),
    PermDef("configuration_task:task:query", "配置任务详情"),
    PermDef("configuration_task:task:add", "配置任务新增"),
    PermDef("configuration_task:task:edit", "配置任务编辑"),
    PermDef("configuration_task:task:publish", "配置任务版本发布"),
    PermDef("configuration_task:task:run", "配置任务运行"),
)


def register() -> None:
    """注册资源模块权限码，供路由权限扫描和菜单同步使用。"""
    for permission in PERM_DEFS:
        register_perm(permission)
