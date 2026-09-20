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
    PermDef("configuration_task:task:approve", "配置任务阶段审批"),
    PermDef("configuration_task:artifact:upload", "配置任务产物上报"),
    PermDef("configuration_task:report:generate", "配置任务报告归档"),
    PermDef("configuration_task:resource:sftp", "配置任务SFTP资源上传"),
    PermDef("configuration_task:resource:download", "配置任务资源下载"),
    PermDef("configuration_task:resource:delete", "配置任务资源删除"),
)


def register() -> None:
    """注册资源模块权限码，供路由权限扫描和菜单同步使用。"""
    for permission in PERM_DEFS:
        register_perm(permission)
