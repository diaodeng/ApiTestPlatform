"""配置任务模块权限与菜单定义。

门店配置任务是生产配置类数据，独立挂载顶级目录「门店配置」，不与测试管理、
工单管理等其他业务混放；菜单通过 common.permission.sync 在后端启动时自动同步。
"""

from common.permission.model import MenuConfig, PermDef
from common.permission.registry import register_menu, register_perm

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
    PermDef("configuration_task:artifact:query", "配置任务产物查询"),
    PermDef("configuration_task:artifact:preview", "配置任务产物预览"),
    PermDef("configuration_task:artifact:download", "配置任务产物下载"),
    PermDef("configuration_task:report:generate", "配置任务报告归档"),
    PermDef("configuration_task:resource:sftp", "配置任务SFTP资源上传"),
    PermDef("configuration_task:resource:download", "配置任务资源下载"),
    PermDef("configuration_task:resource:delete", "配置任务资源删除"),
)


def _menu(
    key: str,
    name: str,
    menu_type: str,
    parent_key: str | None = None,
    *,
    perm: str = "",
    path: str = "",
    component: str = "",
    icon: str = "#",
    order: int = 1,
    remark: str = "",
) -> MenuConfig:
    """构建菜单配置，公共字段取项目默认值。"""
    return MenuConfig(
        key=key,
        name=name,
        menu_type=menu_type,
        parent_key=parent_key,
        perm=perm,
        path=path,
        component=component,
        icon=icon,
        order=order,
        remark=remark,
    )


# 顶级目录 order 取 30，排在工单管理（20）之后；顶级必须是 M 目录，顶级 C 菜单会导致
# vue-router "Invalid path" 报错（与 unidata 模块注释的约定一致）。
MENU_DEFS: tuple[MenuConfig, ...] = (
    _menu(
        "configtask.root",
        "门店配置",
        "M",
        None,
        path="configtask",
        icon="shopping",
        order=30,
        remark="门店配置任务目录（生产配置类数据独立存放）",
    ),
    _menu(
        "configtask.task",
        "配置任务",
        "C",
        "configtask.root",
        perm="configuration_task:task:list",
        path="configuration-task",
        component="hrm/configuration-task/index",
        icon="build",
        order=1,
        remark="门店配置任务管理：任务/版本/运行/审批/报告",
    ),
    # 任务管理按钮权限
    _menu("configtask.task.query", "任务详情", "F", "configtask.task",
          perm="configuration_task:task:query", order=1),
    _menu("configtask.task.add", "任务新增", "F", "configtask.task",
          perm="configuration_task:task:add", order=2),
    _menu("configtask.task.edit", "任务编辑", "F", "configtask.task",
          perm="configuration_task:task:edit", order=3),
    _menu("configtask.task.publish", "版本发布", "F", "configtask.task",
          perm="configuration_task:task:publish", order=4),
    _menu("configtask.task.run", "任务运行", "F", "configtask.task",
          perm="configuration_task:task:run", order=5),
    _menu("configtask.task.approve", "阶段审批", "F", "configtask.task",
          perm="configuration_task:task:approve", order=6),
    # 资源按钮权限
    _menu("configtask.resource.list", "资源列表", "F", "configtask.task",
          perm="configuration_task:resource:list", order=7),
    _menu("configtask.resource.query", "资源详情", "F", "configtask.task",
          perm="configuration_task:resource:query", order=8),
    _menu("configtask.resource.add", "资源登记", "F", "configtask.task",
          perm="configuration_task:resource:add", order=9),
    _menu("configtask.resource.edit", "资源就绪确认", "F", "configtask.task",
          perm="configuration_task:resource:edit", order=10),
    _menu("configtask.resource.transfer", "资源传输", "F", "configtask.task",
          perm="configuration_task:resource:transfer", order=11),
    _menu("configtask.resource.sftp", "SFTP资源上传", "F", "configtask.task",
          perm="configuration_task:resource:sftp", order=12),
    _menu("configtask.resource.download", "资源下载", "F", "configtask.task",
          perm="configuration_task:resource:download", order=13),
    _menu("configtask.resource.delete", "资源删除", "F", "configtask.task",
          perm="configuration_task:resource:delete", order=14),
    # 产物与报告按钮权限
    _menu("configtask.artifact.upload", "产物上报", "F", "configtask.task",
          perm="configuration_task:artifact:upload", order=15),
    _menu("configtask.artifact.query", "产物查询", "F", "configtask.task",
          perm="configuration_task:artifact:query", order=16),
    _menu("configtask.artifact.preview", "产物预览", "F", "configtask.task",
          perm="configuration_task:artifact:preview", order=17),
    _menu("configtask.artifact.download", "产物下载", "F", "configtask.task",
          perm="configuration_task:artifact:download", order=18),
    _menu("configtask.report.generate", "报告归档", "F", "configtask.task",
          perm="configuration_task:report:generate", order=19),
)


def register() -> None:
    """注册配置任务模块权限码与菜单，供路由权限扫描和菜单同步使用。"""
    for permission in PERM_DEFS:
        register_perm(permission)
    for menu in MENU_DEFS:
        register_menu(menu)
