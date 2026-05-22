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


def M(
    key: str,
    name: str,
    path: str,
    icon: str,
    order: int,
    *,
    parent_key: str | None = None,
    perm: str = "",
    component: str = "",
    remark: str = "",
) -> MenuConfig:
    return _menu(
        key,
        name,
        "M",
        parent_key,
        perm=perm,
        path=path,
        component=component,
        icon=icon,
        order=order,
        remark=remark,
    )


def C(
    key: str,
    name: str,
    parent_key: str,
    path: str,
    component: str,
    perm: str,
    icon: str,
    order: int,
    *,
    remark: str = "",
) -> MenuConfig:
    return _menu(
        key,
        name,
        "C",
        parent_key,
        perm=perm,
        path=path,
        component=component,
        icon=icon,
        order=order,
        remark=remark,
    )


def F(key: str, name: str, parent_key: str, perm: str, order: int, *, remark: str = "") -> MenuConfig:
    return _menu(key, name, "F", parent_key, perm=perm, order=order, icon="#", remark=remark)


MENU_DEFS: tuple[MenuConfig, ...] = (
    M("ticket.root", "工单管理", "ticket", "message", 20, remark="工单管理目录"),
    C(
        "ticket.ticket",
        "工单列表",
        "ticket.root",
        "ticket",
        "ticket/index",
        "ticket:ticket:list",
        "list",
        1,
        remark="工单列表菜单",
    ),
    F("ticket.ticket.add", "工单新增", "ticket.ticket", "ticket:ticket:add", 1),
    F("ticket.ticket.edit", "工单编辑", "ticket.ticket", "ticket:ticket:edit", 2),
    F("ticket.ticket.remove", "工单删除", "ticket.ticket", "ticket:ticket:remove", 3),
    F("ticket.ticket.query", "工单详情", "ticket.ticket", "ticket:ticket:query", 4),
    F("ticket.ticket.assign", "工单指派", "ticket.ticket", "ticket:ticket:assign", 5),
    F("ticket.ticket.status", "状态流转", "ticket.ticket", "ticket:ticket:status", 6),
    F("ticket.ticket.timeline", "工单时间线", "ticket.ticket", "ticket:ticket:timeline", 7),
    F("ticket.ticket.import", "工单导入", "ticket.ticket", "ticket:ticket:import", 8),
    F("ticket.comment.add", "评论新增", "ticket.ticket", "ticket:comment:add", 9),
    F("ticket.event.add", "事件新增", "ticket.ticket", "ticket:event:add", 10),
    F("ticket.rca.edit", "RCA保存", "ticket.ticket", "ticket:rca:edit", 11),
    F("ticket.logpull.query", "日志拉取查询", "ticket.ticket", "ticket:logpull:query", 12),
    F("ticket.logpull.add", "日志拉取新增", "ticket.ticket", "ticket:logpull:add", 13),
    F("ticket.logpull.config", "日志拉取配置", "ticket.ticket", "ticket:logpull:config", 14),
    C(
        "ticket.ai.repo-mapping",
        "AI仓库映射",
        "ticket.root",
        "aiRepoMapping",
        "ticket/ai-repo-mapping/index",
        "ticket:ai:mapping:list",
        "link",
        5,
        remark="工单AI仓库映射管理菜单",
    ),
    F("ticket.ai.mapping.list", "AI映射查询", "ticket.ticket", "ticket:ai:mapping:list", 15),
    F("ticket.ai.mapping.add", "AI映射新增", "ticket.ticket", "ticket:ai:mapping:add", 16),
    F("ticket.ai.mapping.edit", "AI映射编辑", "ticket.ticket", "ticket:ai:mapping:edit", 17),
    F("ticket.ai.mapping.remove", "AI映射删除", "ticket.ticket", "ticket:ai:mapping:remove", 18),
    F("ticket.ai.analysis.list", "AI分析查询", "ticket.ticket", "ticket:ai:analysis:list", 19),
    F("ticket.ai.analysis.run", "AI分析执行", "ticket.ticket", "ticket:ai:analysis:run", 20),
    C(
        "ticket.knowledge",
        "知识库",
        "ticket.root",
        "knowledge",
        "ticket/knowledge/index",
        "ticket:knowledge:list",
        "education",
        2,
        remark="工单知识库菜单",
    ),
    F("ticket.knowledge.add", "知识库新增", "ticket.knowledge", "ticket:knowledge:add", 1),
    F("ticket.knowledge.edit", "知识库编辑", "ticket.knowledge", "ticket:knowledge:edit", 2),
    F("ticket.knowledge.remove", "知识库删除", "ticket.knowledge", "ticket:knowledge:remove", 3),
    F("ticket.knowledge.query", "知识库详情", "ticket.knowledge", "ticket:knowledge:query", 4),
    C(
        "ticket.workflow",
        "工单工作流",
        "ticket.root",
        "workflow",
        "ticket/workflow/index",
        "ticket:workflow:list",
        "tree-table",
        3,
        remark="工单工作流配置菜单",
    ),
    F("ticket.workflow.edit", "工作流编辑", "ticket.workflow", "ticket:workflow:edit", 1),
    F("ticket.workflow.remove", "工作流删除", "ticket.workflow", "ticket:workflow:remove", 2),
    C(
        "ticket.statistics",
        "工单统计",
        "ticket.root",
        "statistics",
        "ticket/statistics/index",
        "ticket:statistics:list",
        "chart",
        4,
        remark="工单统计菜单",
    ),
)


def register() -> None:
    """
    注册工单模块菜单和权限定义。
    :return: 无
    """
    for menu in MENU_DEFS:
        register_menu(menu)
