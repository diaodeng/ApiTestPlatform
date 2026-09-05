"""
手动创建工单后处理桥接服务。

负责把 ``TicketService.create_ticket`` 保存成功的工单桥接到统一的同步后处理编排
（``TicketSyncPostProcessService.execute_deferred_sync_post_process``），使手动创建
场景（``manual_create``）复用与外部推送、远端拉取、多维表格拉取相同的 AI 统一提取、
翻译、同步后自动化（相似工单/自动拉日志/自动 AI）、向量刷新和发布状态收敛链路。

职责边界：
- 只做"本地工单 -> 外部同步模型"的载荷转换、有效开关合并和后台分发；
- 不承担具体业务步骤，是否执行各步骤由
  ``ticket.sync.automation`` 的 ``manual_create`` 场景开关、表单勾选的任务级参数
  和 ``ticket.similarity.config`` 场景开关共同决定；
- 分发时合并并固化开关快照，后续配置修改不影响已创建工单的后处理。
"""
from typing import Any

from sqlalchemy.orm import Session

from module_admin.entity.vo.user_vo import CurrentUserModel
from modules.ticket.entity.do.ticket_do import Ticket
from modules.ticket.entity.vo.ticket_vo import (
    TicketExternalSyncUpsertModel,
    TicketSyncAutomationModel,
    TicketSyncSourcePayloadModel,
)
from modules.ticket.service.sync.ticket_sync_config_service import TicketSyncConfigService
from modules.ticket.service.sync.ticket_sync_post_process_service import TicketSyncPostProcessService
from utils.log_util import logger

# 手动创建后处理的来源系统标识，写入 extra_data.external_sync 元数据便于追溯。
MANUAL_CREATE_SOURCE_SYSTEM = "manual_create"


class TicketManualCreatePostProcessService:
    """手动创建工单的后处理编排桥接。"""

    SYNC_SCENE = "manual_create"

    @classmethod
    def resolve_effective_automation(
        cls,
        db: Session,
        *,
        log_pull_config: dict[str, Any] | None,
        auto_translate: bool,
        need_log_pull: bool,
    ) -> tuple[TicketSyncAutomationModel, dict[str, Any]]:
        """
        合并表单勾选与 manual_create 场景开关，得到本次后处理的有效自动化配置快照。

        语义：任务级勾选与场景开关取"或"；Agent/Provider 缺失时自动 AI 降级关闭并记录原因，
        避免触发模型校验失败导致整个后处理中断。
        :param db: 数据库会话。
        :param log_pull_config: 表单填写的日志拉取参数，可为空。
        :param auto_translate: 表单勾选的自动翻译开关。
        :param need_log_pull: 表单勾选的自动拉日志开关。
        :return: (有效自动化模型, 决策审计字典)。
        """
        config = TicketSyncConfigService.load_sync_config(db)
        auto_config = config.get("automationConfig") if isinstance(config.get("automationConfig"), dict) else {}
        translate_config = config.get("translateConfig") if isinstance(config.get("translateConfig"), dict) else {}
        log_pull_defaults = config.get("logPullDefaults") if isinstance(config.get("logPullDefaults"), dict) else {}

        scene_auto_identify = bool(auto_config.get("autoIdentifyOnManualCreate"))
        scene_auto_log_pull = bool(auto_config.get("autoLogPullOnManualCreate"))
        scene_auto_ai = bool(auto_config.get("autoAiAnalysisOnManualCreate"))
        scene_translate = bool(translate_config.get("translateOnManualCreate"))
        default_agent_code = str(log_pull_defaults.get("aiAgentCode") or "").strip() or None
        default_provider_code = str(log_pull_defaults.get("aiProviderCode") or "").strip() or None

        effective_auto_ai = scene_auto_ai
        ai_skip_reason = ""
        if scene_auto_ai and not (default_agent_code or default_provider_code):
            # 自动 AI 需要 Agent/Provider；两者都缺时关闭并记录原因，防止模型校验异常。
            effective_auto_ai = False
            ai_skip_reason = "manual_create 场景开启自动AI但未配置 aiAgentCode/aiProviderCode，已降级关闭"

        automation = TicketSyncAutomationModel(
            auto_identify=scene_auto_identify,
            auto_log_pull=bool(need_log_pull) or scene_auto_log_pull,
            auto_ai_analysis=effective_auto_ai,
            auto_translate=bool(auto_translate) or scene_translate,
            ai_agent_code=default_agent_code,
            ai_provider_code=default_provider_code,
            log_pull_config=log_pull_config or None,
        )
        decision = {
            "autoIdentify": scene_auto_identify,
            "autoIdentifySource": "scene_switch" if scene_auto_identify else "off",
            "autoLogPull": automation.auto_log_pull,
            "autoLogPullSource": "form" if need_log_pull else ("scene_switch" if scene_auto_log_pull else "off"),
            "autoAiAnalysis": effective_auto_ai,
            "autoAiAnalysisSource": "scene_switch" if scene_auto_ai else "off",
            "autoAiAnalysisSkipReason": ai_skip_reason,
            "autoTranslate": automation.auto_translate,
            "autoTranslateSource": "form" if auto_translate else ("scene_switch" if scene_translate else "off"),
        }
        return automation, decision

    @classmethod
    def build_manual_create_sync_object(
        cls,
        ticket: Ticket,
        *,
        automation: TicketSyncAutomationModel,
    ) -> TicketExternalSyncUpsertModel:
        """
        将已入库的手动工单转换为后处理编排所需的外部同步模型。

        只承载后处理链路需要的字段：工单号、标题、描述、模块和日志拉取参数；
        不写 external_field_mapping，也不参与外部字段映射与邮箱补齐。
        :param ticket: 已保存的工单 ORM 实体。
        :param automation: 合并后的任务级自动化配置。
        :return: 满足后处理契约的外部同步模型。
        """
        extra_data = dict(ticket.extra_data or {}) if isinstance(ticket.extra_data, dict) else {}
        raw_payload = {
            "ticketNo": ticket.ticket_no,
            "title": ticket.title,
            "description": ticket.description,
            "moduleName": ticket.module_name,
            "status": ticket.status,
        }
        # 保存请求已内联翻译过描述时，extra_data.origin_description 才是原始文本；
        # 同步对象必须携带原始描述，保证编排层"已有成功翻译则跳过"的查重判断命中，
        # 避免对已翻译文本二次翻译。
        origin_description = str(extra_data.get("origin_description") or "").strip()
        effective_description = origin_description or ticket.description
        raw_payload["description"] = effective_description
        log_pull_config = automation.log_pull_config if isinstance(automation.log_pull_config, dict) else None
        return TicketExternalSyncUpsertModel.model_validate(
            {
                "ticket_no": ticket.ticket_no,
                "title": ticket.title,
                "description": effective_description,
                "module_id": ticket.module_id,
                "module_code": ticket.module_code,
                "module_name": ticket.module_name,
                "status": ticket.status,
                "submit_time": ticket.submit_time,
                # 表单日志参数同时写入基础字段，供 AI 提取回填与提示快照合并使用；
                # automation.log_pull_config 作为任务级参数保证表单值优先于 AI 结果。
                "log_pull_config": dict(log_pull_config) if log_pull_config else None,
                "extra_data": extra_data,
                "source": TicketSyncSourcePayloadModel(
                    system=MANUAL_CREATE_SOURCE_SYSTEM,
                    record_id=str(ticket.ticket_id),
                    record_url=ticket.ticket_url,
                    pushed_at=ticket.create_time,
                ),
                "automation": automation,
                "raw_payload": raw_payload,
            }
        )

    @classmethod
    def dispatch_manual_create_post_process(
        cls,
        db: Session,
        ticket: Ticket,
        *,
        log_pull_config: dict[str, Any] | None,
        auto_translate: bool,
        need_log_pull: bool,
        current_user: CurrentUserModel,
    ) -> dict[str, Any]:
        """
        分发手动创建后处理任务：Celery 可用时投递 Celery，否则降级本地后台线程。

        分发动作只做配置合并与载荷序列化，不执行 AI 步骤，可在保存事务提交后同步调用。
        :param db: 数据库会话，用于读取同步自动化配置。
        :param ticket: 已保存的工单 ORM 实体。
        :param log_pull_config: 表单填写的日志拉取参数，可为空。
        :param auto_translate: 表单勾选的自动翻译开关。
        :param need_log_pull: 表单勾选的自动拉日志开关。
        :param current_user: 当前登录用户。
        :return: 分发结果摘要。
        """
        automation, decision = cls.resolve_effective_automation(
            db,
            log_pull_config=log_pull_config,
            auto_translate=auto_translate,
            need_log_pull=need_log_pull,
        )
        logger.info(
            f"手动创建工单后处理开关快照: ticket_no={ticket.ticket_no}, decision={decision}"
        )
        sync_object = cls.build_manual_create_sync_object(ticket, automation=automation)
        sync_payload = sync_object.model_dump()
        user_payload = TicketSyncPostProcessService.normalize_current_user_payload(current_user.model_dump())
        dispatch_result = TicketSyncPostProcessService.dispatch_deferred_sync_post_process_task(
            sync_payload,
            user_payload,
            cls.SYNC_SCENE,
        )
        if dispatch_result.get("mode") == TicketSyncPostProcessService.CELERY_DISPATCH_MODE:
            return dispatch_result
        # Celery 不可用时降级本地后台线程执行，保证手动创建的后处理不依赖 Worker 部署。
        background_started = cls.run_in_background(sync_payload, user_payload)
        return {**dispatch_result, "backgroundStarted": background_started}

    @classmethod
    def run_in_background(
        cls,
        sync_payload: dict[str, Any],
        current_user_payload: dict[str, Any],
    ) -> bool:
        """
        在本地后台线程执行手动创建后处理（复用外部同步的降级执行入口）。
        :param sync_payload: 手动创建同步载荷字典。
        :param current_user_payload: 归一化后的当前用户字典。
        :return: 后台线程是否成功启动。
        """
        import threading

        def _run() -> None:
            TicketSyncPostProcessService.run_deferred_sync_post_process(
                sync_payload,
                current_user_payload,
                cls.SYNC_SCENE,
            )

        try:
            thread = threading.Thread(target=_run, name="ticket-manual-create-post-process", daemon=True)
            thread.start()
            logger.info(
                f"手动创建工单后处理已提交本地后台线程: ticket_no={sync_payload.get('ticketNo') or '-'}"
            )
            return True
        except Exception as exc:
            logger.error(f"手动创建工单后处理后台线程启动失败: error={exc}")
            return False

    @classmethod
    def log_dispatch_summary(cls, ticket: Ticket, dispatch_result: dict[str, Any]) -> None:
        """
        输出手动创建后处理分发日志，便于排查执行方式与失败原因。
        :param ticket: 已保存的工单 ORM 实体。
        :param dispatch_result: 分发结果摘要。
        :return: 无。
        """
        logger.info(
            f"手动创建工单后处理分发完成: ticket_no={ticket.ticket_no}, ticket_id={ticket.ticket_id}, "
            f"mode={dispatch_result.get('mode') or '-'}, reason={dispatch_result.get('reason') or '-'}"
        )
